"""Calcolo importo IVA righe primanota da AliquoteIva."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.documenti.castelletto import resolve_aliquota


def calc_importo_iva(imponibile, codice_iva) -> float | None:
    """Importo IVA = imponibile × Aliquota.percentuale / 100 (tabella aliquote)."""
    code = (codice_iva or "").strip()
    if not code or imponibile in (None, ""):
        return None
    try:
        base = Decimal(str(imponibile).replace(",", "."))
    except Exception:
        return None
    info = resolve_aliquota(code)
    iva = base * info.percentuale / Decimal("100")
    return float(iva.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
