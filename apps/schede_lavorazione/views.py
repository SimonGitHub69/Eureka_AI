from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from apps.aziende.models import Azienda, AziendaDati
from apps.core.mixins import RequireExtraMixin
from apps.core.pagination import PerPageListMixin
from apps.core.sorting import SortableListMixin
from apps.schede_lavorazione.forms import (
    SchedaLavorazioneCreateForm,
    SchedaLavorazioneUpdateForm,
)
from apps.schede_lavorazione.lookup import lookup_pezzo
from apps.schede_lavorazione.models import RigaSchedaLavorazione, SchedaLavorazione

PRINT_MIN_ROWS = 10


def _branding_azienda() -> dict:
    """Logo azienda da AziendaDati (preferisce logo stampe documenti)."""
    from django.db import transaction
    from django.db.utils import OperationalError, ProgrammingError

    from apps.aziende.configurazione import resolve_azienda_dati

    dati = resolve_azienda_dati()
    if dati is None:
        try:
            with transaction.atomic():
                azienda = Azienda.objects.order_by("id").first()
        except (ProgrammingError, OperationalError):
            azienda = None
        if azienda:
            dati = AziendaDati.objects.filter(
                is_active=True, azienda_id=azienda.id
            ).first()

    logo = None
    if dati:
        if dati.logo_documenti:
            logo = dati.logo_documenti
        elif dati.logo:
            logo = dati.logo

    return {"logo": logo}



class SchedaLavorazioneListView(
    LoginRequiredMixin, RequireExtraMixin, SortableListMixin, PerPageListMixin, ListView
):
    model = SchedaLavorazione
    template_name = "schede_lavorazione/scheda_list.html"
    context_object_name = "schede"
    sortable_fields = ("data", "operatore_nome", "operatore_codice", "matricola", "id")
    default_sort = "data"
    default_dir = "desc"
    sort_tiebreaker = "id"
    paginate_by = 50

    def get_queryset(self):
        qs = SchedaLavorazione.objects.filter(is_active=True)
        q = (self.request.GET.get("q") or "").strip()
        data = (self.request.GET.get("data") or "").strip()
        if q:
            qs = qs.filter(
                Q(operatore_nome__icontains=q)
                | Q(operatore_codice__icontains=q)
                | Q(matricola__icontains=q)
            )
        if data:
            qs = qs.filter(data=data)
        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["data"] = (self.request.GET.get("data") or "").strip()
        context["has_filters"] = bool(context["q"] or context["data"])
        context["totale"] = SchedaLavorazione.objects.filter(is_active=True).count()
        return context


class SchedaLavorazioneCreateView(LoginRequiredMixin, RequireExtraMixin, View):
    template_name = "schede_lavorazione/scheda_create.html"

    def _context(self, form):
        import json

        return {
            "form": form,
            "operatori_json": json.dumps(form.operatori, ensure_ascii=False),
        }

    def get(self, request):
        return render(request, self.template_name, self._context(SchedaLavorazioneCreateForm()))

    def post(self, request):
        form = SchedaLavorazioneCreateForm(request.POST)
        if form.is_valid():
            scheda = form.save(commit=False)
            scheda.created_by = request.user
            scheda.updated_by = request.user
            scheda.save()
            messages.success(request, "Scheda creata. Inserisci le righe pezzo.")
            return redirect("schede_lavorazione:detail", pk=scheda.pk)
        return render(request, self.template_name, self._context(form))


class SchedaLavorazioneUpdateView(LoginRequiredMixin, RequireExtraMixin, View):
    """Modifica sola testata (data/operatore/matricola). Le righe non vengono toccate."""

    template_name = "schede_lavorazione/scheda_edit.html"

    def _get_scheda(self, pk):
        return get_object_or_404(SchedaLavorazione, pk=pk, is_active=True)

    def _context(self, form, scheda):
        import json

        return {
            "form": form,
            "scheda": scheda,
            "operatori_json": json.dumps(form.operatori, ensure_ascii=False),
        }

    def get(self, request, pk):
        scheda = self._get_scheda(pk)
        form = SchedaLavorazioneUpdateForm(instance=scheda)
        return render(request, self.template_name, self._context(form, scheda))

    def post(self, request, pk):
        scheda = self._get_scheda(pk)
        form = SchedaLavorazioneUpdateForm(request.POST, instance=scheda)
        if form.is_valid():
            scheda = form.save(commit=False)
            scheda.updated_by = request.user
            scheda.save()
            messages.success(request, "Testata scheda aggiornata.")
            return redirect("schede_lavorazione:detail", pk=scheda.pk)
        return render(request, self.template_name, self._context(form, scheda))


