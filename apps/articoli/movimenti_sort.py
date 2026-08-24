"""Ordinamento colonne movimenti magazzino sulla scheda articolo."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from apps.articoli.movimenti_magazzino import MovimentoArticoloRiga

MOVIMENTI_ARTICOLO_SORT_FIELDS = (
    "num_registraz",
    "data_registraz",
    "causale",
    "dep_entrata",
    "dep_uscita",
    "cli_for_codice",
    "cli_for_ragione",
    "num_doc",
    "data_doc",
    "carico",
    "scarico",
    "prezzo_lordo",
    "prezzo_unitario",
    "giacenza",
)


def _text_key(value: str | None) -> tuple[int, str]:
    text = (value or "").strip().casefold()
    return (0 if text else 1, text)


def _date_key(value: date | None) -> tuple[int, date]:
    if value is None:
        return (1, date.min)
    return (0, value)


def _num_key(value: float | int | None) -> tuple[int, float]:
    if value is None:
        return (1, 0.0)
    return (0, float(value))


def _int_key(value: int | None) -> tuple[int, int]:
    if value is None:
        return (1, 0)
    return (0, int(value))


_SORT_KEYS: dict[str, Callable[[MovimentoArticoloRiga], Any]] = {
    "num_registraz": lambda r: _int_key(r.num_registraz),
    "data_registraz": lambda r: _date_key(r.data_registraz),
    "causale": lambda r: _text_key(r.causale_descrizione or r.causale),
    "dep_entrata": lambda r: _text_key(r.dep_entrata),
    "dep_uscita": lambda r: _text_key(r.dep_uscita),
    "cli_for_codice": lambda r: _text_key(r.cli_for_codice),
    "cli_for_ragione": lambda r: _text_key(r.cli_for_ragione),
    "num_doc": lambda r: _text_key(r.num_doc),
    "data_doc": lambda r: _date_key(r.data_doc),
    "carico": lambda r: _num_key(r.carico),
    "scarico": lambda r: _num_key(r.scarico),
    "prezzo_lordo": lambda r: _num_key(r.prezzo_lordo),
    "prezzo_unitario": lambda r: _num_key(r.prezzo_unitario),
    "giacenza": lambda r: _num_key(r.giacenza),
}


def sort_movimenti_righe(
    righe: list[MovimentoArticoloRiga],
    sort: str | None,
    direction: str = "asc",
) -> list[MovimentoArticoloRiga]:
    """Ordina le righe movimento; giacenza precedente e totali restano fisse."""
    if not righe or not sort or sort not in _SORT_KEYS:
        return righe

    key_fn = _SORT_KEYS[sort]
    reverse = direction == "desc"
    prec = [r for r in righe if r.is_giacenza_precedente]
    totale = [r for r in righe if r.is_totale]
    data = [r for r in righe if not r.is_giacenza_precedente and not r.is_totale]

    data.sort(key=key_fn, reverse=reverse)
    return prec + data + totale
