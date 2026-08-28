"""Scadenze di pagamento sulla testata documento (numero di rate libero)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

# Tetto solo anti-abuso (rate mensili su più anni). Il numero reale viene da Condizione.numero_rate.
MAX_SCADENZE = 36


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _apply_giorno_fisso(d: date, giorno: int | None, *, fine_mese: bool = False) -> date:
    try:
        g = int(giorno or 0)
    except (TypeError, ValueError):
        return d
    if g <= 0:
        return d

    def day_for_month(year: int, month: int) -> int | None:
        last = monthrange(year, month)[1]
        if fine_mese:
            return last
        if g <= last:
            return g
        return None

    day = day_for_month(d.year, d.month)
    if day is not None:
        candidate = d.replace(day=day)
        if candidate >= d:
            return candidate

    nxt = _add_months(d.replace(day=1), 1)
    while True:
        day = day_for_month(nxt.year, nxt.month)
        if day is not None:
            return nxt.replace(day=day)
        nxt = _add_months(nxt.replace(day=1), 1)


def _skip_mesi_esclusione(
    d: date,
    mese_esclusione: int | None,
    mese_esclusione2: int | None,
    gg_mese_esclus: int | None,
    gg_mese_esclus2: int | None,
) -> date:
    excluded = set()
    for mese in (mese_esclusione, mese_esclusione2):
        try:
            m = int(mese or 0)
        except (TypeError, ValueError):
            m = 0
        if 1 <= m <= 12:
            excluded.add(m)
    if not excluded or d.month not in excluded:
        return d
    gg = gg_mese_esclus if d.month == mese_esclusione else gg_mese_esclus2
    if not gg:
        gg = gg_mese_esclus or gg_mese_esclus2
    nxt = _add_months(d.replace(day=1), 1)
    while nxt.month in excluded:
        nxt = _add_months(nxt, 1)
    try:
        day = int(gg or 1)
    except (TypeError, ValueError):
        day = 1
    last = monthrange(nxt.year, nxt.month)[1]
    return nxt.replace(day=min(max(day, 1), last))


def _split_importo(totale: Any, n: int) -> list[float | None]:
    if n <= 0 or totale in (None, ""):
        return [None] * max(n, 0)
    try:
        cents = int(round(float(totale) * 100))
    except (TypeError, ValueError):
        return [None] * n
    base, rem = divmod(cents, n)
    out: list[float | None] = []
    for i in range(n):
        piece = base + (rem if i == n - 1 else 0)
        out.append(piece / 100.0)
    return out


def empty_slots(n: int = 1) -> list[dict]:
    n = max(0, int(n or 0))
    return [{"numero": i, "data": None, "importo": None} for i in range(1, n + 1)]


def dates_to_iso_list(dates: list[date | None]) -> list[str]:
    out: list[str] = []
    for value in dates:
        d = _as_date(value)
        if d:
            out.append(d.isoformat())
    return out


def stored_dates(documento) -> list[date]:
    """Date salvate sulla testata (lista JSON, senza padding)."""
    raw = getattr(documento, "scadenze", None) or []
    if not isinstance(raw, list):
        return []
    dates: list[date] = []
    for item in raw:
        if isinstance(item, dict):
            d = _as_date(item.get("data"))
        else:
            d = _as_date(item)
        if d:
            dates.append(d)
    return dates


def slots_from_dates(dates: list[date], *, totale: Any = None) -> list[dict]:
    importi = _split_importo(totale, len(dates))
    slots = empty_slots(len(dates))
    for i, d in enumerate(dates):
        slots[i]["data"] = d
        slots[i]["importo"] = importi[i] if i < len(importi) else None
    return slots


def calcola_scadenze(
    *,
    data_documento: Any,
    condizione=None,
    totale: Any = None,
    max_n: int = MAX_SCADENZE,
) -> list[dict]:
    """Calcola N scadenze da data documento + condizione (N = numero_rate)."""
    n = 1
    prima = 0
    intervallo = 0
    giorno_fisso = 0
    fine_mese = False
    mese_esclusione = None
    mese_esclusione2 = None
    gg_mese_esclus = None
    gg_mese_esclus2 = None
    if condizione is not None:
        try:
            n = int(getattr(condizione, "numero_rate", None) or 1)
        except (TypeError, ValueError):
            n = 1
        try:
            prima = int(getattr(condizione, "prima_rata", None) or 0)
        except (TypeError, ValueError):
            prima = 0
        try:
            intervallo = int(getattr(condizione, "intervallo", None) or 0)
        except (TypeError, ValueError):
            intervallo = 0
        giorno_fisso = getattr(condizione, "giorno_fisso", None)
        fine_mese = bool(getattr(condizione, "fine_mese", False))
        mese_esclusione = getattr(condizione, "mese_esclusione", None)
        mese_esclusione2 = getattr(condizione, "mese_esclusione2", None)
        gg_mese_esclus = getattr(condizione, "gg_mese_esclus", None)
        gg_mese_esclus2 = getattr(condizione, "gg_mese_esclus2", None)

    cap = max(1, int(max_n or MAX_SCADENZE))
    n = max(1, min(n, cap))
    slots = empty_slots(n)
    base = _as_date(data_documento)
    if not base:
        return slots

    current = base + timedelta(days=max(prima, 0))
    current = _apply_giorno_fisso(current, giorno_fisso, fine_mese=fine_mese)
    current = _skip_mesi_esclusione(
        current,
        mese_esclusione,
        mese_esclusione2,
        gg_mese_esclus,
        gg_mese_esclus2,
    )
    dates = [current]
    for _ in range(1, n):
        if intervallo > 0:
            current = dates[-1] + timedelta(days=intervallo)
        else:
            current = _add_months(dates[-1], 1)
        current = _apply_giorno_fisso(current, giorno_fisso, fine_mese=fine_mese)
        current = _skip_mesi_esclusione(
            current,
            mese_esclusione,
            mese_esclusione2,
            gg_mese_esclus,
            gg_mese_esclus2,
        )
        dates.append(current)

    importi = _split_importo(totale, n)
    for i, d in enumerate(dates):
        slots[i]["data"] = d
        slots[i]["importo"] = importi[i] if i < len(importi) else None
    return slots


def load_condizione(codice: str | None):
    code = (codice or "").strip()
    if not code:
        return None
    try:
        from apps.condizioni.models import Condizione

        return Condizione.objects.filter(codice__iexact=code).first()
    except Exception:
        return None


def slots_from_stored(documento, *, totale: Any = None) -> list[dict]:
    dates = stored_dates(documento)
    return slots_from_dates(
        dates,
        totale=totale if totale is not None else getattr(documento, "totale", None),
    )


def scadenze_for_documento(
    documento,
    *,
    codice_pagamento: str | None = None,
    totale: Any = None,
) -> list[dict]:
    """Date salvate, oppure calcolate dalla condizione di pagamento (N rate)."""
    stored = slots_from_stored(documento, totale=totale)
    if stored:
        return stored
    code = (codice_pagamento or getattr(documento, "cod_pagamento", None) or "").strip()
    return calcola_scadenze(
        data_documento=getattr(documento, "data_documento", None),
        condizione=load_condizione(code),
        totale=totale if totale is not None else getattr(documento, "totale", None),
    )


def apply_scadenze_to_instance(documento, slots: list[dict] | None) -> None:
    dates = []
    for slot in slots or []:
        d = _as_date(slot.get("data") if isinstance(slot, dict) else slot)
        if d:
            dates.append(d)
    documento.scadenze = dates_to_iso_list(dates)


def ensure_scadenze(documento, *, codice_pagamento: str | None = None) -> None:
    """Se nessuna data è valorizzata, calcola e scrive le scadenze sulla testata."""
    if stored_dates(documento):
        return
    code = (codice_pagamento or getattr(documento, "cod_pagamento", None) or "").strip()
    if not code:
        return
    slots = scadenze_for_documento(documento, codice_pagamento=code)
    apply_scadenze_to_instance(documento, slots)


def slots_as_json(slots: list[dict]) -> list[dict]:
    out = []
    for slot in slots:
        data = slot.get("data")
        out.append(
            {
                "numero": slot.get("numero"),
                "data": data.isoformat() if hasattr(data, "isoformat") and data else "",
                "importo": slot.get("importo"),
            }
        )
    return out
