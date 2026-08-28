from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0018_cod_cau_trasp_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="testadocumento",
            name="validita",
            field=models.TextField(blank=True),
        ),
    ]
