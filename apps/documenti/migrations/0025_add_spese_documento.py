from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0024_cambio_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="add_spese",
            field=models.BooleanField(default=False),
        ),
    ]
