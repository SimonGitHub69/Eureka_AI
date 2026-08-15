from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.export_list import ExportListMixin
from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.sconti.forms import ScontoForm
from apps.sconti.models import Sconto
from apps.sconti.sync import sync_sconti


def _filter_sconti_queryset(request):
    qs = Sconto.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(sconto__icontains=q))
    return qs.order_by("codice")


def _sconti_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Sconto.objects)
    return context


def fetch_sconto_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM sconti WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class ScontoListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = Sconto
    template_name = "sconti/sconto_list.html"
    context_object_name = "sconti"
    sortable_fields = ("codice", "sconto")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_sconti_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _sconti_list_context(self, context)


class ScontoPrintListView(MirrorPrintListView):
    print_title = "Sconti"
    print_subtitle = "Elenco sconti"
    filter_queryset = staticmethod(_filter_sconti_queryset)
    sortable_fields = ("codice", "sconto")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "sconto", "label": "Sconto"},
    )


class ScontoExportListView(ExportListMixin, ScontoPrintListView):
    export_filename = "sconti"


class ScontoDetailView(LoginRequiredMixin, DetailView):
    model = Sconto
    template_name = "sconti/sconto_detail.html"
    context_object_name = "sconto"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_sconto_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class ScontoCreateView(LoginRequiredMixin, View):
    template_name = "sconti/sconto_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": ScontoForm(),
                "is_create": True,
                "page_heading": "Nuovo sconto",
            },
        )

    def post(self, request):
        form = ScontoForm(request.POST)
        if form.is_valid():
            sconto = save_mirror_form_instance(form)
            messages.success(request, f"Sconto {sconto.codice} creato.")
            return redirect("sconti:detail", codice=sconto.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo sconto",
            },
        )


class ScontoUpdateView(LoginRequiredMixin, View):
    template_name = "sconti/sconto_form.html"

    def get_object(self, codice):
        return get_object_or_404(Sconto, pk=codice)

    def get(self, request, codice):
        sconto = self.get_object(codice)
        form = ScontoForm(instance=sconto, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "sconto": sconto,
                "is_create": False,
                "page_heading": "Modifica sconto",
            },
        )

    def post(self, request, codice):
        sconto = self.get_object(codice)
        form = ScontoForm(request.POST, instance=sconto, codice_readonly=True)
        if form.is_valid():
            sconto = save_mirror_form_instance(form)
            messages.success(request, f"Sconto {sconto.codice} aggiornato.")
            return redirect("sconti:detail", codice=sconto.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "sconto": sconto,
                "is_create": False,
                "page_heading": "Modifica sconto",
            },
        )


class ScontoDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        sconto = get_object_or_404(Sconto, pk=codice)
        label = sconto.codice
        sconto.delete()
        messages.success(request, f"Sconto {label} eliminato.")
        return redirect("sconti:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncScontiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "sconti/sync_sconti.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "sconti_count": _pg_table_count("sconti"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_sconti(full=sync_full_from_request(request))
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
