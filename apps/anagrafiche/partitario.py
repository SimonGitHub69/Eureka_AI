"""Partitario (mastrino) clienti/fornitori/sottoconti PDC da Primanota.

Tipi Primanota inclusi: 1 Generico, 2 IVA, 3 Corrispettivi, 4 Iva con Autofattura.

Allineato alla maschera 4D Partitario (Rif, Dt Reg/Comp, Causale, Descrizione,
Pagamento, C/Part, Prot, N.Doc, Dt Doc, Dare, Avere, Saldo).

Sul partitario PDC i Corrispettivi (tipo 3) con CassaCorrispettivi sulla causale
pari al sottoconto vengono conteggiati anche se il conto cassa non compare nei
dettagli (in 4D la cassa è solo metadato di maschera, non scritta su ContoDare/Avere).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from django.db import connection
from django.utils import timezone

Kind = Literal["C", "F", "P"]


@dataclass
class PartitarioRiga:
    data_reg: date | None
    data_comp: date | None
    numero_reg: int | None
    id_testa: int | None
    tipo: int | None
    causale: str
    causale_descrizione: str
    descrizione: str
    pagamento: str
    pagamento_descrizione: str
    numero_doc: str
    numero_prot: str
    data_doc: date | None
    contro_codice: str
    contro_descrizione: str
    dare: float
    avere: float
    saldo: float = 0.0
    is_saldo_precedente: bool = False
    is_totale: bool = False


@dataclass
class PartitarioResult:
    codice: str
    kind: Kind
    data_da: date
    data_a: date
    saldo_precedente: float
    righe: list[PartitarioRiga] = field(default_factory=list)
    totale_dare: float = 0.0
    totale_avere: float = 0.0
    saldo_finale: float = 0.0


def default_periodo(oggi: date | None = None) -> tuple[date, date]:
    today = oggi or timezone.localdate()
    return date(today.year, 1, 1), today


def _norm_code(value: str | None) -> str:
    return (value or "").strip()


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    return getattr(value, "date", lambda: value)()


def _f(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


_MATCHED_CTE = """
    WITH matched AS (
        SELECT
            p."ID" AS id_testa,
            p."NumeroReg" AS numero_reg,
            p."DataReg"::date AS data_reg,
            p."Tipo" AS tipo,
            TRIM(BOTH FROM COALESCE(p."Causale", '')) AS causale,
            TRIM(BOTH FROM COALESCE(p."CodicePartita", '')) AS codice_partita,
            TRIM(BOTH FROM COALESCE(p."CodicePaga", '')) AS codice_paga,
            TRIM(BOTH FROM COALESCE(p."NumeroDoc", '')) AS numero_doc,
            p."DataDoc"::date AS data_doc,
            p."NumeroProt" AS numero_prot,
            TRIM(BOTH FROM COALESCE(p."AlfaProt", '')) AS alfa_prot,
            pd."ID" AS id_riga,
            pd."Pos" AS pos,
            TRIM(BOTH FROM COALESCE(pd."ContoDare", '')) AS conto_dare,
            COALESCE(pd."Dare", 0) AS dare,
            TRIM(BOTH FROM COALESCE(pd."ContoAvere", '')) AS conto_avere,
            COALESCE(pd."Avere_Imponibile", 0) AS avere,
            COALESCE(pd."ImportoIva", 0) AS importo_iva,
            TRIM(BOTH FROM COALESCE(pd."Descrizione", '')) AS descrizione,
            UPPER(TRIM(BOTH FROM COALESCE(p."CodicePartita", ''))) = UPPER(%s) AS match_partita,
            UPPER(TRIM(BOTH FROM COALESCE(pd."ContoDare", ''))) = UPPER(%s) AS match_dare,
            UPPER(TRIM(BOTH FROM COALESCE(pd."ContoAvere", ''))) = UPPER(%s) AS match_avere
        FROM primanota p
        JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter"
        WHERE p."Tipo" IN (1, 2, 3, 4)
          AND pd."dummy" IS NOT TRUE
          AND (
            UPPER(TRIM(BOTH FROM COALESCE(p."CodicePartita", ''))) = UPPER(%s)
            OR UPPER(TRIM(BOTH FROM COALESCE(pd."ContoDare", ''))) = UPPER(%s)
            OR UPPER(TRIM(BOTH FROM COALESCE(pd."ContoAvere", ''))) = UPPER(%s)
          )
    )
