"""Calcolo giacenza articolo dai movimenti di magazzino (Flag_CD su dettaglio)."""

from __future__ import annotations

import math
from datetime import date
from django.db import connection
from django.http import HttpRequest
from django.utils import timezone
from django.utils.dateparse import parse_date

# Nel mirror 4D: 1, 2, 3 = carico; 4, 5 = scarico.
FLAG_CD_CARICO = (1, 2, 3)
FLAG_CD_SCARICO = (4, 5)
FLAG_CD_GIACENZA = FLAG_CD_CARICO + FLAG_CD_SCARICO
# Ultimo/medio acquisto: carichi Flag_CD 1/2/3, filtrati da flag causale separati.
FLAG_CD_ULTIMO_ACQUISTO = (1, 2, 3)
CAUSALE_GIACENZA_INIZIALE = "01"
# Flag causale: aggiorna ultimo prezzo (4D Update_Listino) / prezzo medio (Eureka).
# Usa %% perché la query è eseguita con parametri (%s).
_UPDATE_ULTIMO_PREZZO_SQL = (
    "UPPER(TRIM(BOTH FROM COALESCE(cm.\"Update_Listino\", ''))) LIKE 'SI%%'"
)
_UPDATE_PREZZO_MEDIO_SQL = (
    "UPPER(TRIM(BOTH FROM COALESCE(cm.\"Update_Prezzo_Medio\", ''))) LIKE 'SI%%'"
)


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


def parse_inventario_periodo(request: HttpRequest) -> tuple[date | None, date | None]:
    """Legge ``data_da`` / ``data_a`` da GET; scambia se l'intervallo è invertito."""
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())
    if data_da and data_a and data_da > data_a:
        data_da, data_a = data_a, data_da
    return data_da, data_a


def parse_inventario_categorie(request: HttpRequest) -> tuple[str, str]:
    """Legge ``categoria_da`` / ``categoria_a`` da GET; scambia se l'intervallo è invertito."""
    cat_da = (request.GET.get("categoria_da") or "").strip()
    cat_a = (request.GET.get("categoria_a") or "").strip()
    if cat_da and cat_a and cat_da.upper() > cat_a.upper():
        cat_da, cat_a = cat_a, cat_da
    return cat_da, cat_a


def inventario_periodo_label(data_da: date | None, data_a: date | None) -> str:
    """Etichetta periodo per filtro/sottotitolo stampa inventario."""
    if data_da and data_a:
        return f"dal {data_da.strftime('%d/%m/%Y')} al {data_a.strftime('%d/%m/%Y')}"
    if data_da:
        return f"dal {data_da.strftime('%d/%m/%Y')}"
    if data_a:
        return f"al {data_a.strftime('%d/%m/%Y')}"
    return ""


def inventario_periodo_anno(anno: int) -> tuple[date, date]:
    """Intero anno solare (1 gen – 31 dic)."""
    return date(anno, 1, 1), date(anno, 12, 31)


def inventario_preset_urls(request: HttpRequest, oggi: date | None = None) -> dict[str, str]:
    """URL relativi per scorciatoie anno corrente / anno precedente."""
    today = oggi or timezone.localdate()
    presets = {
        "corrente": inventario_periodo_anno(today.year),
        "precedente": inventario_periodo_anno(today.year - 1),
    }
    urls: dict[str, str] = {}
    for key, (data_da, data_a) in presets.items():
        qs = request.GET.copy()
        qs["data_da"] = data_da.isoformat()
        qs["data_a"] = data_a.isoformat()
        urls[key] = f"?{qs.urlencode()}"
    return urls


def inventario_active_preset(
    data_da: date | None,
    data_a: date | None,
    *,
    oggi: date | None = None,
) -> str | None:
    """Preset attivo ('corrente' / 'precedente') se le date coincidono con l'anno solare."""
    if not data_da or not data_a:
        return None
    today = oggi or timezone.localdate()
    for key, anno in (("corrente", today.year), ("precedente", today.year - 1)):
        da, a = inventario_periodo_anno(anno)
        if data_da == da and data_a == a:
            return key
    return None


def inventario_categorie_label(cat_da: str, cat_a: str) -> str:
    """Etichetta intervallo categorie per filtro/sottotitolo stampa inventario."""
    if cat_da and cat_a:
        return f"da categoria {cat_da} a categoria {cat_a}"
    if cat_da:
        return f"da categoria {cat_da}"
    if cat_a:
        return f"a categoria {cat_a}"
    return ""


