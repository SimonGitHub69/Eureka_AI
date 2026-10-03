"""Bilancio di Verifica: totali Dare/Avere per sottoconto PDC nel periodo.

Aggrega i movimenti Primanota (tipo 1–4) sui conti Dare/Avere dei dettagli,
più i Corrispettivi con CassaCorrispettivi sulla causale (come il partitario PDC).

Le partite clienti/fornitori (codici C*/F*) nel bilancio sintetico non compaiono
come dettaglio: i loro importi sono ribaltati sul sottoconto allegato
(CPContoCli / CPContoFor, oppure i default 1.13.1 / 2.30.1).

La «Situazione analitica clienti/fornitori» usa invece la stessa logica del
partitario clifor: IVA/Autofattura su CodicePartita (imponibile+IVA) e
Generico/Corrispettivi su ContoDare/ContoAvere.

Per le registrazioni IVA/Autofattura (Tipo 2 e 4) nel bilancio PDC i lati sono
invertiti rispetto ai campi ContoDare/ContoAvere, allineati al 4D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import connection
from django.utils import timezone

from apps.anagrafiche.partitario import default_periodo
from apps.pdc.hierarchy import (
    LIVELLO_CONTO,
    LIVELLO_MASTRO,
    LIVELLO_SOTTOCONTO,
    PDC_TIPO_CONTROPARTITA,
    pdc_conto_codice,
    pdc_is_contropartita,
    pdc_livello,
    pdc_mastro_codice,
)

# Sottoconti di default per allegato A/B quando CPContoCli/CPContoFor è vuoto.
DEFAULT_CONTO_CLIENTI = "1.13.1"
DEFAULT_CONTO_FORNITORI = "2.30.1"

# Tipi di stampa del bilancio / situazioni analitiche.
MODALITA_BILANCIO = "bilancio"
MODALITA_CLIENTI = "clienti"
MODALITA_FORNITORI = "fornitori"
MODALITA_LABELS = {
    MODALITA_BILANCIO: "Bilancio di Verifica",
    MODALITA_CLIENTI: "Situazione analitica clienti",
    MODALITA_FORNITORI: "Situazione analitica fornitori",
}


def normalize_modalita(value: str | None) -> str:
    key = _norm(value).lower()
    if key in MODALITA_LABELS:
        return key
    return MODALITA_BILANCIO


def modalita_label(value: str | None) -> str:
    return MODALITA_LABELS[normalize_modalita(value)]


@dataclass
class BilancioRiga:
    codice: str
    descrizione: str
    # Movimenti contabili: Dare = addebiti, Avere = accrediti.
    dare_precedente: float = 0.0
    avere_precedente: float = 0.0
    dare_periodo: float = 0.0
    avere_periodo: float = 0.0
    livello: int = LIVELLO_SOTTOCONTO
    is_riepilogo: bool = False

    @property
    def saldo_precedente(self) -> float:
        return round(self.dare_precedente - self.avere_precedente, 2)

    @property
    def saldo_periodo(self) -> float:
        """Saldo periodo = Dare − Avere (positivo = Dare, negativo = Avere)."""
        return round(self.dare_periodo - self.avere_periodo, 2)

    @property
    def saldo_finale(self) -> float:
        return round(
            (self.dare_precedente + self.dare_periodo)
            - (self.avere_precedente + self.avere_periodo),
            2,
        )

    @property
    def ha_movimento_periodo(self) -> bool:
        return abs(self.dare_periodo) > 0.005 or abs(self.avere_periodo) > 0.005

    @property
    def ha_saldo(self) -> bool:
        return abs(self.saldo_finale) > 0.005


@dataclass
class BilancioVerificaResult:
    data_da: date
    data_a: date
    righe: list[BilancioRiga] = field(default_factory=list)
    totale_dare_precedente: float = 0.0
    totale_avere_precedente: float = 0.0
    totale_dare_periodo: float = 0.0
    totale_avere_periodo: float = 0.0
    totale_saldo_periodo: float = 0.0

    @property
    def sbilancio_periodo(self) -> float:
        return round(self.totale_dare_periodo - self.totale_avere_periodo, 2)

    @property
    def n_conti(self) -> int:
        return sum(1 for r in self.righe if not r.is_riepilogo)


def _money(value) -> float:
    """Arrotonda a 2 decimali come 4D (via rappresentazione float)."""
    try:
        return float(
            Decimal(str(float(value or 0))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    except (TypeError, ValueError, ArithmeticError):
        return 0.0


def _f(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _is_partita_clifor(codice: str) -> bool:
    """True se il codice è una partita C*/F* (non un sottoconto PDC)."""
    code = _norm(codice)
    if not code or pdc_is_contropartita(code):
        return False
    return code[0].upper() in ("C", "F")


def _load_allegato_map() -> dict[str, str]:
    """Mappa Codice partita (upper) → sottoconto PDC allegato."""
    out: dict[str, str] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT UPPER(TRIM(BOTH FROM "Codice")),
                   COALESCE(
                       NULLIF(TRIM(BOTH FROM COALESCE("CPContoCli", '')), ''),
                       %s
                   )
            FROM clienti
            WHERE TRIM(BOTH FROM COALESCE("Codice", '')) <> ''
            """,
            [DEFAULT_CONTO_CLIENTI],
        )
        for codice, conto in cursor.fetchall():
            key = _norm(codice).upper()
            target = _norm(conto) or DEFAULT_CONTO_CLIENTI
            if key:
                out[key] = target
        cursor.execute(
            """
            SELECT UPPER(TRIM(BOTH FROM "Codice")),
                   COALESCE(
                       NULLIF(TRIM(BOTH FROM COALESCE("CPContoFor", '')), ''),
                       %s
                   )
            FROM fornitori
            WHERE TRIM(BOTH FROM COALESCE("Codice", '')) <> ''
            """,
            [DEFAULT_CONTO_FORNITORI],
        )
        for codice, conto in cursor.fetchall():
            key = _norm(codice).upper()
            target = _norm(conto) or DEFAULT_CONTO_FORNITORI
            if key:
                out[key] = target
    return out


