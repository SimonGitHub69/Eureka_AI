"""Calcolo giacenza articolo dai movimenti di magazzino (Flag_CD su dettaglio)."""

from __future__ import annotations

from django.db import connection

# Nel mirror 4D: 1, 2, 3 = carico; 4, 5 = scarico.
FLAG_CD_CARICO = (1, 2, 3)
FLAG_CD_SCARICO = (4, 5)
FLAG_CD_GIACENZA = FLAG_CD_CARICO + FLAG_CD_SCARICO


def _flag_cd_in_sql(values: tuple[int, ...]) -> str:
    return ", ".join(str(v) for v in values)


def flag_cd_sign(flag_cd: int | None) -> int:
    """Restituisce +1 carico, -1 scarico, 0 movimento neutro o sconosciuto."""
    if flag_cd in FLAG_CD_CARICO:
        return 1
    if flag_cd in FLAG_CD_SCARICO:
        return -1
    return 0


def _norm_codice(codice: str | None) -> str:
    return (codice or "").strip().upper()


_GIACENZA_SUM = f"""
    COALESCE(SUM(
        COALESCE(pd."Quantita", 0) * CASE
            WHEN pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_CARICO)}) THEN 1
            WHEN pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_SCARICO)}) THEN -1
            ELSE 0
        END
    ), 0)
"""


def giacenza_articolo(codice: str | None) -> float:
    """Giacenza calcolata dalla somma algebrica delle quantità sui movimenti."""
    key = _norm_codice(codice)
    if not key:
        return 0.0
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {_GIACENZA_SUM}
            FROM movimentit_dettaglio pd
            WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = %s
            """,
            [key],
        )
        row = cursor.fetchone()
    return float(row[0] or 0)


def giacenze_per_codici(codici: list[str]) -> dict[str, float]:
    """Mappa codice normalizzato → giacenza per un elenco di articoli."""
    keys = sorted({_norm_codice(c) for c in codici if _norm_codice(c)})
    if not keys:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) AS cod,
                   {_GIACENZA_SUM}
            FROM movimentit_dettaglio pd
            WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = ANY(%s)
            GROUP BY 1
            """,
            [keys],
        )
        return {row[0]: float(row[1] or 0) for row in cursor.fetchall()}


def attach_giacenze_articoli(articoli) -> None:
    """Imposta ``giacenza_quantita`` su ogni articolo (batch query)."""
    articoli = list(articoli)
    if not articoli:
        return
    by_key = giacenze_per_codici([a.codice for a in articoli])
    for articolo in articoli:
        key = _norm_codice(articolo.codice)
        articolo.giacenza_quantita = by_key.get(key, 0.0)
