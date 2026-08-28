from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db import connection
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mirror_crud import mirror_row_to_campi, stamp_modifica
from apps.core.pagination import PER_PAGE_OPTIONS, resolve_per_page
from apps.core.export_list import RawExportListMixin
from apps.core.print_list import RawPrintListView
from apps.core.sorting import resolve_sort
from apps.operatori.forms import OperatoreForm
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


def _optional_col_sql(columns: list[str], *candidates: str) -> str:
    for col in candidates:
        if col in columns:
            return f'NULLIF(TRIM("{col}"::text), \'\')'
    return "NULL"


def _fetch_operatori_page(columns: list[str], q: str, page: int, per_page: int, *, order_sql: str | None = None):
    where_sql = ""
    params: list = []
    if q:
        conditions, params = _search_conditions(columns, q)
        where_sql = "WHERE " + conditions

    label_sql = _label_sql(columns)
    email_sql = _optional_col_sql(columns, "email", "E_Mail")
    reparto_sql = _optional_col_sql(columns, "Reparto")
    if not order_sql:
        order_sql = f'ORDER BY {_label_sql(columns)} NULLS LAST, "Codice"'

    with connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM operatori {where_sql}", params)
        total = cur.fetchone()[0]

        offset = max(page - 1, 0) * per_page
        cur.execute(
            f'SELECT "Codice", {label_sql} AS label, {email_sql} AS email, {reparto_sql} AS reparto '
            f"FROM operatori {where_sql} {order_sql} LIMIT %s OFFSET %s",
            [*params, per_page, offset],
        )
        rows = [
            {
                "codice": row[0],
                "label": row[1],
                "email": row[2],
                "reparto": row[3],
            }
            for row in cur.fetchall()
        ]

    return rows, total


def _operatori_order_sql(columns: list[str], sort: str | None, direction: str) -> str:
    label_sql = _label_sql(columns)
    mapping = {
        "codice": '"Codice"',
        "label": f"{label_sql}",
        "email": _optional_col_sql(columns, "email", "E_Mail"),
        "reparto": _optional_col_sql(columns, "Reparto"),
    }
    expr = mapping.get(sort) or label_sql
    if expr == "NULL":
        expr = label_sql
    dir_sql = "DESC" if direction == "desc" else "ASC"
    return f'ORDER BY {expr} {dir_sql} NULLS LAST, "Codice" ASC'


def _fetch_operatori_all(columns: list[str], q: str) -> list[dict]:
    """Tutti gli operatori (filtro ricerca incluso), ordinati per stampa QR."""
    where_sql = ""
    params: list = []
    if q:
        conditions, params = _search_conditions(columns, q)
        where_sql = "WHERE " + conditions

    label_sql = _label_sql(columns)
    order_sql = f'ORDER BY {label_sql} NULLS LAST, "Codice"'

    with connection.cursor() as cur:
        cur.execute(
            f'SELECT "Codice", {label_sql} AS label FROM operatori {where_sql} {order_sql}',
            params,
        )
        return [{"codice": row[0], "label": row[1]} for row in cur.fetchall()]


def _fetch_operatori_print_all(columns: list[str], q: str, *, order_sql: str | None = None) -> list[dict]:
    where_sql = ""
    params: list = []
    if q:
        conditions, params = _search_conditions(columns, q)
        where_sql = "WHERE " + conditions

    label_sql = _label_sql(columns)
    email_sql = _optional_col_sql(columns, "email", "E_Mail")
    reparto_sql = _optional_col_sql(columns, "Reparto")
    if not order_sql:
        order_sql = f'ORDER BY {label_sql} NULLS LAST, "Codice"'

    with connection.cursor() as cur:
        cur.execute(
            f'SELECT "Codice", {label_sql} AS label, {email_sql} AS email, {reparto_sql} AS reparto '
            f"FROM operatori {where_sql} {order_sql}",
            params,
        )
        return [
            {
                "codice": row[0],
                "label": row[1],
                "email": row[2],
                "reparto": row[3],
            }
            for row in cur.fetchall()
        ]


