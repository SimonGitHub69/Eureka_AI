from django.db import migrations, models


def seed_categoria_ddt(apps, schema_editor):
    TipoDocumento = apps.get_model("documenti", "TipoDocumento")
    TipoDocumento.objects.filter(codice="DDT", categoria="ALTRO").update(categoria="DDT")


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0006_alter_colonna_riga_tipo_doc"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tipodocumento",
            name="categoria",
            field=models.CharField(
                choices=[
                    ("ORDINI", "Ordini"),
                    ("FATTURE", "Fatture"),
                    ("NOTE_CREDITO", "Note credito"),
                    ("NOTE_DEBITO", "Note debito"),
                    ("PREVENTIVI", "Preventivi"),
                    ("DDT", "DDT"),
                    ("ALTRO", "Altro"),
                ],
                db_index=True,
                default="ALTRO",
                help_text="Famiglia del documento: consente più codici per Ordini, Fatture, ecc.",
                max_length=20,
                verbose_name="Famiglia",
            ),
        ),
        migrations.RunPython(seed_categoria_ddt, migrations.RunPython.noop),
    ]
