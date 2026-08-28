from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0002_seed_tipi_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="syncdocumentilog",
            name="cancel_requested",
            field=models.BooleanField(default=False),
        ),
    ]
