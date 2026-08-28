from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0013_tipodocumento_contatori"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="codice_agente",
            field=models.TextField(blank=True),
        ),
    ]
