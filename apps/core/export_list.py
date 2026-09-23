"""Infrastructure condivisa per export elenco tabelle (XLSX)."""

from __future__ import annotations

from django.utils import timezone

from apps.core.export import export_table
from apps.core.print_list import build_print_rows


class ExportListMixin:
    """
    Export XLSX riusando queryset, colonne e ordinamento della vista stampa
    (PrintListView / MirrorPrintListView).
    """

    export_filename = ""
    export_sheet_title = "Dati"

    def get_export_filename_stem(self) -> str:
        base = self.export_filename or "export"
        return f"{base}_{timezone.localdate():%Y-%m-%d}"

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        headers, rows = build_print_rows(list(self.object_list), self.print_columns)
        return export_table(
            filename=self.get_export_filename_stem(),
            headers=headers,
            rows=rows,
            fmt="xlsx",
            sheet_title=self.export_sheet_title,
            as_attachment=True,
        )


class RawExportListMixin:
    """Export CSV/XLSX per viste stampa raw (query SQL / dataclass)."""

    export_filename = ""
    export_sheet_title = "Dati"
    export_default_fmt = "xlsx"

    def get_export_filename_stem(self) -> str:
        base = self.export_filename or "export"
        return f"{base}_{timezone.localdate():%Y-%m-%d}"

    def get_export_fmt(self, request) -> str:
        from apps.core.export import normalize_export_fmt

        raw = request.GET.get("fmt") or request.GET.get("export") or self.export_default_fmt
        return normalize_export_fmt(raw)

    def get(self, request):
        from apps.core.export import export_table

        object_list = self.get_object_list(request)
        headers, rows = build_print_rows(object_list, self.print_columns)
        return export_table(
            filename=self.get_export_filename_stem(),
            headers=headers,
            rows=rows,
            fmt=self.get_export_fmt(request),
            sheet_title=self.export_sheet_title,
            as_attachment=True,
        )
