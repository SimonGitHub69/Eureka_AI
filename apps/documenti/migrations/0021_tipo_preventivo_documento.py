from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0020_data_consegna_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="tipo_preventivo",
            field=models.TextField(blank=True),
        ),
    ]
