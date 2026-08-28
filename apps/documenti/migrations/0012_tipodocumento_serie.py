from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0011_contatore_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="tipodocumento",
            name="serie",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Opzionale: serie (alfa) precompilata sui nuovi documenti. "
                    "Se valorizzata ha priorità sulla serie del contatore."
                ),
                max_length=16,
                verbose_name="Serie",
            ),
        ),
    ]
