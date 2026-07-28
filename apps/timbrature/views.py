from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db import connection
from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.core.pagination import resolve_per_page
from apps.timbrature.models import Timbratura
from apps.timbrature.presenze import (
    default_period,
    parse_presenza_row,
    period_from_request,
)
from apps.timbrature.sync import sync_timbrature

SELECT_SQL = """
SELECT
    t."ID",
    t."Cod_Operatore",
    t."Data",
    t."E1_Ora", t."U1_Ora",
    t."E2_Ora", t."U2_Ora",
    t."E3_Ora", t."U3_Ora",
    t."Note",
    t."E1_Ora_Rett", t."U1_Ora_Rett",
    t."E2_Ora_Rett", t."U2_Ora_Rett",
    t."E3_Ora_Rett", t."U3_Ora_Rett",
    t."Scheda_Validata",
    t.synced_at,
    COALESCE(NULLIF(TRIM(o."Nome"), ''), t."Cod_Operatore") AS operatore_nome,
    COALESCE(NULLIF(TRIM(o."Reparto"), ''), '') AS reparto
FROM timbrature t
LEFT JOIN operatori o ON TRIM(o."Codice") = TRIM(t."Cod_Operatore")
"""


def _row_to_dict(columns: list[str], row: tuple) -> dict:
    return dict(zip(columns, row))


