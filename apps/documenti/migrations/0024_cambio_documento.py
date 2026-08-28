from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0023_valuta_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="cambio",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
