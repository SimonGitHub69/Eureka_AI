from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0026_cod_banca_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="codice_sconto",
            field=models.TextField(blank=True),
        ),
    ]
