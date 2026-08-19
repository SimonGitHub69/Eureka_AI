from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_configurazioneprogramma_debug_ai_sql"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="ai_recent_searches_limit",
            field=models.PositiveSmallIntegerField(
                default=10,
                help_text=(
                    "Numero massimo di ricerche recenti della bacchetta magica da "
                    "conservare nel browser per ogni utente."
                ),
                verbose_name="Ricerche recenti AI per utente",
            ),
        ),
    ]
