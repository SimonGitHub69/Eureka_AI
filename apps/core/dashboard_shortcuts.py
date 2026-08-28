"""Scorciatoie Dashboard / barra alta, configurabili per postazione (Parametri PC)."""

from __future__ import annotations

from typing import Any

# Valori JSON in ConfigurazionePC.dashboard_shortcuts
SHORTCUT_OFF = "off"  # nascosta ovunque
SHORTCUT_DASH = "dash"  # solo card nella maschera Dashboard
SHORTCUT_BAR = "bar"  # solo icona in barra alta
SHORTCUT_BOTH = "both"  # Dashboard + icona in barra alta

SHORTCUT_MODE_CHOICES = (
    (SHORTCUT_OFF, "Disattivo"),
    (SHORTCUT_DASH, "Solo Dashboard"),
    (SHORTCUT_BAR, "Solo barra"),
    (SHORTCUT_BOTH, "Dashboard + barra"),
)

DOC_SHORTCUT_BY_CODICE = {
    "PRV": "doc_prv",
    "ORV": "doc_orv",
    "ORA": "doc_ora",
    "DDT": "doc_ddt",
    "FAT": "doc_fat",
    "NCR": "doc_ncr",
    "NDB": "doc_ndb",
}

def _sc(
    key: str,
    label: str,
    section: str,
    icon: str,
    url_name: str,
    *,
    url_kwargs: dict | None = None,
    default: str = SHORTCUT_OFF,
    requires_extra: str | None = None,
    requires_perm: str | None = None,
    color: str = "secondary",
    subtitle: str = "",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "key": key,
        "label": label,
        "section": section,
        "icon": icon,
        "url_name": url_name,
        "url_kwargs": url_kwargs,
        "default": default,
        "color": color,
        "subtitle": subtitle,
    }
    if requires_extra:
        item["requires_extra"] = requires_extra
    if requires_perm:
        item["requires_perm"] = requires_perm
    return item