def _conto_allegato(codice: str, allegato_map: dict[str, str]) -> str:
    """Risolve la partita C*/F* nel sottoconto allegato da mostrare in bilancio."""
    key = _norm(codice).upper()
    if key in allegato_map:
        return allegato_map[key]
    if key.startswith("C"):
        return DEFAULT_CONTO_CLIENTI
    return DEFAULT_CONTO_FORNITORI


def _clifor_descrizioni(prefix: str) -> dict[str, str]:
    """Mappa Codice.upper() → ragione sociale per clienti (C) o fornitori (F)."""
    table = "clienti" if prefix.upper() == "C" else "fornitori"
    out: dict[str, str] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT UPPER(TRIM(BOTH FROM "Codice")),
                   TRIM(BOTH FROM COALESCE("RagioneSociale1", ''))
            FROM {table}
            WHERE TRIM(BOTH FROM COALESCE("Codice", '')) <> ''
            """
        )
        for codice, descrizione in cursor.fetchall():
            key = _norm(codice).upper()
            if key:
                out[key] = _norm(descrizione)
    return out


def _sum_righe(righe: list[BilancioRiga], *, codice: str, descrizione: str, livello: int) -> BilancioRiga:
    return BilancioRiga(
        codice=codice,
        descrizione=descrizione or codice,
        dare_precedente=round(sum(r.dare_precedente for r in righe), 2),
        avere_precedente=round(sum(r.avere_precedente for r in righe), 2),
        dare_periodo=round(sum(r.dare_periodo for r in righe), 2),
        avere_periodo=round(sum(r.avere_periodo for r in righe), 2),
        livello=livello,
        is_riepilogo=True,
    )


def _pdc_descrizioni(codici: set[str]) -> dict[str, str]:
    """Mappa Codice.upper() → descrizione PDC per i riepiloghi conto/mastro."""
    codes = sorted({_norm(c) for c in codici if _norm(c)})
    if not codes:
        return {}
    out: dict[str, str] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT TRIM(BOTH FROM "Codice"),
                   TRIM(BOTH FROM COALESCE("Descrizione", "DescConto", ''))
            FROM pdc
            WHERE UPPER(TRIM(BOTH FROM "Codice")) = ANY(%s)
            """,
            [[c.upper() for c in codes]],
        )
        for codice, descrizione in cursor.fetchall():
            code = _norm(codice)
            if code:
                out[code.upper()] = _norm(descrizione)
    return out


