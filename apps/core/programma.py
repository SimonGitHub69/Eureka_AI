"""Lettura parametri programma con eventuale override da postazione PC."""

from __future__ import annotations

from apps.core.models import ConfigurazioneProgramma
from apps.core.pc import (
    detect_client_pc_name,
    get_configurazione_pc,
    get_nome_pc_from_request,
)

DOC_MENU_FIELDS: dict[str, str] = {
    "PRV": "doc_prv",
    "ORV": "doc_orv",
    "ORA": "doc_ora",
    "DDT": "doc_ddt",
    "FAT": "doc_fat",
    "NCR": "doc_ncr",
    "NDB": "doc_ndb",
}

DOC_MENU_ICONS: dict[str, str] = {
    "PRV": "ti-file-text",
    "PRF": "ti-file-text",
    "ORV": "ti-shopping-cart",
    "ORA": "ti-shopping-bag",
    "DDT": "ti-truck-delivery",
    "FAT": "ti-file-invoice",
    "NCR": "ti-receipt-refund",
    "NDB": "ti-receipt",
}

CATEGORIA_MENU_FIELDS: dict[str, str] = {
    "PREVENTIVI": "doc_prv",
    "FATTURE": "doc_fat",
    "NOTE_CREDITO": "doc_ncr",
    "NOTE_DEBITO": "doc_ndb",
    "DDT": "doc_ddt",
}

DEFAULT_DOC_MENU_FLAGS: dict[str, bool] = dict.fromkeys(DOC_MENU_FIELDS, True)

# Personalizzazioni extra (moduli verticali, es. CARBON). Estendere qui.
EXTRA_MENU_FIELDS: dict[str, str] = {
    "CARBON": "extra_carbon",
}

DEFAULT_EXTRA_MENU_FLAGS: dict[str, bool] = dict.fromkeys(EXTRA_MENU_FIELDS, True)


def get_configurazione_programma():
    return ConfigurazioneProgramma.get_solo()


def get_documenti_menu_flags() -> dict[str, bool]:
    cfg = get_configurazione_programma()
    return {
        codice: bool(getattr(cfg, field, True))
        for codice, field in DOC_MENU_FIELDS.items()
    }


def get_extra_menu_flags() -> dict[str, bool]:
    """Flag delle personalizzazioni extra (CARBON, …)."""
    cfg = get_configurazione_programma()
    return {
        codice: bool(getattr(cfg, field, True))
        for codice, field in EXTRA_MENU_FIELDS.items()
    }


def is_extra_enabled(codice: str) -> bool:
    key = (codice or "").upper()
    field = EXTRA_MENU_FIELDS.get(key)
    if not field:
        return False
    return bool(getattr(get_configurazione_programma(), field, True))


def get_documenti_menu_extra():
    """Tipi extra attivi (non nel menu predefinito), da mostrare in Fatturazione.

    Le varianti di serie sulla stessa tabella 4D (es. PRF / Preventivi FF) restano
    tipi di sync, non voci di menu.
    """
    from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO, PREVENTIVI_TIPI
    from apps.documenti.models import TipoDocumento

    builtin_sources = {
        (spec.get("source_table_4d") or "").strip().casefold()
        for spec in DEFAULT_TIPI_DOCUMENTO
        if spec.get("source_table_4d")
    }
    hidden_codes = {c for c in PREVENTIVI_TIPI if c not in DOC_MENU_FIELDS}
    extras = []
    for tipo in (
        TipoDocumento.objects.filter(attivo=True)
        .exclude(codice__in=DOC_MENU_FIELDS)
        .order_by("ordine", "codice")
        .only("codice", "label", "ordine", "source_table_4d")
    ):
        if tipo.codice in hidden_codes:
            continue
        source = (tipo.source_table_4d or "").strip().casefold()
        if source and source in builtin_sources:
            continue
        extras.append(tipo)
    return extras


