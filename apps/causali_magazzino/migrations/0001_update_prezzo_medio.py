from django.db import migrations


def add_update_prezzo_medio(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
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


def remove_update_prezzo_medio(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
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
            'ALTER TABLE causali_maga DROP COLUMN IF EXISTS "Update_Prezzo_Medio"'
        )


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunPython(add_update_prezzo_medio, remove_update_prezzo_medio),
    ]