"""


def _fetch_movimenti_clifor(codice: str):
    """
    IVA / Autofattura con CodicePartita + Generico / Corrispettivi con
    ContoDare/ContoAvere = codice (Primanota Tipo 1–4).

    IVA (2) e Iva con Autofattura (4): una riga per registrazione; importi
    positivi (avere+IVA) e negativi (abbuoni) come in 4D.
    Generico (1) e Corrispettivi (3): una riga per ogni dettaglio coinvolto.
    """
    code = _norm_code(codice)
    if not code:
        return []

    sql = (
        _MATCHED_CTE
        + """
    , iva_agg AS (
        SELECT
            id_testa,
            numero_reg,
            data_reg,
            tipo,
            causale,
            codice_partita,
            codice_paga,
            numero_doc,
            data_doc,
            numero_prot,
            alfa_prot,
            SUM(
                CASE WHEN (avere + importo_iva) > 0
                     THEN avere + importo_iva ELSE 0 END
            ) AS importo_pos,
            SUM(
                CASE WHEN (avere + importo_iva) < 0
                     THEN -(avere + importo_iva) ELSE 0 END
            ) AS importo_neg,
            (ARRAY_AGG(conto_avere ORDER BY pos, id_riga)
                FILTER (
                    WHERE conto_avere <> ''
                      AND (avere + importo_iva) > 0
                ))[1] AS contro,
            COALESCE(
                (ARRAY_AGG(descrizione ORDER BY pos, id_riga)
                    FILTER (WHERE descrizione <> ''))[1],
                NULLIF(numero_doc, ''),
                ''
            ) AS descrizione
        FROM matched
        WHERE tipo IN (2, 4) AND match_partita
        GROUP BY
            id_testa, numero_reg, data_reg, tipo, causale, codice_partita,
            codice_paga, numero_doc, data_doc, numero_prot, alfa_prot
    ),
    gen_rows AS (
        SELECT
            id_testa,
            numero_reg,
            data_reg,
            tipo,
            causale,
            codice_partita,
            codice_paga,
            numero_doc,
            data_doc,
            numero_prot,
            alfa_prot,
            pos,
            id_riga,
            match_dare,
            match_avere,
            dare,
            avere,
            conto_dare,
            conto_avere,
            descrizione
        FROM matched
        WHERE tipo IN (1, 3) AND (match_dare OR match_avere)
    )
    SELECT
        'iva' AS fonte,
        id_testa,
        numero_reg,
        data_reg,
        tipo,
        causale,
        codice_paga,
        numero_doc,
        data_doc,
        numero_prot,
        alfa_prot,
        importo_pos AS dare_amt,
        importo_neg AS avere_amt,
        contro AS contro_codice,
        descrizione,
        0 AS pos,
        0 AS id_riga
    FROM iva_agg
    UNION ALL
    SELECT
        'gen' AS fonte,
        id_testa,
        numero_reg,
        data_reg,
        tipo,
        causale,
        codice_paga,
        numero_doc,
        data_doc,
        numero_prot,
        alfa_prot,
        CASE WHEN match_dare THEN dare ELSE 0 END AS dare_amt,
        CASE
            WHEN match_avere THEN
                CASE WHEN avere <> 0 THEN avere ELSE dare END
            ELSE 0
        END AS avere_amt,
        CASE
            WHEN match_dare THEN conto_avere
            WHEN match_avere THEN conto_dare
            ELSE ''
        END AS contro_codice,
        descrizione,
        pos,
        id_riga
    FROM gen_rows
    ORDER BY data_reg NULLS LAST, numero_reg NULLS LAST, pos, id_riga
    """
    )
    params = [code, code, code, code, code, code]
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_movimenti_pdc_dettaglio(codice: str):
    """
    Sottoconto PDC: Primanota Tipo 1–4 dove ContoDare o ContoAvere = codice.

    Una riga per ogni dettaglio che coinvolge il sottoconto.
    Su IVA / Autofattura (2, 4) l'importo del conto è l'imponibile (Dare/Avere)
    se presente, altrimenti solo ImportoIva (riga conto IVA) — come mastrino 4D.
    Contro/partita: CodicePartita se valorizzato, altrimenti conto opposto.
    """
    code = _norm_code(codice)
    if not code:
        return []

    sql = (
        _MATCHED_CTE
        + """
    , detail_rows AS (
        SELECT
            id_testa,
            numero_reg,
            data_reg,
            tipo,
            causale,
            codice_partita,
            codice_paga,
            numero_doc,
            data_doc,
            numero_prot,
            alfa_prot,
            pos,
            id_riga,
            match_dare,
            match_avere,
            dare,
            avere,
            importo_iva,
            conto_dare,
            conto_avere,
            descrizione
        FROM matched
        WHERE tipo IN (1, 2, 3, 4) AND (match_dare OR match_avere)
    )
    SELECT
        CASE WHEN tipo IN (2, 4) THEN 'iva' ELSE 'gen' END AS fonte,
        id_testa,
        numero_reg,
        data_reg,
        tipo,
        causale,
        codice_paga,
        numero_doc,
        data_doc,
        numero_prot,
        alfa_prot,
        CASE
            WHEN match_dare THEN
                CASE
                    WHEN tipo IN (2, 4) THEN
                        CASE WHEN dare <> 0 THEN dare ELSE importo_iva END
                    ELSE dare
                END
            ELSE 0
        END AS dare_amt,
        CASE
            WHEN match_avere THEN
                CASE
                    WHEN tipo IN (2, 4) THEN
                        CASE WHEN avere <> 0 THEN avere ELSE importo_iva END
                    WHEN avere <> 0 THEN avere
                    ELSE dare
                END
            ELSE 0
        END AS avere_amt,
        CASE
            WHEN NULLIF(codice_partita, '') IS NOT NULL THEN codice_partita
            WHEN match_dare THEN conto_avere
            WHEN match_avere THEN conto_dare
            ELSE ''
        END AS contro_codice,
        COALESCE(NULLIF(descrizione, ''), NULLIF(numero_doc, ''), '') AS descrizione,
        pos,
        id_riga
    FROM detail_rows
    ORDER BY data_reg NULLS LAST, numero_reg NULLS LAST, pos, id_riga
    """
    )
    params = [code, code, code, code, code, code]
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_movimenti_pdc_cassa_corrispettivi(codice: str):
    """
    Corrispettivi (tipo 3) la cui causale ha CassaCorrispettivi = sottoconto.

    In 4D/Eureka la cassa non viene scritta su ContoDare/ContoAvere dei dettagli
    (solo ricavi/IVA in Avere). Per il partitario PDC si genera una riga per
    registrazione in Dare (= solo imponibile, come totale documento Corrispettivi),
    escludendo le registrazioni che già muovono il sottoconto sul dettaglio
    (no doppio conteggio).
    """
    code = _norm_code(codice)
    if not code:
        return []

    sql = """
    SELECT
        'gen' AS fonte,
        p."ID" AS id_testa,
        p."NumeroReg" AS numero_reg,
        p."DataReg"::date AS data_reg,
        p."Tipo" AS tipo,
        TRIM(BOTH FROM COALESCE(p."Causale", '')) AS causale,
        TRIM(BOTH FROM COALESCE(p."CodicePaga", '')) AS codice_paga,
        TRIM(BOTH FROM COALESCE(p."NumeroDoc", '')) AS numero_doc,
        p."DataDoc"::date AS data_doc,
        p."NumeroProt" AS numero_prot,
        TRIM(BOTH FROM COALESCE(p."AlfaProt", '')) AS alfa_prot,
        CASE
            WHEN SUM(COALESCE(pd."Avere_Imponibile", 0)) > 0
            THEN SUM(COALESCE(pd."Avere_Imponibile", 0))
            ELSE 0
        END AS dare_amt,
        CASE
            WHEN SUM(COALESCE(pd."Avere_Imponibile", 0)) < 0
            THEN -SUM(COALESCE(pd."Avere_Imponibile", 0))
            ELSE 0
        END AS avere_amt,
        COALESCE(
            (ARRAY_AGG(
                TRIM(BOTH FROM COALESCE(pd."ContoAvere", ''))
                ORDER BY pd."Pos", pd."ID"
            ) FILTER (
                WHERE TRIM(BOTH FROM COALESCE(pd."ContoAvere", '')) <> ''
            ))[1],
            ''
        ) AS contro_codice,
        COALESCE(
            (ARRAY_AGG(
                TRIM(BOTH FROM COALESCE(pd."Descrizione", ''))
                ORDER BY pd."Pos", pd."ID"
            ) FILTER (
                WHERE TRIM(BOTH FROM COALESCE(pd."Descrizione", '')) <> ''
            ))[1],
            NULLIF(TRIM(BOTH FROM COALESCE(p."NumeroDoc", '')), ''),
            ''
        ) AS descrizione,
        0 AS pos,
        0 AS id_riga
    FROM primanota p
    JOIN causali_contabili cc
      ON UPPER(TRIM(BOTH FROM COALESCE(cc."Codice", '')))
       = UPPER(TRIM(BOTH FROM COALESCE(p."Causale", '')))
    JOIN primanota_dettaglio pd
      ON p."ID" = pd."id_added_by_converter"
    WHERE p."Tipo" = 3
      AND pd."dummy" IS NOT TRUE
      AND UPPER(TRIM(BOTH FROM COALESCE(cc."CassaCorrispettivi", ''))) = UPPER(%s)
      AND NOT EXISTS (
          SELECT 1
          FROM primanota_dettaglio pd2
          WHERE pd2."id_added_by_converter" = p."ID"
            AND pd2."dummy" IS NOT TRUE
            AND (
              UPPER(TRIM(BOTH FROM COALESCE(pd2."ContoDare", ''))) = UPPER(%s)
              OR UPPER(TRIM(BOTH FROM COALESCE(pd2."ContoAvere", ''))) = UPPER(%s)
            )
      )
    GROUP BY
        p."ID", p."NumeroReg", p."DataReg", p."Tipo", p."Causale",
        p."CodicePaga", p."NumeroDoc", p."DataDoc", p."NumeroProt", p."AlfaProt"
    HAVING SUM(COALESCE(pd."Avere_Imponibile", 0)) <> 0
    ORDER BY data_reg NULLS LAST, numero_reg NULLS LAST, id_testa
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [code, code, code])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_movimenti_pdc(codice: str):
    """Dettagli sul sottoconto + corrispettivi con CassaCorrispettivi = codice."""
    rows = _fetch_movimenti_pdc_dettaglio(codice)
    rows.extend(_fetch_movimenti_pdc_cassa_corrispettivi(codice))
    rows.sort(
        key=lambda r: (
            r["data_reg"] is None,
            r["data_reg"] or date.min,
            r["numero_reg"] is None,
            r["numero_reg"] or 0,
            r.get("pos") or 0,
            r.get("id_riga") or 0,
            r.get("id_testa") or 0,
        )
    )
    return rows