# Chiavi in ConfigurazionePC.dashboard_shortcuts (JSON).
# Allineato alle voci e alla gerarchia del menu laterale (sidebar.html).
NAVBAR_SHORTCUT_CATALOG: tuple[dict[str, Any], ...] = (
    # --- Principale ---
    _sc("agenda", "Agenda", "Principale", "ti-calendar", "agenda:calendario", default=SHORTCUT_DASH, color="cyan", subtitle="Calendario e scadenze"),
    # --- Archivi ---
    _sc("clienti", "Clienti", "Archivi", "ti-users", "anagrafiche:clienti_list", default=SHORTCUT_DASH, color="azure", subtitle="Anagrafica clienti"),
    _sc("fornitori", "Fornitori", "Archivi", "ti-truck", "anagrafiche:fornitori_list", default=SHORTCUT_DASH, color="orange", subtitle="Anagrafica fornitori"),
    _sc("agenti", "Agenti", "Archivi", "ti-user-star", "anagrafiche:agenti_list", default=SHORTCUT_OFF, color="purple", subtitle="Anagrafica agenti"),
    # --- Primanota · Gestione ---
    _sc("pdc", "Piano dei Conti", "Primanota · Gestione", "ti-report-money", "pdc:list", default=SHORTCUT_DASH, color="green", subtitle="Primanota"),
    _sc("primanota", "Primanota", "Primanota · Gestione", "ti-notebook", "primanota:list", default=SHORTCUT_DASH, color="teal", subtitle="Primanota"),
    _sc("causali_contabili", "Causali Contabili", "Primanota · Gestione", "ti-file-description", "causali_contabili:list", default=SHORTCUT_OFF, color="lime", subtitle="Primanota"),
    _sc("raggruppamento_conti", "Raggruppamento Conti", "Primanota · Gestione", "ti-category-2", "raggruppamento_conti:list", default=SHORTCUT_OFF, color="green"),
    _sc("raggruppamento_clifor", "Raggr. Clienti-Fornitori", "Primanota · Gestione", "ti-users-group", "raggruppamento_clifor:list", default=SHORTCUT_OFF, color="azure"),
    # --- Primanota · Stampe ---
    _sc("stampa_pdc", "Piano dei Conti", "Primanota · Stampe", "ti-report-money", "pdc:print_list", default=SHORTCUT_OFF, color="green", subtitle="Stampa elenco piano dei conti"),
    _sc("stampa_primanota", "Primanota", "Primanota · Stampe", "ti-notebook", "primanota:print_list", default=SHORTCUT_OFF, color="teal", subtitle="Stampa elenco registrazioni"),
    _sc("stampa_registri_iva", "Registri IVA", "Primanota · Stampe", "ti-book-2", "registri_iva:print_list", default=SHORTCUT_OFF, color="teal", subtitle="Libro registro IVA per periodo"),
    _sc("stampa_causali_contabili", "Causali Contabili", "Primanota · Stampe", "ti-file-description", "causali_contabili:print_list", default=SHORTCUT_OFF, color="lime", subtitle="Stampa elenco causali contabili"),
    _sc("stampa_raggruppamento_conti", "Raggruppamento Conti", "Primanota · Stampe", "ti-category-2", "raggruppamento_conti:print_list", default=SHORTCUT_OFF, color="green", subtitle="Stampa raggruppamenti conti"),
    _sc("stampa_raggruppamento_clifor", "Raggr. Clienti-Fornitori", "Primanota · Stampe", "ti-users-group", "raggruppamento_clifor:print_list", default=SHORTCUT_OFF, color="azure", subtitle="Stampa raggruppamenti clienti/fornitori"),
    # --- Fatturazione Magazzino · Magazzino ---
    _sc("articoli", "Articoli", "Fatturazione Magazzino · Magazzino", "ti-package", "articoli:list", default=SHORTCUT_DASH, color="blue", subtitle="Anagrafica articoli"),
    _sc("distinte_base", "Distinte base", "Fatturazione Magazzino · Magazzino", "ti-list-tree", "distinte_base:list", default=SHORTCUT_OFF, color="indigo"),
    _sc("movimenti", "Movimenti", "Fatturazione Magazzino · Magazzino", "ti-transfer", "movimenti:list", default=SHORTCUT_OFF, color="orange"),
    # --- Fatturazione Magazzino · Documenti ---
    _sc("doc_prv", "Preventivi", "Fatturazione Magazzino · Documenti", "ti-file-text", "documenti:list", url_kwargs={"tipo_doc": "PRV"}, default=SHORTCUT_DASH, color="azure"),
    _sc("doc_orv", "Ordini vendita", "Fatturazione Magazzino · Documenti", "ti-shopping-cart", "documenti:list", url_kwargs={"tipo_doc": "ORV"}, default=SHORTCUT_DASH, color="indigo"),
    _sc("doc_ora", "Ordini acquisto", "Fatturazione Magazzino · Documenti", "ti-shopping-bag", "documenti:list", url_kwargs={"tipo_doc": "ORA"}, default=SHORTCUT_DASH, color="orange"),
    _sc("doc_ddt", "DDT / Bolle", "Fatturazione Magazzino · Documenti", "ti-truck-delivery", "documenti:list", url_kwargs={"tipo_doc": "DDT"}, default=SHORTCUT_DASH, color="teal"),
    _sc("doc_fat", "Fatture", "Fatturazione Magazzino · Documenti", "ti-file-invoice", "fatture:list", default=SHORTCUT_DASH, color="green"),
    _sc("doc_ncr", "Note di credito", "Fatturazione Magazzino · Documenti", "ti-receipt-refund", "documenti:list", url_kwargs={"tipo_doc": "NCR"}, default=SHORTCUT_DASH, color="pink"),
    _sc("doc_ndb", "Note di debito", "Fatturazione Magazzino · Documenti", "ti-receipt", "documenti:list", url_kwargs={"tipo_doc": "NDB"}, default=SHORTCUT_DASH, color="red"),
    # --- Fatturazione Magazzino · Stampe ---
    _sc("stampa_articoli", "Articoli", "Fatturazione Magazzino · Stampe", "ti-package", "articoli:print_list", default=SHORTCUT_OFF, color="blue", subtitle="Stampa elenco articoli"),
    _sc("stampa_inventario", "Inventario", "Fatturazione Magazzino · Stampe", "ti-packages", "core:stampe_inventario", default=SHORTCUT_OFF, color="azure", subtitle="Valori articoli / giacenze"),
    _sc("stampa_distinte_base", "Distinte base", "Fatturazione Magazzino · Stampe", "ti-list-tree", "distinte_base:print_list", default=SHORTCUT_OFF, color="indigo", subtitle="Stampa distinte base"),
    _sc("stampa_movimenti", "Movimenti", "Fatturazione Magazzino · Stampe", "ti-transfer", "movimenti:print_list", default=SHORTCUT_OFF, color="orange", subtitle="Stampa movimenti"),
    # --- Elaborazioni ---
    _sc("analisi_fatturato", "Analisi fatturato", "Elaborazioni", "ti-chart-bar", "fatture:analisi", default=SHORTCUT_DASH, color="cyan", subtitle="Confronti periodi e clienti persi"),
    _sc("classifica_clienti", "Classifica clienti", "Elaborazioni", "ti-trophy", "fatture:classifica", default=SHORTCUT_DASH, color="yellow", subtitle="Migliori clienti nel periodo"),
    _sc("fatturato_geografico", "Fatturato geografico", "Elaborazioni", "ti-map-2", "fatture:analisi_regioni", default=SHORTCUT_DASH, color="green", subtitle="Italia, mondo ISO e cartine"),
    # --- CARBON ---
    _sc("carbon", "Panoramica", "CARBON", "ti-layout-grid", "carbon:hub", default=SHORTCUT_DASH, requires_extra="CARBON", color="teal", subtitle="Produzione e seriali"),
    _sc("carbon_seriali", "Dashboard seriali", "CARBON", "ti-chart-histogram", "carbon:seriali_dashboard", default=SHORTCUT_OFF, requires_extra="CARBON", color="teal"),
    _sc("schede_lavorazione", "Schede di lavorazione", "CARBON", "ti-clipboard-list", "schede_lavorazione:list", default=SHORTCUT_DASH, requires_extra="CARBON", color="teal"),
    _sc("stampi", "Stampi", "CARBON", "ti-box", "stampi:list", default=SHORTCUT_DASH, requires_extra="CARBON", color="teal"),
    _sc("lavorazioni_partite", "Lavorazioni partite", "CARBON", "ti-list-details", "carbon:lavorazioni_list", default=SHORTCUT_OFF, requires_extra="CARBON", color="teal"),
    _sc("stampi_seriali", "Stampi seriali", "CARBON", "ti-barcode", "carbon:stampi_seriali_list", default=SHORTCUT_OFF, requires_extra="CARBON", color="teal"),
    _sc("lavorazioni_extra", "Lavorazioni extra", "CARBON", "ti-tools", "lavorazioni_extra:list", default=SHORTCUT_OFF, requires_extra="CARBON", color="teal"),
    # --- Tabelle · Magazzino ---
    _sc("categorie", "Categorie", "Tabelle · Magazzino", "ti-category", "categorie:list", default=SHORTCUT_OFF, color="blue"),
    _sc("gruppi_articoli", "Gruppi articoli", "Tabelle · Magazzino", "ti-folders", "gruppi_articoli:list", default=SHORTCUT_OFF, color="indigo"),
    _sc("gruppi_magazzini", "Gruppi Magazzini", "Tabelle · Magazzino", "ti-building-warehouse", "gruppi_magazzini:list", default=SHORTCUT_OFF, color="azure"),
    _sc("magazzini", "Magazzini", "Tabelle · Magazzino", "ti-building-store", "magazzini:list", default=SHORTCUT_OFF, color="cyan"),
    _sc("depositi", "Depositi", "Tabelle · Magazzino", "ti-box", "depositi:list", default=SHORTCUT_OFF, color="lime"),
    _sc("causali_magazzino", "Causali magazzino", "Tabelle · Magazzino", "ti-arrows-exchange", "causali_magazzino:list", default=SHORTCUT_OFF, color="orange"),
    # --- Primanota · Tabelle ---
    _sc("aliquote", "Aliquote IVA", "Primanota · Tabelle", "ti-receipt-tax", "aliquote:list", default=SHORTCUT_OFF, color="green"),
    _sc("registri_iva", "Registri IVA", "Primanota · Tabelle", "ti-book-2", "registri_iva:list", default=SHORTCUT_OFF, color="teal"),
    _sc("banche", "Banche", "Primanota · Tabelle", "ti-building-bank", "banche:list", default=SHORTCUT_OFF, color="azure"),
    _sc("sconti", "Sconti", "Primanota · Tabelle", "ti-percentage", "sconti:list", default=SHORTCUT_OFF, color="yellow"),
    _sc("valute", "Valute", "Primanota · Tabelle", "ti-currency-dollar", "valute:list", default=SHORTCUT_OFF, color="lime"),
    _sc("condizioni", "Condizioni di Pagamento", "Primanota · Tabelle", "ti-cash", "condizioni:list", default=SHORTCUT_OFF, color="green"),
    # --- Tabelle · Fatturazione ---
    _sc("aziende", "Azienda", "Tabelle · Fatturazione", "ti-building", "aziende:list", default=SHORTCUT_OFF, color="blue"),
    _sc("zone", "Zone", "Tabelle · Fatturazione", "ti-world", "zone:list", default=SHORTCUT_OFF, color="cyan"),
    _sc("destinazioni", "Destinazioni diverse", "Tabelle · Fatturazione", "ti-map-pin", "destinazioni:list", default=SHORTCUT_OFF, color="orange"),
    _sc("porto", "Porto", "Tabelle · Fatturazione", "ti-package", "documenti:porto_list", default=SHORTCUT_OFF, color="indigo"),
    _sc("vettori", "Spedizionieri", "Tabelle · Fatturazione", "ti-truck", "vettori:list", default=SHORTCUT_OFF, color="azure"),
    _sc("causali_trasp", "Causali trasporto", "Tabelle · Fatturazione", "ti-package-export", "causali_trasp:list", default=SHORTCUT_OFF, color="teal"),
    _sc("regioni", "Regioni", "Tabelle · Fatturazione", "ti-map", "geografia:regioni_list", default=SHORTCUT_OFF, color="green"),
    _sc("province", "Province", "Tabelle · Fatturazione", "ti-map-pin", "geografia:province_list", default=SHORTCUT_OFF, color="lime"),
    _sc("citta", "Città", "Tabelle · Fatturazione", "ti-building-community", "geografia:citta_list", default=SHORTCUT_OFF, color="cyan"),
    # --- Tabelle · Risorse Umane ---
    _sc("operatori", "Operatori", "Tabelle · Risorse Umane", "ti-user-cog", "operatori:list", default=SHORTCUT_OFF, color="purple"),
    _sc("reparti", "Reparti", "Tabelle · Risorse Umane", "ti-building-factory", "carbon:reparti_list", default=SHORTCUT_OFF, requires_extra="CARBON", color="teal"),
    _sc("timbrature", "Presenze", "Tabelle · Risorse Umane", "ti-clock", "timbrature:list", default=SHORTCUT_OFF, color="azure"),
    # --- Parametri ---
    _sc("offline", "Dati offline", "Parametri", "ti-cloud-download", "core:offline", default=SHORTCUT_OFF, color="secondary"),
    _sc("parametri_documento", "Parametri documento", "Parametri", "ti-file-settings", "documenti:parametri_list", default=SHORTCUT_OFF, color="azure"),
    _sc("contatori", "Contatori", "Parametri", "ti-hash", "documenti:contatori_list", default=SHORTCUT_OFF, color="indigo"),
    _sc("parametri_contabili", "Parametri contabili", "Parametri", "ti-calculator", "core:parametri_contabili", default=SHORTCUT_OFF, color="green"),
    _sc("parametri_mail", "Parametri mail", "Parametri", "ti-mail", "core:parametri_mail", default=SHORTCUT_OFF, requires_perm="core.access_parametri_4d", color="cyan"),
    _sc("parametri_programma", "Programma", "Parametri", "ti-adjustments", "core:parametri_programma", default=SHORTCUT_OFF, requires_perm="core.access_parametri_4d", color="blue"),
    _sc("parametri_pc", "Parametri PC", "Parametri", "ti-device-desktop", "core:configurazione_pc_list", default=SHORTCUT_OFF, requires_perm="core.access_parametri_4d", color="azure"),
    _sc("parametri_4d", "Parametri 4D", "Parametri", "ti-database-cog", "core:parametri_4d", default=SHORTCUT_DASH, requires_perm="core.access_parametri_4d", color="azure", subtitle="Configura accesso alle tabelle 4D"),
    _sc("comandi_vocali", "Comandi vocali", "Parametri", "ti-microphone", "core:comandi_vocali_list", default=SHORTCUT_OFF, requires_perm="core.access_parametri_4d", color="pink"),
    _sc("sync_4d", "Sync 4D", "Parametri", "ti-refresh", "core:parametri_4d", default=SHORTCUT_OFF, requires_perm="core.access_parametri_4d", color="orange", subtitle="Sincronizzazione tabelle 4D"),
    # --- Sistema ---
    _sc("sistema", "Sistema", "Sistema", "ti-settings", "dashboard:sistema", default=SHORTCUT_DASH, color="secondary", subtitle="Impostazioni e tabelle importate"),
)

