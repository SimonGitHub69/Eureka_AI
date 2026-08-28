"""Export tabelle in CSV o XLSX."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any, Iterable, Sequence

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"


def normalize_export_fmt(fmt: str | None) -> str:
    value = (fmt or "csv").strip().lower()
    if value in {"xlsx", "xls", "excel"}:
        return "xlsx"
    return "csv"


def wants_export_bridge(request: HttpRequest) -> bool:
    """Disattivata: export gestito dal foglio Scarica / Apri in Numbers."""
    return False


def wants_open_inline(request: HttpRequest) -> bool:
    """True → anteprima Numbers (inline). False → download classico (attachment)."""
    return (request.GET.get("open") or "").strip().lower() in {"1", "true", "yes"}


def export_bridge_response(request: HttpRequest, *, title: str = "Esportazione") -> HttpResponse:
    """Tenuta per compatibilità con le view; non usata."""
    back_params = request.GET.copy()
    for key in ("export", "fmt", "bridge", "dl", "open"):
        back_params.pop(key, None)
    query = back_params.urlencode()
    back_url = f"{request.path}?{query}" if query else request.path
    return render(
        request,
        "core/export_bridge.html",
        {
            "export_title": title,
            "download_url": back_url,
            "back_url": back_url,
            "file_ext": "csv",
            "file_label": "CSV",
        },
    )


def build_xlsx_bytes(
    *,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    sheet_title: str = "Dati",
) -> bytes:
    """Genera un workbook XLSX in memoria."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = (sheet_title or "Dati")[:31]
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_csv_bytes(
    *,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    delimiter: str = ";",
) -> bytes:
    """CSV con BOM UTF-8 (default separatore ';' per Excel italiano)."""
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def export_table(
    *,
    filename: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    fmt: str = "csv",
    sheet_title: str = "Dati",
    as_attachment: bool = True,
) -> HttpResponse:
    """
    Genera CSV (BOM UTF-8, separatore ;) o XLSX.
    as_attachment=True  → Scarica / File (Content-Disposition: attachment)
    as_attachment=False → Apri in Numbers (Content-Disposition: inline)
    """
    fmt = normalize_export_fmt(fmt)
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    disposition = "attachment" if as_attachment else "inline"

    if fmt == "xlsx":
        content = build_xlsx_bytes(
            headers=headers, rows=rows, sheet_title=sheet_title
        )
        response = HttpResponse(content, content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = f'{disposition}; filename="{stem}.xlsx"'
        response["X-Content-Type-Options"] = "nosniff"
        return response

    csv_content_type = (
        "application/octet-stream" if as_attachment else CSV_CONTENT_TYPE
    )
    response = HttpResponse(
        build_csv_bytes(headers=headers, rows=rows),
        content_type=csv_content_type,
    )
    response["Content-Disposition"] = f'{disposition}; filename="{stem}.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _csv_cell(value: Any) -> Any:
    if isinstance(value, float):
        return f"{value:.2f}".replace(".", ",")
    return value
