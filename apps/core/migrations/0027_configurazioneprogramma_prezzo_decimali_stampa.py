from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_configurazioneprogramma_prezzo_decimali"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="prezzo_decimali_stampa",
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text=(
                    "Numero massimo di decimali per i prezzi unitari nelle stampe "
                    "(inventario, movimenti articolo, elenco articoli, ecc.). "
                    "Importi e totali in stampa restano a 2 decimali."
                ),
                verbose_name="Decimali prezzi unitari in stampa",
            ),
        ),
        migrations.AlterField(
            model_name="configurazioneprogramma",
            name="prezzo_decimali",
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text=(
                    "Numero massimo di decimali per i prezzi unitari a video "
                    "(schede articolo, movimenti di magazzino, righe documento, ecc.). "
                    "Importi e totali restano a 2 decimali."
                ),
                verbose_name="Decimali prezzi unitari",
            ),
        ),
    ]