DASHBOARD_SHORTCUT_CATALOG = NAVBAR_SHORTCUT_CATALOG


def _default_posizione_for_key(key: str) -> int:
    for index, item in enumerate(NAVBAR_SHORTCUT_CATALOG, start=1):
        if item["key"] == key:
            return index * 10
    return 9990


def normalize_shortcut_mode(value: Any) -> str:
    """Converte bool legacy / stringhe in off|dash|bar|both."""
    if value is True or value == 1 or value == "1":
        return SHORTCUT_BOTH
    if value is False or value == 0 or value == "0" or value is None:
        return SHORTCUT_OFF
    text = str(value).strip().casefold()
    if text in ("true", "si", "sì", "yes", "on"):
        return SHORTCUT_BOTH
    if text in ("false", "no", "off", ""):
        return SHORTCUT_OFF
    if text in (SHORTCUT_OFF, SHORTCUT_DASH, SHORTCUT_BAR, SHORTCUT_BOTH):
        return text
    if text in ("dashboard", "solo", "solo_dashboard", "dash_only"):
        return SHORTCUT_DASH
    if text in ("barra", "navbar", "solo_barra", "bar_only", "top"):
        return SHORTCUT_BAR
    if text in ("both", "all", "dash_barra"):
        return SHORTCUT_BOTH
    return SHORTCUT_OFF


