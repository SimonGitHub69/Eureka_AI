from __future__ import annotations

from apps.core.sync_4d import SyncResult, quote_ident, sync_tables

DEFAULT_SYNC_BATCH_SIZE = 5000
DEFAULT_SYNC_PAGE_SIZE = 50000

TABLES = (
    {
        "source": "Articoli",
        "target": "articoli",
        "pk": "Codice",
        "page_by_pk": True,
        "incremental_by_pk": True,
        "batch_size": DEFAULT_SYNC_BATCH_SIZE,
        "page_size": DEFAULT_SYNC_PAGE_SIZE,
        "post_create": lambda cur, target: _create_articoli_indexes(cur, target),
    },
)


def _create_articoli_indexes(cur, target: str) -> None:
    """Indici btree usati da liste/export AI (ricreati dopo sync full con DROP TABLE)."""
    t = quote_ident(target)
    for name, column in (
        ("idx_articoli_descrizione", "Descrizione"),
        ("idx_articoli_codgruppo", "CodGruppo"),
        ("idx_articoli_codiva", "CodIva"),
        ("idx_articoli_codfornitore", "CodFornitore"),
        ("idx_articoli_catom", "CatOmogenea"),
        ("idx_articoli_fldisatt", "FlDisattivato"),
    ):
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS {name} "
            f"ON {t} ({quote_ident(column)});"
        )


def sync_articoli(
    batch_size: int = DEFAULT_SYNC_BATCH_SIZE,
    only: str | None = None,
    full: bool = False,
) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Articoli completata.",
    )