def giacenze_non_nulle(
    *,
    data_da: date | None = None,
    data_a: date | None = None,
) -> dict[str, float]:
    """Mappa codice → giacenza per articoli con stock ≠ 0.

    Senza date: somma tutti i movimenti (giacenza attuale).
    Con ``data_a``: inventario alla data (movimenti con DataRegistraz ≤ data_a).
    Solo ``data_da``: movimenti da quella data in poi.
    """
    join_sql = ""
    date_sql = ""
    params: list[date] = []
    if data_da or data_a:
        join_sql = 'JOIN movimentit p ON p."ID_Testa" = pd."id_added_by_converter"'
        if data_a:
            # Inventario alla data di chiusura (come stampa 4D Valori Articoli).
            date_sql += ' AND p."DataRegistraz"::date <= %s'
            params.append(data_a)
        elif data_da:
            date_sql += ' AND p."DataRegistraz"::date >= %s'
            params.append(data_da)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) AS cod,
                   {_GIACENZA_SUM} AS qty
            FROM movimentit_dettaglio pd
            {join_sql}
            WHERE TRIM(BOTH FROM COALESCE(pd."CodiceArt", '')) <> ''
            {date_sql}
            GROUP BY 1
            HAVING {_GIACENZA_SUM} <> 0
            """,
            params,
        )
        return {row[0]: float(row[1] or 0) for row in cursor.fetchall() if row[0]}


def costo_inventario(articolo) -> float:
    """Costo unitario per valorizzazione: medio acquisto, altrimenti listino 1."""
    for attr in ("prezzo_medio_acquisto", "listino1"):
        raw = getattr(articolo, attr, None)
        if _prezzo_valido(raw):
            return float(raw)
    return 0.0


def _prezzo_valido(value) -> bool:
    """True se il prezzo anagrafica/movimento è utilizzabile."""
    if value in (None, ""):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return not (math.isinf(number) or math.isnan(number) or number < 0)


def _prezzo_campo(articolo, attr: str) -> float:
    raw = getattr(articolo, attr, None)
    if not _prezzo_valido(raw):
        return 0.0
    return float(raw)


def _date_range_sql(
    *,
    data_da: date | None = None,
    data_a: date | None = None,
) -> tuple[str, list]:
    """Filtro DataRegistraz opzionale; restituisce (sql, params)."""
    parts: list[str] = []
    params: list = []
    if data_da:
        parts.append('p."DataRegistraz"::date >= %s')
        params.append(data_da)
    if data_a:
        parts.append('p."DataRegistraz"::date <= %s')
        params.append(data_a)
    if not parts:
        return "", []
    return " AND " + " AND ".join(parts), params


def prezzi_movimento_per_codici(
    codici: list[str],
    *,
    data_da: date | None = None,
    data_a: date | None = None,
) -> dict[str, dict[str, float]]:
    """Prezzi unitari da movimenti carico (ultimo, medio, giacenza iniziale).

    ``ultimo_carico`` usa Flag_CD 1/2/3 e causali con ``Update_Listino`` attivo.
    ``medio_carico`` usa Flag_CD 1/2/3 e causali con ``Update_Prezzo_Medio`` attivo.
    Entrambi rispettano il range ``data_da``–``data_a`` se indicato.
    """
    keys = sorted({_norm_codice(c) for c in codici if _norm_codice(c)})
    if not keys:
        return {}

    date_sql, date_params = _date_range_sql(data_da=data_da, data_a=data_a)
    params_base: list = [keys, *date_params]

    carico_ultimo_sql = f"""
        pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_ULTIMO_ACQUISTO)})
        AND {_UPDATE_ULTIMO_PREZZO_SQL}
        AND COALESCE(pd."ValoreUnNetto", 0) > 0
        {date_sql}
    """
    carico_medio_sql = f"""
        pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_ULTIMO_ACQUISTO)})
        AND {_UPDATE_PREZZO_MEDIO_SQL}
        AND COALESCE(pd."ValoreUnNetto", 0) > 0
        {date_sql}
    """
    carico_giacenza_sql = f"""
        pd."Flag_CD" IN ({_flag_cd_in_sql(FLAG_CD_CARICO)})
        AND COALESCE(pd."ValoreUnNetto", 0) > 0
        {date_sql}
    """
    order_by = """
        cod,
        "DataRegistraz" DESC NULLS LAST,
        "NumRegistraz" DESC NULLS LAST,
        "Pos" DESC NULLS LAST,
        "ID" DESC
    """

    result: dict[str, dict[str, float]] = {}

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT DISTINCT ON (cod) cod, valore
            FROM (
                SELECT UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) AS cod,
                       pd."ValoreUnNetto" AS valore,
                       p."DataRegistraz",
                       p."NumRegistraz",
                       pd."Pos",
                       pd."ID"
                FROM movimentit_dettaglio pd
                JOIN movimentit p ON p."ID_Testa" = pd."id_added_by_converter"
                LEFT JOIN causali_maga cm
                  ON TRIM(BOTH FROM COALESCE(cm."Codice", ''))
                   = TRIM(BOTH FROM COALESCE(p."Causale", ''))
                WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = ANY(%s)
                  AND {carico_ultimo_sql}
            ) sub
            ORDER BY {order_by}
            """,
            params_base,
        )
        for cod, valore in cursor.fetchall():
            if cod and _prezzo_valido(valore):
                result.setdefault(cod, {})["ultimo_carico"] = float(valore)

        cursor.execute(
            f"""
            SELECT UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) AS cod,
                   SUM(pd."Quantita" * pd."ValoreUnNetto")
                     / NULLIF(SUM(pd."Quantita"), 0) AS medio
            FROM movimentit_dettaglio pd
            JOIN movimentit p ON p."ID_Testa" = pd."id_added_by_converter"
            LEFT JOIN causali_maga cm
              ON TRIM(BOTH FROM COALESCE(cm."Codice", ''))
               = TRIM(BOTH FROM COALESCE(p."Causale", ''))
            WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = ANY(%s)
              AND {carico_medio_sql}
              AND COALESCE(pd."Quantita", 0) > 0
            GROUP BY 1
            """,
            params_base,
        )
        for cod, medio in cursor.fetchall():
            if cod and _prezzo_valido(medio):
                result.setdefault(cod, {})["medio_carico"] = float(medio)

        cursor.execute(
            f"""
            SELECT DISTINCT ON (cod) cod, valore
            FROM (
                SELECT UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) AS cod,
                       pd."ValoreUnNetto" AS valore,
                       p."DataRegistraz",
                       p."NumRegistraz",
                       pd."Pos",
                       pd."ID"
                FROM movimentit_dettaglio pd
                JOIN movimentit p ON p."ID_Testa" = pd."id_added_by_converter"
                WHERE UPPER(TRIM(BOTH FROM COALESCE(pd."CodiceArt", ''))) = ANY(%s)
                  AND TRIM(COALESCE(p."Causale", '')) = %s
                  AND {carico_giacenza_sql}
            ) sub
            ORDER BY {order_by}
            """,
            [keys, CAUSALE_GIACENZA_INIZIALE, *date_params],
        )
        for cod, valore in cursor.fetchall():
            if cod and _prezzo_valido(valore):
                result.setdefault(cod, {})["giacenza_iniziale"] = float(valore)

    return result