def _fetch_movimenti_raw(codice: str, *, kind: Kind):
    if kind == "P":
        return _fetch_movimenti_pdc(codice)
    return _fetch_movimenti_clifor(codice)


def _protocollo(numero_prot, alfa_prot) -> str:
    serie = (alfa_prot or "").strip()
    try:
        numero = int(numero_prot) if numero_prot is not None else None
    except (TypeError, ValueError):
        numero = None
        if numero_prot is not None and str(numero_prot).strip():
            raw = str(numero_prot).strip()
            if raw not in {"0", "0.0"}:
                return f"{raw}/{serie}" if serie else raw
    if numero is None or numero == 0:
        return serie
    if not serie:
        return str(numero)
    return f"{numero}/{serie}"


def _batch_labels(codes: set[str]) -> dict[str, str]:
    """Descrizione PDC / cliente / fornitore per Contro/Partita."""
    cleaned = {_norm_code(c) for c in codes if _norm_code(c)}
    if not cleaned:
        return {}
    labels: dict[str, str] = {}
    placeholders = ", ".join(["%s"] * len(cleaned))
    params = list(cleaned)

    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT "Codice", "Descrizione" FROM pdc WHERE "Codice" IN ({placeholders})',
            params,
        )
        for codice, desc in cursor.fetchall():
            key = _norm_code(codice)
            if key and desc:
                labels[key] = str(desc).strip()

        cursor.execute(
            f"""
            SELECT "Codice",
                   TRIM(BOTH FROM CONCAT(COALESCE("RagioneSociale1", ''), ' ',
                                        COALESCE("RagioneSociale2", '')))
            FROM clienti WHERE "Codice" IN ({placeholders})
            """,
            params,
        )
        for codice, desc in cursor.fetchall():
            key = _norm_code(codice)
            if key and desc and key not in labels:
                labels[key] = str(desc).strip()

        cursor.execute(
            f"""
            SELECT "Codice",
                   TRIM(BOTH FROM CONCAT(COALESCE("RagioneSociale1", ''), ' ',
                                        COALESCE("RagioneSociale2", '')))
            FROM fornitori WHERE "Codice" IN ({placeholders})
            """,
            params,
        )
        for codice, desc in cursor.fetchall():
            key = _norm_code(codice)
            if key and desc and key not in labels:
                labels[key] = str(desc).strip()

    return labels