def inserisci_riepiloghi(
    righe: list[BilancioRiga],
    *,
    descrizioni: dict[str, str] | None = None,
) -> list[BilancioRiga]:
    """Inserisce righi riepilogativi di conto e mastro come nella stampa 4D.

    Dopo i sottoconti ``1.10.*`` emette ``1.10``; al cambio mastro emette anche
    il totale ``1``, ``2``, … I totali di stampa restano calcolati solo sui
    sottoconti (righe non riepilogo).
    """
    if not righe:
        return []

    needed: set[str] = set()
    for riga in righe:
        conto = pdc_conto_codice(riga.codice)
        mastro = pdc_mastro_codice(riga.codice)
        if conto:
            needed.add(conto)
        if mastro:
            needed.add(mastro)
    desc = descrizioni if descrizioni is not None else _pdc_descrizioni(needed)

    def _label(codice: str) -> str:
        return desc.get(codice.upper(), "") or codice

    out: list[BilancioRiga] = []
    cur_conto: str | None = None
    cur_mastro: str | None = None
    buf_conto: list[BilancioRiga] = []
    buf_mastro: list[BilancioRiga] = []

    def flush_conto() -> None:
        nonlocal buf_conto, cur_conto
        if cur_conto and buf_conto:
            out.append(
                _sum_righe(
                    buf_conto,
                    codice=cur_conto,
                    descrizione=_label(cur_conto),
                    livello=LIVELLO_CONTO,
                )
            )
        buf_conto = []

    def flush_mastro() -> None:
        nonlocal buf_mastro, cur_mastro
        flush_conto()
        if cur_mastro and buf_mastro:
            out.append(
                _sum_righe(
                    buf_mastro,
                    codice=cur_mastro,
                    descrizione=_label(cur_mastro),
                    livello=LIVELLO_MASTRO,
                )
            )
        buf_mastro = []

    for riga in righe:
        mastro = pdc_mastro_codice(riga.codice) or riga.codice
        conto = pdc_conto_codice(riga.codice)
        # Sottoconto → raggruppa per conto; riga già di livello conto/mastro → nessun sotto-gruppo.
        if conto is None:
            if cur_mastro is not None and mastro != cur_mastro:
                flush_mastro()
            elif cur_conto is not None:
                flush_conto()
            cur_mastro = mastro
            cur_conto = None
            out.append(riga)
            buf_mastro.append(riga)
            continue

        if cur_mastro is not None and mastro != cur_mastro:
            flush_mastro()
        elif cur_conto is not None and conto != cur_conto:
            flush_conto()

        cur_mastro = mastro
        cur_conto = conto
        detail = BilancioRiga(
            codice=riga.codice,
            descrizione=riga.descrizione,
            dare_precedente=riga.dare_precedente,
            avere_precedente=riga.avere_precedente,
            dare_periodo=riga.dare_periodo,
            avere_periodo=riga.avere_periodo,
            livello=pdc_livello(riga.codice),
            is_riepilogo=False,
        )
        out.append(detail)
        buf_conto.append(detail)
        buf_mastro.append(detail)

    flush_mastro()
    return out


