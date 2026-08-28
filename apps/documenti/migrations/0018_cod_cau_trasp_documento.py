from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0017_annotazioni_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="cod_cau_trasp",
            field=models.TextField(blank=True),
        ),
    ]
