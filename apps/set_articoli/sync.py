from __future__ import annotations

from apps.core.sync_4d import SyncResult, quote_ident, sync_tables


def _post_create_h(cur, target: str) -> None:
    t = quote_ident(target)
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS set_articoli_h_numeroset_idx "
        f"ON {t} ({quote_ident('NumeroSet')});"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS set_articoli_h_nomeset_idx "
        f"ON {t} ({quote_ident('NomeSet')});"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS set_articoli_h_fornitore_idx "
        f"ON {t} ({quote_ident('Fornitore')});"
    )


def _post_create_d(cur, target: str) -> None:
    t = quote_ident(target)
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS set_articoli_d_idtesta_idx "
        f"ON {t} ({quote_ident('ID_Testa')});"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS set_articoli_d_codart_idx "
        f"ON {t} ({quote_ident('CodArt')});"
    )


TABLES = (
    {
        "source": "Set_Articoli_H",
        "target": "set_articoli_h",
        "pk": "ID",
        "post_create": _post_create_h,
    },
    {
        "source": "Set_Articoli_D",
        "target": "set_articoli_d",
        "pk": "ID",
        "page_by_pk": True,
        "post_create": _post_create_d,
    },
)


def sync_set_articoli(
    batch_size: int = 2000, only: str | None = None, full: bool = False
) -> SyncResult:
    return sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Set_Articoli_H / Set_Articoli_D completata.",
    )
