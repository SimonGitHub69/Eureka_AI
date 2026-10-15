from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RegistroIvaStampaStato",
            fields=[
                (
                    "registro_codice",
                    models.CharField(max_length=64, primary_key=True, serialize=False),
                ),
                ("data_finale", models.DateField(blank=True, null=True)),
                ("ultimo_protocollo", models.IntegerField(blank=True, null=True)),
                (
                    "ultima_pagina",
                    models.IntegerField(blank=True, default=0, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Stato stampa definitiva registro IVA",
                "verbose_name_plural": "Stati stampa definitiva registri IVA",
                "db_table": "registri_iva_stampa_stato",
            },
        ),
    ]
