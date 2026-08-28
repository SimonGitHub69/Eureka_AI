from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0022_confermato_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="valuta",
            field=models.TextField(blank=True),
        ),
    ]
