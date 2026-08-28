from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0021_tipo_preventivo_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="confermato",
            field=models.BooleanField(default=False),
        ),
    ]
