from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_parametri_mail"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="extra_carbon",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Mostra la personalizzazione CARBON nel menu laterale "
                    "(produzione, seriali, stampi, schede di lavorazione)."
                ),
                verbose_name="CARBON",
            ),
        ),
    ]
