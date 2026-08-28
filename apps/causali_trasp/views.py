from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.causali_trasp.forms import CausaleTrasportoForm
from apps.causali_trasp.models import CausaleTrasporto
from apps.causali_trasp.sync import sync_causali_trasp


def _filter_causali_trasp_queryset(request):
    qs = CausaleTrasporto.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(causale_maga__icontains=q)
            | Q(reparto_ecr__icontains=q)
            | Q(c_partita_vend__icontains=q)
        )
    return qs.order_by("descrizione", "codice")


def _causali_trasp_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(CausaleTrasporto.objects)
    return context


def fetch_causale_trasp_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM causali_trasp WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class CausaleTrasportoListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = CausaleTrasporto
    template_name = "causali_trasp/causale_list.html"
    context_object_name = "causali"
    sortable_fields = ("descrizione", "codice", "fatturabile", "causale_maga")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_causali_trasp_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _causali_trasp_list_context(self, context)


class CausaleTrasportoPrintListView(MirrorPrintListView):
    print_title = "Causali trasporto"
    print_subtitle = "Elenco causali trasporto"
    filter_queryset = staticmethod(_filter_causali_trasp_queryset)
    sortable_fields = ("descrizione", "codice", "fatturabile", "causale_maga")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "fatturabile", "label": "Fatturabile", "bool": True},
        {"field": "causale_maga", "label": "Causale mag."},
    )


class CausaleTrasportoExportListView(ExportListMixin, CausaleTrasportoPrintListView):
    export_filename = "causali_trasp"


class CausaleTrasportoDetailView(LoginRequiredMixin, DetailView):
    model = CausaleTrasporto
    template_name = "causali_trasp/causale_detail.html"
    context_object_name = "causale"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_causale_trasp_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class CausaleTrasportoCreateView(LoginRequiredMixin, View):
    template_name = "causali_trasp/causale_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": CausaleTrasportoForm(),
                "is_create": True,
                "page_heading": "Nuova causale trasporto",
            },
        )

    def post(self, request):
        form = CausaleTrasportoForm(request.POST)
        if form.is_valid():
            causale = save_mirror_form_instance(form)
            messages.success(request, f"Causale trasporto {causale.codice} creata.")
            return redirect("causali_trasp:detail", codice=causale.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova causale trasporto",
            },
        )


class CausaleTrasportoUpdateView(LoginRequiredMixin, View):
    template_name = "causali_trasp/causale_form.html"

    def get_object(self, codice):
        return get_object_or_404(CausaleTrasporto, pk=codice)

    def get(self, request, codice):
        causale = self.get_object(codice)
        form = CausaleTrasportoForm(instance=causale, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "causale": causale,
                "is_create": False,
                "page_heading": "Modifica causale trasporto",
            },
        )

    def post(self, request, codice):
        causale = self.get_object(codice)
        form = CausaleTrasportoForm(request.POST, instance=causale, codice_readonly=True)
        if form.is_valid():
            causale = save_mirror_form_instance(form)
            messages.success(request, f"Causale trasporto {causale.codice} aggiornata.")
            return redirect("causali_trasp:detail", codice=causale.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "causale": causale,
                "is_create": False,
                "page_heading": "Modifica causale trasporto",
            },
        )


class CausaleTrasportoDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        causale = get_object_or_404(CausaleTrasporto, pk=codice)
        label = causale.codice
        causale.delete()
        messages.success(request, f"Causale trasporto {label} eliminata.")
        return redirect("causali_trasp:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncCausaliTraspView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "causali_trasp/sync_causali_trasp.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "causali_count": _pg_table_count("causali_trasp"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_causali_trasp(full=sync_full_from_request(request))
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
