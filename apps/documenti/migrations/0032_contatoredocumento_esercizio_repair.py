# Repair: aggiunge esercizio se mancante (es. DB PostgreSQL non migrato).

from django.db import migrations
from django.utils import timezone


def _year_default() -> int:
    return timezone.localdate().year


def add_esercizio_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    year = _year_default()
    with connection.cursor() as cursor:
        columns = {
            col.name
            for col in connection.introspection.get_table_description(
                cursor, "contatori_documento"
            )
        }
        if "esercizio" in columns:
            return
        if connection.vendor == "postgresql":
            cursor.execute(
                "ALTER TABLE contatori_documento "
                "ADD COLUMN esercizio smallint NOT NULL DEFAULT %s",
                [year],
            )
        else:
            cursor.execute(
                "ALTER TABLE contatori_documento "
                f"ADD COLUMN esercizio integer NOT NULL DEFAULT {year}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0031_contatoredocumento_esercizio"),
    ]

    operations = [
        migrations.RunPython(add_esercizio_if_missing, migrations.RunPython.noop),
    ]
