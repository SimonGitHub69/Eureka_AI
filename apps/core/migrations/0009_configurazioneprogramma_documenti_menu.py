from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_configurazioneprogramma_suono_errore"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="doc_prv",
            field=models.BooleanField(
                default=True,
                help_text="Mostra Preventivi nel menu Fatturazione Magazzino.",
                verbose_name="Preventivi",
            ),
        ),
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="doc_orv",
            field=models.BooleanField(
                default=True,
                help_text="Mostra Ordini vendita nel menu Fatturazione Magazzino.",
                verbose_name="Ordini vendita",
            ),
        ),
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="doc_ora",
            field=models.BooleanField(
                default=True,
                help_text="Mostra Ordini acquisto nel menu Fatturazione Magazzino.",
                verbose_name="Ordini acquisto",
            ),
        ),
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="doc_ddt",
            field=models.BooleanField(
                default=True,
                help_text="Mostra DDT / Bolle nel menu Fatturazione Magazzino.",
                verbose_name="DDT / Bolle",
            ),
        ),
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="doc_fat",
            field=models.BooleanField(
                default=True,
                help_text="Mostra Fatture nel menu Fatturazione Magazzino.",
                verbose_name="Fatture",
            ),
        ),
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="doc_ncr",
            field=models.BooleanField(
                default=True,
                help_text="Mostra Note di credito nel menu Fatturazione Magazzino.",
                verbose_name="Note di credito",
            ),
        ),
        migrations.AddField(
            model_name="configurazioneprogramma",
            name="doc_ndb",
            field=models.BooleanField(
                default=True,
                help_text="Mostra Note di debito nel menu Fatturazione Magazzino.",
                verbose_name="Note di debito",
            ),
        ),
    ]
