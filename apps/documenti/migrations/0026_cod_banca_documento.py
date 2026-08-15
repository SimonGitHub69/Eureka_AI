from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0025_add_spese_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="cod_banca",
            field=models.TextField(blank=True),
        ),
    ]
