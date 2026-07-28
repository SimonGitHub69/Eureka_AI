import json
from datetime import datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views import View

from apps.agenda.models import EventoAgenda
from apps.schede_lavorazione.models import SchedaLavorazione


def _parse_iso(value: str | None):
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = parse_datetime(text)
    if dt is None:
        # FullCalendar può passare solo la data (YYYY-MM-DD).
        day = parse_date(text[:10]) if len(text) >= 10 else parse_date(text)
        if day is None:
            return None
        dt = datetime.combine(day, time.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _validate_event_payload(data: dict, *, partial: bool = False):
    errors = []
    titolo = (data.get("titolo") or data.get("title") or "").strip()
    if not partial and not titolo:
        errors.append("Titolo obbligatorio.")
    elif partial and "titolo" not in data and "title" not in data:
        titolo = None
    elif partial and ("titolo" in data or "title" in data) and not titolo:
        errors.append("Titolo obbligatorio.")

    inizio = _parse_iso(data.get("inizio") or data.get("start"))
    fine = _parse_iso(data.get("fine") or data.get("end"))
    if not partial:
        if inizio is None:
            errors.append("Data/ora inizio non valida.")
        if fine is None:
            errors.append("Data/ora fine non valida.")
    else:
        if ("inizio" in data or "start" in data) and inizio is None:
            errors.append("Data/ora inizio non valida.")
        if ("fine" in data or "end" in data) and fine is None:
            errors.append("Data/ora fine non valida.")

    if inizio and fine and fine < inizio:
        errors.append("La fine deve essere successiva all'inizio.")

    tutto_il_giorno = data.get("tutto_il_giorno")
    if tutto_il_giorno is None:
        tutto_il_giorno = data.get("allDay")
    if tutto_il_giorno is not None:
        tutto_il_giorno = bool(tutto_il_giorno)

    colore = (data.get("colore") or data.get("color") or "").strip()
    if colore and colore not in EventoAgenda.Colore.values:
        errors.append("Colore non valido.")

    descrizione = data.get("descrizione")
    if descrizione is None:
        descrizione = data.get("description")
    luogo = data.get("luogo")
    if luogo is None:
        luogo = data.get("location")

    return {
        "errors": errors,
        "titolo": titolo,
        "inizio": inizio,
        "fine": fine,
        "tutto_il_giorno": tutto_il_giorno,
        "colore": colore or None,
        "descrizione": None if descrizione is None else str(descrizione).strip(),
        "luogo": None if luogo is None else str(luogo).strip()[:200],
    }


class AgendaView(LoginRequiredMixin, View):
    template_name = "agenda/calendario.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "colori": EventoAgenda.Colore.choices,
                "colore_default": EventoAgenda.Colore.BLU,
            },
        )


class EventiListApiView(LoginRequiredMixin, View):
    def get(self, request):
        start = _parse_iso(request.GET.get("start"))
        end = _parse_iso(request.GET.get("end"))
        qs = EventoAgenda.objects.filter(is_active=True)
        if start:
            qs = qs.filter(fine__gte=start)
        if end:
            qs = qs.filter(inizio__lte=end)
        return JsonResponse([e.to_fullcalendar() for e in qs], safe=False)

    def post(self, request):
        data = _json_body(request)
        if data is None:
            return JsonResponse({"ok": False, "error": "JSON non valido."}, status=400)

        parsed = _validate_event_payload(data, partial=False)
        if parsed["errors"]:
            return JsonResponse(
                {"ok": False, "error": " ".join(parsed["errors"])},
                status=400,
            )

        inizio = parsed["inizio"]
        fine = parsed["fine"]
        tutto_il_giorno = bool(parsed["tutto_il_giorno"])
        if tutto_il_giorno:
            inizio = timezone.make_aware(
                datetime.combine(inizio.date(), time.min),
                timezone.get_current_timezone(),
            )
            fine = timezone.make_aware(
                datetime.combine(fine.date(), time.min),
                timezone.get_current_timezone(),
            )
            if fine <= inizio:
                fine = inizio + timedelta(days=1)

        evento = EventoAgenda(
            titolo=parsed["titolo"],
            descrizione=parsed["descrizione"] or "",
            inizio=inizio,
            fine=fine,
            tutto_il_giorno=tutto_il_giorno,
            luogo=parsed["luogo"] or "",
            colore=parsed["colore"] or EventoAgenda.Colore.BLU,
            created_by=request.user,
            updated_by=request.user,
        )
        evento.save()
        return JsonResponse({"ok": True, "event": evento.to_fullcalendar()}, status=201)


