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
from apps.vettori.forms import VettoreForm
from apps.vettori.models import Vettore
from apps.vettori.sync import sync_vettori


def _filter_vettori_queryset(request):
    qs = Vettore.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(denominazione__icontains=q)
            | Q(citta__icontains=q)
            | Q(partita_iva__icontains=q)
            | Q(codice_fiscale__icontains=q)
            | Q(telefono__icontains=q)
            | Q(email__icontains=q)
        )
    return qs.order_by("denominazione", "codice")


def _vettori_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Vettore.objects)
    return context


def fetch_vettore_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM vettori WHERE "CodiceVet" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class VettoreListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = Vettore
    template_name = "vettori/vettore_list.html"
    context_object_name = "vettori"
    sortable_fields = ("denominazione", "codice", "citta", "partita_iva")
    default_sort = "denominazione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_vettori_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _vettori_list_context(self, context)


class VettorePrintListView(MirrorPrintListView):
    print_title = "Spedizionieri"
    print_subtitle = "Elenco spedizionieri"
    filter_queryset = staticmethod(_filter_vettori_queryset)
    sortable_fields = ("denominazione", "codice", "citta", "partita_iva")
    default_sort = "denominazione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "denominazione", "label": "Denominazione"},
        {"field": "citta", "label": "Città"},
        {"field": "partita_iva", "label": "Partita IVA"},
        {"field": "iscrizione_albo", "label": "Iscrizione albo"},
    )


class VettoreExportListView(ExportListMixin, VettorePrintListView):
    export_filename = "vettori"


class VettoreDetailView(LoginRequiredMixin, DetailView):
    model = Vettore
    template_name = "vettori/vettore_detail.html"
    context_object_name = "vettore"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_vettore_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class VettoreCreateView(LoginRequiredMixin, View):
    template_name = "vettori/vettore_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": VettoreForm(),
                "is_create": True,
                "page_heading": "Nuovo spedizioniere",
            },
        )

    def post(self, request):
        form = VettoreForm(request.POST)
        if form.is_valid():
            vettore = save_mirror_form_instance(form)
            messages.success(request, f"Spedizioniere {vettore.codice} creato.")
            return redirect("vettori:detail", codice=vettore.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo spedizioniere",
            },
        )


class VettoreUpdateView(LoginRequiredMixin, View):
    template_name = "vettori/vettore_form.html"

    def get_object(self, codice):
        return get_object_or_404(Vettore, pk=codice)

    def get(self, request, codice):
        vettore = self.get_object(codice)
        form = VettoreForm(instance=vettore, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "vettore": vettore,
                "is_create": False,
                "page_heading": "Modifica spedizioniere",
            },
        )

    def post(self, request, codice):
        vettore = self.get_object(codice)
        form = VettoreForm(request.POST, instance=vettore, codice_readonly=True)
        if form.is_valid():
            vettore = save_mirror_form_instance(form)
            messages.success(request, f"Spedizioniere {vettore.codice} aggiornato.")
            return redirect("vettori:detail", codice=vettore.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "vettore": vettore,
                "is_create": False,
                "page_heading": "Modifica spedizioniere",
            },
        )


class VettoreDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        vettore = get_object_or_404(Vettore, pk=codice)
        label = vettore.codice
        vettore.delete()
        messages.success(request, f"Spedizioniere {label} eliminato.")
        return redirect("vettori:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncVettoriView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "vettori/sync_vettori.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "vettori_count": _pg_table_count("vettori"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_vettori(full=sync_full_from_request(request))
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
