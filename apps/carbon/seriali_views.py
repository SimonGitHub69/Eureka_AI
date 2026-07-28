"""
CARBON seriali dashboard API backed by Eureka's PostgreSQL 4D mirrors.

Table mapping: GS_Lavorazioni_Partite -> lavorazioni_partite,
GS_TabStampi_Seriali_Partite -> stampi_seriali_partite, GS_REPARTI ->
reparti, GS_OPERATORI -> operatori, and TabLavorazioniExtra ->
lavorazioni_extra.  These are PostgreSQL mirrors, not the SQL Server
GS_* tables used by the original CARBON dashboard.
"""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


SERIAL_COLS = [f'"CodArtSer{i}"' for i in range(1, 17)]
OPE_COLS = [f'"CodOpe{i}"' for i in range(1, 11)]
ACTIVE_LAVORAZIONE = 'COALESCE(l."DaCancellare", FALSE) = FALSE'
REG_DATETIME = (
    '(CAST({a}."Data" AS date) + COALESCE({a}."Ora", TIME \'00:00:00\'))'
)


def _trim(column):
    return f'TRIM({column})'


def _sql_operatore_match(alias="l"):
    return " OR ".join(f"{_trim(f'{alias}.{column}')} = %s" for column in OPE_COLS)


OPE_AGGREGATES = ", ".join(
    f"""MAX(CASE WHEN {_trim('l."Stato"')} = 'INIZIO' """
    f"THEN NULLIF({_trim(f'l.{column}')}, '') END) AS codope{i}"
    for i, column in enumerate(OPE_COLS, start=1)
)


SERIALI_AGG_CTE = f"""
WITH agg AS (
    SELECT
        {_trim('l."CodArtSer"')} AS seriale,
        {_trim('l."CodReparto"')} AS cod_reparto,
        MAX(CASE WHEN {_trim('l."Stato"')} = 'INIZIO' THEN 1 ELSE 0 END) AS ha_inizio,
        MAX(CASE WHEN {_trim('l."Stato"')} = 'FINE' THEN 1 ELSE 0 END) AS ha_fine,
        MIN(CASE WHEN {_trim('l."Stato"')} = 'INIZIO'
            THEN {REG_DATETIME.format(a='l')} END) AS data_inizio,
        MAX(CASE WHEN {_trim('l."Stato"')} = 'FINE'
            THEN {REG_DATETIME.format(a='l')} END) AS data_fine,
        MAX({_trim('l."CodArt"')}) AS codart,
        MAX({_trim('l."CodStampo"')}) AS codstampo,
        {OPE_AGGREGATES}
    FROM lavorazioni_partite l
    WHERE {ACTIVE_LAVORAZIONE}
      AND l."CodArtSer" IS NOT NULL
      AND {_trim('l."CodArtSer"')} <> ''
      {{inner_where}}
    GROUP BY {_trim('l."CodArtSer"')}, {_trim('l."CodReparto"')}
    HAVING MAX(CASE WHEN {_trim('l."Stato"')} = 'INIZIO' THEN 1 ELSE 0 END) = 1
),
seriali AS (
    SELECT
        a.seriale,
        a.cod_reparto,
        COALESCE(NULLIF({_trim('r."Descrizione"')}, ''), a.cod_reparto) AS descr_reparto,
        CASE WHEN a.ha_fine = 1 THEN 'COMPLETATO' ELSE 'DA TERMINARE' END AS stato_avanzamento,
        a.data_inizio, a.data_fine, a.codart, a.codstampo,
        a.codope1, a.codope2, a.codope3, a.codope4, a.codope5,
        a.codope6, a.codope7, a.codope8, a.codope9, a.codope10
    FROM agg a
    LEFT JOIN reparti r ON a.cod_reparto = {_trim('r."Codice"')}
)
"""


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_limit(request, default, maximum):
    try:
        return min(max(int(request.GET.get("limit", default)), 1), maximum)
    except (TypeError, ValueError):
        return default


