from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0014_codice_agente"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="telefono",
            field=models.TextField(blank=True),
        ),
    ]
