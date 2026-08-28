from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0016_porto_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="annotazioni",
            field=models.TextField(blank=True),
        ),
    ]