def _batch_causali(codes: set[str]) -> dict[str, str]:
    cleaned = {_norm_code(c) for c in codes if _norm_code(c)}
    if not cleaned:
        return {}
    placeholders = ", ".join(["%s"] * len(cleaned))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT "Codice", "Descrizione"
            FROM causali_contabili
            WHERE "Codice" IN ({placeholders})
            """,
            list(cleaned),
        )
        return {
            _norm_code(codice): (desc or "").strip()
            for codice, desc in cursor.fetchall()
            if _norm_code(codice)
        }


def _batch_pagamenti(codes: set[str]) -> dict[str, str]:
    cleaned = {_norm_code(c) for c in codes if _norm_code(c)}
    if not cleaned:
        return {}
    placeholders = ", ".join(["%s"] * len(cleaned))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT "Codice", "Descrizione"
            FROM condizioni
            WHERE "Codice" IN ({placeholders})
            """,
            list(cleaned),
        )
        return {
            _norm_code(codice): (desc or "").strip()
            for codice, desc in cursor.fetchall()
            if _norm_code(codice)
        }


def _signed_amounts(kind: Kind, fonte: str, dare_amt: float, avere_amt: float) -> tuple[float, float]:
    """
    Cliente IVA: positivi → Dare, negativi (abbuoni) → Avere (come 4D).
    Fornitore IVA: invertito.
    Generico e sottoconto PDC: rispetta il lato dove compare il codice.
    """
    pos = _f(dare_amt)
    neg = _f(avere_amt)
    if fonte == "iva" and kind in {"C", "F"}:
        if kind == "C":
            return pos, neg
        return neg, pos
    return pos, neg