def _sql_seriali_inner_filter(request):
    clauses, params = [], []
    reparto = request.GET.get("reparto", "").strip()
    codartser = request.GET.get("codartser", "").strip()
    stampo = request.GET.get("stampo", "").strip()
    operatore = request.GET.get("operatore", "").strip()

    if reparto:
        clauses.append(f"""{_trim('l."CodReparto"')} = %s""")
        params.append(reparto)
    if codartser:
        like = f"%{codartser}%"
        serial_match = " OR ".join(
            f"{_trim(f's.{column}')} LIKE %s" for column in SERIAL_COLS
        )
        clauses.append(f"""(
            {_trim('l."CodArtSer"')} LIKE %s
            OR l."Key_lav" IN (
                SELECT s."key_Lav_Partite" FROM stampi_seriali_partite s
                WHERE {serial_match}
            )
        )""")
        params.extend([like] * (len(SERIAL_COLS) + 1))
    if stampo:
        clauses.append(f"""(
            {_trim('l."CodStampo"')} = %s
            OR l."Key_lav" IN (
                SELECT "key_Lav_Partite" FROM stampi_seriali_partite
                WHERE {_trim('"CodiceStampo"')} = %s
            )
        )""")
        params.extend([stampo, stampo])
    if operatore:
        clauses.append(f"({_sql_operatore_match()})")
        params.extend([operatore] * len(OPE_COLS))
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _sql_seriali_outer_filter(request):
    clauses, params = [], []
    stato = request.GET.get("stato", "").strip().upper()
    if stato == "COMPLETATO":
        clauses.append("stato_avanzamento = 'COMPLETATO'")
    elif stato in ("DA TERMINARE", "DA_TERMINARE"):
        clauses.append("stato_avanzamento = 'DA TERMINARE'")
    for key, operator in (("da", ">="), ("a", "<=")):
        value = _parse_date(request.GET.get(key))
        if value:
            clauses.append(f"CAST(data_inizio AS date) {operator} %s")
            params.append(value)
    return (" AND ".join(clauses) if clauses else "TRUE"), params


def _seriali_query_parts(request):
    inner_where, inner_params = _sql_seriali_inner_filter(request)
    outer_where, outer_params = _sql_seriali_outer_filter(request)
    return SERIALI_AGG_CTE.format(inner_where=inner_where), outer_where, inner_params + outer_params


def _sql_lavorazioni_filter(request):
    """Filters on individual mirror rows, for raw-work KPI and charts."""
    clauses, params = [ACTIVE_LAVORAZIONE], []
    reparto = request.GET.get("reparto", "").strip()
    lavextra = request.GET.get("lavextra", "").strip()
    codartser = request.GET.get("codartser", "").strip()
    stampo = request.GET.get("stampo", "").strip()
    operatore = request.GET.get("operatore", "").strip()
    if reparto:
        clauses.append(f"""{_trim('l."CodReparto"')} = %s""")
        params.append(reparto)
    if lavextra:
        clauses.append(f"""{_trim('l."CodLavExtra"')} = %s""")
        params.append(lavextra)
    if codartser:
        like = f"%{codartser}%"
        serial_match = " OR ".join(f"{_trim(f's.{col}')} LIKE %s" for col in SERIAL_COLS)
        clauses.append(
            f"""({_trim('l."CodArtSer"')} LIKE %s OR l."Key_lav" IN """
            f'(SELECT s."key_Lav_Partite" FROM stampi_seriali_partite s WHERE {serial_match}))'
        )
        params.extend([like] * (len(SERIAL_COLS) + 1))
    if stampo:
        clauses.append(
            f"""({_trim('l."CodStampo"')} = %s OR l."Key_lav" IN """
            f"""(SELECT "key_Lav_Partite" FROM stampi_seriali_partite """
            f"""WHERE {_trim('"CodiceStampo"')} = %s))"""
        )
        params.extend([stampo, stampo])
    if operatore:
        clauses.append(f"({_sql_operatore_match()})")
        params.extend([operatore] * len(OPE_COLS))
    for key, operator in (("da", ">="), ("a", "<=")):
        value = _parse_date(request.GET.get(key))
        if value:
            clauses.append(f'CAST(l."Data" AS date) {operator} %s')
            params.append(value)
    return " AND ".join(clauses), params


def _operator_name_column():
    """Return a usable optional label column without assuming the mirror schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'operatori'
              AND column_name IN ('Nome', 'Descrizione')
            ORDER BY CASE column_name WHEN 'Nome' THEN 0 ELSE 1 END
            LIMIT 1
            """
        )
        row = cursor.fetchone()
    return row[0] if row else None


