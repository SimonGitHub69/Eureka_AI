"""Numerazione automatica CodiceDest destinazioni diverse (stile 4D).

Clienti (codice C…): D#####  — es. D00001, D00230, D01209
Fornitori (codice F…): E##### — es. E00001, E00002
"""

from __future__ import annotations

import re

from django.db import connection

from apps.destinazioni.models import tipo_clifor

TABLE = '"DestCliFor"'
COLUMN = '"CodiceDest"'


def compute_next_codice_dest(
    existing_codes,
    prefix: str,
    min_width: int = 5,
) -> str:
    """Prossimo PREFIX + progressivo da una lista di CodiciDest esistenti.

    Considera solo valori che matchano ``PREFIX`` + sole cifre; incrementa il
    massimo. La larghezza è almeno ``min_width`` e almeno quella del max attuale.
    """
    prefix = (prefix or "").upper()
    if not prefix:
        raise ValueError("prefix obbligatorio")

    plen = len(prefix)
    max_n = 0
    max_width = min_width
    for raw in existing_codes or ():
        code = str(raw or "").strip().upper()
        if not code.startswith(prefix):
            continue
        digits = code[plen:]
        if not digits.isdigit():
            continue
        max_n = max(max_n, int(digits))
        max_width = max(max_width, len(digits))

    next_n = max_n + 1
    width = max(max_width, len(str(next_n)), min_width)
    return f"{prefix}{next_n:0{width}d}"


def next_codice_dest(prefix: str, min_width: int = 5) -> str:
    """Ritorna il prossimo CodiceDest PREFIX + progressivo zero-padded."""
    prefix = (prefix or "").upper()
    if prefix not in {"D", "E"}:
        raise ValueError("prefix deve essere D (clienti) o E (fornitori)")

    pat = f"^{re.escape(prefix)}[0-9]+$"
    sql = f"SELECT {COLUMN} FROM {TABLE} WHERE {COLUMN} ~ %s"
    with connection.cursor() as cur:
        cur.execute(sql, [pat])
        rows = [row[0] for row in cur.fetchall() if row and row[0]]

    next_n_base = compute_next_codice_dest(rows, prefix, min_width=min_width)
    # Estrae il progressivo dal candidato e salta collisioni rare (gap / race)
    digits = next_n_base[len(prefix) :]
    next_n = int(digits)
    max_width = max(min_width, len(digits))
    while True:
        width = max(max_width, len(str(next_n)), min_width)
        candidate = f"{prefix}{next_n:0{width}d}"
        with connection.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {TABLE} WHERE {COLUMN} = %s LIMIT 1",
                [candidate],
            )
            if cur.fetchone() is None:
                return candidate
        next_n += 1


def next_codice_dest_cliente() -> str:
    return next_codice_dest("D", min_width=5)


def next_codice_dest_fornitore() -> str:
    return next_codice_dest("E", min_width=5)


def next_codice_dest_for_anagrafica(codice: str | None) -> str:
    """Prossimo CodiceDest in base al tipo Cli/For (C→D#####, F→E#####)."""
    tipo = tipo_clifor(codice)
    if tipo == "C":
        return next_codice_dest_cliente()
    if tipo == "F":
        return next_codice_dest_fornitore()
    return ""