_AGG_SQL = """
WITH detail_mov AS (
    SELECT
        p."DataReg"::date AS data_reg,
        p."Tipo" AS tipo,
        TRIM(BOTH FROM COALESCE(pd."ContoDare", '')) AS conto_dare,
        TRIM(BOTH FROM COALESCE(pd."ContoAvere", '')) AS conto_avere,
        CASE
            WHEN p."Tipo" IN (2, 4) THEN
                CASE
                    WHEN COALESCE(pd."Dare", 0) <> 0 THEN COALESCE(pd."Dare", 0)
                    ELSE COALESCE(pd."ImportoIva", 0)
                END
            ELSE COALESCE(pd."Dare", 0)
        END AS dare_amt,
        CASE
            WHEN p."Tipo" IN (2, 4) THEN
                CASE
                    WHEN COALESCE(pd."Avere_Imponibile", 0) <> 0
                    THEN COALESCE(pd."Avere_Imponibile", 0)
                    ELSE COALESCE(pd."ImportoIva", 0)
                END
            WHEN COALESCE(pd."Avere_Imponibile", 0) <> 0
            THEN COALESCE(pd."Avere_Imponibile", 0)
            ELSE COALESCE(pd."Dare", 0)
        END AS avere_amt
    FROM primanota p
    JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter"
    WHERE p."Tipo" IN (1, 2, 3, 4)
      AND pd."dummy" IS NOT TRUE
      AND p."DataReg" IS NOT NULL
      AND p."DataReg"::date <= %s
),
detail_lines AS (
    -- Tipo 2/4 (IVA/Autofattura): in bilancio 4D i lati ContoDare/ContoAvere sono invertiti.
    SELECT
        conto_dare AS codice,
        data_reg,
        CASE WHEN tipo IN (2, 4) THEN 0 ELSE dare_amt END AS dare,
        CASE WHEN tipo IN (2, 4) THEN dare_amt ELSE 0 END AS avere
    FROM detail_mov
    WHERE conto_dare <> ''
    UNION ALL
    SELECT
        conto_avere AS codice,
        data_reg,
        CASE WHEN tipo IN (2, 4) THEN avere_amt ELSE 0 END AS dare,
        CASE WHEN tipo IN (2, 4) THEN 0 ELSE avere_amt END AS avere
    FROM detail_mov
    WHERE conto_avere <> ''
),
cassa_mov AS (
    -- Una riga per ogni dettaglio imponibile (arrotondamento 4D riga-per-riga).
    SELECT
        TRIM(BOTH FROM COALESCE(cc."CassaCorrispettivi", '')) AS codice,
        p."DataReg"::date AS data_reg,
        CASE
            WHEN COALESCE(pd."Avere_Imponibile", 0) > 0
            THEN COALESCE(pd."Avere_Imponibile", 0)
            ELSE 0
        END AS dare,
        CASE
            WHEN COALESCE(pd."Avere_Imponibile", 0) < 0
            THEN -COALESCE(pd."Avere_Imponibile", 0)
            ELSE 0
        END AS avere
    FROM primanota p
    JOIN causali_contabili cc
      ON UPPER(TRIM(BOTH FROM COALESCE(cc."Codice", '')))
       = UPPER(TRIM(BOTH FROM COALESCE(p."Causale", '')))
    JOIN primanota_dettaglio pd
      ON p."ID" = pd."id_added_by_converter"
    WHERE p."Tipo" = 3
      AND pd."dummy" IS NOT TRUE
      AND p."DataReg" IS NOT NULL
      AND p."DataReg"::date <= %s
      AND TRIM(BOTH FROM COALESCE(cc."CassaCorrispettivi", '')) <> ''
      AND COALESCE(pd."Avere_Imponibile", 0) <> 0
      AND NOT EXISTS (
          SELECT 1
          FROM primanota_dettaglio pd2
          WHERE pd2."id_added_by_converter" = p."ID"
            AND pd2."dummy" IS NOT TRUE
            AND (
              UPPER(TRIM(BOTH FROM COALESCE(pd2."ContoDare", '')))
                = UPPER(TRIM(BOTH FROM COALESCE(cc."CassaCorrispettivi", '')))
              OR UPPER(TRIM(BOTH FROM COALESCE(pd2."ContoAvere", '')))
                = UPPER(TRIM(BOTH FROM COALESCE(cc."CassaCorrispettivi", '')))
            )
      )
),
all_lines AS (
    SELECT codice, data_reg, dare, avere FROM detail_lines
    UNION ALL
    SELECT codice, data_reg, dare, avere FROM cassa_mov
)
SELECT codice, data_reg, dare, avere
FROM all_lines
WHERE codice <> ''
"""


