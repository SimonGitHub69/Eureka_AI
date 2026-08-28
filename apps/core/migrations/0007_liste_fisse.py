from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_configurazione_pc"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="liste_fisse",
            field=models.BooleanField(
                default=True,
                help_text="Se attivo, titolo e filtri delle liste restano in alto durante lo scorrimento.",
                verbose_name="Intestazione liste fissa",
            ),
        ),
        migrations.AddField(
            model_name="configurazionepc",
            name="liste_fisse",
            field=models.BooleanField(
                default=True,
                help_text="Se attivo, titolo e filtri delle liste restano in alto durante lo scorrimento.",
                verbose_name="Intestazione liste fissa",
            ),
        ),
    ]
