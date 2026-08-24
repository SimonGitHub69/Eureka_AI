from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_articoli_copy_chi1_to_chi1_natura"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="inventario_discrepanza_pct",
            field=models.PositiveSmallIntegerField(
                default=25,
                help_text=(
                    "Nella stampa inventario evidenzia (e filtra) le righe in cui "
                    "|ultimo − medio| / max(ultimo, medio) supera questa percentuale. "
                    "Valori tipici: 15–30."
                ),
                verbose_name="Soglia discrepanza prezzi inventario (%)",
            ),
        ),
    ]
