"""
Indice trigram parziale su articoli disattivati per ricerche AI con ILIKE.

Migration 0018 ha idx_articoli_descrizione_trgm (tutti) e
idx_articoli_descrizione_trgm_attivi (WHERE FlDisattivato IS NOT TRUE).
Le query su articoli disattivati non possono usare l'indice attivi: serve
un indice parziale su FlDisattivato IS TRUE per sfruttare il GIN trigram.
"""

from django.db import migrations


FORWARD = [
    (
        'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione_trgm_disattivi '
        'ON articoli USING gin ("Descrizione" gin_trgm_ops) '
        'WHERE "FlDisattivato" IS TRUE'
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
