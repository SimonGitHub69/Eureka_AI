"""Export tabelle in CSV o XLSX."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any, Iterable, Sequence

from django.http import HttpResponse

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def normalize_export_fmt(fmt: str | None) -> str:
    value = (fmt or "csv").strip().lower()
    if value in {"xlsx", "xls", "excel"}:
        return "xlsx"
    return "csv"


def export_table(
    *,
    filename: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    fmt: str = "csv",
    sheet_title: str = "Dati",
) -> HttpResponse:
    """
    Genera un download CSV (BOM UTF-8, separatore ;) o XLSX.
    Per XLSX i valori numerici restano numeri (non stringhe italianizzate).
    """
    fmt = normalize_export_fmt(fmt)
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename

    if fmt == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = (sheet_title or "Dati")[:31]
        ws.append(list(headers))
        for row in rows:
            ws.append(list(row))
        buffer = BytesIO()
        wb.save(buffer)
        response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = f'attachment; filename="{stem}.xlsx"'
        return response

    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{stem}.csv"'
    response.write("\ufeff")
    response.write(buffer.getvalue())
    return response


def _csv_cell(value: Any) -> Any:
    if isinstance(value, float):
        return f"{value:.2f}".replace(".", ",")
    return value
