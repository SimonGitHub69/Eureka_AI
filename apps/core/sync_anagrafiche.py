from __future__ import annotations

from apps.core.sync_4d import SyncResult, sync_tables

TABLES = (
    {
        "source": "Clienti",
        "target": "clienti",
        "pk": "Codice",
    },
    {
        "source": "Fornitori",
        "target": "fornitori",
        "pk": "Codice",
    },
    {
        "source": "Agenti",
        "target": "agenti",
        "pk": "Codice",
    },
)


def sync_clienti_fornitori(batch_size: int = 2000, only: str | None = None) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        success_message="Sincronizzazione Clienti / Fornitori / Agenti completata.",
    )
