from __future__ import annotations

from apps.core.sync_4d import SyncResult, sync_tables

TABLES = (
    {
        "source": "Depositi",
        "target": "depositi",
        "pk": "Numero",
    },
)


def sync_depositi(batch_size: int = 2000, only: str | None = None, full: bool = False) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Depositi completata.",
    )
