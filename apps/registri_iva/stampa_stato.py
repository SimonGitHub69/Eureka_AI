"""Stato ultima stampa definitiva libro registro IVA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils.dateparse import parse_date

from apps.registri_iva.models import RegistroIvaStampaStato

RIGHE_PER_PAGINA_STIMA = 55

# Chiave sintetica in RegistroIvaStampaStato per la Liquidazione Periodica IVA
LIQUIDAZIONE_STAMPA_CODICE = "LIQUIDAZIONE"


def _month_end(d: date) -> date:
    """Ultimo giorno del mese di ``d``."""
    import calendar

    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


@dataclass
class StampaDefinitivaInfo:
    registro_codice: str
    data_finale: date | None = None
    ultimo_protocollo: int | None = None
    ultima_pagina: int = 0

    @property
    def data_da_suggerita(self) -> date | None:
        """Giorno successivo all'ultima definitiva (es. 31/01 → 01/02)."""
        if self.data_finale is None:
            return None
        return self.data_finale + timedelta(days=1)

    @property
    def data_a_suggerita(self) -> date | None:
        """Fine mese del periodo da stampare (es. da 01/02 → 28/02)."""
        start = self.data_da_suggerita
        if start is None:
            return None
        return _month_end(start)

    @property
    def pagina_da_suggerita(self) -> int:
        return max(1, int(self.ultima_pagina or 0) + 1)


def get_stampa_stato(registro_codice: str) -> StampaDefinitivaInfo:
    code = (registro_codice or "").strip()
    if not code:
        return StampaDefinitivaInfo(registro_codice="")
    row = RegistroIvaStampaStato.objects.filter(registro_codice__iexact=code).first()
    if row is None:
        return StampaDefinitivaInfo(registro_codice=code)
    return StampaDefinitivaInfo(
        registro_codice=row.registro_codice,
        data_finale=row.data_finale,
        ultimo_protocollo=row.ultimo_protocollo,
        ultima_pagina=int(row.ultima_pagina or 0),
    )


def save_stampa_stato(
    *,
    registro_codice: str,
    data_finale: date | None,
    ultimo_protocollo: int | None,
    ultima_pagina: int | None,
) -> RegistroIvaStampaStato:
    code = (registro_codice or "").strip()
    if not code:
        raise ValueError("Codice registro obbligatorio")
    obj, _ = RegistroIvaStampaStato.objects.update_or_create(
        registro_codice=code,
        defaults={
            "data_finale": data_finale,
            "ultimo_protocollo": ultimo_protocollo,
            "ultima_pagina": int(ultima_pagina or 0),
        },
    )
    return obj


def stima_num_pagine(
    righe_count: int,
    *,
    pagina_da: int = 1,
    con_riepilogo: bool = False,
) -> int:
    """Stima pagine libro (righe tabella + eventuale foglio riepilogo).

    Il riepilogo IVA è sempre un foglio separato: se i movimenti occupano
    N pagine, con riepilogo il totale è N+1 (es. 3 + riepilogo → 4).
    """
    del pagina_da  # riservato per firme compatibili; non altera il conteggio
    rows = max(0, int(righe_count or 0))
    if rows == 0:
        pages = 1
    else:
        # +2: overhead masthead/intestazioni nelle pagine movimenti
        pages = max(1, (rows + 2 + RIGHE_PER_PAGINA_STIMA - 1) // RIGHE_PER_PAGINA_STIMA)
    if con_riepilogo:
        pages += 1
    return pages


def periodo_sovrappone_definitiva(
    data_da: date | None,
    data_a: date | None,
    stato: StampaDefinitivaInfo,
) -> bool:
    """True se il periodo richiesto è <= data_finale già stampata."""
    if stato.data_finale is None:
        return False
    if data_a is not None and data_a <= stato.data_finale:
        return True
    if data_da is not None and data_da <= stato.data_finale:
        return True
    return False


def parse_int_or_none(raw) -> int | None:
    text = (str(raw) if raw is not None else "").strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def resolve_data_da_default(request_get, stato: StampaDefinitivaInfo) -> str:
    """Prefill data_da da GET o giorno dopo data_finale."""
    raw = (request_get.get("data_da") or "").strip()
    if raw:
        return raw
    suggested = stato.data_da_suggerita
    if suggested is None:
        return ""
    return suggested.isoformat()


def resolve_data_a_default(
    request_get,
    stato: StampaDefinitivaInfo,
    *,
    data_da: str = "",
) -> str:
    """Prefill data_a da GET o fine mese del periodo proposto (da data_da / stato)."""
    raw = (request_get.get("data_a") or "").strip()
    if raw:
        return raw
    start = parse_date((data_da or "").strip()) if data_da else None
    if start is None:
        suggested = stato.data_a_suggerita
        if suggested is None:
            return ""
        return suggested.isoformat()
    return _month_end(start).isoformat()


def resolve_pagina_da(request_get, stato: StampaDefinitivaInfo) -> int:
    raw = parse_int_or_none(request_get.get("pagina_da"))
    if raw is not None and raw >= 1:
        return raw
    return stato.pagina_da_suggerita