@login_required
@require_GET
def seriali_dashboard(request):
    label_column = _operator_name_column()
    operator_label = (
        f"""COALESCE(NULLIF({_trim(f'o."{label_column}"')}, ''), u.cod)"""
        if label_column else "u.cod"
    )
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT DISTINCT {_trim('l."CodReparto"')} AS codice,
                COALESCE(NULLIF({_trim('r."Descrizione"')}, ''), {_trim('l."CodReparto"')}) AS descrizione
            FROM lavorazioni_partite l
            LEFT JOIN reparti r ON {_trim('l."CodReparto"')} = {_trim('r."Codice"')}
            WHERE {ACTIVE_LAVORAZIONE} AND l."CodReparto" IS NOT NULL
              AND {_trim('l."CodReparto"')} <> ''
            ORDER BY codice
        """)
        reparti = [{"codice": row[0], "descrizione": row[1]} for row in cursor.fetchall()]
        union = " UNION ".join(
            f'SELECT {_trim(f"l.{column}")} AS cod FROM lavorazioni_partite l '
            f'WHERE {ACTIVE_LAVORAZIONE} AND l.{column} IS NOT NULL '
            f'AND {_trim(f"l.{column}")} <> \'\''
            for column in OPE_COLS
        )
        cursor.execute(f"""
            SELECT DISTINCT u.cod, {operator_label} AS nome
            FROM ({union}) u
            LEFT JOIN operatori o ON u.cod = {_trim('o."Codice"')}
            ORDER BY nome
        """)
        operatori = [{"codice": row[0], "nome": row[1]} for row in cursor.fetchall()]
    return render(request, "carbon/seriali_dashboard.html", {
        "reparti": reparti, "operatori": operatori,
    })


@login_required
@require_GET
def api_kpi(request):
    cte, outer_where, params = _seriali_query_parts(request)
    raw_where, raw_params = _sql_lavorazioni_filter(request)
    with connection.cursor() as cursor:
        cursor.execute(f"""
            {cte}
            SELECT COUNT(*),
                SUM(CASE WHEN stato_avanzamento = 'COMPLETATO' THEN 1 ELSE 0 END),
                SUM(CASE WHEN stato_avanzamento = 'DA TERMINARE' THEN 1 ELSE 0 END),
                COUNT(DISTINCT cod_reparto)
            FROM seriali WHERE {outer_where}
        """, params)
        seriali = cursor.fetchone()
        cursor.execute(f"""
            SELECT COUNT(*), SUM(CASE WHEN COALESCE(l."Rilavorazione", FALSE) THEN 1 ELSE 0 END)
            FROM lavorazioni_partite l WHERE {raw_where}
        """, raw_params)
        raw = cursor.fetchone()
    return JsonResponse({
        "totale_seriali": seriali[0] or 0, "completati": seriali[1] or 0,
        "da_terminare": seriali[2] or 0, "reparti_coinvolti": seriali[3] or 0,
        "lavorazioni_raw": raw[0] or 0, "rilavorazioni": raw[1] or 0,
    })


def _fmt_operatore(codice, nome):
    cod, nom = (codice or "").strip(), (nome or "").strip()
    return "—" if not cod else (f"{cod} — {nom}" if nom else cod)


@login_required
@require_GET
def api_seriali_lista(request):
    limit = _safe_limit(request, 100, 500)
    cte, outer_where, params = _seriali_query_parts(request)
    name_column = _operator_name_column()
    joins = "\n".join(
        f'LEFT JOIN operatori op{i} ON {_trim(f"s.codope{i}")} = '
        f"""{_trim("op" + str(i) + '."Codice"')}"""
        for i in range(1, 11)
    )
    names = ", ".join(
        f"""{_trim("op" + str(i) + f'."{name_column}"')} AS nome_ope{i}"""
        if name_column else f"NULL AS nome_ope{i}"
        for i in range(1, 11)
    )
    with connection.cursor() as cursor:
        cursor.execute(f"""
            {cte}
            SELECT s.seriale, s.cod_reparto, s.descr_reparto, s.stato_avanzamento,
                s.data_inizio, s.data_fine, s.codart, s.codstampo,
                s.codope1, s.codope2, s.codope3, s.codope4, s.codope5,
                s.codope6, s.codope7, s.codope8, s.codope9, s.codope10, {names}
            FROM seriali s {joins}
            WHERE {outer_where}
            ORDER BY CASE s.stato_avanzamento WHEN 'DA TERMINARE' THEN 0 ELSE 1 END,
                s.data_inizio DESC, s.seriale
            LIMIT {limit}
        """, params)
        rows = cursor.fetchall()

    def fmt_dt(value):
        return value.strftime("%d/%m/%Y %H:%M:%S") if value and value.year > 2000 else "—"

    result = []
    for values in rows:
        row = {
            "seriale": values[0], "cod_reparto": values[1] or "—",
            "descr_reparto": (values[2] or values[1] or "—").strip(),
            "stato": values[3], "data_inizio": fmt_dt(values[4]), "data_fine": fmt_dt(values[5]),
            "codart": values[6] or "—", "codstampo": (values[7] or "").strip() or "—",
        }
        for i in range(1, 11):
            row[f"operatore{i}"] = _fmt_operatore(values[7 + i], values[17 + i])
        result.append(row)
    return JsonResponse({"rows": result, "total": len(result)})


@login_required
@require_GET
def api_seriali_stato(request):
    cte, outer_where, params = _seriali_query_parts(request)
    with connection.cursor() as cursor:
        cursor.execute(f"{cte} SELECT stato_avanzamento, COUNT(*) FROM seriali "
                       f"WHERE {outer_where} GROUP BY stato_avanzamento ORDER BY COUNT(*) DESC", params)
        rows = cursor.fetchall()
    return JsonResponse({"labels": [r[0] for r in rows], "valori": [r[1] for r in rows]})


@login_required
@require_GET
def api_seriali_reparto(request):
    cte, outer_where, params = _seriali_query_parts(request)
    with connection.cursor() as cursor:
        cursor.execute(f"""
            {cte}
            SELECT cod_reparto, descr_reparto,
                SUM(CASE WHEN stato_avanzamento = 'COMPLETATO' THEN 1 ELSE 0 END),
                SUM(CASE WHEN stato_avanzamento = 'DA TERMINARE' THEN 1 ELSE 0 END)
            FROM seriali WHERE {outer_where}
            GROUP BY cod_reparto, descr_reparto ORDER BY cod_reparto
        """, params)
        rows = cursor.fetchall()
    return JsonResponse({
        "labels": [f"{(r[0] or '').strip()} — {(r[1] or '').strip()[:25]}" for r in rows],
        "completati": [r[2] for r in rows], "da_terminare": [r[3] for r in rows],
    })


@login_required
@require_GET
def api_lavorazioni_giorno(request):
    where, params = _sql_lavorazioni_filter(request)
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT CAST(l."Data" AS date), COUNT(*)
            FROM lavorazioni_partite l
            WHERE {where} AND l."Data" IS NOT NULL
            GROUP BY CAST(l."Data" AS date) ORDER BY 1
        """, params)
        rows = cursor.fetchall()
    valid = [(day, count) for day, count in rows if day and day.year > 2000]
    return JsonResponse({"labels": [d.strftime("%d/%m/%Y") for d, _ in valid],
                         "valori": [count for _, count in valid]})