def prezzi_periodo_articolo(
    codice: str | None,
    *,
    data_da: date | None = None,
    data_a: date | None = None,
) -> dict[str, float | None]:
    """Ultimo prezzo e prezzo medio di acquisto sul periodo (solo da movimenti)."""
    key = _norm_codice(codice)
    if not key:
        return {"ultimo": None, "medio": None}
    mov = prezzi_movimento_per_codici([key], data_da=data_da, data_a=data_a).get(key, {})
    ultimo = mov.get("ultimo_carico")
    medio = mov.get("medio_carico")
    return {
        "ultimo": float(ultimo) if ultimo else None,
        "medio": float(medio) if medio else None,
    }


def _resolve_prezzo_ultimo(articolo, mov: dict[str, float]) -> float:
    """Prezzo ultimo acquisto: solo da movimenti (Update_Listino). Mai anagrafica."""
    value = mov.get("ultimo_carico")
    return float(value) if value else 0.0


def _resolve_prezzo_medio(articolo, mov: dict[str, float]) -> float:
    """Prezzo medio: solo da movimenti (Update_Prezzo_Medio). Mai anagrafica."""
    value = mov.get("medio_carico")
    return float(value) if value else 0.0


def prezzo_ultimo_acquisto_articolo(
    articolo,
    *,
    data_a: date | None = None,
) -> float | None:
    """Prezzo ultimo acquisto da movimenti (nessun fallback anagrafica)."""
    mov = prezzi_movimento_per_codici([articolo.codice], data_a=data_a).get(
        _norm_codice(articolo.codice), {}
    )
    value = _resolve_prezzo_ultimo(articolo, mov)
    return value if value else None


