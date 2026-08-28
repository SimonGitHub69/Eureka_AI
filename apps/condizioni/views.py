from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from apps.condizioni.forms import CondizioneForm
from apps.condizioni.lookups import (
    attach_banca_condizione,
    build_scadenze_riepilogo,
    has_esclusioni,
)
from apps.condizioni.models import Condizione
from apps.condizioni.sync import sync_condizioni
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin


def _filter_condizioni_queryset(request):
    qs = Condizione.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(tipo_pagamento__icontains=q)
            | Q(codice_banca__icontains=q)
            | Q(pag_fatt_elett_pa__icontains=q)
        )
    return qs.order_by("descrizione", "codice")


def _condizioni_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Condizione.objects)
    return context


def _stamp_modifica(instance: Condizione) -> None:
    now = timezone.localtime()
    instance.data_modifica = timezone.make_naive(now)
    instance.ora_modifica = now.time().replace(microsecond=0)
    instance.synced_at = now


class CondizioneListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Condizione
    template_name = "condizioni/condizione_list.html"
    context_object_name = "condizioni"
    sortable_fields = (
        "descrizione",
        "codice",
        "tipo_pagamento",
        "pag_fatt_elett_pa",
        "numero_rate",
        "prima_rata",
        "intervallo",
    )
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_condizioni_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _condizioni_list_context(self, context)


class CondizionePrintListView(MirrorPrintListView):
    print_title = "Condizioni di pagamento"
    print_subtitle = "Elenco condizioni di pagamento"
    filter_queryset = staticmethod(_filter_condizioni_queryset)
    sortable_fields = ("descrizione", "codice", "tipo_pagamento", "pag_fatt_elett_pa", "numero_rate", "prima_rata", "intervallo")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "tipo_pagamento", "label": "Tipo"},
        {"field": "pag_fatt_elett_pa", "label": "Modalità SDI"},
        {"field": "numero_rate", "label": "Rate"},
        {"field": "prima_rata", "label": "Prima rata (gg)"},
    )


class CondizioneExportListView(ExportListMixin, CondizionePrintListView):
    export_filename = "condizioni"


class CondizioneDetailView(LoginRequiredMixin, DetailView):
    model = Condizione
    template_name = "condizioni/condizione_detail.html"
    context_object_name = "condizione"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        condizione = self.object
        attach_banca_condizione(condizione)
        context["banca_collegata"] = getattr(condizione, "banca_collegata", None)
        context["scadenze_riepilogo"] = build_scadenze_riepilogo(condizione)
        context["has_esclusioni"] = has_esclusioni(condizione)
        return context


class CondizioneCreateView(LoginRequiredMixin, View):
    template_name = "condizioni/condizione_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": CondizioneForm(),
                "is_create": True,
                "page_heading": "Nuova condizione",
            },
        )

    def post(self, request):
        form = CondizioneForm(request.POST)
        if form.is_valid():
            condizione = form.save(commit=False)
            _stamp_modifica(condizione)
            condizione.save()
            messages.success(request, f"Condizione {condizione.codice} creata.")
            return redirect("condizioni:detail", codice=condizione.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova condizione",
            },
        )


class CondizioneUpdateView(LoginRequiredMixin, View):
    template_name = "condizioni/condizione_form.html"

    def get_object(self, codice):
        return get_object_or_404(Condizione, pk=codice)

    def get(self, request, codice):
        condizione = self.get_object(codice)
        form = CondizioneForm(instance=condizione, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "condizione": condizione,
                "is_create": False,
                "page_heading": "Modifica condizione",
            },
        )

    def post(self, request, codice):
        condizione = self.get_object(codice)
        form = CondizioneForm(request.POST, instance=condizione, codice_readonly=True)
        if form.is_valid():
            condizione = form.save(commit=False)
            _stamp_modifica(condizione)
            condizione.save()
            messages.success(request, f"Condizione {condizione.codice} aggiornata.")
            return redirect("condizioni:detail", codice=condizione.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "condizione": condizione,
                "is_create": False,
                "page_heading": "Modifica condizione",
            },
        )


class CondizioneDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        condizione = get_object_or_404(Condizione, pk=codice)
        label = condizione.codice
        condizione.delete()
        messages.success(request, f"Condizione {label} eliminata.")
        return redirect("condizioni:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncCondizioniView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "condizioni/sync_condizioni.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "condizioni_count": _pg_table_count("condizioni"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_condizioni()
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
