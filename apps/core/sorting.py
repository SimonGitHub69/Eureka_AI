"""Ordinamento colonne per ListView: ?sort=campo&dir=asc|desc."""

from __future__ import annotations

from django.core.exceptions import FieldError
from django.shortcuts import redirect

from apps.core.list_state import get_remembered_sort, remember_sort

ALLOWED_DIRS = frozenset({"asc", "desc"})


def resolve_sort(
    request,
    *,
    allowed,
    default_sort=None,
    default_dir="asc",
):
    """
    Valida sort/dir dalla query string.

    Restituisce sempre (sort, dir) effettivi usati per order_by e per la UI.
    Campi non in whitelist → default_sort (se valido) oppure None.
    """
    allowed_set = set(allowed or ())
    raw_sort = (request.GET.get("sort") or "").strip()
    raw_dir = (request.GET.get("dir") or "").strip().lower()

    if default_dir not in ALLOWED_DIRS:
        default_dir = "asc"

    sort = raw_sort if raw_sort in allowed_set else None
    if sort is None and default_sort in allowed_set:
        sort = default_sort

    direction = raw_dir if raw_dir in ALLOWED_DIRS else default_dir
    return sort, direction


def _tiebreaker_fields(tiebreaker) -> tuple[str, ...]:
    if not tiebreaker:
        return ()
    if isinstance(tiebreaker, str):
        return (tiebreaker,)
    return tuple(tiebreaker)


def order_by_fields(sort, direction, *, tiebreaker=None):
    """Costruisce la tupla per QuerySet.order_by(...).

    ``tiebreaker`` può essere un campo (sempre ASC) o una sequenza, anche con
    prefisso ``-`` per DESC (es. ``("-numero", "alfa")``).
    """
    if not sort:
        return ()
    prefix = "-" if direction == "desc" else ""
    fields = [f"{prefix}{sort}"]
    for extra in _tiebreaker_fields(tiebreaker):
        name = extra.lstrip("-")
        if not name or name == sort:
            continue
        fields.append(extra)
    return tuple(fields)


class SortableListMixin:
    """
    Mixin per ListView: ordinamento per colonna via GET sort/dir.

    Uso tipico (prima di SafeMirrorListMixin così wrappa get_queryset):

        class ClienteListView(
            LoginRequiredMixin,
            SortableListMixin,
            SafeMirrorListMixin,
            PerPageListMixin,
            ListView,
        ):
            sortable_fields = ("ragione_sociale1", "localita", "partita_iva")
            default_sort = "ragione_sociale1"
            default_dir = "asc"
            sort_tiebreaker = "codice"

    ``get_queryset`` applica ``order_by`` *dopo* ``super().get_queryset()``,
    così le annotation della subclass (es. Subquery) sono già presenti.

    Nelle template: {% load pagination_tags %} … {% sort_th "localita" "Località" %}
    """

    sortable_fields: tuple[str, ...] = ()
    default_sort: str | None = None
    default_dir: str = "asc"
    # Usato solo se non c'è uno sort risolto (es. whitelist vuota / default assente)
    default_ordering: tuple[str, ...] | None = None
    sort_tiebreaker: str | tuple[str, ...] | None = None
    # Se order_by sul campo richiesto fallisce (es. annotation assente), prova questi
    sort_fallbacks: dict[str, str] | None = None
    # Ripristina sort/dir in sessione quando si torna all'elenco senza ?sort=
    remember_list_sort: bool = True

    def get_sortable_fields(self) -> tuple[str, ...]:
        """Whitelist effettiva (override per escludere campi annotation non disponibili)."""
        return self.sortable_fields

    def dispatch(self, request, *args, **kwargs):
        redirected = self.maybe_restore_sort_redirect(request)
        if redirected is not None:
            return redirected
        return super().dispatch(request, *args, **kwargs)

    def maybe_restore_sort_redirect(self, request):
        """Se manca ?sort= ma in sessione c'è un ordinamento, redirect con sort/dir."""
        if not self.remember_list_sort:
            return None
        if request.method != "GET":
            return None
        if "sort" in request.GET:
            return None
        remembered = get_remembered_sort(request)
        if not remembered:
            return None
        sort, direction = remembered
        if sort not in set(self.get_sortable_fields()):
            return None
        params = request.GET.copy()
        params["sort"] = sort
        params["dir"] = direction
        return redirect(f"{request.path}?{params.urlencode()}")

    def resolve_sorting(self):
        return resolve_sort(
            self.request,
            allowed=self.get_sortable_fields(),
            default_sort=self.default_sort,
            default_dir=self.default_dir,
        )

    def apply_sorting(self, queryset):
        sort, direction = self.resolve_sorting()
        candidates: list[str | None] = [sort]
        if sort and self.sort_fallbacks:
            fallback = self.sort_fallbacks.get(sort)
            if fallback and fallback != sort:
                candidates.append(fallback)

        for candidate in candidates:
            fields = order_by_fields(
                candidate, direction, tiebreaker=self.sort_tiebreaker
            )
            if not fields:
                continue
            try:
                return queryset.order_by(*fields)
            except FieldError:
                # Annotation assente o queryset vuoto senza quell'alias (es. mirror clienti).
                continue

        if self.default_ordering:
            return queryset.order_by(*self.default_ordering)
        return queryset

    def get_queryset(self):
        # order_by dopo le annotation di SafeMirrorListMixin / get_mirror_queryset
        return self.apply_sorting(super().get_queryset())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort, direction = self.resolve_sorting()
        context["sort"] = sort or ""
        context["dir"] = direction
        if self.remember_list_sort and (self.request.GET.get("sort") or "").strip():
            if sort:
                remember_sort(self.request, sort, direction)
        return context
