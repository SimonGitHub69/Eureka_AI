from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.banche.forms import BancaForm
from apps.banche.models import Banca
from apps.banche.sync import sync_banche
from apps.core.mirror_crud import mirror_row_to_campi, stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin


def _filter_banche_queryset(request):
    qs = Banca.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(localita__icontains=q)
            | Q(provincia__icontains=q)
            | Q(codice_abi__icontains=q)
            | Q(codice_cab__icontains=q)
            | Q(iban__icontains=q)
            | Q(agenzia__icontains=q)
            | Q(swift_code__icontains=q)
        )
    return qs.order_by("descrizione", "codice")


def _banche_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Banca.objects)
    return context


def fetch_banca_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM banche WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class BancaListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Banca
    template_name = "banche/banca_list.html"
    context_object_name = "banche"
    sortable_fields = ("descrizione", "codice", "localita", "codice_abi", "codice_cab", "iban")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_banche_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _banche_list_context(self, context)


class BancaPrintListView(MirrorPrintListView):
    print_title = "Banche"
    print_subtitle = "Elenco banche"
    filter_queryset = staticmethod(_filter_banche_queryset)
    sortable_fields = ("descrizione", "codice", "localita", "codice_abi", "codice_cab", "iban")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "localita", "label": "Località"},
        {"field": "codice_abi", "label": "ABI"},
        {"field": "codice_cab", "label": "CAB"},
        {"field": "iban", "label": "IBAN"},
    )


class BancaExportListView(ExportListMixin, BancaPrintListView):
    export_filename = "banche"


class BancaDetailView(LoginRequiredMixin, DetailView):
    model = Banca
    template_name = "banche/banca_detail.html"
    context_object_name = "banca"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_banca_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class BancaCreateView(LoginRequiredMixin, View):
    template_name = "banche/banca_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": BancaForm(),
                "is_create": True,
                "page_heading": "Nuova banca",
            },
        )

    def post(self, request):
        form = BancaForm(request.POST)
        if form.is_valid():
            banca = form.save(commit=False)
            stamp_modifica(banca)
            banca.save()
            messages.success(request, f"Banca {banca.codice} creata.")
            return redirect("banche:detail", codice=banca.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova banca",
            },
        )


class BancaUpdateView(LoginRequiredMixin, View):
    template_name = "banche/banca_form.html"

    def get_object(self, codice):
        return get_object_or_404(Banca, pk=codice)

    def get(self, request, codice):
        banca = self.get_object(codice)
        form = BancaForm(instance=banca, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "banca": banca,
                "is_create": False,
                "page_heading": "Modifica banca",
            },
        )

    def post(self, request, codice):
        banca = self.get_object(codice)
        form = BancaForm(request.POST, instance=banca, codice_readonly=True)
        if form.is_valid():
            banca = form.save(commit=False)
            stamp_modifica(banca)
            banca.save()
            messages.success(request, f"Banca {banca.codice} aggiornata.")
            return redirect("banche:detail", codice=banca.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "banca": banca,
                "is_create": False,
                "page_heading": "Modifica banca",
            },
        )


class BancaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        banca = get_object_or_404(Banca, pk=codice)
        label = banca.codice
        banca.delete()
        messages.success(request, f"Banca {label} eliminata.")
        return redirect("banche:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncBancheView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "banche/sync_banche.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "banche_count": _pg_table_count("banche"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_banche()
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
