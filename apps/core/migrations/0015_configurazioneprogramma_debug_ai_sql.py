from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_ai_search_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="debug_ai_sql",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Mostra nel modale dell'assistente AI la query SQL generata e la relativa spiegazione. "
                    "Da usare solo per debug."
                ),
                verbose_name="Mostra SQL e spiegazione AI (debug)",
            ),
        ),
    ]