class SchedaLavorazioneDetailView(LoginRequiredMixin, RequireExtraMixin, View):
    template_name = "schede_lavorazione/scheda_detail.html"

    def get(self, request, pk):
        scheda = get_object_or_404(SchedaLavorazione, pk=pk, is_active=True)
        righe = scheda.righe.filter(is_active=True).order_by("ordine", "id")
        from_agenda = (request.GET.get("from") or "").strip().lower() == "agenda"
        agenda_back_url = reverse("agenda:calendario")
        if from_agenda:
            from urllib.parse import urlencode

            params = {}
            tipo = (request.GET.get("tipo") or "schede").strip()
            vista = (request.GET.get("vista") or "").strip()
            data = (request.GET.get("data") or "").strip()
            if tipo:
                params["tipo"] = tipo
            if vista:
                params["vista"] = vista
            if data:
                params["data"] = data
            if params:
                agenda_back_url = f"{agenda_back_url}?{urlencode(params)}"
        return render(
            request,
            self.template_name,
            {
                "scheda": scheda,
                "righe": righe,
                "lookup_url": reverse("schede_lavorazione:api_lookup_pezzo"),
                "save_rows_url": reverse("schede_lavorazione:api_save_righe", kwargs={"pk": scheda.pk}),
                "print_url": reverse("schede_lavorazione:print", kwargs={"pk": scheda.pk}),
                "edit_url": reverse("schede_lavorazione:edit", kwargs={"pk": scheda.pk}),
                "from_agenda": from_agenda,
                "agenda_back_url": agenda_back_url,
            },
        )


class SchedaLavorazionePrintView(LoginRequiredMixin, RequireExtraMixin, View):
    """Stampa HTML della scheda di lavorazione."""

    template_name = "schede_lavorazione/scheda_print.html"

    def get(self, request, pk):
        scheda = get_object_or_404(SchedaLavorazione, pk=pk, is_active=True)
        righe = list(scheda.righe.filter(is_active=True).order_by("ordine", "id"))
        blank_rows = max(0, PRINT_MIN_ROWS - len(righe))
        branding = _branding_azienda()
        return render(
            request,
            self.template_name,
            {
                "scheda": scheda,
                "righe": righe,
                "blank_rows": range(blank_rows),
                "azienda_logo": branding["logo"],
                "autoprint": (request.GET.get("autoprint") or "").strip() in {"1", "true", "yes"},
            },
        )


class SchedaLavorazioneDeleteView(LoginRequiredMixin, RequireExtraMixin, View):
    def post(self, request, pk):
        scheda = get_object_or_404(SchedaLavorazione, pk=pk, is_active=True)
        for riga in scheda.righe.filter(is_active=True):
            riga.soft_delete(user=request.user)
        scheda.soft_delete(user=request.user)
        messages.success(request, "Scheda eliminata.")
        return redirect("schede_lavorazione:list")


class LookupPezzoApiView(LoginRequiredMixin, RequireExtraMixin, View):
    def get(self, request):
        codice = (request.GET.get("codice") or "").strip()
        return JsonResponse(lookup_pezzo(codice))


class SaveRigheApiView(LoginRequiredMixin, RequireExtraMixin, View):
    def post(self, request, pk):
        scheda = get_object_or_404(SchedaLavorazione, pk=pk, is_active=True)
        try:
            import json

            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON non valido."}, status=400)

        rows = payload.get("righe") or []
        if not isinstance(rows, list):
            return JsonResponse({"ok": False, "error": "Formato righe non valido."}, status=400)

        # Soft-delete existing rows, then recreate from payload (simple replace).
        for existing in scheda.righe.filter(is_active=True):
            existing.soft_delete(user=request.user)

        created = []
        ordine = 0
        for raw in rows:
            codice_pezzo = str(raw.get("codice_pezzo") or "").strip()
            if not codice_pezzo:
                continue
            ordine += 1
            try:
                tempo = Decimal(str(raw.get("tempo_distinta") or "0").replace(",", "."))
            except (InvalidOperation, TypeError, ValueError):
                tempo = Decimal("0")

            pezzo = lookup_pezzo(codice_pezzo)
            if pezzo.get("ok"):
                cod_art_cliente = pezzo.get("cod_art_cliente") or ""
                descrizione_componente = pezzo.get("descrizione_componente") or ""
            else:
                cod_art_cliente = str(raw.get("cod_art_cliente") or "").strip()
                descrizione_componente = str(raw.get("descrizione_componente") or "").strip()

            riga = RigaSchedaLavorazione.objects.create(
                scheda=scheda,
                ordine=ordine,
                codice_pezzo=codice_pezzo,
                cliente="",
                cod_art_cliente=cod_art_cliente,
                descrizione_componente=descrizione_componente,
                tempo_distinta=tempo,
                created_by=request.user,
                updated_by=request.user,
            )
            created.append(
                {
                    "id": riga.id,
                    "ordine": riga.ordine,
                    "codice_pezzo": riga.codice_pezzo,
                    "cod_art_cliente": riga.cod_art_cliente,
                    "descrizione_componente": riga.descrizione_componente,
                    "tempo_distinta": str(riga.tempo_distinta),
                }
            )

        scheda.updated_by = request.user
        scheda.save(update_fields=["updated_by", "updated_at"])

        return JsonResponse(
            {
                "ok": True,
                "message": f"Salvate {len(created)} righe.",
                "righe": created,
            }
        )
