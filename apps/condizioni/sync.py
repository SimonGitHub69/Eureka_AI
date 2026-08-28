from __future__ import annotations

from apps.core.sync_4d import SyncResult, sync_tables

TABLES = (
    {
        "source": "CondizioniPag",
        "target": "condizioni",
        "pk": "Codice",
    },
)


def sync_condizioni(batch_size: int = 2000, only: str | None = None, full: bool = False) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Condizioni di Pagamento (CondizioniPag) completata.",
    )
