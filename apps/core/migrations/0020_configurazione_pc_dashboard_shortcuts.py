from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_articoli_descrizione_trgm_disattivi"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazionepc",
            name="dashboard_shortcuts",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Voci di menu da mostrare come icone nella Dashboard (SI/NO per postazione).",
                verbose_name="Abbreviazioni dashboard",
            ),
        ),
    ]
