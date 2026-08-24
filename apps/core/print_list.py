"""Infrastructure condivisa per stampa elenco tabelle (A4, multipagina)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.aziende.configurazione import resolve_print_azienda_context
from apps.core.sorting import SortableListMixin


def format_it_number(value, *, decimals: int = 2) -> str:
    """Formatta un numero in stile italiano (1.234,56) con arrotondamento commerciale."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    if not number.is_finite():
        return "—"
    quant = Decimal("1").scaleb(-decimals) if decimals else Decimal("1")
    number = number.quantize(quant, rounding=ROUND_HALF_UP)
    sign = "-" if number < 0 else ""
    number = abs(number)
    text = f"{number:.{decimals}f}" if decimals else f"{int(number)}"
    intpart, _, frac = text.partition(".")
    groups: list[str] = []
    while intpart:
        groups.append(intpart[-3:])
        intpart = intpart[:-3]
    grouped = ".".join(reversed(groups)) or "0"
    if decimals:
        return f"{sign}{grouped},{frac}"
    return f"{sign}{grouped}"


def resolve_column_value(obj, column: dict) -> str:
    """Estrae il valore di cella da modello o dict."""
    getter = column.get("value")
    if callable(getter):
        val = getter(obj)
    else:
        field = column.get("field") or column.get("attr")
        if field is None:
            val = None
        elif isinstance(obj, dict):
            val = obj.get(field)
        else:
            val = obj
            for part in field.split("__"):
                if val is None:
                    break
                val = getattr(val, part, None)

    if column.get("decimals") is not None or column.get("number"):
        if val is None or val == "":
            return "—"
        return format_it_number(val, decimals=int(column.get("decimals") or 2))

    if val is None or val == "":
        return "—"

    if column.get("bool"):
        return "Sì" if val else "No"
    if column.get("percent"):
        return f"{val}%"
    if column.get("date"):
        try:
            return val.strftime("%d/%m/%Y")
        except (AttributeError, TypeError, ValueError):
            return str(val)

    return str(val)


def build_print_rows(object_list, columns) -> tuple[list[str], list[list[str]]]:
    headers = [col["label"] for col in columns]
    rows = [
        [resolve_column_value(obj, col) for col in columns] for obj in object_list
    ]
    return headers, rows


def print_header_cells(columns) -> list[dict[str, str]]:
    return [
        {
            "label": col["label"],
            "align": col.get("align", "start"),
            "nowrap": bool(col.get("nowrap")),
        }
        for col in columns
    ]


def structured_print_row(
    cells: list[str],
    columns,
    *,
    row_class: str = "",
    cell_classes: list[str] | None = None,
    row_title: str = "",
) -> dict:
    aligns = [col.get("align", "start") for col in columns]
    nowraps = [bool(col.get("nowrap")) for col in columns]
    extras = list(cell_classes or [])
    while len(extras) < len(cells):
        extras.append("")
    return {
        "cells": [
            {
                "text": text,
                "align": aligns[i],
                "nowrap": nowraps[i],
                "cell_class": extras[i],
            }
            for i, text in enumerate(cells)
        ],
        "row_class": row_class,
        "row_title": row_title,
    }


class PrintListView(LoginRequiredMixin, SortableListMixin, ListView):
    """
    Vista stampa elenco: tutti i record filtrati (no paginazione), ordinamento da GET.
    """

    template_name = "base/print_layout.html"
    context_object_name = "object_list"
    paginate_by = None

    print_title = ""
    print_subtitle = ""
    print_columns: tuple[dict, ...] = ()
    # "liste" = logo generale; "documenti" = logo stampe documenti (+ fallback)
    print_branding = "liste"

    def get_print_queryset(self):
        raise NotImplementedError

    def get_queryset(self):
        return self.apply_sorting(self.get_print_queryset())

    def get_print_subtitle(self) -> str:
        return self.print_subtitle

    def get_filter_summary(self) -> str:
        parts: list[str] = []
        q = (self.request.GET.get("q") or "").strip()
        if q:
            parts.append(f'Ricerca: "{q}"')
        return " · ".join(parts)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        object_list = list(context.get(self.context_object_name, []))
        headers, rows = build_print_rows(object_list, self.print_columns)
        context.update(
            {
                "print_title": self.print_title,
                "print_subtitle": self.get_print_subtitle(),
                "print_headers": headers,
                "print_rows": rows,
                "print_count": len(rows),
                "print_date": timezone.localdate(),
                "print_filter_summary": self.get_filter_summary(),
                **resolve_print_azienda_context(branding=self.print_branding),
            }
        )
        return context


class MirrorPrintListView(PrintListView):
    """Stampa per tabelle mirror 4D con funzione filtro condivisa con la lista."""

    filter_queryset = None

    def get_print_queryset(self):
        if self.filter_queryset is None:
            raise NotImplementedError("filter_queryset required")
        return self.filter_queryset(self.request)


class RawPrintListView(LoginRequiredMixin, View):
    """Stampa elenco da righe dict/dataclass (es. query SQL raw)."""

    template_name = "base/print_layout.html"
    print_title = ""
    print_subtitle = ""
    print_columns: tuple[dict, ...] = ()
    print_branding = "liste"

    def get_object_list(self, request):
        raise NotImplementedError

    def get_filter_summary(self, request) -> str:
        q = (request.GET.get("q") or "").strip()
        if q:
            return f'Ricerca: "{q}"'
        return ""

    def get(self, request):
        from django.shortcuts import render

        object_list = self.get_object_list(request)
        headers, rows = build_print_rows(object_list, self.print_columns)
        return render(
            request,
            self.template_name,
            {
                "print_title": self.print_title,
                "print_subtitle": self.print_subtitle,
                "print_headers": headers,
                "print_rows": rows,
                "print_count": len(rows),
                "print_date": timezone.localdate(),
                "print_filter_summary": self.get_filter_summary(request),
                **resolve_print_azienda_context(branding=self.print_branding),
            },
        )
