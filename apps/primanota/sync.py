from __future__ import annotations

from apps.core.sync_4d import SyncResult, quote_ident, sync_tables

TABLES = (
    {
        "source": "Primanota",
        "target": "primanota",
        "pk": "ID",
        "page_by_pk": True,
        "post_create": lambda cur, target: cur.execute(
            f"CREATE INDEX IF NOT EXISTS primanota_datareg_idx "
            f"ON {quote_ident(target)} ({quote_ident('DataReg')});"
        ),
    },
    {
        "source": "Primanota_Dettaglio",
        "target": "primanota_dettaglio",
        "pk": "ID",
        "page_by_pk": True,
        "post_create": lambda cur, target: cur.execute(
            f"CREATE INDEX IF NOT EXISTS primanota_dettaglio_id_testa_idx "
            f"ON {quote_ident(target)} ({quote_ident('id_added_by_converter')});"
        ),
    },
)


def sync_primanota(
    batch_size: int = 2000, only: str | None = None, full: bool = False
) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Primanota / Primanota_Dettaglio completata.",
    )
