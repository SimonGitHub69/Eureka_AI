from __future__ import annotations

from apps.core.sync_4d import SyncResult, sync_tables

TABLES = (
    {
        "source": "CatMerce",
        "target": "categorie",
        "pk": "Codice",
    },
)


def sync_categorie(batch_size: int = 2000, only: str | None = None) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        success_message="Sincronizzazione Categorie (CatMerce) completata.",
    )
