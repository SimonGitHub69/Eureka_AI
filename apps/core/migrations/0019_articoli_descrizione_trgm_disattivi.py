"""
Indice trigram parziale su articoli disattivati per ricerche AI con ILIKE.

Si applica solo se la tabella articoli esiste (sync 4D).
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
    _create_if_table(
        "articoli",
        'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione_trgm_disattivi '
        'ON articoli USING gin ("Descrizione" gin_trgm_ops) '
        'WHERE "FlDisattivato" IS TRUE',
    ),
]

REVERSE = [
    "DROP INDEX IF EXISTS idx_articoli_descrizione_trgm_disattivi",
]


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_articoli_ai_search_trgm"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD,
            reverse_sql=REVERSE,
        ),
    ]
