from __future__ import annotations

from apps.core.sync_4d import SyncResult, sync_tables


def _post_create_indexes(cur, target: str) -> None:
    cur.execute(
        f'CREATE INDEX IF NOT EXISTS "{target}_codicedb_idx" ON "{target}" ("CodiceDB")'
    )
    cur.execute(
        f'CREATE INDEX IF NOT EXISTS "{target}_codiceart_idx" ON "{target}" ("Codice_Art")'
    )


TABLES = (
    {
        "source": "Distinte_Base",
        "target": "distinte_base",
        "pk": "ID",
        "post_create": _post_create_indexes,
    },
)


def sync_distinte_base(batch_size: int = 2000, only: str | None = None) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        success_message="Sincronizzazione Distinte_Base completata.",
    )