class EventoDetailApiView(LoginRequiredMixin, View):
    def get(self, request, pk):
        evento = get_object_or_404(EventoAgenda, pk=pk, is_active=True)
        return JsonResponse({"ok": True, "event": evento.to_fullcalendar()})

    def patch(self, request, pk):
        evento = get_object_or_404(EventoAgenda, pk=pk, is_active=True)
        data = _json_body(request)
        if data is None:
            return JsonResponse({"ok": False, "error": "JSON non valido."}, status=400)

        parsed = _validate_event_payload(data, partial=True)
        if parsed["errors"]:
            return JsonResponse(
                {"ok": False, "error": " ".join(parsed["errors"])},
                status=400,
            )

        if parsed["titolo"] is not None:
            evento.titolo = parsed["titolo"]
        if parsed["descrizione"] is not None:
            evento.descrizione = parsed["descrizione"]
        if parsed["luogo"] is not None:
            evento.luogo = parsed["luogo"]
        if parsed["colore"] is not None:
            evento.colore = parsed["colore"]
        if parsed["tutto_il_giorno"] is not None:
            evento.tutto_il_giorno = parsed["tutto_il_giorno"]
        if parsed["inizio"] is not None:
            evento.inizio = parsed["inizio"]
        if parsed["fine"] is not None:
            evento.fine = parsed["fine"]

        if evento.tutto_il_giorno:
            evento.inizio = timezone.make_aware(
                datetime.combine(evento.inizio.date(), time.min),
                timezone.get_current_timezone(),
            )
            evento.fine = timezone.make_aware(
                datetime.combine(evento.fine.date(), time.min),
                timezone.get_current_timezone(),
            )
            if evento.fine <= evento.inizio:
                evento.fine = evento.inizio + timedelta(days=1)

        if evento.fine < evento.inizio:
            return JsonResponse(
                {"ok": False, "error": "La fine deve essere successiva all'inizio."},
                status=400,
            )

        evento.updated_by = request.user
        evento.save()
        return JsonResponse({"ok": True, "event": evento.to_fullcalendar()})

    def delete(self, request, pk):
        evento = get_object_or_404(EventoAgenda, pk=pk, is_active=True)
        evento.soft_delete(user=request.user)
        return JsonResponse({"ok": True})


class SchedeLavorazioneCalendarioApiView(LoginRequiredMixin, View):
    """Eventi FullCalendar dalle schede di lavorazione (campo data)."""

    COLORE = "#0f766e"

    def get(self, request):
        start = _parse_iso(request.GET.get("start"))
        end = _parse_iso(request.GET.get("end"))
        qs = SchedaLavorazione.objects.filter(is_active=True)
        if start:
            qs = qs.filter(data__gte=start.date())
        if end:
            qs = qs.filter(data__lt=end.date())
        qs = qs.order_by("data", "operatore_nome", "id")

        events = []
        for scheda in qs:
            operatore = scheda.operatore_nome or scheda.operatore_codice or "Scheda"
            title = operatore
            if scheda.matricola:
                title = f"{operatore} · mat. {scheda.matricola}"
            events.append(
                {
                    "id": f"scheda-{scheda.pk}",
                    "title": title,
                    "start": scheda.data.isoformat(),
                    "allDay": True,
                    "backgroundColor": self.COLORE,
                    "borderColor": self.COLORE,
                    "textColor": "#ffffff",
                    "editable": False,
                    "extendedProps": {
                        "tipo": "scheda",
                        "schedaId": scheda.pk,
                        "operatore": operatore,
                        "matricola": scheda.matricola,
                        "url": reverse("schede_lavorazione:detail", args=[scheda.pk]),
                    },
                }
            )
        return JsonResponse(events, safe=False)
