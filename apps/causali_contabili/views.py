from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.causali_contabili.forms import CausaleContabileForm
from apps.causali_contabili.lookups import (
    DETAIL_DB_EXCLUDE,
    attach_pdc_causale,
    attach_registri_iva_causali,
    build_conti_righe,
    conto_url_label,
    has_autofattura_fields,
    linked_labels_for_causale,
    tipo_doc_fel_matching_codes,
)
from apps.causali_contabili.models import CausaleContabile
from apps.causali_contabili.sync import sync_causali_contabili
from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin


def _filter_causali_queryset(request):
    qs = CausaleContabile.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        fel_q = Q(tipo_doc_fel__icontains=q)
        fel_codes = tipo_doc_fel_matching_codes(q)
        if fel_codes:
            fel_q |= Q(tipo_doc_fel__in=fel_codes)
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(tipo_causale__icontains=q)
            | Q(registro_iva__icontains=q)
            | Q(desc_reg_iva__icontains=q)
            | fel_q
        )
    return qs.order_by("codice")


def _causali_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(CausaleContabile.objects)
    return context


def fetch_causale_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM causali_contabili WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class CausaleContabileListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = CausaleContabile
    template_name = "causali_contabili/causale_list.html"
    context_object_name = "causali"
    sortable_fields = (
        "codice",
        "descrizione",
        "tipo_causale",
        "registro_iva",
        "tipo_doc_fel",
    )
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_causali_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attach_registri_iva_causali(context.get("causali") or [])
        return _causali_list_context(self, context)


class CausaleContabilePrintListView(MirrorPrintListView):
    print_title = "Causali Contabili"
    print_subtitle = "Elenco causali contabili"
    filter_queryset = staticmethod(_filter_causali_queryset)
    sortable_fields = (
        "codice",
        "descrizione",
        "tipo_causale",
        "registro_iva",
        "tipo_doc_fel",
    )
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "tipo_causale", "label": "Tipo"},
        {"field": "registro_iva", "label": "Registro IVA"},
        {"field": "tipo_doc_fel", "label": "Doc. FEL"},
    )


class CausaleContabileDetailView(LoginRequiredMixin, DetailView):
    model = CausaleContabile
    template_name = "causali_contabili/causale_detail.html"
    context_object_name = "causale"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        causale = self.object
        attach_registri_iva_causali([causale])
        attach_pdc_causale(causale)
        dare_1_url, dare_1_label = conto_url_label(
            causale.c_dare_1, getattr(causale, "pdc_dare_1", None)
        )
        avere_1_url, avere_1_label = conto_url_label(
            causale.c_avere_1, getattr(causale, "pdc_avere_1", None)
        )
        row = fetch_causale_row(causale.codice) or []
        context["campi_extra"] = mirror_row_to_campi(row, exclude=DETAIL_DB_EXCLUDE)
        context["primanota_causale"] = (causale.codice or "").strip()
        context["registro_collegato"] = getattr(causale, "registro_collegato", None)
        context["conti_righe"] = build_conti_righe(causale)
        context["pdc_dare_1_url"] = dare_1_url
        context["pdc_dare_1_label"] = dare_1_label
        context["pdc_avere_1_url"] = avere_1_url
        context["pdc_avere_1_label"] = avere_1_label
        context["show_autofattura"] = has_autofattura_fields(causale)
        return context


def _causale_form_context(form, *, is_create: bool, causale=None):
    return {
        "form": form,
        "is_create": is_create,
        "causale": causale,
        "page_heading": "Nuova causale" if is_create else "Modifica causale",
        "labels": linked_labels_for_causale(form),
        "lookup_url": reverse("articoli:lookup_codice"),
    }


class CausaleContabileCreateView(LoginRequiredMixin, View):
    template_name = "causali_contabili/causale_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            _causale_form_context(CausaleContabileForm(), is_create=True),
        )

    def post(self, request):
        form = CausaleContabileForm(request.POST)
        if form.is_valid():
            causale = save_mirror_form_instance(form)
            messages.success(request, f"Causale {causale.codice} creata.")
            return redirect("causali_contabili:detail", codice=causale.codice)
        return render(
            request,
            self.template_name,
            _causale_form_context(form, is_create=True),
        )


class CausaleContabileUpdateView(LoginRequiredMixin, View):
    template_name = "causali_contabili/causale_form.html"

    def get_object(self, codice):
        return get_object_or_404(CausaleContabile, pk=codice)

    def get(self, request, codice):
        causale = self.get_object(codice)
        form = CausaleContabileForm(instance=causale, codice_readonly=True)
        return render(
            request,
            self.template_name,
            _causale_form_context(form, is_create=False, causale=causale),
        )

    def post(self, request, codice):
        causale = self.get_object(codice)
        form = CausaleContabileForm(
            request.POST, instance=causale, codice_readonly=True
        )
        if form.is_valid():
            causale = save_mirror_form_instance(form)
            messages.success(request, f"Causale {causale.codice} aggiornata.")
            return redirect("causali_contabili:detail", codice=causale.codice)
        return render(
            request,
            self.template_name,
            _causale_form_context(form, is_create=False, causale=causale),
        )


class CausaleContabileDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        causale = get_object_or_404(CausaleContabile, pk=codice)
        label = causale.codice
        causale.delete()
        messages.success(request, f"Causale {label} eliminata.")
        return redirect("causali_contabili:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncCausaliContabiliView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "causali_contabili/sync_causali.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "causali_count": _pg_table_count("causali_contabili"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_causali_contabili()
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
