from django.db import migrations


def copy_chi1_to_chi1_natura(apps, schema_editor):
    """Dopo il rename 4D Chi1 → Chi1_Natura i dati restano in Chi1 finché non si rifà sync.

    Copia i valori esistenti così la maschera mostra subito Natura.
    """
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
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'articoli'
                  AND column_name = 'Chi1'
            )
            """
        )
        if not cursor.fetchone()[0]:
            return
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'articoli'
                  AND column_name = 'Chi1_Natura'
            )
            """
        )
        if not cursor.fetchone()[0]:
            return
        cursor.execute(
            """
            UPDATE articoli
            SET "Chi1_Natura" = NULLIF(BTRIM("Chi1"), '')
            WHERE COALESCE(BTRIM("Chi1_Natura"), '') = ''
              AND COALESCE(BTRIM("Chi1"), '') <> ''
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_articoli_chi1_natura"),
    ]

    operations = [
        migrations.RunPython(copy_chi1_to_chi1_natura, noop_reverse),
    ]
