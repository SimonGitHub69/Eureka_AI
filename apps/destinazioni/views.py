from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.destinazioni.forms import DestinazioneDiversaForm
from apps.destinazioni.models import DestinazioneDiversa, compact_codice, resolve_anagrafica, tipo_clifor
from apps.destinazioni.sync import sync_destinazioni


def anagrafica_detail_url(codice: str | None) -> str:
    """Scheda Cliente/Fornitore per il codice Cli/For (C… / F…)."""
    compact = compact_codice(codice)
    tipo = tipo_clifor(compact)
    if tipo == "F":
        return reverse("anagrafiche:fornitore_detail", kwargs={"codice": compact})
    if tipo == "C":
        return reverse("anagrafiche:cliente_detail", kwargs={"codice": compact})
    return ""


def _from_anagrafica(request) -> bool:
    raw = (request.GET.get("from") or request.POST.get("from") or "").strip().lower()
    return raw == "anagrafica"


def _return_url_anagrafica(request, codice: str | None = None) -> str:
    """URL di ritorno alla scheda anagrafica se il flusso parte da lì."""
    code = compact_codice(codice) or compact_codice(request.GET.get("codice"))
    if not code:
        return ""
    # Creazione da scheda: ?codice=C… (senza from); modifica/dettaglio: ?from=anagrafica
    if compact_codice(request.GET.get("codice")) or _from_anagrafica(request):
        return anagrafica_detail_url(code)
    return ""


def _filter_destinazioni_queryset(request):
    qs = DestinazioneDiversa.objects.all()
    q = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip().upper()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(codice_dest__icontains=q)
            | Q(ragione_sociale__icontains=q)
            | Q(indirizzo__icontains=q)
            | Q(citta__icontains=q)
            | Q(provincia__icontains=q)
            | Q(telefono__icontains=q)
            | Q(email__icontains=q)
        )
    if tipo in {"C", "F"}:
        qs = qs.filter(codice__istartswith=tipo)
    return qs.order_by("codice", "codice_dest", "id")


def _list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["tipo"] = (view.request.GET.get("tipo") or "").strip().upper()
    context["has_filters"] = bool(context["q"] or context["tipo"])
    context["totale"] = safe_mirror_count(DestinazioneDiversa.objects)
    return context


def next_id() -> int:
    last = DestinazioneDiversa.objects.aggregate(Max("id"))["id__max"]
    return (last or 0) + 1


class DestinazioneListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = DestinazioneDiversa
    template_name = "destinazioni/destinazione_list.html"
    context_object_name = "destinazioni"
    sortable_fields = (
        "codice",
        "codice_dest",
        "ragione_sociale",
        "citta",
        "provincia",
    )
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "id"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_destinazioni_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _list_context(self, context)


class DestinazionePrintListView(MirrorPrintListView):
    print_title = "Destinazioni diverse"
    print_subtitle = "Elenco destinazioni diverse"
    filter_queryset = staticmethod(_filter_destinazioni_queryset)
    sortable_fields = ("codice", "codice_dest", "ragione_sociale", "citta", "provincia")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "id"
    print_columns = (
        {"field": "codice", "label": "Cli/For"},
        {"field": "codice_dest", "label": "Cod. dest."},
        {"field": "ragione_sociale", "label": "Destinazione"},
        {"field": "indirizzo", "label": "Indirizzo"},
        {"field": "citta", "label": "Città"},
        {"field": "provincia", "label": "Provincia"},
    )

    def get_filter_summary(self):
        parts = []
        q = (self.request.GET.get("q") or "").strip()
        tipo = (self.request.GET.get("tipo") or "").strip().upper()
        if q:
            parts.append(f'Ricerca: "{q}"')
        if tipo in {"C", "F"}:
            parts.append("Clienti" if tipo == "C" else "Fornitori")
        return " · ".join(parts)


class DestinazioneExportListView(ExportListMixin, DestinazionePrintListView):
    export_filename = "destinazioni"