INVENTARIO_PREZZO_DECIMALS = 3  # fallback; usare get_prezzo_decimali()


def _round_prezzo_inventario(value: float) -> float:
    """Allinea il prezzo ai decimali configurati (half-up commerciale)."""
    from apps.core.prezzi import round_prezzo

    return round_prezzo(value)


def attach_inventario_articoli(
    articoli,
    stocks: dict[str, float] | None = None,
    *,
    data_a: date | None = None,
) -> None:
    """Imposta giacenza e valorizzazione (prezzo ultimo / medio) su ogni articolo."""
    articoli = list(articoli)
    if stocks is None:
        stocks = giacenze_per_codici([a.codice for a in articoli])
    mov_prezzi = prezzi_movimento_per_codici([a.codice for a in articoli], data_a=data_a)
    for articolo in articoli:
        key = _norm_codice(articolo.codice)
        qty = stocks.get(key, 0.0)
        mov = mov_prezzi.get(key, {})
        ultimo = _round_prezzo_inventario(_resolve_prezzo_ultimo(articolo, mov))
        medio = _round_prezzo_inventario(_resolve_prezzo_medio(articolo, mov))
        articolo.giacenza_quantita = qty
        articolo.prezzo_ultimo_acquisto = ultimo
        articolo.prezzo_medio_inventario = medio
        if qty < 0:
            articolo.valore_prezzo_ultimo = 0.0
            articolo.valore_prezzo_medio = 0.0
            articolo.costo_inventario = medio or ultimo or costo_inventario(articolo)
            articolo.valore_inventario = 0.0
        else:
            articolo.valore_prezzo_ultimo = qty * ultimo
            articolo.valore_prezzo_medio = qty * medio
            articolo.costo_inventario = medio or ultimo or costo_inventario(articolo)
            articolo.valore_inventario = qty * articolo.costo_inventario


def inventario_row_class(articolo, *, soglia: float | None = None) -> str:
    """Classi riga stampa: giacenza negativa e anomalie prezzi."""
    return " ".join(inventario_row_classes(articolo, soglia=soglia))


INVENTARIO_PREZZO_DISCREPANZA_PCT_DEFAULT = 25


def inventario_discrepanza_pct() -> int:
    """Percentuale soglia da Parametri programma (fallback 25)."""
    try:
        from apps.core.models import ConfigurazioneProgramma

        value = ConfigurazioneProgramma.get_solo().inventario_discrepanza_pct
    except Exception:
        value = INVENTARIO_PREZZO_DISCREPANZA_PCT_DEFAULT
    if value is None:
        return INVENTARIO_PREZZO_DISCREPANZA_PCT_DEFAULT
    return max(1, min(100, int(value)))


def inventario_discrepanza_soglia(*, pct: int | None = None) -> float:
    """Soglia relativa 0–1 per |ultimo−medio|/max."""
    if pct is None:
        pct = inventario_discrepanza_pct()
    return max(0.0, min(1.0, float(pct) / 100.0))


# Retrocompatibilità: default numerico come prima (0.25).
INVENTARIO_PREZZO_DISCREPANZA = inventario_discrepanza_soglia(
    pct=INVENTARIO_PREZZO_DISCREPANZA_PCT_DEFAULT
)


def inventario_row_classes(
    articolo, *, soglia: float | None = None
) -> list[str]:
    """Elenco classi CSS per anomalie inventario."""
    if soglia is None:
        soglia = inventario_discrepanza_soglia()
    classes: list[str] = []
    qty = float(getattr(articolo, "giacenza_quantita", 0) or 0)
    if qty < 0:
        classes.append("eureka-print-row--giacenza-negativa")
    if qty > 0:
        ultimo = float(getattr(articolo, "prezzo_ultimo_acquisto", 0) or 0)
        medio = float(getattr(articolo, "prezzo_medio_inventario", 0) or 0)
        if ultimo <= 0:
            classes.append("eureka-print-row--prezzo-zero-ultimo")
        if medio <= 0:
            classes.append("eureka-print-row--prezzo-zero-medio")
        if ultimo > 0 and medio > 0:
            base = max(ultimo, medio)
            if abs(ultimo - medio) / base >= soglia:
                classes.append("eureka-print-row--prezzo-discrepanza")
    return classes


