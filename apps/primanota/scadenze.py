"""Scadenze Primanota: riusa l'algoritmo documenti (Condizione.numero_rate)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from apps.documenti.scadenze import (
    _as_date,
    calcola_scadenze,
    empty_slots,
    load_condizione,
)
from apps.primanota.models import Primanota

# Maschera 4D: Scad1..Scad10 / ImpScad1..ImpScad10.
PRIMANOTA_MAX_SCADENZE = 10


def _num(value: Any) -> float:
    if value in (None, "", False):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _date_to_dt(value: Any) -> datetime | None:
    d = _as_date(value)
    if d is None:
        return None
    return datetime.combine(d, time.min)


def data_base_scadenze(*, data_doc: Any = None, data_reg: Any = None) -> date | None:
    """Data documento, altrimenti data registrazione."""
    return _as_date(data_doc) or _as_date(data_reg)


def totale_per_scadenze(
    *,
    tipo: Any,
    totale_imponibile: Any = 0,
    totale_iva: Any = 0,
    totale_dare: Any = 0,
    totale_avere: Any = 0,
) -> float | None:
    """IVA: imponibile+IVA. Generico: dare, altrimenti avere."""
    try:
        kind = int(tipo)
    except (TypeError, ValueError):
        kind = None
    if kind in (Primanota.TIPO_IVA, Primanota.TIPO_IVA_AUTOFATTURA):
        tot = _num(totale_imponibile) + _num(totale_iva)
    else:
        tot = _num(totale_dare) or _num(totale_avere)
    return tot if tot else None


def totals_from_riga_formset(formset) -> dict[str, float]:
    tot_imp = tot_iva = tot_dare = tot_avere = 0.0
    deleted = set(getattr(formset, "deleted_forms", None) or [])
    for form in getattr(formset, "forms", None) or []:
        if form in deleted:
            continue
        cleaned = getattr(form, "cleaned_data", None)
        if not isinstance(cleaned, dict) or cleaned.get("DELETE"):
            continue
        tot_imp += _num(cleaned.get("imponibile"))
        tot_iva += _num(cleaned.get("importo_iva"))
        tot_dare += _num(cleaned.get("dare"))
        tot_avere += _num(cleaned.get("avere"))
    return {
        "totale_imponibile": tot_imp,
        "totale_iva": tot_iva,
        "totale_dare": tot_dare,
        "totale_avere": tot_avere,
    }


def compute_scadenze(
    *,
    codice_paga: str | None,
    data_doc: Any = None,
    data_reg: Any = None,
    tipo: Any = None,
    totale_imponibile: Any = 0,
    totale_iva: Any = 0,
    totale_dare: Any = 0,
    totale_avere: Any = 0,
    condizione=None,
) -> list[dict]:
    """Calcola fino a 10 rate da condizione di pagamento. Senza codice → slot vuoti."""
    code = (codice_paga or "").strip()
    if not code:
        return empty_slots(PRIMANOTA_MAX_SCADENZE)
    if condizione is None:
        condizione = load_condizione(code)
    return calcola_scadenze(
        data_documento=data_base_scadenze(data_doc=data_doc, data_reg=data_reg),
        condizione=condizione,
        totale=totale_per_scadenze(
            tipo=tipo,
            totale_imponibile=totale_imponibile,
            totale_iva=totale_iva,
            totale_dare=totale_dare,
            totale_avere=totale_avere,
        ),
        max_n=PRIMANOTA_MAX_SCADENZE,
    )


def apply_scadenze_to_primanota(obj: Primanota, slots: list[dict] | None) -> None:
    rows = list(slots or [])
    for i in range(1, PRIMANOTA_MAX_SCADENZE + 1):
        slot = rows[i - 1] if i <= len(rows) else None
        data = slot.get("data") if isinstance(slot, dict) else None
        importo = slot.get("importo") if isinstance(slot, dict) else None
        setattr(obj, f"scad{i}", _date_to_dt(data))
        setattr(
            obj,
            f"imp_scad{i}",
            float(importo) if importo is not None and importo != "" else None,
        )


def maybe_apply_scadenze(obj: Primanota, formset=None, *, totals: dict | None = None) -> bool:
    """Se scadenze_ins è spento, riempie scad/imp dalla condizione. Non tocca flag RA."""
    if obj.scadenze_ins:
        return False
    amounts = totals if totals is not None else totals_from_riga_formset(formset)
    slots = compute_scadenze(
        codice_paga=obj.codice_paga,
        data_doc=obj.data_doc,
        data_reg=obj.data_reg,
        tipo=obj.tipo,
        totale_imponibile=amounts.get("totale_imponibile"),
        totale_iva=amounts.get("totale_iva"),
        totale_dare=amounts.get("totale_dare"),
        totale_avere=amounts.get("totale_avere"),
    )
    apply_scadenze_to_primanota(obj, slots)
    return True
