import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from apps.anagrafiche.vies import check_anagrafica_vat, parse_vat_input


def _load_vies_payload(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


class ViesCheckApiView(LoginRequiredMixin, View):
    """Verifica o anteprima VIES da partita IVA e nazione (form o scheda)."""

    def post(self, request):
        payload = _load_vies_payload(request)
        partita_iva = payload.get("partita_iva")
        cod_nazione = payload.get("cod_nazione")

        if payload.get("preview"):
            parsed = parse_vat_input(partita_iva, cod_nazione)
            if not parsed:
                if not (partita_iva or "").strip():
                    message = "Inserire una partita IVA per abilitare la verifica VIES."
                else:
                    message = "Verifica non disponibile: paese non UE VIES o formato non valido."
                return JsonResponse({"eligible": False, "message": message})
            return JsonResponse(
                {
                    "eligible": True,
                    "message": f"Controllo UE su {parsed.display_country} {parsed.display_vat}",
                    "country_code": parsed.country_code,
                    "vat_number": parsed.vat_number,
                }
            )

        result = check_anagrafica_vat(partita_iva, cod_nazione)
        status = 200 if result.ok or not result.eligible else 503
        return JsonResponse(result.to_dict(), status=status)
