from django.db import migrations


def add_fine_mese_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'condizioni'
            )
            """
        )
        if not cursor.fetchone()[0]:
            return
        cursor.execute(
            'ALTER TABLE condizioni ADD COLUMN IF NOT EXISTS "FineMese" boolean'
        )


def remove_fine_mese_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'condizioni'
            )
            """
        )
        if not cursor.fetchone()[0]:
            return
        cursor.execute('ALTER TABLE condizioni DROP COLUMN IF EXISTS "FineMese"')


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunPython(add_fine_mese_column, remove_fine_mese_column),
    ]
