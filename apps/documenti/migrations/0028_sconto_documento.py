from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0027_codice_sconto_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="sconto",
            field=models.TextField(blank=True),
        ),
    ]
