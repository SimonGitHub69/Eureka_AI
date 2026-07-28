from __future__ import annotations

from apps.core.sync_4d import SyncResult, sync_tables

TABLES = (
    {
        "source": "TabLavorazioniExtra",
        "target": "lavorazioni_extra",
        "pk": "ID",
    },
)


def sync_lavorazioni_extra(batch_size: int = 2000, only: str | None = None) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        success_message="Sincronizzazione Lavorazioni extra (TabLavorazioniExtra) completata.",
    )
