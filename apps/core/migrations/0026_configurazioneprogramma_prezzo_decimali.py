from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_configurazioneprogramma_inventario_discrepanza_pct"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="prezzo_decimali",
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text=(
                    "Numero massimo di decimali per i prezzi unitari "
                    "(schede articolo, movimenti di magazzino, righe documento, "
                    "stampe inventario, ecc.). Importi e totali restano a 2 decimali."
                ),
                verbose_name="Decimali prezzi unitari",
            ),
        ),
    ]