def _fetch_operatori_options(selected: str = "") -> list[dict]:
    """Opzioni filtro operatore: solo attivi; tiene il selezionato anche se disattivato."""
    selected = (selected or "").strip()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT t."Cod_Operatore",
                       COALESCE(NULLIF(TRIM(o."Nome"), ''), t."Cod_Operatore") AS nome
                FROM timbrature t
                LEFT JOIN operatori o ON TRIM(o."Codice") = TRIM(t."Cod_Operatore")
                WHERE COALESCE(o."OperatoreDisattivo", FALSE) IS FALSE
                   OR (%s <> '' AND TRIM(t."Cod_Operatore") = %s)
                ORDER BY nome, t."Cod_Operatore"
                """,
                [selected, selected],
            )
            return [{"codice": r[0], "nome": r[1]} for r in cur.fetchall()]
    except Exception:
        return []


def _build_filters(
    *,
    data_da: date,
    data_a: date,
    operatore: str,
    q: str,
    stato: str,
) -> tuple[str, list]:
    clauses = ['t."Data"::date >= %s', 't."Data"::date <= %s']
    params: list = [data_da, data_a]

    if operatore:
        clauses.append('TRIM(t."Cod_Operatore") = %s')
        params.append(operatore.strip())

    if q:
        clauses.append(
            '(t."Cod_Operatore" ILIKE %s OR o."Nome" ILIKE %s OR o."NomeBreve" ILIKE %s OR o."Reparto" ILIKE %s)'
        )
        like = f"%{q}%"
        params.extend([like, like, like, like])

    if stato == "validate":
        clauses.append('t."Scheda_Validata" IS TRUE')
    elif stato == "non_validate":
        clauses.append('COALESCE(t."Scheda_Validata", FALSE) IS FALSE')

    return " AND ".join(clauses), params


def _fetch_kpi(where_sql: str, params: list) -> dict:
    sql = f"""
        SELECT
            COUNT(*) AS giornate,
            COUNT(DISTINCT t."Cod_Operatore") AS operatori,
            SUM(
                GREATEST(0, EXTRACT(EPOCH FROM (
                    COALESCE(NULLIF(t."U1_Ora_Rett", TIME '00:00'), NULLIF(t."U1_Ora", TIME '00:00'))
                    - COALESCE(NULLIF(t."E1_Ora_Rett", TIME '00:00'), NULLIF(t."E1_Ora", TIME '00:00'))
                )) / 60)
                + GREATEST(0, EXTRACT(EPOCH FROM (
                    COALESCE(NULLIF(t."U2_Ora_Rett", TIME '00:00'), NULLIF(t."U2_Ora", TIME '00:00'))
                    - COALESCE(NULLIF(t."E2_Ora_Rett", TIME '00:00'), NULLIF(t."E2_Ora", TIME '00:00'))
                )) / 60)
                + GREATEST(0, EXTRACT(EPOCH FROM (
                    COALESCE(NULLIF(t."U3_Ora_Rett", TIME '00:00'), NULLIF(t."U3_Ora", TIME '00:00'))
                    - COALESCE(NULLIF(t."E3_Ora_Rett", TIME '00:00'), NULLIF(t."E3_Ora", TIME '00:00'))
                )) / 60)
            )::bigint AS minuti,
            SUM(CASE WHEN COALESCE(t."Scheda_Validata", FALSE) IS FALSE THEN 1 ELSE 0 END) AS da_validare
        FROM timbrature t
        LEFT JOIN operatori o ON TRIM(o."Codice") = TRIM(t."Cod_Operatore")
        WHERE {where_sql}
    """
    try:
        with connection.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            minuti = int(row[2] or 0)
            return {
                "giornate": int(row[0] or 0),
                "operatori": int(row[1] or 0),
                "minuti_totali": minuti,
                "ore_totali": round(minuti / 60, 1),
                "da_validare": int(row[3] or 0),
            }
    except Exception:
        return {
            "giornate": 0,
            "operatori": 0,
            "minuti_totali": 0,
            "ore_totali": 0.0,
            "da_validare": 0,
        }


def _fetch_presenze(where_sql: str, params: list, page: int, per_page: int):
    base_from = f"{SELECT_SQL} WHERE {where_sql}"
    order_sql = 'ORDER BY t."Data" DESC, operatore_nome ASC, t."ID" DESC'

    with connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM timbrature t LEFT JOIN operatori o ON TRIM(o.\"Codice\") = TRIM(t.\"Cod_Operatore\") WHERE {where_sql}", params)
        total = cur.fetchone()[0]

        offset = max(page - 1, 0) * per_page
        cur.execute(
            f"{base_from} {order_sql} LIMIT %s OFFSET %s",
            [*params, per_page, offset],
        )
        columns = [col[0] for col in cur.description]
        presenze = [parse_presenza_row(_row_to_dict(columns, row)) for row in cur.fetchall()]

    return presenze, total


def _fetch_presenza(pk: int):
    with connection.cursor() as cur:
        cur.execute(f"{SELECT_SQL} WHERE t.\"ID\" = %s", [pk])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
        return parse_presenza_row(_row_to_dict(columns, row))


def _resolve_period(request) -> tuple[date, date, str, str]:
    preset = (request.GET.get("preset") or "").strip()
    today = date.today()

    if preset == "oggi":
        start = end = today
    elif preset == "settimana":
        end = today
        start = today - timedelta(days=today.weekday())
    elif preset == "mese":
        start, end = default_period()
    else:
        data_da_str = (request.GET.get("data_da") or "").strip()
        data_a_str = (request.GET.get("data_a") or "").strip()
        if not data_da_str and not data_a_str:
            start, end = default_period()
        else:
            start, end = period_from_request(data_da_str, data_a_str)

    return start, end, start.isoformat(), end.isoformat()


class TimbraturaListView(LoginRequiredMixin, View):
    template_name = "timbrature/presenze_list.html"

    def get(self, request):
        operatore = (request.GET.get("operatore") or "").strip()
        q = (request.GET.get("q") or "").strip()
        stato = (request.GET.get("stato") or "").strip()
        data_da, data_a, data_da_str, data_a_str = _resolve_period(request)

        page = max(int(request.GET.get("page") or 1), 1)
        per_page = resolve_per_page(request)
        where_sql, params = _build_filters(
            data_da=data_da,
            data_a=data_a,
            operatore=operatore,
            q=q,
            stato=stato,
        )

        try:
            presenze, total = _fetch_presenze(where_sql, params, page, per_page)
            kpi = _fetch_kpi(where_sql, params)
        except Exception:
            presenze, total = [], 0
            kpi = _fetch_kpi("FALSE", [])

        paginator = Paginator(range(total), per_page)
        page_obj = paginator.get_page(page)

        params_qs = request.GET.copy()
        params_qs.pop("page", None)
        has_filters = bool(q or operatore or stato)

        return render(
            request,
            self.template_name,
            {
                "presenze": presenze,
                "page_obj": page_obj,
                "paginator": paginator,
                "is_paginated": paginator.num_pages > 1,
                "filter_query": params_qs.urlencode(),
                "data_da_str": data_da_str,
                "data_a_str": data_a_str,
                "operatore": operatore,
                "operatori_options": _fetch_operatori_options(operatore),
                "q": q,
                "stato": stato,
                "has_filters": has_filters,
                "totale": total,
                "per_page": per_page,
                "per_page_options": (25, 50, 100),
                "kpi": kpi,
            },
        )


class TimbraturaDetailView(LoginRequiredMixin, View):
    template_name = "timbrature/presenza_detail.html"

    def get(self, request, pk):
        get_object_or_404(Timbratura, id=pk)
        presenza = _fetch_presenza(int(pk))
        if presenza is None:
            get_object_or_404(Timbratura, id=pk)

        params = request.GET.copy()
        back_query = params.urlencode()
        return render(
            request,
            self.template_name,
            {
                "presenza": presenza,
                "back_query": back_query,
            },
        )


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncTimbratureView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "timbrature/sync_timbrature.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "timbrature_count": _pg_table_count("timbrature"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_timbrature()
        message = "\n".join(t.message for t in result.tables) or result.message

        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)

        return render(
            request,
            self.template_name,
            self.get_context(last_message=message),
        )