def _safe_int(value: Any, default: int, *, minimum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None and number < minimum:
        return minimum
    return number


def normalize_shortcut_entry(
    value: Any,
    *,
    default_mode: str = SHORTCUT_OFF,
    default_gruppo: int = 1,
    default_posizione: int = 10,
    default_etichetta: str = "",
) -> dict[str, Any]:
    """Normalizza voce JSON legacy (bool/str) o dict {mode,gruppo,posizione,etichetta}."""
    default_label = (default_etichetta or "").strip()
    if isinstance(value, dict):
        mode_raw = value.get("mode", value.get("stato", default_mode))
        etichetta = (
            value.get("etichetta")
            or value.get("label")
            or value.get("etichetta_barra")
            or ""
        )
        etichetta = str(etichetta).strip() or default_label
        return {
            "mode": normalize_shortcut_mode(mode_raw),
            "gruppo": _safe_int(value.get("gruppo"), default_gruppo, minimum=1),
            "posizione": _safe_int(value.get("posizione"), default_posizione),
            "etichetta": etichetta,
        }
    return {
        "mode": normalize_shortcut_mode(value if value is not None else default_mode),
        "gruppo": default_gruppo,
        "posizione": default_posizione,
        "etichetta": default_label,
    }


def shows_on_dashboard(mode: str) -> bool:
    return normalize_shortcut_mode(mode) in (SHORTCUT_DASH, SHORTCUT_BOTH)


def shows_on_navbar(mode: str) -> bool:
    return normalize_shortcut_mode(mode) in (SHORTCUT_BAR, SHORTCUT_BOTH)


def catalog_by_section() -> list[tuple[str, list[dict[str, Any]]]]:
    sections: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in NAVBAR_SHORTCUT_CATALOG:
        section = item["section"]
        if section not in sections:
            sections[section] = []
            order.append(section)
        sections[section].append(item)
    return [(name, sections[name]) for name in order]


def default_shortcut_configs() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in NAVBAR_SHORTCUT_CATALOG:
        key = item["key"]
        out[key] = {
            "mode": normalize_shortcut_mode(item["default"]),
            "gruppo": 1,
            "posizione": _default_posizione_for_key(key),
            "etichetta": item["label"],
        }
    return out


def resolve_shortcut_configs(stored: dict | None) -> dict[str, dict[str, Any]]:
    configs = default_shortcut_configs()
    if not isinstance(stored, dict):
        return configs
    # Retrocompat: vecchia voce unica «Stampe» → le 4 stampe del menu laterale.
    legacy_stampe = stored.get("stampe")
    if legacy_stampe is not None:
        for key in (
            "stampa_articoli",
            "stampa_inventario",
            "stampa_distinte_base",
            "stampa_movimenti",
        ):
            if key not in stored:
                stored = {**stored, key: legacy_stampe}
    for key, value in stored.items():
        if key not in configs:
            continue
        base = configs[key]
        configs[key] = normalize_shortcut_entry(
            value,
            default_mode=base["mode"],
            default_gruppo=base["gruppo"],
            default_posizione=base["posizione"],
            default_etichetta=base["etichetta"],
        )
    return configs


def default_shortcut_modes() -> dict[str, str]:
    return {key: cfg["mode"] for key, cfg in default_shortcut_configs().items()}


def resolve_shortcut_modes(stored: dict | None) -> dict[str, str]:
    return {key: cfg["mode"] for key, cfg in resolve_shortcut_configs(stored).items()}


# Alias retrocompatibilità
default_shortcut_flags = default_shortcut_modes
resolve_shortcut_flags = resolve_shortcut_modes


def is_shortcut_on_dashboard(modes: dict[str, str], key: str) -> bool:
    return shows_on_dashboard(modes.get(key, SHORTCUT_OFF))


def is_shortcut_on_navbar(modes: dict[str, str], key: str) -> bool:
    return shows_on_navbar(modes.get(key, SHORTCUT_OFF))


def shortcut_visible_for_user(item: dict[str, Any], user) -> bool:
    from apps.core.programma import get_documenti_menu_flags, is_extra_enabled

    requires_extra = item.get("requires_extra")
    if requires_extra and not is_extra_enabled(requires_extra):
        return False
    # Documenti: rispetta i flag di Parametri Programma (come il menu laterale).
    doc_codice = next(
        (cod for cod, key in DOC_SHORTCUT_BY_CODICE.items() if key == item["key"]),
        None,
    )
    if doc_codice is not None:
        if not get_documenti_menu_flags().get(doc_codice, True):
            return False
    requires_perm = item.get("requires_perm")
    if not requires_perm:
        return True
    if user is not None and user.is_authenticated:
        return bool(user.has_perm(requires_perm) or user.is_superuser)
    return False


def build_navbar_shortcut_groups(
    request,
    *,
    configs: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Gruppi icone barra alta: ordinati per gruppo, voci per posizione."""
    from django.urls import NoReverseMatch, reverse

    if configs is None:
        from apps.core.pc import get_dashboard_shortcut_configs_for_request

        configs = get_dashboard_shortcut_configs_for_request(request)

    user = getattr(request, "user", None)
    buckets: dict[int, list[dict[str, Any]]] = {}
    for item in NAVBAR_SHORTCUT_CATALOG:
        cfg = configs.get(item["key"]) or {}
        mode = cfg.get("mode", SHORTCUT_OFF)
        if not shows_on_navbar(mode):
            continue
        if not shortcut_visible_for_user(item, user):
            continue
        try:
            kwargs = item.get("url_kwargs") or {}
            href = reverse(item["url_name"], kwargs=kwargs)
        except NoReverseMatch:
            continue
        gruppo = _safe_int(cfg.get("gruppo"), 1, minimum=1)
        posizione = _safe_int(
            cfg.get("posizione"), _default_posizione_for_key(item["key"])
        )
        buckets.setdefault(gruppo, []).append(
            {
                "key": item["key"],
                "label": (cfg.get("etichetta") or item["label"] or "").strip()
                or item["label"],
                "icon": item["icon"],
                "href": href,
                "gruppo": gruppo,
                "posizione": posizione,
            }
        )

    groups: list[dict[str, Any]] = []
    for gruppo in sorted(buckets.keys()):
        items = sorted(
            buckets[gruppo], key=lambda row: (row["posizione"], row["label"])
        )
        # Tono stabile per numero gruppo (1→0, 2→1, …) per sfumature distinte.
        tone = (gruppo - 1) % 6
        groups.append({"gruppo": gruppo, "tone": tone, "items": items})
    return groups


def build_navbar_shortcuts(
    request,
    *,
    modes: dict[str, str] | None = None,
    flags: dict[str, str] | None = None,
    configs: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Elenco piatto icone barra (compat); preferire build_navbar_shortcut_groups."""
    if configs is None and modes is None and flags is None:
        return [
            item
            for group in build_navbar_shortcut_groups(request)
            for item in group["items"]
        ]
    if configs is None:
        mode_map = modes if modes is not None else flags or {}
        configs = default_shortcut_configs()
        for key, mode in mode_map.items():
            if key in configs:
                configs[key] = {
                    **configs[key],
                    "mode": normalize_shortcut_mode(mode),
                }
    return [
        item
        for group in build_navbar_shortcut_groups(request, configs=configs)
        for item in group["items"]
    ]