@login_required
@require_GET
def api_lavorazioni_extra(request):
    limit = _safe_limit(request, 12, 20)
    where, params = _sql_lavorazioni_filter(request)
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT {_trim('l."CodLavExtra"')}, COUNT(*)
            FROM lavorazioni_partite l
            WHERE {where} AND l."CodLavExtra" IS NOT NULL AND {_trim('l."CodLavExtra"')} <> ''
            GROUP BY {_trim('l."CodLavExtra"')} ORDER BY COUNT(*) DESC LIMIT {limit}
        """, params)
        rows = cursor.fetchall()
        cursor.execute('SELECT "Cod", "Descrizione" FROM lavorazioni_extra')
        descriptions = {(code or "").strip(): description or code or "" for code, description in cursor.fetchall()}
    return JsonResponse({
        "labels": [(descriptions.get(code, code))[:40] for code, _ in rows],
        "codici": [code for code, _ in rows], "valori": [count for _, count in rows],
    })


@login_required
@require_GET
def api_stampi_opzioni(request):
    da, a = _parse_date(request.GET.get("da")), _parse_date(request.GET.get("a"))
    if not da and not a:
        return JsonResponse({"stampi": [], "richiede_periodo": True})
    clauses, params = [ACTIVE_LAVORAZIONE, 'l."CodStampo" IS NOT NULL', f"""{_trim('l."CodStampo"')} <> ''"""], []
    if da:
        clauses.append('CAST(l."Data" AS date) >= %s')
        params.append(da)
    if a:
        clauses.append('CAST(l."Data" AS date) <= %s')
        params.append(a)
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT {_trim('l."CodStampo"')} FROM lavorazioni_partite l
            WHERE {' AND '.join(clauses)}
            GROUP BY {_trim('l."CodStampo"')} ORDER BY 1
        """, params)
        stampi = [row[0] for row in cursor.fetchall() if row[0]]
    return JsonResponse({"stampi": stampi, "richiede_periodo": False})


