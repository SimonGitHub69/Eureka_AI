from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0029_riga_provvigione"),
    ]

    operations = [
        migrations.AddField(
            model_name="tipodocumento",
            name="testo_mail",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Testo precompilato in Invia mail. Segnaposto: "
                    "{tipo} {numero} {data} {cliente} {totale} {destinatario} {codice}"
                ),
                verbose_name="Testo mail",
            ),
        ),
    ]
