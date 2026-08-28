from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_configurazione_pc_card_compatte"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configurazionepc",
            name="card_compatte",
        ),
    ]