def _empty_riga(**kwargs) -> PartitarioRiga:
    base = dict(
        data_reg=None,
        data_comp=None,
        numero_reg=None,
        id_testa=None,
        tipo=None,
        causale="",
        causale_descrizione="",
        descrizione="",
        pagamento="",
        pagamento_descrizione="",
        numero_doc="",
        numero_prot="",
        data_doc=None,
        contro_codice="",
        contro_descrizione="",
        dare=0.0,
        avere=0.0,
        saldo=0.0,
    )
    base.update(kwargs)
    return PartitarioRiga(**base)


def build_partitario(
    codice: str,
    *,
    kind: Kind,
    data_da: date | None = None,
    data_a: date | None = None,
) -> PartitarioResult:
    """
    Partitario del periodo [data_da, data_a], come maschera/stampa 4D.

    Il «Saldo precedente» è sempre 0 (riga di intestazione):
    si considerano solo i movimenti con DataReg nel periodo.

    kind: ``C`` cliente, ``F`` fornitore, ``P`` sottoconto PDC.
    """
    default_da, default_a = default_periodo()
    data_da = data_da or default_da
    data_a = data_a or default_a
    code = _norm_code(codice)

    raw = _fetch_movimenti_raw(code, kind=kind)

    causali = _batch_causali({r["causale"] for r in raw})
    pagamenti = _batch_pagamenti({r.get("codice_paga") or "" for r in raw})
    contro_labels = _batch_labels({r["contro_codice"] for r in raw})

    period_rows: list[dict] = []
    for row in raw:
        dreg = _as_date(row["data_reg"])
        if dreg is None:
            continue
        if dreg < data_da or dreg > data_a:
            continue
        dare, avere = _signed_amounts(
            kind, row["fonte"], _f(row["dare_amt"]), _f(row["avere_amt"])
        )
        period_rows.append({**row, "dare": dare, "avere": avere, "data_reg": dreg})

    saldo = 0.0
    righe: list[PartitarioRiga] = [
        _empty_riga(
            descrizione="Saldo precedente",
            is_saldo_precedente=True,
        )
    ]

    tot_dare = 0.0
    tot_avere = 0.0
    for row in period_rows:
        dare = row["dare"]
        avere = row["avere"]
        saldo += dare - avere
        tot_dare += dare
        tot_avere += avere
        causale = _norm_code(row["causale"])
        paga = _norm_code(row.get("codice_paga"))
        contro = _norm_code(row["contro_codice"])
        numero_doc = _norm_code(row["numero_doc"])
        desc = _norm_code(row["descrizione"]) or numero_doc
        dreg = row["data_reg"]
        righe.append(
            _empty_riga(
                data_reg=dreg,
                data_comp=dreg,  # in mirror non c'è Dt Comp. separata
                numero_reg=row["numero_reg"],
                id_testa=row["id_testa"],
                tipo=row["tipo"],
                causale=causale,
                causale_descrizione=causali.get(causale, ""),
                descrizione=desc,
                pagamento=paga,
                pagamento_descrizione=pagamenti.get(paga, ""),
                numero_doc=numero_doc,
                numero_prot=_protocollo(row["numero_prot"], row["alfa_prot"]),
                data_doc=_as_date(row["data_doc"]),
                contro_codice=contro,
                contro_descrizione=contro_labels.get(contro, ""),
                dare=dare,
                avere=avere,
                saldo=saldo,
            )
        )

    saldo_finale = tot_dare - tot_avere
    shown_dare = sum(r.dare for r in righe if not r.is_saldo_precedente)
    shown_avere = sum(r.avere for r in righe if not r.is_saldo_precedente)
    righe.append(
        _empty_riga(
            data_reg=data_a,
            data_comp=data_a,
            descrizione=f"Saldo al {data_a.strftime('%d/%m/%y')}",
            dare=shown_dare,
            avere=shown_avere,
            saldo=shown_dare - shown_avere,
            is_totale=True,
        )
    )

    return PartitarioResult(
        codice=code,
        kind=kind,
        data_da=data_da,
        data_a=data_a,
        saldo_precedente=0.0,
        righe=righe,
        totale_dare=tot_dare,
        totale_avere=tot_avere,
        saldo_finale=saldo_finale,
    )


