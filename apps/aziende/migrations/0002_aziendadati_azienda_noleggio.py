from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aziende", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="aziendadati",
            name="azienda_noleggio",
            field=models.BooleanField(
                default=False,
                help_text="Abilita Nomenclatura Intrastat, Bene o servizio e Tipo noleggio nel Piano dei Conti.",
                verbose_name="Azienda di noleggio",
            ),
        ),
    ]
