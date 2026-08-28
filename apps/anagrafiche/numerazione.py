"""Numerazione automatica codici anagrafiche (stile 4D)."""

from __future__ import annotations

import re

from django.db import connection


def next_codice_prefisso(table: str, prefix: str = "", min_width: int = 4) -> str:
    """Ritorna il prossimo codice PREFIX + progressivo zero-padded.

    Legge i codici esistenti che matchano ``PREFIX`` + sole cifre e incrementa
    il massimo. La larghezza è almeno ``min_width`` e almeno quella del max attuale.
    ``prefix`` può essere vuoto (es. agenti numerici).
    """
    prefix = (prefix or "").upper()

    if prefix:
        pat = f"^{re.escape(prefix)}[0-9]+$"
    else:
        pat = r"^[0-9]+$"
    sql = f'SELECT "Codice" FROM {table} WHERE "Codice" ~ %s'
    with connection.cursor() as cur:
        cur.execute(sql, [pat])
        rows = [row[0] for row in cur.fetchall() if row and row[0]]

    max_n = 0
    max_width = min_width
    plen = len(prefix)
    for raw in rows:
        code = str(raw).strip()
        digits = code[plen:]
        if not digits.isdigit():
            continue
        max_n = max(max_n, int(digits))
        max_width = max(max_width, len(digits))

    next_n = max_n + 1
    # Evita collisioni rare (gap / race): salta finché libero
    while True:
        width = max(max_width, len(str(next_n)), min_width)
        candidate = f"{prefix}{next_n:0{width}d}"
        with connection.cursor() as cur:
            cur.execute(f'SELECT 1 FROM {table} WHERE "Codice" = %s LIMIT 1', [candidate])
            if cur.fetchone() is None:
                return candidate
        next_n += 1


def next_codice_cliente() -> str:
    return next_codice_prefisso("clienti", "C", min_width=5)


def next_codice_fornitore() -> str:
    return next_codice_prefisso("fornitori", "F", min_width=4)


def next_codice_agente() -> str:
    return next_codice_prefisso("agenti", "", min_width=2)
