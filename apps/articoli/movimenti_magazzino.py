"""Lista movimenti di magazzino per articolo (esistenza / carico / scarico)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.db import connection

from apps.articoli.giacenza import (
    FLAG_CD_CARICO,
    FLAG_CD_GIACENZA,
    FLAG_CD_SCARICO,
    _flag_cd_in_sql,
    _norm_codice,
    flag_cd_sign,
    giacenza_articolo,
)
from apps.depositi.lookups import depositi_by_codes
from apps.movimenti.lookups import (
    causali_magazzino_by_codes,
    clienti_ragione_sociale_by_codes,
    fornitori_ragione_sociale_by_codes,
)


@dataclass
class MovimentoArticoloRiga:
    id_testa: int | None
    num_registraz: int | None
    data_registraz: date | None
    causale: str
    causale_descrizione: str
    dep_entrata: str
    dep_uscita: str
    cli_for_codice: str
    cli_for_ragione: str
    cli_for_kind: str
    num_doc: str
    data_doc: date | None
    carico: float
    scarico: float
    valore: float
    giacenza: float = 0.0
    is_totale: bool = False
    is_giacenza_precedente: bool = False
    dep_entrata_link: str = ""
    dep_uscita_link: str = ""


@dataclass
class MovimentiArticoloResult:
    codice: str
    esistenza_attuale: float
    righe: list[MovimentoArticoloRiga] = field(default_factory=list)
    totale_carico: float = 0.0
    totale_scarico: float = 0.0
    data_da: date | None = None
    data_a: date | None = None
    giacenza_precedente: float = 0.0
    filtro_attivo: bool = False


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _text(value) -> str:
    return (value or "").strip()


_GIACENZA_SIGN_EXPR = f"""
    COALESCE(pd."Quantita", 0) * CASE
        WHEN pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_CARICO)}) THEN 1
        WHEN pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_SCARICO)}) THEN -1
        ELSE 0
    END
"""


def _giacenza_precedente(codice: str, before: date) -> float:
    key = _norm_codice(codice)
    if not key:
        return 0.0
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COALESCE(SUM({_GIACENZA_SIGN_EXPR}), 0)
            FROM movimentit_dettaglio pd
            JOIN movimentit p ON p."ID_Testa" = pd."id_added_by_converter"
            WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = %s
              AND pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_GIACENZA)})
              AND p."DataRegistraz"::date < %s
            """,
            [key, before],
        )
        row = cursor.fetchone()
    return float(row[0] or 0)


