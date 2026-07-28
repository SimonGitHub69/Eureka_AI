from __future__ import annotations

from django.db import connection

# Campo 4D mirror: TRUE = operatore disattivato (non selezionabile nelle UI).
DISATTIVO_COLUMN = "OperatoreDisattivo"


def _attivo_sql(alias: str = "") -> str:
    prefix = f'{alias}.' if alias else ""
    return f'COALESCE({prefix}"{DISATTIVO_COLUMN}", FALSE) IS FALSE'


def lookup_operatore(codice: str) -> dict | None:
    codice = (codice or "").strip()
    if not codice:
        return None
    try:
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    "Codice",
                    COALESCE(NULLIF(TRIM("Nome"), ''), "Codice") AS nome,
                    COALESCE(
                        NULLIF(TRIM("Matricola_Timbratore"), ''),
                        NULLIF(TRIM("NumBadge"), ''),
                        "Codice"
                    ) AS matricola,
                    COALESCE(NULLIF(TRIM("Reparto"), ''), '') AS reparto,
                    COALESCE("{DISATTIVO_COLUMN}", FALSE) AS disattivo
                FROM operatori
                WHERE TRIM("Codice") = %s
                LIMIT 1
                """,
                [codice],
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "codice": row[0],
                "nome": row[1],
                "matricola": row[2],
                "reparto": row[3],
                "disattivo": bool(row[4]),
            }
    except Exception:
        return None


def list_operatori_attivi() -> list[dict]:
    """Elenco operatori selezionabili (esclude OperatoreDisattivo = true)."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    "Codice",
                    COALESCE(NULLIF(TRIM("Nome"), ''), "Codice") AS nome,
                    COALESCE(
                        NULLIF(TRIM("Matricola_Timbratore"), ''),
                        NULLIF(TRIM("NumBadge"), ''),
                        "Codice"
                    ) AS matricola,
                    COALESCE(NULLIF(TRIM("NomeBreve"), ''), '') AS nome_breve
                FROM operatori
                WHERE {_attivo_sql()}
                ORDER BY nome, "Codice"
                """
            )
            return [
                {
                    "codice": r[0],
                    "nome": r[1],
                    "matricola": r[2],
                    "nome_breve": r[3],
                }
                for r in cur.fetchall()
            ]
    except Exception:
        return []
