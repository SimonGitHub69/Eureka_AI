"""Decimali prezzo unitario (Parametri programma)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PREZZO_DECIMALI_DEFAULT = 3
PREZZO_DECIMALI_MIN = 2
PREZZO_DECIMALI_MAX = 6


def clamp_prezzo_decimali(value) -> int:
    if value in (None, ""):
        return PREZZO_DECIMALI_DEFAULT
    try:
        number = int(value)
    except (TypeError, ValueError):
        return PREZZO_DECIMALI_DEFAULT
    return max(PREZZO_DECIMALI_MIN, min(PREZZO_DECIMALI_MAX, number))


def get_prezzo_decimali() -> int:
    """Numero massimo di decimali per prezzi unitari a video."""
    try:
        from apps.core.models import ConfigurazioneProgramma

        value = ConfigurazioneProgramma.get_solo().prezzo_decimali
    except Exception:
        value = PREZZO_DECIMALI_DEFAULT
    return clamp_prezzo_decimali(value)


def get_prezzo_decimali_stampa() -> int:
    """Numero massimo di decimali per prezzi unitari nelle stampe."""
    try:
        from apps.core.models import ConfigurazioneProgramma

        value = ConfigurazioneProgramma.get_solo().prezzo_decimali_stampa
    except Exception:
        value = PREZZO_DECIMALI_DEFAULT
    return clamp_prezzo_decimali(value)


def prezzo_input_step() -> str:
    """Attributo HTML ``step`` per input prezzo unitario."""
    dec = get_prezzo_decimali()
    if dec <= 0:
        return "1"
    return str(Decimal("1").scaleb(-dec))


def round_prezzo(value) -> float:
    """Arrotonda un prezzo unitario a video (half-up commerciale)."""
    return _round_prezzo_with_decimals(value, get_prezzo_decimali())


def round_prezzo_stampa(value) -> float:
    """Arrotonda un prezzo unitario per le stampe (half-up commerciale)."""
    return _round_prezzo_with_decimals(value, get_prezzo_decimali_stampa())


def _round_prezzo_with_decimals(value, dec: int) -> float:
    if value in (None, ""):
        return 0.0
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0
    if not number.is_finite():
        return 0.0
    quant = Decimal("1").scaleb(-dec)
    return float(number.quantize(quant, rounding=ROUND_HALF_UP))
