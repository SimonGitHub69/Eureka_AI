import json

from apps.core.programma import (
    current_pc_context,
    get_assistente_vocale_attivo,
    get_navbar_fissa,
)
from apps.core.models import ComandoVocale


def voice_commands(request):
    enabled = False
    navbar_fissa = True
    commands_json = "[]"
    pc_ctx = {
        "current_pc_name": "",
        "current_pc_label": "",
        "current_pc_config": None,
    }

    if getattr(request, "user", None) and request.user.is_authenticated:
        try:
            enabled = get_assistente_vocale_attivo(request)
            navbar_fissa = get_navbar_fissa(request)
            pc_ctx = current_pc_context(request)
        except Exception:
            enabled = True
            navbar_fissa = True

        if enabled:
            commands = (
                ComandoVocale.objects.filter(attivo=True, is_active=True)
                .order_by("ordine", "frase")
                .values(
                    "frase",
                    "azione",
                    "destinazione",
                    "query",
                    "match_mode",
                    "ordine",
                )
            )
            commands_json = json.dumps(list(commands), ensure_ascii=False)

    return {
        "eureka_voice_enabled": enabled,
        "eureka_navbar_fissa": navbar_fissa,
        "eureka_voice_commands_json": commands_json,
        **pc_ctx,
    }


def integrations(request):
    from django.conf import settings

    url = (getattr(settings, "CARBON_URL", "") or "").strip()
    return {
        "eureka_carbon_url": url,
        "eureka_carbon_enabled": bool(url),
    }