def ultime_date_movimenti(codice: str | None) -> tuple[date | None, date | None]:
    """Restituisce (ultima data carico, ultima data scarico) dai movimenti dettaglio."""
    key = _norm_codice(codice)
    if not key:
        return None, None
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                MAX(p."DataRegistraz") FILTER (
                    WHERE pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_CARICO)})
                ),
                MAX(p."DataRegistraz") FILTER (
                    WHERE pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_SCARICO)})
                )
            FROM movimentit_dettaglio pd
            JOIN movimentit p ON p."ID_Testa" = pd."id_added_by_converter"
            WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = %s
            """,
            [key],
        )
        row = cursor.fetchone()
    if not row:
        return None, None
    return _as_date(row[0]), _as_date(row[1])


def _fetch_rows(
    codice: str,
    *,
    data_da: date | None = None,
    data_a: date | None = None,
) -> list[dict]:
    key = _norm_codice(codice)
    if not key:
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                p."ID_Testa",
                p."NumRegistraz",
                p."DataRegistraz",
                p."Causale",
                COALESCE(NULLIF(TRIM(pd."DepEnt"), ''), NULLIF(TRIM(p."DepEntrata"), '')) AS dep_ent,
                COALESCE(NULLIF(TRIM(pd."DepUsc"), ''), NULLIF(TRIM(p."DepUscita"), '')) AS dep_usc,
                p."Cliente",
                p."Fornitore",
                p."NumDoc",
                p."DataDoc",
                pd."Quantita",
                pd."Flag_CD",
                pd."ValoreTotale"
            FROM movimentit_dettaglio pd
            JOIN movimentit p ON p."ID_Testa" = pd."id_added_by_converter"
            WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = %s
              AND pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_GIACENZA)})
              AND (%s IS NULL OR p."DataRegistraz"::date >= %s)
              AND (%s IS NULL OR p."DataRegistraz"::date <= %s)
            ORDER BY
                p."DataRegistraz" ASC NULLS LAST,
                p."NumRegistraz" ASC NULLS LAST,
                pd."Pos" ASC NULLS LAST,
                pd."ID" ASC
            """,
            [key, data_da, data_da, data_a, data_a],
        )
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _build_riga(
    row: dict,
    *,
    causali,
    clienti,
    fornitori,
    magazzini,
) -> tuple[MovimentoArticoloRiga, float, float]:
    qty = float(row.get("Quantita") or 0)
    sign = flag_cd_sign(row.get("Flag_CD"))
    carico = qty if sign > 0 else 0.0
    scarico = qty if sign < 0 else 0.0

    cliente = _text(row.get("Cliente"))
    fornitore = _text(row.get("Fornitore"))
    if fornitore:
        cli_for_codice = fornitore
        cli_for_kind = "F"
        cli_for_ragione = fornitori.get(fornitore.upper(), "")
    else:
        cli_for_codice = cliente
        cli_for_kind = "C" if cliente else ""
        cli_for_ragione = clienti.get(cliente.upper(), "")

    causale = _text(row.get("Causale"))
    dep_entrata = _text(row.get("dep_ent"))
    dep_uscita = _text(row.get("dep_usc"))
    riga = MovimentoArticoloRiga(
        id_testa=row.get("ID_Testa"),
        num_registraz=row.get("NumRegistraz"),
        data_registraz=_as_date(row.get("DataRegistraz")),
        causale=causale,
        causale_descrizione=causali.get(causale.upper(), ""),
        dep_entrata=dep_entrata,
        dep_uscita=dep_uscita,
        dep_entrata_link=magazzini.get(dep_entrata.upper(), ""),
        dep_uscita_link=magazzini.get(dep_uscita.upper(), ""),
        cli_for_codice=cli_for_codice,
        cli_for_ragione=cli_for_ragione,
        cli_for_kind=cli_for_kind,
        num_doc=_text(row.get("NumDoc")),
        data_doc=_as_date(row.get("DataDoc")),
        carico=carico,
        scarico=scarico,
        valore=float(row.get("ValoreTotale") or 0),
    )
    return riga, carico, scarico


