from django.db import migrations


def add_chi1_natura_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'articoli'
            )
            """
        )
        if not cursor.fetchone()[0]:
            return
        cursor.execute(
            'ALTER TABLE articoli ADD COLUMN IF NOT EXISTS "Chi1_Natura" text'
        )


def remove_chi1_natura_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'articoli'
            )
            """
        )
        if not cursor.fetchone()[0]:
            return
        cursor.execute('ALTER TABLE articoli DROP COLUMN IF EXISTS "Chi1_Natura"')


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_remove_configurazione_pc_card_compatte"),
    ]

    operations = [
        migrations.RunPython(add_chi1_natura_column, remove_chi1_natura_column),
    ]
