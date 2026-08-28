from django.db import migrations, models


CATEGORIA_BY_CODICE = {
    "ORV": "ORDINI",
    "ORA": "ORDINI",
    "PRV": "PREVENTIVI",
    "DDT": "ALTRO",
    "FAT": "FATTURE",
    "NCR": "NOTE_CREDITO",
    "NDB": "NOTE_DEBITO",
}


def seed_categoria(apps, schema_editor):
    TipoDocumento = apps.get_model("documenti", "TipoDocumento")
    for tipo in TipoDocumento.objects.all():
        categoria = CATEGORIA_BY_CODICE.get(tipo.codice, "ALTRO")
        if tipo.categoria != categoria:
            tipo.categoria = categoria
            tipo.save(update_fields=["categoria"])


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0003_syncdocumentilog_cancel_requested"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="tipodocumento",
            options={
                "ordering": ["ordine", "codice"],
                "verbose_name": "Parametro documento",
                "verbose_name_plural": "Parametri documento",
            },
        ),
        migrations.AlterModelTable(
            name="tipodocumento",
            table="parametri_documento",
        ),
        migrations.AddField(
            model_name="tipodocumento",
            name="categoria",
            field=models.CharField(
                choices=[
                    ("ORDINI", "Ordini"),
                    ("FATTURE", "Fatture"),
                    ("NOTE_CREDITO", "Note credito"),
                    ("NOTE_DEBITO", "Note debito"),
                    ("PREVENTIVI", "Preventivi"),
                    ("ALTRO", "Altro"),
                ],
                db_index=True,
                default="ALTRO",
                help_text="Famiglia del documento: consente più codici per Ordini, Fatture, ecc.",
                max_length=20,
                verbose_name="Famiglia",
            ),
        ),
        migrations.AlterField(
            model_name="tipodocumento",
            name="clifor_tipo",
            field=models.CharField(
                blank=True,
                choices=[("C", "Cliente"), ("F", "Fornitore")],
                help_text="Il documento è intestato a un cliente o a un fornitore.",
                max_length=1,
                verbose_name="Anagrafica",
            ),
        ),
        migrations.AlterField(
            model_name="tipodocumento",
            name="codice",
            field=models.CharField(
                help_text="Codice breve univoco: ORV, ORA, PRV, DDT, FAT, NCR, NDB o altro personalizzato.",
                max_length=8,
                primary_key=True,
                serialize=False,
                verbose_name="Codice",
            ),
        ),
        migrations.AlterField(
            model_name="tipodocumento",
            name="descrizione",
            field=models.TextField(blank=True, verbose_name="Note"),
        ),
        migrations.AlterField(
            model_name="tipodocumento",
            name="label",
            field=models.CharField(max_length=120, verbose_name="Descrizione"),
        ),
        migrations.AlterField(
            model_name="tipodocumento",
            name="source_detail_4d",
            field=models.CharField(
                blank=True, max_length=80, verbose_name="Tabella 4D righe"
            ),
        ),
        migrations.AlterField(
            model_name="tipodocumento",
            name="source_table_4d",
            field=models.CharField(
                blank=True, max_length=80, verbose_name="Tabella 4D testata"
            ),
        ),
        migrations.RunPython(seed_categoria, migrations.RunPython.noop),
    ]