PARTITARIO_SORT_FIELDS = (
    "numero_reg",
    "data_reg",
    "data_comp",
    "causale",
    "descrizione",
    "pagamento",
    "contro_codice",
    "numero_prot",
    "numero_doc",
    "data_doc",
    "dare",
    "avere",
    "saldo",
)


def _partitario_sort_key(riga: PartitarioRiga, sort: str):
    if sort == "causale":
        text = riga.causale_descrizione or riga.causale or ""
        return text.casefold()
    if sort == "pagamento":
        text = riga.pagamento_descrizione or riga.pagamento or ""
        return text.casefold()
    if sort in {"descrizione", "contro_codice", "numero_prot", "numero_doc"}:
        return (getattr(riga, sort, None) or "").casefold()
    if sort in {"data_reg", "data_comp", "data_doc"}:
        val = getattr(riga, sort, None)
        return (0, val) if val is not None else (1, None)
    if sort == "numero_reg":
        val = riga.numero_reg
        return (0, val) if val is not None else (1, None)
    if sort in {"dare", "avere", "saldo"}:
        return float(getattr(riga, sort, 0) or 0)
    return ""


def sort_partitario_righe(
    righe: list[PartitarioRiga],
    *,
    sort: str | None,
    direction: str = "asc",
) -> list[PartitarioRiga]:
    """
    Ordina le righe movimento; lascia fisse intestazione (saldo precedente)
    e totale. Ricalcola il saldo progressivo nell'ordine visualizzato.
    """
    if not righe:
        return righe

    header = [r for r in righe if r.is_saldo_precedente]
    footer = [r for r in righe if r.is_totale]
    moves = [r for r in righe if not r.is_saldo_precedente and not r.is_totale]

    if sort in PARTITARIO_SORT_FIELDS and moves:
        reverse = (direction or "asc").lower() == "desc"

        def full_key(r: PartitarioRiga):
            return (
                _partitario_sort_key(r, sort),
                r.numero_reg is None,
                r.numero_reg or 0,
                r.id_testa or 0,
            )

        moves = sorted(moves, key=full_key, reverse=reverse)

        saldo = 0.0
        for r in moves:
            saldo += (r.dare or 0.0) - (r.avere or 0.0)
            r.saldo = saldo

    return header + moves + footer
