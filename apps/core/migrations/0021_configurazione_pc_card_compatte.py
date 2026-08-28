from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_configurazione_pc_dashboard_shortcuts"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazionepc",
            name="card_compatte",
            field=models.BooleanField(
                default=True,
                help_text="Se attivo, le schede delle maschere (form/dettaglio) usano spaziature più dense.",
                verbose_name="Card compatte",
            ),
        ),
    ]
