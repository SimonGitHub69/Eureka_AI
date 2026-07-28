from __future__ import annotations

from django.db import connection

# Selezione operatori: helper condivisi (filtro OperatoreDisattivo).
from apps.operatori.lookup import list_operatori_attivi, lookup_operatore  # noqa: F401


def _first_nonempty(*values) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def lookup_pezzo(codice: str) -> dict:
    """
    Dato il codice pezzo (Articoli.Codice), ricava:
    - Cod. Art. Cliente ← CodiceAlternativo1
    - Descrizione componente ← Descrizione
    """
    codice = (codice or "").strip()
    empty = {
        "ok": False,
        "codice_pezzo": codice,
        "cod_art_cliente": "",
        "descrizione_componente": "",
        "tempo_distinta": 0,
        "message": "Codice pezzo non trovato in Articoli.",
    }
    if not codice:
        empty["message"] = "Inserisci un codice pezzo."
        return empty

    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    "Codice",
                    "Descrizione",
                    "DescrExpress",
                    "CodiceAlternativo1",
                    "Nomenclatura"
                FROM articoli
                WHERE TRIM("Codice") = %s
                LIMIT 1
                """,
                [codice],
            )
            row = cur.fetchone()
            if not row:
                return empty

            cols = [c[0] for c in cur.description]
            data = dict(zip(cols, row))

            descrizione = _first_nonempty(
                data.get("Descrizione"),
                data.get("DescrExpress"),
                data.get("Nomenclatura"),
            )
            cod_art_cliente = _first_nonempty(data.get("CodiceAlternativo1"))

            return {
                "ok": True,
                "codice_pezzo": codice,
                "cod_art_cliente": cod_art_cliente,
                "descrizione_componente": descrizione,
                "tempo_distinta": 0,
                "articolo_codice": data.get("Codice") or "",
                "message": "Dati pezzo caricati da Articoli.",
            }
    except Exception as exc:
        empty["message"] = f"Errore lookup pezzo: {exc}"
        return empty
