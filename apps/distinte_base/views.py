from urllib.parse import unquote

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import mirror_row_to_campi, stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.distinte_base.forms import DistintaBaseForm
from apps.distinte_base.models import DistintaBase
from apps.distinte_base.sync import sync_distinte_base


def _next_distinta_id() -> int:
    current = DistintaBase.objects.aggregate(m=Max("id"))["m"] or 0
    return int(current) + 1


def _sibling_righe(riga: DistintaBase, limit: int = 50):
    """Altre righe della stessa distinta (CodiceDB), esclusa la corrente."""
    if not riga.codice_db:
        return []
    try:
        return list(
            DistintaBase.objects.filter(codice_db=riga.codice_db)
            .exclude(pk=riga.pk)
            .order_by("fase", "codice_art", "id")[:limit]
        )
    except Exception:
        return []


def _safe_distinta_list_back_url(request) -> str | None:
    """URL della lista filtrata da cui si è arrivati, oppure None."""
    raw = unquote((request.GET.get("list_back") or "").strip())
    if not raw or "//" in raw:
        return None
    list_root = reverse("distinte_base:list")
    if raw == list_root or raw.startswith(list_root + "?"):
        # Solo se c'è una query (filtri/pagina) è una selezione diversa dall'elenco
        if "?" in raw:
            return raw
        return None
    return None


def _filter_distinte_queryset(request):
    qs = DistintaBase.objects.all()
    q = (request.GET.get("q") or "").strip()
    codice_db = (request.GET.get("codice_db") or "").strip()
    codice_art = (request.GET.get("codice_art") or "").strip()

    if q:
        qs = qs.filter(
            Q(codice_db__icontains=q)
            | Q(codice_art__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(fase__icontains=q)
            | Q(cod_forn__icontains=q)
            | Q(cod_gruppo_art__icontains=q)
        )
    if codice_db:
        qs = qs.filter(codice_db__iexact=codice_db)
    if codice_art:
        qs = qs.filter(codice_art__iexact=codice_art)

    return qs.order_by("codice_db", "fase", "codice_art", "id")


def _distinte_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["codice_db"] = (view.request.GET.get("codice_db") or "").strip()
    context["codice_art"] = (view.request.GET.get("codice_art") or "").strip()
    context["has_filters"] = bool(
        context["q"] or context["codice_db"] or context["codice_art"]
    )
    context["totale"] = safe_mirror_count(DistintaBase.objects)
    return context


def fetch_distinta_row(pk: int) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM distinte_base WHERE "ID" = %s', [pk])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class DistintaBaseListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = DistintaBase
    template_name = "distinte_base/distinta_list.html"
    context_object_name = "righe"
    sortable_fields = ("codice_db", "codice_art", "descrizione", "qta", "um", "fase", "id")
    default_sort = "codice_db"
    default_dir = "asc"
    sort_tiebreaker = "id"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_distinte_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _distinte_list_context(self, context)


class DistintaBasePrintListView(MirrorPrintListView):
    print_title = "Distinte base"
    print_subtitle = "Elenco distinte base"
    filter_queryset = staticmethod(_filter_distinte_queryset)
    sortable_fields = ("codice_db", "codice_art", "descrizione", "qta", "um", "fase", "id")
    default_sort = "codice_db"
    default_dir = "asc"
    sort_tiebreaker = "id"
    print_columns = (
        {"field": "codice_db", "label": "Distinta"},
        {"field": "codice_art", "label": "Componente"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "qta", "label": "Qta", "align": "end"},
        {"field": "um", "label": "UM"},
        {"field": "fase", "label": "Fase"},
    )


class DistintaBaseDetailView(LoginRequiredMixin, DetailView):
    model = DistintaBase
    template_name = "distinte_base/distinta_detail.html"
    context_object_name = "riga"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_distinta_row(self.object.pk) or []
        context["campi"] = mirror_row_to_campi(row)
        context["list_back_url"] = _safe_distinta_list_back_url(self.request)
        context["list_url"] = reverse("distinte_base:list")
        if self.object.codice_db:
            context["parent_articolo_url"] = reverse(
                "articoli:detail",
                kwargs={"codice": self.object.codice_db},
            )
        else:
            context["parent_articolo_url"] = ""
        context["sibling_righe"] = _sibling_righe(self.object)
        return context


class DistintaBaseCreateView(LoginRequiredMixin, View):
    template_name = "distinte_base/distinta_form.html"

    def get(self, request):
        initial = {}
        codice_db = (request.GET.get("codice_db") or "").strip()
        if codice_db:
            initial["codice_db"] = codice_db
        return render(
            request,
            self.template_name,
            {
                "form": DistintaBaseForm(initial=initial),
                "is_create": True,
                "page_heading": "Nuova riga distinta",
            },
        )

    def post(self, request):
        form = DistintaBaseForm(request.POST)
        if form.is_valid():
            riga = form.save(commit=False)
            riga.id = _next_distinta_id()
            stamp_modifica(riga)
            riga.save(force_insert=True)
            messages.success(request, f"Riga distinta {riga.id} creata.")
            return redirect("distinte_base:detail", pk=riga.id)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova riga distinta",
            },
        )


class DistintaBaseUpdateView(LoginRequiredMixin, View):
    template_name = "distinte_base/distinta_form.html"

    def get_object(self, pk):
        return get_object_or_404(DistintaBase, pk=pk)

    def get(self, request, pk):
        riga = self.get_object(pk)
        form = DistintaBaseForm(instance=riga)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "riga": riga,
                "is_create": False,
                "page_heading": "Modifica riga distinta",
            },
        )

    def post(self, request, pk):
        riga = self.get_object(pk)
        form = DistintaBaseForm(request.POST, instance=riga)
        if form.is_valid():
            riga = form.save(commit=False)
            stamp_modifica(riga)
            riga.save()
            messages.success(request, f"Riga distinta {riga.id} aggiornata.")
            return redirect("distinte_base:detail", pk=riga.id)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "riga": riga,
                "is_create": False,
                "page_heading": "Modifica riga distinta",
            },
        )


class DistintaBaseDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        riga = get_object_or_404(DistintaBase, pk=pk)
        label = riga.id
        riga.delete()
        messages.success(request, f"Riga distinta {label} eliminata.")
        return redirect("distinte_base:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncDistinteBaseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "distinte_base/sync_distinte_base.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "distinte_count": _pg_table_count("distinte_base"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_distinte_base()
        message = "\n".join(t.message for t in result.tables) or result.message
        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)
        return render(
            request,
            self.template_name,
            self.get_context(last_message=message),
        )
