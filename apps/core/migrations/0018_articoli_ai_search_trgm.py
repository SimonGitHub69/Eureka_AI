"""
Indici trigram su articoli."Descrizione" per ricerche AI con ILIKE.

Migration 0014 ha già idx_articoli_fldisatt (FlDisattivato) e idx_articoli_descrizione
(btree, inutile per pattern '%testo%'). Qui si aggiunge pg_trgm + GIN per ILIKE,
più un indice parziale sugli articoli attivi (FlDisattivato non true).
"""

from django.db import migrations


FORWARD = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    (
        'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione_trgm '
        'ON articoli USING gin ("Descrizione" gin_trgm_ops)'
    ),
    (
        'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione_trgm_attivi '
        'ON articoli USING gin ("Descrizione" gin_trgm_ops) '
        'WHERE "FlDisattivato" IS NOT TRUE'
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
