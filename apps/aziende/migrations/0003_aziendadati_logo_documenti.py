from django.db import migrations, models

import apps.aziende.models


class Migration(migrations.Migration):

    dependencies = [
        ("aziende", "0002_aziendadati_azienda_noleggio"),
    ]

    operations = [
        migrations.AddField(
            model_name="aziendadati",
            name="logo_documenti",
            field=models.ImageField(
                blank=True,
                help_text=(
                    "Intestazione nelle stampe di preventivi, fatture "
                    "e altri documenti. Formato PNG o JPG."
                ),
                null=True,
                upload_to=apps.aziende.models.azienda_logo_documenti_upload_to,
                verbose_name="Logo stampe documenti",
            ),
        ),
        migrations.AlterField(
            model_name="aziendadati",
            name="logo",
            field=models.ImageField(
                blank=True,
                help_text="Logo generale (elenchi, UI). Formato PNG o JPG.",
                null=True,
                upload_to=apps.aziende.models.azienda_logo_upload_to,
                verbose_name="Logo",
            ),
        ),
    ]