class OperatoreListView(LoginRequiredMixin, View):
    template_name = "operatori/operatore_list.html"

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        page = max(int(request.GET.get("page") or 1), 1)
        per_page = resolve_per_page(request)
        columns = _table_columns()
        sort, direction = resolve_sort(
            request,
            allowed=("codice", "label", "email", "reparto"),
            default_sort="label",
            default_dir="asc",
        )
        order_sql = _operatori_order_sql(columns, sort, direction)

        try:
            rows, total = _fetch_operatori_page(
                columns, q, page, per_page, order_sql=order_sql
            )
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
                "per_page_options": PER_PAGE_OPTIONS,
                "sort": sort or "",
                "dir": direction,
            },
        )


class OperatorePrintListView(RawPrintListView):
    print_title = "Operatori"
    print_subtitle = "Elenco operatori"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "label", "label": "Nominativo"},
        {"field": "reparto", "label": "Reparto"},
        {"field": "email", "label": "Email"},
    )

    def get_object_list(self, request):
        q = (request.GET.get("q") or "").strip()
        columns = _table_columns()
        sort, direction = resolve_sort(
            request,
            allowed=("codice", "label", "email", "reparto"),
            default_sort="label",
            default_dir="asc",
        )
        order_sql = _operatori_order_sql(columns, sort, direction)
        try:
            return _fetch_operatori_print_all(columns, q, order_sql=order_sql)
        except Exception:
            return []


class OperatoreExportListView(RawExportListMixin, OperatorePrintListView):
    export_filename = "operatori"


class OperatoreQrPrintView(LoginRequiredMixin, View):
    """Pagina stampabile con QR code DIP-{codice} e nominativo."""

    template_name = "operatori/operatore_qr_print.html"

    def get(self, request):
        from apps.operatori.qrcode_util import qr_payload_operatore, qr_png_data_uri

        q = (request.GET.get("q") or "").strip()
        columns = _table_columns()
        try:
            rows = _fetch_operatori_all(columns, q)
        except Exception:
            rows = []

        badges = []
        for row in rows:
            codice = str(row.get("codice") or "").strip()
            if not codice:
                continue
            payload = qr_payload_operatore(codice)
            badges.append(
                {
                    "codice": codice,
                    "label": (row.get("label") or "").strip() or codice,
                    "payload": payload,
                    "qr_src": qr_png_data_uri(payload, box_size=4, border=1),
                }
            )

        per_page = 22
        pages = [
            badges[i : i + per_page] for i in range(0, len(badges), per_page)
        ] or [[]]

        return render(
            request,
            self.template_name,
            {
                "pages": pages,
                "badges": badges,
                "q": q,
                "totale": len(badges),
                "per_page": per_page,
            },
        )


class OperatoreDetailView(LoginRequiredMixin, View):
    template_name = "operatori/operatore_detail.html"

    def get(self, request, codice):
        operatore = get_object_or_404(Operatore, codice=codice)
        row = fetch_operatore_row(codice) or []
        campi = mirror_row_to_campi(row)
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


class OperatoreCreateView(LoginRequiredMixin, View):
    template_name = "operatori/operatore_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": OperatoreForm(),
                "is_create": True,
                "page_heading": "Nuovo operatore",
            },
        )

    def post(self, request):
        form = OperatoreForm(request.POST)
        if form.is_valid():
            operatore = form.save(commit=False)
            stamp_modifica(operatore)
            operatore.save()
            messages.success(request, f"Operatore {operatore.codice} creato.")
            return redirect("operatori:detail", codice=operatore.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo operatore",
            },
        )


class OperatoreUpdateView(LoginRequiredMixin, View):
    template_name = "operatori/operatore_form.html"

    def get_object(self, codice):
        return get_object_or_404(Operatore, pk=codice)

    def get(self, request, codice):
        operatore = self.get_object(codice)
        form = OperatoreForm(instance=operatore, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "operatore": operatore,
                "is_create": False,
                "page_heading": "Modifica operatore",
            },
        )

    def post(self, request, codice):
        operatore = self.get_object(codice)
        form = OperatoreForm(request.POST, instance=operatore, codice_readonly=True)
        if form.is_valid():
            operatore = form.save(commit=False)
            stamp_modifica(operatore)
            operatore.save()
            messages.success(request, f"Operatore {operatore.codice} aggiornato.")
            return redirect("operatori:detail", codice=operatore.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "operatore": operatore,
                "is_create": False,
                "page_heading": "Modifica operatore",
            },
        )


class OperatoreDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        operatore = get_object_or_404(Operatore, pk=codice)
        label = operatore.codice
        operatore.delete()
        messages.success(request, f"Operatore {label} eliminato.")
        return redirect("operatori:list")


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
