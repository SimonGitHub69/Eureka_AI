"""
Indici trigram su articoli."Descrizione" per ricerche AI con ILIKE.

Si applicano solo se la tabella articoli esiste (sync 4D).
"""

from django.db import migrations


def _create_if_table(table: str, create_sql: str) -> str:
    escaped = create_sql.replace("'", "''")
    return f"""
DO $migration$
BEGIN
  IF to_regclass('public.{table}') IS NOT NULL THEN
    EXECUTE '{escaped}';
  END IF;
END
$migration$;
"""


FORWARD = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    _create_if_table(
        "articoli",
        'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione_trgm '
        'ON articoli USING gin ("Descrizione" gin_trgm_ops)',
    ),
    _create_if_table(
        "articoli",
        'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione_trgm_attivi '
        'ON articoli USING gin ("Descrizione" gin_trgm_ops) '
        'WHERE "FlDisattivato" IS NOT TRUE',
    ),
]

REVERSE = [
    "DROP INDEX IF EXISTS idx_articoli_descrizione_trgm_attivi",
    "DROP INDEX IF EXISTS idx_articoli_descrizione_trgm",
]


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_configurazioneprogramma_ai_example_prompt"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD,
            reverse_sql=REVERSE,
        ),
    ]
