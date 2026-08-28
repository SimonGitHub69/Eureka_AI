from __future__ import annotations

from apps.core.sync_4d import SyncResult, quote_ident, sync_tables

TABLES = (
    {
        "source": "MovimentiT",
        "target": "movimentit",
        "pk": "ID_Testa",
        "page_by_pk": True,
        "post_create": lambda cur, target: cur.execute(
            f"CREATE INDEX IF NOT EXISTS movimentit_datareg_idx "
            f"ON {quote_ident(target)} ({quote_ident('DataRegistraz')});"
        ),
    },
    {
        "source": "MovimentiT_Dettaglio",
        "target": "movimentit_dettaglio",
        "pk": "ID",
        "page_by_pk": True,
        "post_create": lambda cur, target: cur.execute(
            f"CREATE INDEX IF NOT EXISTS movimentit_dettaglio_id_testa_idx "
            f"ON {quote_ident(target)} ({quote_ident('id_added_by_converter')});"
        ),
    },
)


def sync_movimenti(
    batch_size: int = 2000, only: str | None = None, full: bool = False
) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione MovimentiT / MovimentiT_Dettaglio completata.",
    )
