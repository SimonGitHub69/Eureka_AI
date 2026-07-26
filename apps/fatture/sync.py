from __future__ import annotations

from apps.core.sync_4d import SyncResult, quote_ident, sync_tables

TABLES = (
    {
        "source": "Fatture",
        "target": "fatture",
        "pk": "ID_Testa",
    },
    {
        "source": "Fatture_Dettaglio",
        "target": "fatture_dettaglio",
        "pk": "ID",
        "post_create": lambda cur, target: cur.execute(
            f"CREATE INDEX IF NOT EXISTS fatture_dettaglio_id_testa_idx "
            f"ON {quote_ident(target)} ({quote_ident('id_added_by_converter')});"
        ),
    },
)


def sync_fatture(batch_size: int = 2000, only: str | None = None) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        success_message="Sincronizzazione Fatture / Fatture_Dettaglio completata.",
    )
