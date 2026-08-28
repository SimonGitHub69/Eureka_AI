from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_liste_fisse"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="suono_errore_attivo",
            field=models.BooleanField(
                default=True,
                help_text="Riproduce un suono quando la pagina mostra errori di validazione o messaggi di errore.",
                verbose_name="Suono errore",
            ),
        ),
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="suono_errore_wav",
            field=models.FileField(
                blank=True,
                help_text="File audio .wav personalizzato. Se vuoto, viene usato il suono predefinito.",
                null=True,
                upload_to="eureka/sounds/",
                verbose_name="File suono errore (.wav)",
            ),
        ),
    ]
