from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0008_scadenze_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="tipodocumento",
            name="scadenze",
            field=models.CharField(
                choices=[
                    ("FACOLTATIVE", "Facoltative"),
                    ("OBBLIGATORIE", "Obbligatorie"),
                ],
                default="FACOLTATIVE",
                help_text="Se obbligatorie, il documento non si salva senza almeno una data di scadenza.",
                max_length=12,
                verbose_name="Scadenze",
            ),
        ),
    ]