# Situazione analitica clifor: stessa regola del partitario clienti/fornitori.
# params: [data_a, prefix, prefix, prefix, prefix, flip_fornitore]
# flip_fornitore: TRUE per fornitori (inverte Dare/Avere delle sole righe IVA).
_ANALITICA_CLIFOR_SQL = """
WITH base AS (
    SELECT
        p."DataReg"::date AS data_reg,
        p."Tipo" AS tipo,
        UPPER(TRIM(BOTH FROM COALESCE(p."CodicePartita", ''))) AS codice_partita,
        UPPER(TRIM(BOTH FROM COALESCE(pd."ContoDare", ''))) AS conto_dare,
        UPPER(TRIM(BOTH FROM COALESCE(pd."ContoAvere", ''))) AS conto_avere,
        COALESCE(pd."Dare", 0) AS dare,
        COALESCE(pd."Avere_Imponibile", 0) AS avere,
        COALESCE(pd."ImportoIva", 0) AS importo_iva
    FROM primanota p
    JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter"
    WHERE p."Tipo" IN (1, 2, 3, 4)
      AND pd."dummy" IS NOT TRUE
      AND p."DataReg" IS NOT NULL
      AND p."DataReg"::date <= %s
),
lines AS (
    -- IVA / Autofattura: CodicePartita; importo firmato (NC → negativo) come partitario 4D.
    SELECT
        codice_partita AS codice,
        data_reg,
        (avere + importo_iva) AS dare_cli,
        0::float8 AS avere_cli,
        TRUE AS is_iva
    FROM base
    WHERE tipo IN (2, 4)
      AND codice_partita <> ''
      AND LEFT(codice_partita, 1) = %s
    UNION ALL
    -- Generico / Corrispettivi: lato Dare del codice partita.
    SELECT
        conto_dare AS codice,
        data_reg,
        dare AS dare_cli,
        0::float8 AS avere_cli,
        FALSE AS is_iva
    FROM base
    WHERE tipo IN (1, 3)
      AND conto_dare <> ''
      AND LEFT(conto_dare, 1) = %s
    UNION ALL
    -- Generico / Corrispettivi: lato Avere del codice partita.
    SELECT
        conto_avere AS codice,
        data_reg,
        0::float8 AS dare_cli,
        CASE WHEN avere <> 0 THEN avere ELSE dare END AS avere_cli,
        FALSE AS is_iva
    FROM base
    WHERE tipo IN (1, 3)
      AND conto_avere <> ''
      AND LEFT(conto_avere, 1) = %s
)
SELECT
    codice,
    data_reg,
    CASE WHEN is_iva AND %s THEN avere_cli ELSE dare_cli END AS dare,
    CASE WHEN is_iva AND %s THEN dare_cli ELSE avere_cli END AS avere
FROM lines
WHERE codice <> ''
"""


def _fetch_analitica_clifor_rows(prefix: str, data_a: date):
    """Movimenti analitici clifor fino a data_a: (codice, data_reg, dare, avere)."""
    pref = (prefix or "").strip().upper()[:1]
    if pref not in ("C", "F"):
        return []
    flip = pref == "F"
    with connection.cursor() as cursor:
        cursor.execute(
            _ANALITICA_CLIFOR_SQL,
            [data_a, pref, pref, pref, flip, flip],
        )
        return cursor.fetchall()