def _sql_stampi_join_filter(request):
    """Individual-row filters for stampi queries, including the date interval."""
    return _sql_lavorazioni_filter(request)


@login_required
@require_GET
def api_stampi_seriali(request):
    where, params = _sql_stampi_join_filter(request)
    serial_sum = " + ".join(
        f"CASE WHEN {_trim(f's.{column}')} <> '' THEN 1 ELSE 0 END" for column in SERIAL_COLS
    )
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT {_trim('s."CodiceStampo"')} AS stampo, COUNT(DISTINCT s."ID"), SUM({serial_sum})
            FROM stampi_seriali_partite s
            INNER JOIN lavorazioni_partite l ON s."key_Lav_Partite" = l."Key_lav"
            WHERE s."CodiceStampo" IS NOT NULL AND {_trim('s."CodiceStampo"')} <> ''
              AND {where}
            GROUP BY {_trim('s."CodiceStampo"')}
            ORDER BY COUNT(DISTINCT s."ID") DESC, stampo LIMIT 40
        """, params)
        rows = cursor.fetchall()
    return JsonResponse({"labels": [r[0] for r in rows], "partite": [r[1] for r in rows],
                         "seriali": [r[2] or 0 for r in rows]})


@login_required
@require_GET
def api_catalogo_extra(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*),
                COUNT(*) FILTER (WHERE COALESCE("F_Componente", FALSE)),
                COUNT(*) FILTER (WHERE COALESCE("F_Vincolante", FALSE)),
                COUNT(*) FILTER (WHERE COALESCE("F_RichiediNote", FALSE))
            FROM lavorazioni_extra
        """)
        total, componente, vincolante, richiedi_note = cursor.fetchone()
    return JsonResponse({
        "labels": ["Componente", "Vincolante", "Richiede note", "Standard"],
        "valori": [componente, vincolante, richiedi_note, max(0, total - componente)],
    })


@login_required
@require_GET
def api_codartser_suggest(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"suggestions": []})
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT DISTINCT {_trim('l."CodArtSer"')}
            FROM lavorazioni_partite l
            WHERE {ACTIVE_LAVORAZIONE} AND l."CodArtSer" IS NOT NULL
              AND {_trim('l."CodArtSer"')} LIKE %s
            ORDER BY 1 LIMIT 15
        """, [f"%{query}%"])
        suggestions = [row[0] for row in cursor.fetchall() if row[0]]
    return JsonResponse({"suggestions": suggestions})


@login_required
@require_GET
def api_stampi_dettaglio(request):
    limit = _safe_limit(request, 10, 20)
    where, params = _sql_stampi_join_filter(request)
    serials = ", ".join(_trim(f"s.{column}") for column in SERIAL_COLS[:4])
    group_serials = ", ".join(f"s.{column}" for column in SERIAL_COLS[:4])
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT s."ID", s."CodiceStampo", s."key_Lav_Partite", {serials}, s."CodSacco",
                MAX({_trim('l."CodReparto"')}),
                MAX(COALESCE(NULLIF({_trim('rep."Descrizione"')}, ''), {_trim('l."CodReparto"')}))
            FROM stampi_seriali_partite s
            INNER JOIN lavorazioni_partite l ON s."key_Lav_Partite" = l."Key_lav"
            LEFT JOIN reparti rep ON {_trim('l."CodReparto"')} = {_trim('rep."Codice"')}
            WHERE {where}
            GROUP BY s."ID", s."CodiceStampo", s."key_Lav_Partite", {group_serials}, s."CodSacco"
            ORDER BY MAX(l."Data") DESC, s."ID" DESC LIMIT {limit}
        """, params)
        rows = cursor.fetchall()
    return JsonResponse({"rows": [{
        "id": row[0], "stampo": (row[1] or "").strip(),
        "key_lav": (row[2] or "")[:24], "seriali": [item for item in row[3:7] if item],
        "num_seriali": len([item for item in row[3:7] if item]),
        "sacco": (row[7] or "").strip() or "—",
        "cod_reparto": (row[8] or "").strip() or "—",
        "descr_reparto": (row[9] or "").strip() or "—",
    } for row in rows]})
