from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db import connection
from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.core.pagination import resolve_per_page
from apps.operatori.models import Operatore
from apps.operatori.sync import sync_operatori

LABEL_COLUMNS = (
    "Nome",
    "Cognome",
    "Descrizione",
    "RagioneSociale",
    "RagioneSociale1",
    "email",
    "E_Mail",
    "UserName",
)


def _table_columns() -> list[str]:
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                ["operatori"],
            )
            return [row[0] for row in cur.fetchall()]
    except Exception:
        return []


def _label_sql(columns: list[str]) -> str:
    parts = [f'NULLIF(TRIM("{col}"::text), \'\')' for col in LABEL_COLUMNS if col in columns]
    if not parts:
        return "NULL"
    return f"COALESCE({', '.join(parts)})"


def _search_conditions(columns: list[str], q: str) -> tuple[str, list]:
    params: list[str] = []
    conditions = ['"Codice" ILIKE %s']
    params.append(f"%{q}%")
    for col in LABEL_COLUMNS:
        if col in columns:
            conditions.append(f'"{col}" ILIKE %s')
            params.append(f"%{q}%")
    return " OR ".join(conditions), params


def fetch_operatore_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM operatori WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


def _fetch_operatori_page(columns: list[str], q: str, page: int, per_page: int):
    where_sql = ""
    params: list = []
    if q:
        conditions, params = _search_conditions(columns, q)
        where_sql = "WHERE " + conditions

    label_sql = _label_sql(columns)
    order_sql = f'ORDER BY {_label_sql(columns)} NULLS LAST, "Codice"'

    with connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM operatori {where_sql}", params)
        total = cur.fetchone()[0]

        offset = max(page - 1, 0) * per_page
        cur.execute(
            f'SELECT "Codice", {label_sql} AS label FROM operatori {where_sql} {order_sql} LIMIT %s OFFSET %s',
            [*params, per_page, offset],
        )
        rows = [{"codice": row[0], "label": row[1]} for row in cur.fetchall()]

    return rows, total


class OperatoreListView(LoginRequiredMixin, View):
    template_name = "operatori/operatore_list.html"

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        page = max(int(request.GET.get("page") or 1), 1)
        per_page = resolve_per_page(request)
        columns = _table_columns()

        try:
            rows, total = _fetch_operatori_page(columns, q, page, per_page)
        except Exception:
            rows, total = [], 0

        paginator = Paginator(range(total), per_page)
        page_obj = paginator.get_page(page)

        params = request.GET.copy()
        params.pop("page", None)
        return render(
            request,
            self.template_name,
            {
                "operatori": rows,
                "page_obj": page_obj,
                "paginator": paginator,
                "is_paginated": paginator.num_pages > 1,
                "filter_query": params.urlencode(),
                "q": q,
                "has_filters": bool(q),
                "totale": total,
                "per_page": per_page,
                "per_page_options": (25, 50, 100),
            },
        )


class OperatoreDetailView(LoginRequiredMixin, View):
    template_name = "operatori/operatore_detail.html"

    def get(self, request, codice):
        operatore = get_object_or_404(Operatore, codice=codice)
        row = fetch_operatore_row(codice) or []
        campi = [
            (name, value)
            for name, value in row
            if name != "synced_at" and value not in (None, "")
        ]
        label = next((value for name, value in row if name in LABEL_COLUMNS and value), None)
        synced_at = next((value for name, value in row if name == "synced_at"), None)
        return render(
            request,
            self.template_name,
            {
                "operatore": operatore,
                "label": label,
                "synced_at": synced_at,
                "campi": campi,
            },
        )


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncOperatoriView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "operatori/sync_operatori.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "operatori_count": _pg_table_count("operatori"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_operatori()
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