def inventario_filter_giacenza_non_zero(articoli) -> list:
    """Esclude dalla stampa inventario le righe con giacenza a zero."""
    out = []
    for articolo in articoli:
        qty = float(getattr(articolo, "giacenza_quantita", 0) or 0)
        if qty != 0:
            out.append(articolo)
    return out


def inventario_has_anomalia(articolo, *, soglia: float | None = None) -> bool:
    return bool(inventario_row_classes(articolo, soglia=soglia))


def inventario_filter_solo_anomalie(
    articoli, *, soglia: float | None = None
) -> list:
    """Tiene solo le righe con almeno un'anomalia."""
    return [a for a in articoli if inventario_has_anomalia(a, soglia=soglia)]


def inventario_anomalia_counts(
    articoli, *, soglia: float | None = None
) -> dict[str, int]:
    """Conteggi anomalie per legenda anteprima stampa."""
    counts = {
        "giacenza_negativa": 0,
        "prezzo_zero_ultimo": 0,
        "prezzo_zero_medio": 0,
        "prezzo_discrepanza": 0,
    }
    for articolo in articoli:
        classes = set(inventario_row_classes(articolo, soglia=soglia))
        if "eureka-print-row--giacenza-negativa" in classes:
            counts["giacenza_negativa"] += 1
        if "eureka-print-row--prezzo-zero-ultimo" in classes:
            counts["prezzo_zero_ultimo"] += 1
        if "eureka-print-row--prezzo-zero-medio" in classes:
            counts["prezzo_zero_medio"] += 1
        if "eureka-print-row--prezzo-discrepanza" in classes:
            counts["prezzo_discrepanza"] += 1
    return counts


def inventario_totali(articoli) -> dict[str, float]:
    """Totali giacenza e valori per la stampa inventario."""
    tot_qty = 0.0
    tot_ultimo = 0.0
    tot_medio = 0.0
    for articolo in articoli:
        qty = float(getattr(articolo, "giacenza_quantita", 0) or 0)
        tot_qty += qty
        if qty >= 0:
            tot_ultimo += float(getattr(articolo, "valore_prezzo_ultimo", 0) or 0)
            tot_medio += float(getattr(articolo, "valore_prezzo_medio", 0) or 0)
    return {
        "giacenza": tot_qty,
        "valore_ultimo": tot_ultimo,
        "valore_medio": tot_medio,
    }


def inventario_want_rottura(request: HttpRequest) -> bool:
    """True se la stampa richiede rottura per categoria."""
    raw = (request.GET.get("rottura") or "").strip().lower()
    return raw in ("1", "true", "on", "si", "sì", "yes")


def inventario_want_solo_anomalie(request: HttpRequest) -> bool:
    """True se la stampa richiede solo le righe con anomalie."""
    raw = (request.GET.get("solo_anomalie") or "").strip().lower()
    return raw in ("1", "true", "on", "si", "sì", "yes")


def inventario_want_ignora_anomalie(request: HttpRequest) -> bool:
    """True se la stampa non deve evidenziare né filtrare le anomalie."""
    raw = (request.GET.get("ignora_anomalie") or "").strip().lower()
    return raw in ("1", "true", "on", "si", "sì", "yes")


def inventario_categoria_key(articolo) -> str:
    return (getattr(articolo, "cat_omogenea", None) or "").strip()


def inventario_gruppi_per_categoria(articoli) -> list[tuple[str, list]]:
    """Raggruppa articoli consecutivi per categoria (lista già ordinata per cat.)."""
    gruppi: list[tuple[str, list]] = []
    current_key: str | None = None
    current_rows: list = []
    for articolo in articoli:
        key = inventario_categoria_key(articolo)
        if current_key is None:
            current_key = key
            current_rows = [articolo]
            continue
        if key != current_key:
            gruppi.append((current_key, current_rows))
            current_key = key
            current_rows = [articolo]
        else:
            current_rows.append(articolo)
    if current_key is not None:
        gruppi.append((current_key, current_rows))
    return gruppi


def inventario_sort_per_categoria(articoli: list) -> list:
    """Ordina per categoria e codice (necessario per la rottura)."""
    return sorted(
        articoli,
        key=lambda a: (
            inventario_categoria_key(a).upper(),
            (getattr(a, "codice", None) or "").strip().upper(),
        ),
    )