def get_documenti_menu_items(*, flags: dict[str, bool] | None = None, include_extra: bool = True):
    """Voci menu Fatturazione, ordinate per Parametri documento.ordine."""
    from django.urls import reverse

    from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO
    from apps.documenti.models import TipoDocumento

    if flags is None:
        flags = get_documenti_menu_flags()

    defaults = {spec["codice"]: spec for spec in DEFAULT_TIPI_DOCUMENTO}
    tipi = {
        t.codice: t
        for t in TipoDocumento.objects.only("codice", "label", "ordine")
    }

    items: list[dict] = []
    seen: set[str] = set()

    for codice, enabled in flags.items():
        if not enabled:
            continue
        tipo = tipi.get(codice)
        spec = defaults.get(codice, {})
        ordine = tipo.ordine if tipo is not None else spec.get("ordine", 999)
        label = tipo.label if tipo is not None else spec.get("label", codice)
        items.append(_documenti_menu_item(codice, label, ordine, reverse))
        seen.add(codice)

    if include_extra:
        for tipo in get_documenti_menu_extra():
            if tipo.codice in seen:
                continue
            items.append(
                _documenti_menu_item(tipo.codice, tipo.label, tipo.ordine, reverse)
            )

    items.sort(key=lambda item: (item["ordine"], item["codice"]))
    return items


def _documenti_menu_item(codice: str, label: str, ordine: int, reverse) -> dict:
    is_fatture = codice == "FAT"
    href = (
        reverse("fatture:list")
        if is_fatture
        else reverse("documenti:list", kwargs={"tipo_doc": codice})
    )
    return {
        "codice": codice,
        "label": label,
        "ordine": ordine,
        "icon": DOC_MENU_ICONS.get(codice, "ti-file"),
        "href": href,
        "is_fatture": is_fatture,
    }


def menu_codice_for(tipo_doc: str) -> str:
    """Voce di menu a cui appartiene un tipo (PRF/PRT → Preventivi)."""
    codice = (tipo_doc or "").upper()
    if codice in DOC_MENU_FIELDS:
        return codice
    from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO, PREVENTIVI_TIPI

    if codice in PREVENTIVI_TIPI:
        return "PRV"
    try:
        from apps.documenti.models import TipoDocumento

        tipo = (
            TipoDocumento.objects.filter(codice=codice)
            .only("source_table_4d", "categoria")
            .first()
        )
        source = ((tipo.source_table_4d if tipo else "") or "").strip().casefold()
        if source:
            for spec in DEFAULT_TIPI_DOCUMENTO:
                table = (spec.get("source_table_4d") or "").strip().casefold()
                if table == source and spec["codice"] in DOC_MENU_FIELDS:
                    return spec["codice"]
        if tipo and (tipo.categoria or "").upper() == "PREVENTIVI":
            return "PRV"
    except Exception:
        pass
    return codice


def mark_documenti_menu_items_active(request, items: list[dict]) -> list[dict]:
    match = getattr(request, "resolver_match", None)
    namespace = getattr(match, "namespace", "") if match else ""
    url_name = getattr(match, "url_name", "") if match else ""
    tipo_doc = ((getattr(match, "kwargs", None) or {}).get("tipo_doc") or "") if match else ""
    for item in items:
        if item["is_fatture"]:
            item["active"] = namespace == "fatture" and url_name in {
                "list",
                "detail",
                "xml_sdi",
            }
        else:
            item["active"] = (
                namespace == "documenti" and menu_codice_for(tipo_doc) == item["codice"]
            )
    return items


def menu_field_for_tipo(
    codice: str,
    *,
    categoria: str = "",
    clifor_tipo: str = "",
) -> str | None:
    """Campo ConfigurazioneProgramma che abilita questo tipo documento."""
    field = DOC_MENU_FIELDS.get((codice or "").upper())
    if field:
        return field
    if (categoria or "").upper() == "ORDINI":
        return "doc_ora" if (clifor_tipo or "").upper() == "F" else "doc_orv"
    return CATEGORIA_MENU_FIELDS.get((categoria or "").upper())


def is_documento_menu_enabled(tipo_doc: str) -> bool:
    """True se il TipoDoc è abilitato in Parametri programma (menu e sync 4D)."""
    codice = (tipo_doc or "").upper()
    field = DOC_MENU_FIELDS.get(codice)
    if not field and codice == "PRF":
        # Stessa famiglia di PRV (serie FF), stesso flag programma.
        field = "doc_prv"
    if field:
        return bool(getattr(get_configurazione_programma(), field, True))

    from apps.documenti.models import TipoDocumento

    tipo = (
        TipoDocumento.objects.filter(codice=codice, attivo=True)
        .only("categoria", "clifor_tipo")
        .first()
    )
    if tipo is None:
        return False
    field = menu_field_for_tipo(
        codice, categoria=tipo.categoria, clifor_tipo=tipo.clifor_tipo
    )
    if not field:
        # Famiglia Altro (e tipi senza flag programma): visibili se attivi.
        return True
    return bool(getattr(get_configurazione_programma(), field, True))


