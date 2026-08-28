from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

from apps.aziende.configurazione import resolve_print_azienda_context
from apps.core.export_list import ExportListMixin
from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView, print_preview_requested
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.primanota.lookups import registro_iva_choices
from apps.registri_iva.forms import RegistroIvaForm
from apps.registri_iva.libro_registro import (
    LibroRegistroIvaDati,
    _resolve_azienda_header,
    build_libro_registro_iva,
)
from apps.registri_iva.models import RegistroIva
from apps.registri_iva.sync import sync_registri_iva


def _filter_registri_iva_queryset(request):
    qs = RegistroIva.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(tipo_registro__icontains=q)
        )
    tipo = (request.GET.get("tipo") or "").strip()
    if tipo:
        qs = qs.filter(tipo_registro__iexact=tipo)
    attivo = (request.GET.get("attivo") or "").strip()
    if attivo == "1":
        qs = qs.filter(Q(disattivato=False) | Q(disattivato__isnull=True))
    elif attivo == "0":
        qs = qs.filter(disattivato=True)
    return qs.order_by("codice")


def _registri_iva_print_filter_summary(request) -> str:
    parts: list[str] = []
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())
    if data_da and data_a:
        parts.append(
            f"Dal {data_da.strftime('%d/%m/%Y')} al {data_a.strftime('%d/%m/%Y')}"
        )
    elif data_da:
        parts.append(f"Da {data_da.strftime('%d/%m/%Y')}")
    elif data_a:
        parts.append(f"Fino al {data_a.strftime('%d/%m/%Y')}")

    tipo = (request.GET.get("tipo") or "").strip()
    if tipo:
        parts.append(f"Tipo: {tipo}")

    attivo = (request.GET.get("attivo") or "").strip()
    if attivo == "1":
        parts.append("Solo attivi")
    elif attivo == "0":
        parts.append("Solo disattivati")

    q = (request.GET.get("q") or "").strip()
    if q:
        parts.append(f'Ricerca: "{q}"')

    return " · ".join(parts)


def _is_registri_iva_elenco_stampa(request) -> bool:
    return (request.GET.get("elenco") or "").strip() == "1"


def _registri_iva_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    params["elenco"] = "1"
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["tipo"] = (view.request.GET.get("tipo") or "").strip()
    context["attivo"] = (view.request.GET.get("attivo") or "").strip()
    context["has_filters"] = bool(context["q"] or context["tipo"] or context["attivo"])
    context["totale"] = safe_mirror_count(RegistroIva.objects)
    return context


def fetch_registro_iva_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM registri_iva WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class RegistroIvaListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = RegistroIva
    template_name = "registri_iva/registro_list.html"
    context_object_name = "registri"
    sortable_fields = ("codice", "descrizione", "tipo_registro", "disattivato")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_registri_iva_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _registri_iva_list_context(self, context)


class RegistroIvaElencoPrintView(MirrorPrintListView):
    print_title = "Registri IVA"
    print_subtitle = "Elenco registri IVA"
    filter_queryset = staticmethod(_filter_registri_iva_queryset)
    sortable_fields = ("codice", "descrizione", "tipo_registro", "disattivato")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "tipo_registro", "label": "Tipo"},
        {"field": "registro_cee", "label": "CEE", "bool": True},
        {"field": "disattivato", "label": "Disattivato", "bool": True},
    )

    def get_filter_summary(self) -> str:
        return _registri_iva_print_filter_summary(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        context.update(
            {
                "print_registri_iva_filters": True,
                "data_da": (request.GET.get("data_da") or "").strip(),
                "data_a": (request.GET.get("data_a") or "").strip(),
                "q": (request.GET.get("q") or "").strip(),
                "tipo": (request.GET.get("tipo") or "").strip(),
                "attivo": (request.GET.get("attivo") or "").strip(),
            }
        )
        return context


class RegistroIvaLibroPrintView(LoginRequiredMixin, View):
    """Stampa libro registro IVA (layout 4D: protocollo, righe IVA, riepilogo)."""

    template_name = "registri_iva/libro_registro_print.html"

    def get(self, request):
        preview_ready = print_preview_requested(request)
        registro = (request.GET.get("registro") or "").strip()
        data_da = (request.GET.get("data_da") or "").strip()
        data_a = (request.GET.get("data_a") or "").strip()
        libro = build_libro_registro_iva(request) if preview_ready else LibroRegistroIvaDati(
            registro=None,
            registro_label=registro,
            periodo_label="",
            anno=None,
        )
        return render(
            request,
            self.template_name,
            {
                "print_preview_ready": preview_ready,
                "print_date": timezone.localdate(),
                "registro": registro,
                "data_da": data_da,
                "data_a": data_a,
                "registri_choices": registro_iva_choices(registro),
                "libro": libro,
                "azienda_header": _resolve_azienda_header(),
                **resolve_print_azienda_context(branding="liste"),
            },
        )


def registro_iva_print_dispatch(request):
    if _is_registri_iva_elenco_stampa(request):
        return RegistroIvaElencoPrintView.as_view()(request)
    return RegistroIvaLibroPrintView.as_view()(request)


class RegistroIvaExportListView(ExportListMixin, RegistroIvaElencoPrintView):
    export_filename = "registri_iva"


class RegistroIvaDetailView(LoginRequiredMixin, DetailView):
    model = RegistroIva
    template_name = "registri_iva/registro_detail.html"
    context_object_name = "registro"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_registro_iva_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class RegistroIvaCreateView(LoginRequiredMixin, View):
    template_name = "registri_iva/registro_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": RegistroIvaForm(),
                "is_create": True,
                "page_heading": "Nuovo registro IVA",
            },
        )

    def post(self, request):
        form = RegistroIvaForm(request.POST)
        if form.is_valid():
            registro = save_mirror_form_instance(form)
            messages.success(request, f"Registro IVA {registro.codice} creato.")
            return redirect("registri_iva:detail", codice=registro.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo registro IVA",
            },
        )


class RegistroIvaUpdateView(LoginRequiredMixin, View):
    template_name = "registri_iva/registro_form.html"

    def get_object(self, codice):
        return get_object_or_404(RegistroIva, pk=codice)

    def get(self, request, codice):
        registro = self.get_object(codice)
        form = RegistroIvaForm(instance=registro, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "registro": registro,
                "is_create": False,
                "page_heading": "Modifica registro IVA",
            },
        )

    def post(self, request, codice):
        registro = self.get_object(codice)
        form = RegistroIvaForm(request.POST, instance=registro, codice_readonly=True)
        if form.is_valid():
            registro = save_mirror_form_instance(form)
            messages.success(request, f"Registro IVA {registro.codice} aggiornato.")
            return redirect("registri_iva:detail", codice=registro.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "registro": registro,
                "is_create": False,
                "page_heading": "Modifica registro IVA",
            },
        )


class RegistroIvaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        registro = get_object_or_404(RegistroIva, pk=codice)
        label = registro.codice
        registro.delete()
        messages.success(request, f"Registro IVA {label} eliminato.")
        return redirect("registri_iva:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncRegistriIvaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "registri_iva/sync_registri_iva.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "registri_count": _pg_table_count("registri_iva"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_registri_iva(full=sync_full_from_request(request))
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
