from __future__ import annotations

from apps.core.sync_4d import SyncResult, quote_ident, sync_tables


def _post_create_indexes(cur, target: str) -> None:
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_ident(target + '_codice_idx')} "
        f"ON {quote_ident(target)} ({quote_ident('Codice')})"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_ident(target + '_codicedest_idx')} "
        f"ON {quote_ident(target)} ({quote_ident('CodiceDest')})"
    )


TABLES = (
    {
        "source": "DestCliFor",
        "target": "DestCliFor",
        "pk": "ID",
        "post_create": _post_create_indexes,
    },
)


def sync_destinazioni(batch_size: int = 2000, only: str | None = None, full: bool = False) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Destinazioni diverse (DestCliFor) completata.",
    )