def movimenti_articolo(
    codice: str | None,
    *,
    data_da: date | None = None,
    data_a: date | None = None,
) -> MovimentiArticoloResult:
    """Movimenti cronologici con carico/scarico e giacenza progressiva."""
    key = _norm_codice(codice)
    filtro_attivo = data_da is not None or data_a is not None
    esistenza = giacenza_articolo(key)

    giacenza_prec = 0.0
    if filtro_attivo and data_da is not None:
        giacenza_prec = _giacenza_precedente(key, data_da)

    raw_rows = _fetch_rows(key, data_da=data_da, data_a=data_a)
    if not raw_rows and not (filtro_attivo and giacenza_prec):
        return MovimentiArticoloResult(
            codice=key,
            esistenza_attuale=esistenza,
            data_da=data_da,
            data_a=data_a,
            giacenza_precedente=giacenza_prec,
            filtro_attivo=filtro_attivo,
        )

    causali = causali_magazzino_by_codes(r.get("Causale") for r in raw_rows)
    clienti = clienti_ragione_sociale_by_codes(r.get("Cliente") for r in raw_rows)
    fornitori = fornitori_ragione_sociale_by_codes(r.get("Fornitore") for r in raw_rows)
    magazzini = depositi_by_codes(
        code
        for r in raw_rows
        for code in (r.get("dep_ent"), r.get("dep_usc"))
    )

    righe: list[MovimentoArticoloRiga] = []
    saldo = giacenza_prec
    tot_carico = 0.0
    tot_scarico = 0.0

    if filtro_attivo and data_da is not None:
        data_prec = data_da - timedelta(days=1)
        righe.append(
            MovimentoArticoloRiga(
                id_testa=None,
                num_registraz=None,
                data_registraz=data_prec,
                causale="",
                causale_descrizione="Giacenza precedente",
                dep_entrata="",
                dep_uscita="",
                cli_for_codice="",
                cli_for_ragione="",
                cli_for_kind="",
                num_doc="",
                data_doc=None,
                carico=0.0,
                scarico=0.0,
                valore=0.0,
                giacenza=giacenza_prec,
                is_giacenza_precedente=True,
            )
        )

    for row in raw_rows:
        riga, carico, scarico = _build_riga(
            row,
            causali=causali,
            clienti=clienti,
            fornitori=fornitori,
            magazzini=magazzini,
        )
        saldo += carico - scarico
        tot_carico += carico
        tot_scarico += scarico
        riga.giacenza = saldo
        righe.append(riga)

    if raw_rows or (filtro_attivo and giacenza_prec):
        righe.append(
            MovimentoArticoloRiga(
                id_testa=None,
                num_registraz=None,
                data_registraz=data_a if filtro_attivo else None,
                causale="",
                causale_descrizione="",
                dep_entrata="",
                dep_uscita="",
                cli_for_codice="",
                cli_for_ragione="",
                cli_for_kind="",
                num_doc="",
                data_doc=None,
                carico=tot_carico,
                scarico=tot_scarico,
                valore=0.0,
                giacenza=saldo,
                is_totale=True,
            )
        )

    return MovimentiArticoloResult(
        codice=key,
        esistenza_attuale=esistenza,
        righe=righe,
        totale_carico=tot_carico,
        totale_scarico=tot_scarico,
        data_da=data_da,
        data_a=data_a,
        giacenza_precedente=giacenza_prec,
        filtro_attivo=filtro_attivo,
    )


MOVIMENTI_ARTICOLO_PRINT_COLUMNS = (
    {"field": "num_registraz", "label": "Rif", "align": "end"},
    {"field": "data_registraz", "label": "Data", "date": True},
    {"label": "Causale", "value": lambda r: (
        "Totali"
        if r.is_totale
        else (r.causale_descrizione or "Giacenza precedente")
        if r.is_giacenza_precedente
        else (r.causale_descrizione or r.causale or "—")
    )},
    {"field": "dep_entrata", "label": "Dep. E."},
    {"field": "dep_uscita", "label": "Dep. U."},
    {"field": "cli_for_codice", "label": "Cli/For"},
    {"field": "cli_for_ragione", "label": "Rag. soc. Cli/For"},
    {"field": "num_doc", "label": "N. doc."},
    {"field": "data_doc", "label": "Data doc.", "date": True},
    {
        "label": "Carico",
        "value": lambda r: _fmt_qty(r.carico),
        "align": "end",
    },
    {
        "label": "Scarico",
        "value": lambda r: _fmt_qty(r.scarico),
        "align": "end",
    },
    {
        "label": "Valore",
        "value": lambda r: _fmt_euro(r.valore),
        "align": "end",
    },
    {
        "label": "Giacenza",
        "value": lambda r: _fmt_qty(r.giacenza)
        if r.giacenza or r.is_totale or r.is_giacenza_precedente
        else "—",
        "align": "end",
    },
)


def _fmt_qty(value: float) -> str:
    from apps.core.templatetags.format_tags import intit

    if not value:
        return "—"
    return intit(value)


def _fmt_euro(value: float) -> str:
    from apps.core.templatetags.format_tags import euro

    if not value:
        return "—"
    return euro(value)
