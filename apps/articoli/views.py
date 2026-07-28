from urllib.parse import unquote

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.db.models import Q
from django.urls import reverse
from django.views.generic import DetailView, ListView

from apps.articoli.models import Articolo
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin


def _distinta_list_root() -> str:
    return reverse("distinte_base:list")


def _distinta_selection_back_url(request) -> str | None:
    raw = unquote((request.GET.get("list_back") or "").strip())
    if raw and "//" not in raw:
        root = _distinta_list_root()
        if raw.startswith(root + "?"):
            return raw

    if (request.GET.get("from") or "").strip().lower() == "distinta":
        legacy = unquote((request.GET.get("distinta_back") or "").strip())
        root = _distinta_list_root()
        if legacy.startswith(root + "?") and "//" not in legacy:
            return legacy
    return None


def _distinta_articolo_back_url(request) -> str | None:
    if (request.GET.get("from") or "").strip().lower() != "distinta":
        return None
    raw = unquote((request.GET.get("distinta_back") or "").strip())
    if raw.startswith("/articoli/") and "//" not in raw:
        return raw
    return None


def _filter_articoli_queryset(request):
    qs = Articolo.objects.all()

    q = (request.GET.get("q") or "").strip()
    stato = (request.GET.get("stato") or "").strip()

    if q:
        filters = (
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(cat_omogenea__icontains=q)
            | Q(cod_fornitore__icontains=q)
            | Q(codice_alternativo1__icontains=q)
            | Q(codice_alternativo2__icontains=q)
            | Q(cod_breve_art__icontains=q)
            | Q(cod_magazzino__icontains=q)
            | Q(unita_misura__icontains=q)
        )
        qs = qs.filter(filters)

    if stato == "attivi":
        qs = qs.filter(Q(fl_disattivato=False) | Q(fl_disattivato__isnull=True))
    elif stato == "disattivi":
        qs = qs.filter(fl_disattivato=True)

    return qs.order_by("descrizione", "codice")


def _articoli_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["stato"] = (view.request.GET.get("stato") or "").strip()
    context["has_filters"] = bool(context["q"] or context["stato"])
    try:
        context["totale"] = Articolo.objects.count()
    except Exception:
        context["totale"] = 0
    return context


def fetch_articolo_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM articoli WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class ArticoloListView(LoginRequiredMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Articolo
    template_name = "articoli/articolo_list.html"
    context_object_name = "articoli"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_articoli_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _articoli_list_context(self, context)


class ArticoloDetailView(LoginRequiredMixin, DetailView):
    model = Articolo
    template_name = "articoli/articolo_detail.html"
    context_object_name = "articolo"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_articolo_row(self.object.codice) or []
        context["campi"] = [
            (name, value)
            for name, value in row
            if name != "synced_at" and value not in (None, "")
        ]
        try:
            from apps.distinte_base.models import DistintaBase

            context["distinta_righe"] = list(
                DistintaBase.objects.filter(codice_db=self.object.codice).order_by(
                    "fase", "codice_art", "id"
                )[:200]
            )
            context["distinta_count"] = DistintaBase.objects.filter(
                codice_db=self.object.codice
            ).count()
        except Exception:
            context["distinta_righe"] = []
            context["distinta_count"] = 0
        context["distinta_selection_back_url"] = _distinta_selection_back_url(self.request)
        context["distinta_articolo_back_url"] = _distinta_articolo_back_url(self.request)
        return context