is_tipo_doc_enabled = is_documento_menu_enabled


def get_tipi_documento_abilitati() -> tuple[str, ...]:
    """Tipi documento abilitati, nell'ordine canonico DOC_MENU_FIELDS."""
    flags = get_documenti_menu_flags()
    return tuple(codice for codice in DOC_MENU_FIELDS if flags.get(codice, True))


def describe_sync_documenti_tipi() -> str:
    """Descrizione tipi inclusi/esclusi per sync documenti e SYNC_4D_STEPS."""
    flags = get_documenti_menu_flags()
    enabled = [c for c in DOC_MENU_FIELDS if flags.get(c, True)]
    disabled = [c for c in DOC_MENU_FIELDS if not flags.get(c, True)]
    parts = ["Teste/righe documenti"]
    if enabled:
        parts.append(f"({', '.join(enabled)})")
    if disabled:
        parts.append(f"— esclusi: {', '.join(disabled)}")
    return " ".join(parts)


def any_documento_menu_enabled() -> bool:
    return any(get_documenti_menu_flags().values()) or bool(get_documenti_menu_extra())


def get_assistente_vocale_attivo(request=None) -> bool:
    if request is not None:
        cfg_pc = _cfg_pc_for(request)
        if cfg_pc is not None:
            return bool(cfg_pc.assistente_vocale_attivo)
    return bool(get_configurazione_programma().assistente_vocale_attivo)


def get_navbar_fissa(request=None) -> bool:
    if request is not None:
        cfg_pc = _cfg_pc_for(request)
        if cfg_pc is not None:
            return bool(cfg_pc.navbar_fissa)
    return bool(get_configurazione_programma().navbar_fissa)


def get_liste_fisse(request=None) -> bool:
    if request is not None:
        cfg_pc = _cfg_pc_for(request)
        if cfg_pc is not None:
            return bool(cfg_pc.liste_fisse)
    return bool(get_configurazione_programma().liste_fisse)


def get_suono_errore_attivo() -> bool:
    return bool(get_configurazione_programma().suono_errore_attivo)


def get_suono_errore_url() -> str:
    """URL del file .wav da riprodere in caso di errore (personalizzato o predefinito)."""
    from django.templatetags.static import static

    cfg = get_configurazione_programma()
    if not cfg.suono_errore_attivo:
        return ""
    if cfg.suono_errore_wav:
        return cfg.suono_errore_wav.url
    return static("eureka/sounds/error.wav")


def get_debug_ai_sql() -> bool:
    """Abilita in UI la visualizzazione di SQL e spiegazione dell'assistente AI."""
    return bool(get_configurazione_programma().debug_ai_sql)


def get_ai_recent_searches_limit() -> int:
    """Numero massimo di ricerche recenti AI da mantenere per utente nel browser."""
    value = getattr(get_configurazione_programma(), "ai_recent_searches_limit", 10) or 10
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 10
    return min(max(value, 1), 100)


_DEFAULT_AI_EXAMPLE_PROMPT = (
    "Cerca tutti i movimenti IVA il cui imponibile è compreso tra 1500 e 1750 "
    "nell'anno in corso"
)


def get_ai_example_prompt() -> str:
    """Testo di esempio mostrato nel modale dell'assistente AI."""
    value = getattr(get_configurazione_programma(), "ai_example_prompt", "") or ""
    value = str(value).strip()
    return value or _DEFAULT_AI_EXAMPLE_PROMPT


def _cfg_pc_for(request):
    nome = detect_client_pc_name(request) or get_nome_pc_from_request(request)
    return get_configurazione_pc(nome) if nome else None


def current_pc_context(request=None) -> dict:
    nome = ""
    cfg = None
    if request is not None:
        nome = detect_client_pc_name(request) or get_nome_pc_from_request(request)
        cfg = get_configurazione_pc(nome) if nome else None

    label = str(cfg) if cfg else nome
    return {
        "current_pc_name": nome,
        "current_pc_label": label,
        "current_pc_config": cfg,
    }
