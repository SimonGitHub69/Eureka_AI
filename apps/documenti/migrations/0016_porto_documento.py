from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0015_telefono_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="porto",
            field=models.TextField(blank=True),
        ),
    ]
