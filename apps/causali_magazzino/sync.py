from __future__ import annotations

from django.db import connection

from apps.core.sync_4d import SyncResult, sync_tables

TABLES = (
    {
        "source": "CausaliMaga",
        "target": "causali_maga",
        "pk": "Codice",
    },
)


def ensure_update_prezzo_medio_column() -> None:
    """Colonna solo Eureka: il recreate mirror 4D la perde; va ripristinata."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'causali_maga'
            )
            """
        )
        if not cursor.fetchone()[0]:
            return
        cursor.execute(
            'ALTER TABLE causali_maga '
            'ADD COLUMN IF NOT EXISTS "Update_Prezzo_Medio" text'
        )
        # Allinea al comportamento storico (un solo flag Update_Listino).
        cursor.execute(
            """
            UPDATE causali_maga
            SET "Update_Prezzo_Medio" = "Update_Listino"
            WHERE "Update_Prezzo_Medio" IS NULL
            """
        )


def sync_causali_magazzino(
    batch_size: int = 2000, only: str | None = None, full: bool = False
) -> SyncResult:
    result = sync_tables(
        TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione Causali magazzino completata.",
    )
    ensure_update_prezzo_medio_column()
    return result
