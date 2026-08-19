from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0016_configurazioneprogramma_ai_recent_searches_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="ai_example_prompt",
            field=models.CharField(
                default=(
                    "Cerca tutti i movimenti IVA il cui imponibile è compreso tra 1500 e 1750 "
                    "nell'anno in corso"
                ),
                help_text=(
                    "Testo mostrato come suggerimento nel modale della bacchetta magica "
                    "(dopo «Ad esempio:»)."
                ),
                max_length=500,
                verbose_name="Testo di esempio (Assistente AI)",
            ),
        ),
    ]
