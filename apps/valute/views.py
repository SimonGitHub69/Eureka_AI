from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.export_list import ExportListMixin
from apps.core.mirror_crud import stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.valute.forms import (
    ValutaDetForm,
    ValutaDetFormSet,
    ValutaForm,
    det_value_to_date,
    save_single_cambio,
    save_valuta_with_cambi,
)
from apps.valute.lookups import cambio_corrente, currency_symbol
from apps.valute.models import Valuta, ValutaDet
from apps.valute.sync import sync_valute


def _filter_valute_queryset(request):
    qs = Valuta.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(abbrev__icontains=q)
        )
    return qs.order_by("descrizione", "codice")


def _valute_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Valuta.objects)
    return context


class ValutaListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = Valuta
    template_name = "valute/valuta_list.html"
    context_object_name = "valute"
    sortable_fields = ("descrizione", "codice", "abbrev")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_valute_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _valute_list_context(self, context)


class ValutaPrintListView(MirrorPrintListView):
    print_title = "Valute"
    print_subtitle = "Elenco valute"
    filter_queryset = staticmethod(_filter_valute_queryset)
    sortable_fields = ("descrizione", "codice", "abbrev")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "abbrev", "label": "Abbreviazione"},
    )


class ValutaExportListView(ExportListMixin, ValutaPrintListView):
    export_filename = "valute"


class ValutaDetailView(LoginRequiredMixin, DetailView):
    model = Valuta
    template_name = "valute/valuta_detail.html"
    context_object_name = "valuta"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cambi = list(
            ValutaDet.objects.filter(valuta=self.object).order_by("-data", "-id")
        )
        context["cambi"] = cambi
        context["currency_symbol"] = currency_symbol(self.object)
        context["cambio_corrente"] = cambio_corrente(self.object, cambi)
        return context


def _get_valuta(codice: str) -> Valuta:
    return get_object_or_404(Valuta, pk=codice)


def _get_cambio(codice: str, pk: int) -> tuple[Valuta, ValutaDet]:
    valuta = _get_valuta(codice)
    cambio = get_object_or_404(ValutaDet, pk=pk, valuta=valuta)
    return valuta, cambio


def _cambio_form_context(form, *, valuta: Valuta, cambio=None, is_create: bool):
    data_label = ""
    if cambio and cambio.data:
        d = det_value_to_date(cambio.data)
        data_label = d.strftime("%d/%m/%Y") if d else ""
    return {
        "form": form,
        "valuta": valuta,
        "cambio": cambio,
        "is_create": is_create,
        "page_heading": "Nuovo cambio" if is_create else "Modifica cambio",
        "cambio_data_label": data_label,
        "currency_symbol": currency_symbol(valuta),
    }


class ValutaCambioCreateView(LoginRequiredMixin, View):
    template_name = "valute/cambio_form.html"

    def get(self, request, codice):
        valuta = _get_valuta(codice)
        return render(
            request,
            self.template_name,
            _cambio_form_context(
                ValutaDetForm(strict=True), valuta=valuta, is_create=True
            ),
        )

    def post(self, request, codice):
        valuta = _get_valuta(codice)
        form = ValutaDetForm(request.POST, strict=True)
        if form.is_valid():
            save_single_cambio(valuta, form)
            messages.success(request, "Cambio storico aggiunto.")
            return redirect("valute:detail", codice=valuta.codice)
        return render(
            request,
            self.template_name,
            _cambio_form_context(form, valuta=valuta, is_create=True),
        )


class ValutaCambioUpdateView(LoginRequiredMixin, View):
    template_name = "valute/cambio_form.html"

    def get(self, request, codice, pk):
        valuta, cambio = _get_cambio(codice, pk)
        form = ValutaDetForm(instance=cambio, strict=True)
        return render(
            request,
            self.template_name,
            _cambio_form_context(
                form, valuta=valuta, cambio=cambio, is_create=False
            ),
        )

    def post(self, request, codice, pk):
        valuta, cambio = _get_cambio(codice, pk)
        form = ValutaDetForm(request.POST, instance=cambio, strict=True)
        if form.is_valid():
            save_single_cambio(valuta, form)
            messages.success(request, "Cambio storico aggiornato.")
            return redirect("valute:detail", codice=valuta.codice)
        return render(
            request,
            self.template_name,
            _cambio_form_context(
                form, valuta=valuta, cambio=cambio, is_create=False
            ),
        )


class ValutaCambioDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice, pk):
        valuta, cambio = _get_cambio(codice, pk)
        label = det_value_to_date(cambio.data)
        label = label.strftime("%d/%m/%Y") if label else str(pk)
        cambio.delete()
        stamp_modifica(valuta)
        valuta.save()
        messages.success(request, f"Cambio del {label} eliminato.")
        return redirect("valute:detail", codice=valuta.codice)


def _form_context(form, formset, *, is_create: bool, valuta=None):
    return {
        "form": form,
        "formset": formset,
        "valuta": valuta,
        "is_create": is_create,
        "page_heading": "Nuova valuta" if is_create else "Modifica valuta",
        "currency_symbol": currency_symbol(valuta) if valuta else "¤",
    }


class ValutaCreateView(LoginRequiredMixin, View):
    template_name = "valute/valuta_form.html"

    def get(self, request):
        form = ValutaForm()
        formset = ValutaDetFormSet()
        return render(
            request, self.template_name, _form_context(form, formset, is_create=True)
        )

    def post(self, request):
        form = ValutaForm(request.POST)
        if form.is_valid():
            valuta = form.save(commit=False)
            if getattr(valuta, "dummy", None) is None:
                valuta.dummy = False
            formset = ValutaDetFormSet(request.POST, instance=valuta)
            if formset.is_valid():
                valuta = save_valuta_with_cambi(form, formset)
                stamp_modifica(valuta)
                valuta.save()
                messages.success(request, f"Valuta {valuta.codice} creata.")
                return redirect("valute:detail", codice=valuta.codice)
        else:
            formset = ValutaDetFormSet(request.POST)
        return render(
            request,
            self.template_name,
            _form_context(form, formset, is_create=True),
        )


class ValutaUpdateView(LoginRequiredMixin, View):
    template_name = "valute/valuta_form.html"

    def get_object(self, codice):
        return get_object_or_404(Valuta, pk=codice)

    def get(self, request, codice):
        valuta = self.get_object(codice)
        form = ValutaForm(instance=valuta, codice_readonly=True)
        formset = ValutaDetFormSet(instance=valuta)
        return render(
            request,
            self.template_name,
            _form_context(form, formset, is_create=False, valuta=valuta),
        )

    def post(self, request, codice):
        valuta = self.get_object(codice)
        form = ValutaForm(request.POST, instance=valuta, codice_readonly=True)
        formset = ValutaDetFormSet(request.POST, instance=valuta)
        if form.is_valid() and formset.is_valid():
            valuta = save_valuta_with_cambi(form, formset)
            stamp_modifica(valuta)
            valuta.save()
            messages.success(request, f"Valuta {valuta.codice} aggiornata.")
            return redirect("valute:detail", codice=valuta.codice)
        return render(
            request,
            self.template_name,
            _form_context(form, formset, is_create=False, valuta=valuta),
        )


class ValutaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        valuta = get_object_or_404(Valuta, pk=codice)
        label = valuta.codice
        ValutaDet.objects.filter(valuta=valuta).delete()
        valuta.delete()
        messages.success(request, f"Valuta {label} eliminata.")
        return redirect("valute:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncValuteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "valute/sync_valute.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "valuta_count": _pg_table_count("valuta"),
            "valuta_det_count": _pg_table_count("valuta_det"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_valute()
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
