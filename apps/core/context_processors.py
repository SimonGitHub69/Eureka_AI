import json

from apps.core.programma import (
    get_ai_example_prompt,
    get_ai_recent_searches_limit,
    current_pc_context,
    get_debug_ai_sql,
    get_assistente_vocale_attivo,
    get_liste_fisse,
    get_navbar_fissa,
    get_suono_errore_attivo,
    get_suono_errore_url,
)
from apps.core.models import ComandoVocale


def voice_commands(request):
    enabled = False
    navbar_fissa = True
    liste_fisse = True
    error_sound_url = ""
    error_sound_enabled = False
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
            liste_fisse = get_liste_fisse(request)
            pc_ctx = current_pc_context(request)
        except Exception:
            enabled = True
            navbar_fissa = True
            liste_fisse = True

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

        try:
            error_sound_enabled = get_suono_errore_attivo()
            error_sound_url = get_suono_errore_url() if error_sound_enabled else ""
        except Exception:
            error_sound_enabled = True
            error_sound_url = ""

    return {
        "eureka_voice_enabled": enabled,
        "eureka_navbar_fissa": navbar_fissa,
        "eureka_liste_fisse": liste_fisse,
        "eureka_voice_commands_json": commands_json,
        "eureka_error_sound_enabled": error_sound_enabled,
        "eureka_error_sound_url": error_sound_url,
        **pc_ctx,
    }


def integrations(request):
    from django.conf import settings

    from apps.aziende.configurazione import is_azienda_noleggio

    url = (getattr(settings, "CARBON_URL", "") or "").strip()
    azienda_noleggio = False
    if getattr(request, "user", None) and request.user.is_authenticated:
        try:
            azienda_noleggio = is_azienda_noleggio()
        except Exception:
            azienda_noleggio = False
    return {
        "eureka_carbon_url": url,
        "eureka_carbon_enabled": bool(url),
        "eureka_azienda_noleggio": azienda_noleggio,
    }


def programma_documenti(request):
    from apps.core.programma import (
        DEFAULT_DOC_MENU_FLAGS,
        DEFAULT_EXTRA_MENU_FLAGS,
        get_documenti_menu_extra,
        get_documenti_menu_flags,
        get_documenti_menu_items,
        get_extra_menu_flags,
        mark_documenti_menu_items_active,
    )

    flags = DEFAULT_DOC_MENU_FLAGS.copy()
    extra_flags = DEFAULT_EXTRA_MENU_FLAGS.copy()
    extra = []
    items = []
    authenticated = bool(getattr(request, "user", None) and request.user.is_authenticated)
    if authenticated:
        try:
            extra_flags = get_extra_menu_flags()
        except Exception:
            extra_flags = {key: False for key in DEFAULT_EXTRA_MENU_FLAGS}
        try:
            flags = get_documenti_menu_flags()
            extra = get_documenti_menu_extra()
            items = get_documenti_menu_items(flags=flags)
            mark_documenti_menu_items_active(request, items)
        except Exception:
            extra = []
            items = []
    else:
        try:
            items = get_documenti_menu_items(flags=flags, include_extra=False)
            mark_documenti_menu_items_active(request, items)
        except Exception:
            extra = []
            items = []
    return {
        "eureka_doc_menu": flags,
        "eureka_doc_menu_extra": extra,
        "eureka_doc_menu_items": items,
        "eureka_doc_menu_any": any(flags.values()) or bool(extra),
        "eureka_extra_menu": extra_flags,
        "eureka_extra_carbon": bool(extra_flags.get("CARBON")),
    }


def ai_debug_flags(request):
    # Toggle UI e limiti per il modale dell'assistente AI.
    return {
        "eureka_ai_debug_sql": get_debug_ai_sql(),
        "eureka_ai_recent_searches_limit": get_ai_recent_searches_limit(),
        "eureka_ai_example_prompt": get_ai_example_prompt(),
    }
