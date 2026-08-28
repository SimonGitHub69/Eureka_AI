from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0019_validita_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="data_consegna",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
