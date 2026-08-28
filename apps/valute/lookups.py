"""Helper visualizzazione Valute."""

from __future__ import annotations

from datetime import date, datetime

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.valute.models import Valuta, ValutaDet

CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "CHF": "CHF",
    "JPY": "¥",
    "CNY": "¥",
    "CAD": "C$",
    "AUD": "A$",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "PLN": "zł",
    "CZK": "Kč",
    "HUF": "Ft",
    "RON": "lei",
    "TRY": "₺",
    "RUB": "₽",
    "BRL": "R$",
    "INR": "₹",
    "ZAR": "R",
}


def currency_symbol(valuta) -> str:
    for raw in (getattr(valuta, "abbrev", None), getattr(valuta, "codice", None)):
        code = (raw or "").strip().upper()
        if code in CURRENCY_SYMBOLS:
            return CURRENCY_SYMBOLS[code]
    label = (getattr(valuta, "abbrev", None) or getattr(valuta, "codice", None) or "").strip()
    return label[:4] if label else "¤"


def cambio_corrente(valuta, cambi) -> float | None:
    if valuta.cambio is not None:
        return valuta.cambio
    if cambi:
        first = cambi[0]
        value = first.cambio if hasattr(first, "cambio") else first.get("cambio")
        if value is not None:
            return value
    return None


def valuta_choices(current: str | None = None) -> list[tuple[str, str]]:
    """Opzioni select: codice + descrizione, con eventuale valore corrente assente."""
    choices: list[tuple[str, str]] = [("", "—")]
    seen: set[str] = {""}
    try:
        with transaction.atomic():
            for valuta in Valuta.objects.order_by("descrizione", "codice"):
                code = (valuta.codice or "").strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                label = (valuta.descrizione or valuta.abbrev or "").strip()
                if label and label != code:
                    choices.append((code, f"{code} — {label}"))
                else:
                    choices.append((code, code))
    except (ProgrammingError, OperationalError):
        pass
    current_code = (current or "").strip()
    if current_code and current_code not in seen:
        choices.append((current_code, current_code))
    return choices


def resolve_valuta(codice: str | None) -> Valuta | None:
    code = (codice or "").strip()
    if not code:
        return None
    try:
        with transaction.atomic():
            return Valuta.objects.filter(codice__iexact=code).first()
    except (ProgrammingError, OperationalError):
        return None


def _as_date(value):
    from apps.valute.forms import det_value_to_date

    return det_value_to_date(value)


def coerce_cambio_date(value) -> date | None:
    """Data di calendario da Date/DateTime/stringa ISO (YYYY-MM-DD)."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_date(value)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        raw = value.strip()[:10]
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _det_to_info(det) -> dict:
    data = _as_date(getattr(det, "data", None))
    cambio = getattr(det, "cambio", None)
    return {
        "cambio": float(cambio) if cambio is not None else None,
        "data": data,
    }


def _pick_det(dets, alla_data: date | None):
    """Listino vigente: ultimo Valuta_Det con data locale <= alla_data (o il più recente)."""
    for det in dets:
        if alla_data is None:
            return det
        data = _as_date(getattr(det, "data", None))
        if data is not None and data <= alla_data:
            return det
    return None


def cambio_info(codice: str | None, alla_data=None) -> dict:
    """Cambio e data listino dalla valuta (Valuta_Det, altrimenti anagrafica).

    Con `alla_data` usa il listino vigente in quella data (come 4D in Primanota),
    non l'ultimo cambio dello storico.
    """
    result: dict = {"codice": (codice or "").strip(), "cambio": None, "data": None}
    as_of = coerce_cambio_date(alla_data)
    valuta = resolve_valuta(codice)
    if valuta is None:
        return result
    result["codice"] = (valuta.codice or result["codice"]).strip()
    try:
        with transaction.atomic():
            dets = list(
                ValutaDet.objects.filter(valuta=valuta)
                .exclude(cambio=None)
                .order_by("-data", "-id")
            )
    except (ProgrammingError, OperationalError):
        dets = []
    det = _pick_det(dets, as_of)
    if det is not None:
        result.update(_det_to_info(det))
        return result
    if as_of is None and valuta.cambio not in (None, 0, 0.0):
        result["cambio"] = float(valuta.cambio)
    return result


def is_cambio_visible(codice: str | None) -> bool:
    """True se la valuta impostata ha abbreviazione diversa da EUR."""
    code = (codice or "").strip()
    if not code:
        return False
    valuta = resolve_valuta(code)
    abbrev = (getattr(valuta, "abbrev", None) or "").strip() if valuta else ""
    return abbrev.upper() != "EUR"


def valute_cambi_catalog() -> dict[str, dict]:
    """Mappa codice valuta → {cambio, data, history} per la maschera Primanota."""
    catalog: dict[str, dict] = {}
    try:
        with transaction.atomic():
            valute = list(Valuta.objects.all().only("codice", "cambio", "abbrev"))
            history: dict[str, list[dict]] = {}
            for det in (
                ValutaDet.objects.exclude(cambio=None).order_by("valuta_id", "-data", "-id")
            ):
                key = (det.valuta_id or "").strip()
                if not key:
                    continue
                info = _det_to_info(det)
                history.setdefault(key, []).append(
                    {
                        "cambio": info["cambio"],
                        "data": info["data"].isoformat() if info["data"] else "",
                    }
                )
            for valuta in valute:
                code = (valuta.codice or "").strip()
                if not code:
                    continue
                rows = history.get(code) or []
                if rows:
                    latest = rows[0]
                    cambio = latest.get("cambio")
                    data = latest.get("data") or ""
                elif valuta.cambio not in (None, 0, 0.0):
                    cambio = float(valuta.cambio)
                    data = ""
                else:
                    cambio = None
                    data = ""
                catalog[code] = {
                    "cambio": cambio,
                    "data": data,
                    "abbrev": (valuta.abbrev or "").strip(),
                    "history": rows,
                }
    except (ProgrammingError, OperationalError):
        pass
    return catalog
