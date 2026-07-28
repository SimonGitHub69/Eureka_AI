# Generated manually for ConfigurazioneProgramma.navbar_fissa

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_configurazioneprogramma"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="navbar_fissa",
            field=models.BooleanField(
                default=True,
                help_text="Se attivo, la barra con menu e utente resta in alto durante lo scorrimento (utile su tablet).",
                verbose_name="Barra superiore fissa",
            ),
        ),
    ]
