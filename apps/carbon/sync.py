from __future__ import annotations

from apps.core.sync_4d import SyncResult, sync_tables

TABLES = (
    {
        "source": "Reparti",
        "target": "reparti",
        "pk": "Codice",
    },
    {
        "source": "Lavorazioni_Partite",
        "target": "lavorazioni_partite",
        "pk": "ID",
    },
    {
        "source": "TabStampi_Seriali_Partite",
        "target": "stampi_seriali_partite",
        "pk": "ID",
    },
)


def sync_carbon(batch_size: int = 2000, only: str | None = None, full: bool = False) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione tabelle CARBON (Reparti, Lavorazioni_Partite, TabStampi_Seriali_Partite) completata.",
    )
