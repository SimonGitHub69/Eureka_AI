import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from apps.anagrafiche.codice_fiscale import cf_eligible, check_anagrafica_cf, normalize_cf


def _load_cf_payload(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


def _as_bool(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sì", "on"}


class CfCheckApiView(LoginRequiredMixin, View):
    """Verifica formale del codice fiscale italiano (form o scheda)."""

    def post(self, request):
        payload = _load_cf_payload(request)
        cod_fiscale = payload.get("cod_fiscale")
        cod_nazione = payload.get("cod_nazione")
        partita_iva = payload.get("partita_iva")
        persona_fisica = _as_bool(payload.get("persona_fisica"))

        if payload.get("preview"):
            normalized = normalize_cf(cod_fiscale)
            if not normalized:
                return JsonResponse(
                    {
                        "eligible": False,
                        "message": "Inserire un codice fiscale per abilitare il controllo.",
                    }
                )
            if not cf_eligible(normalized, cod_nazione):
                return JsonResponse(
                    {
                        "eligible": False,
                        "message": "Controllo formale italiano non applicato per anagrafiche estere.",
                    }
                )
            return JsonResponse(
                {
                    "eligible": True,
                    "message": f"Controllo formale su {normalized}",
                    "normalized": normalized,
                }
            )

        result = check_anagrafica_cf(
            cod_fiscale,
            cod_nazione,
            partita_iva=partita_iva,
            persona_fisica=persona_fisica,
        )
        return JsonResponse(result.to_dict())