def build_bilancio_verifica(
    data_da: date,
    data_a: date,
    *,
    solo_con_movimenti: bool = True,
    escludi_saldo_zero: bool = False,
    includi_tutti_sottoconti: bool = False,
    modalita: str = MODALITA_BILANCIO,
) -> BilancioVerificaResult:
    """Calcola il bilancio di verifica o la situazione analitica clifor."""
    if data_da > data_a:
        data_da, data_a = data_a, data_da

    modalita = normalize_modalita(modalita)
    analitica = modalita in (MODALITA_CLIENTI, MODALITA_FORNITORI)
    clifor_prefix = (
        "C"
        if modalita == MODALITA_CLIENTI
        else ("F" if modalita == MODALITA_FORNITORI else "")
    )

    result = BilancioVerificaResult(data_da=data_da, data_a=data_a)

    if analitica:
        # Stessa logica del partitario clifor (IVA su CodicePartita + gen su conti).
        rows = _fetch_analitica_clifor_rows(clifor_prefix, data_a)
        allegato_map = {}
    else:
        with connection.cursor() as cursor:
            cursor.execute(_AGG_SQL, [data_a, data_a])
            rows = cursor.fetchall()
        allegato_map = _load_allegato_map()

    # Accumulatore: dare/avere prec+periodo, arrotondati riga-per-riga come in 4D.
    # Bilancio: partite C*/F* → sottoconto allegato (es. 1.13.1 / 2.30.1).
    acc: dict[str, list[float]] = {}
    codes_order: dict[str, str] = {}
    for codice, data_reg, dare_raw, avere_raw in rows:
        code = _norm(codice)
        if not code or data_reg is None:
            continue
        if analitica:
            if not _is_partita_clifor(code) or code[0].upper() != clifor_prefix:
                continue
        elif _is_partita_clifor(code):
            code = _conto_allegato(code, allegato_map)
        key = code.upper()
        codes_order.setdefault(key, code)
        bucket = acc.setdefault(key, [0.0, 0.0, 0.0, 0.0])
        dare = _money(dare_raw)
        avere = _money(avere_raw)
        if data_reg < data_da:
            bucket[0] = round(bucket[0] + dare, 2)
            bucket[1] = round(bucket[1] + avere, 2)
        elif data_reg <= data_a:
            bucket[2] = round(bucket[2] + dare, 2)
            bucket[3] = round(bucket[3] + avere, 2)

    needed_desc = set(codes_order.values())
    by_code: dict[str, BilancioRiga] = {}
    for key, code in codes_order.items():
        d_prec, a_prec, d_per, a_per = acc[key]
        by_code[key] = BilancioRiga(
            codice=code,
            descrizione="",  # riempito sotto
            dare_precedente=d_prec,
            avere_precedente=a_prec,
            dare_periodo=d_per,
            avere_periodo=a_per,
        )

    if includi_tutti_sottoconti and not analitica:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT TRIM(BOTH FROM "Codice"),
                       TRIM(BOTH FROM COALESCE("Descrizione", "DescConto", ''))
                FROM pdc
                WHERE "Tipo" = %s
                  AND COALESCE("Disabilitato", FALSE) IS NOT TRUE
                ORDER BY "Codice"
                """,
                [PDC_TIPO_CONTROPARTITA],
            )
            for codice, descrizione in cursor.fetchall():
                code = _norm(codice)
                if not code:
                    continue
                key = code.upper()
                needed_desc.add(code)
                if key not in by_code:
                    by_code[key] = BilancioRiga(
                        codice=code, descrizione=_norm(descrizione)
                    )
    elif includi_tutti_sottoconti and analitica:
        clifor_desc = _clifor_descrizioni(clifor_prefix)
        for key, descrizione in clifor_desc.items():
            if key not in by_code:
                # Mantieni casing originale dal codice anagrafica (upper ok).
                by_code[key] = BilancioRiga(codice=key, descrizione=descrizione)
            needed_desc.add(key)

    dettaglio: list[BilancioRiga] = []
    for riga in sorted(by_code.values(), key=lambda r: r.codice):
        if analitica:
            if not _is_partita_clifor(riga.codice):
                continue
            if riga.codice[0].upper() != clifor_prefix:
                continue
        elif not pdc_is_contropartita(riga.codice):
            # Solo sottoconti PDC; esclude partite C/F e altri codici.
            continue
        if solo_con_movimenti and not includi_tutti_sottoconti:
            # Allineato alla stampa 4D: solo conti con Dare/Avere nel periodo.
            if not riga.ha_movimento_periodo:
                continue
        if escludi_saldo_zero and not riga.ha_saldo:
            continue
        dettaglio.append(riga)
        if not analitica:
            conto = pdc_conto_codice(riga.codice)
            mastro = pdc_mastro_codice(riga.codice)
            if conto:
                needed_desc.add(conto)
            if mastro:
                needed_desc.add(mastro)

    if analitica:
        descrizioni = _clifor_descrizioni(clifor_prefix)
        for riga in dettaglio:
            if not riga.descrizione:
                riga.descrizione = descrizioni.get(riga.codice.upper(), "")
        result.righe = dettaglio
    else:
        descrizioni = _pdc_descrizioni(needed_desc)
        for riga in dettaglio:
            if not riga.descrizione:
                riga.descrizione = descrizioni.get(riga.codice.upper(), "")
        result.righe = inserisci_riepiloghi(dettaglio, descrizioni=descrizioni)

    soli_dettaglio = [r for r in result.righe if not r.is_riepilogo]
    result.totale_dare_precedente = round(
        sum(r.dare_precedente for r in soli_dettaglio), 2
    )
    result.totale_avere_precedente = round(
        sum(r.avere_precedente for r in soli_dettaglio), 2
    )
    result.totale_dare_periodo = round(sum(r.dare_periodo for r in soli_dettaglio), 2)
    result.totale_avere_periodo = round(sum(r.avere_periodo for r in soli_dettaglio), 2)
    # Saldo totale = differenza delle somme (non somma dei saldi riga).
    result.totale_saldo_periodo = round(
        result.totale_dare_periodo - result.totale_avere_periodo, 2
    )
    return result