class DestinazioneDetailView(LoginRequiredMixin, DetailView):
    model = DestinazioneDiversa
    template_name = "destinazioni/destinazione_detail.html"
    context_object_name = "destinazione"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        anagrafica = resolve_anagrafica(self.object.codice)
        context["anagrafica"] = anagrafica
        context["anagrafica_url"] = self.object.anagrafica_url() if anagrafica else ""
        return_url = _return_url_anagrafica(self.request, self.object.codice)
        context["return_url"] = return_url
        context["from_anagrafica"] = bool(return_url)
        return context


class DestinazioneCreateView(LoginRequiredMixin, View):
    template_name = "destinazioni/destinazione_form.html"

    def _initial(self, request):
        raw = compact_codice(request.GET.get("codice"))
        if raw:
            return {"codice": raw}
        return {}

    def _form_context(self, request, form):
        return_url = _return_url_anagrafica(request)
        return {
            "form": form,
            "is_create": True,
            "page_heading": "Nuova destinazione diversa",
            "return_url": return_url,
            "from_anagrafica": bool(return_url),
        }

    def get(self, request):
        initial = self._initial(request)
        form = DestinazioneDiversaForm(
            initial=initial,
            auto_codice_dest=True,
            chiave_readonly=bool(initial.get("codice")),
        )
        return render(request, self.template_name, self._form_context(request, form))

    def post(self, request):
        # initial necessario: campi chiave disabled non arrivano nel POST.
        initial = self._initial(request)
        form = DestinazioneDiversaForm(
            request.POST,
            initial=initial,
            auto_codice_dest=True,
            chiave_readonly=bool(initial.get("codice")),
        )
        if form.is_valid():
            destinazione = form.save(commit=False)
            destinazione.id = next_id()
            stamp_modifica(destinazione)
            destinazione.save()
            messages.success(
                request,
                f"Destinazione {destinazione.codice} {destinazione.codice_dest or destinazione.id} creata.",
            )
            return_url = _return_url_anagrafica(request, destinazione.codice)
            if return_url:
                return redirect(return_url)
            return redirect("destinazioni:detail", pk=destinazione.pk)
        return render(request, self.template_name, self._form_context(request, form))


class DestinazioneUpdateView(LoginRequiredMixin, View):
    template_name = "destinazioni/destinazione_form.html"

    def get_object(self, pk):
        return get_object_or_404(DestinazioneDiversa, pk=pk)

    def _form_context(self, request, form, destinazione):
        return_url = _return_url_anagrafica(request, destinazione.codice)
        return {
            "form": form,
            "destinazione": destinazione,
            "is_create": False,
            "page_heading": "Modifica destinazione diversa",
            "return_url": return_url,
            "from_anagrafica": bool(return_url),
        }

    def get(self, request, pk):
        destinazione = self.get_object(pk)
        form = DestinazioneDiversaForm(instance=destinazione, chiave_readonly=True)
        return render(
            request,
            self.template_name,
            self._form_context(request, form, destinazione),
        )

    def post(self, request, pk):
        destinazione = self.get_object(pk)
        form = DestinazioneDiversaForm(
            request.POST, instance=destinazione, chiave_readonly=True
        )
        if form.is_valid():
            destinazione = form.save(commit=False)
            stamp_modifica(destinazione)
            destinazione.save()
            messages.success(
                request,
                f"Destinazione {destinazione.codice} {destinazione.codice_dest or destinazione.id} aggiornata.",
            )
            return_url = _return_url_anagrafica(request, destinazione.codice)
            if return_url:
                return redirect(return_url)
            return redirect("destinazioni:detail", pk=destinazione.pk)
        return render(
            request,
            self.template_name,
            self._form_context(request, form, destinazione),
        )


class DestinazioneDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        destinazione = get_object_or_404(DestinazioneDiversa, pk=pk)
        label = f"{destinazione.codice} {destinazione.codice_dest or destinazione.id}"
        return_url = ""
        if _from_anagrafica(request):
            return_url = anagrafica_detail_url(destinazione.codice)
        destinazione.delete()
        messages.success(request, f"Destinazione {label} eliminata.")
        if return_url:
            return redirect(return_url)
        return redirect("destinazioni:list")


class SyncDestinazioniView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "destinazioni/sync_destinazioni.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "destinazioni_count": safe_mirror_count(DestinazioneDiversa.objects),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_destinazioni(full=sync_full_from_request(request))
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
