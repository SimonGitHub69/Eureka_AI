from __future__ import annotations

from apps.core.sync_4d import SyncResult, quote_ident, sync_tables

TABLES = (
    {
        "source": "Valuta",
        "target": "valuta",
        "pk": "Codice",
    },
    {
        "source": "Valuta_Det",
        "target": "valuta_det",
        "pk": "ID",
        "post_create": lambda cur, target: cur.execute(
            f"CREATE INDEX IF NOT EXISTS valuta_det_cod_valuta_idx "
            f"ON {quote_ident(target)} ({quote_ident('Cod_Valuta')});"
        ),
    },
)


def sync_valute(
    batch_size: int = 2000, only: str | None = None, full: bool = False
) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Valuta / Valuta_Det completata.",
    )
