# Generated manually for TipoDocumento.contatori M2M

from django.db import migrations, models


def copy_default_contatore_to_m2m(apps, schema_editor):
    TipoDocumento = apps.get_model("documenti", "TipoDocumento")
    for tipo in TipoDocumento.objects.exclude(contatore_id__isnull=True).exclude(
        contatore_id=""
    ):
        tipo.contatori.add(tipo.contatore_id)


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0012_tipodocumento_serie"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tipodocumento",
            name="contatore",
            field=models.ForeignKey(
                blank=True,
                help_text="Contatore predefinito in creazione (combo Serie). Vuoto = numerazione automatica per tipo se non ci sono contatori associati.",
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="tipi_documento",
                to="documenti.contatoredocumento",
                verbose_name="Contatore predefinito",
            ),
        ),
        migrations.AlterField(
            model_name="tipodocumento",
            name="serie",
            field=models.CharField(
                blank=True,
                help_text="Opzionale: serie (alfa) precompilata sui nuovi documenti. Se valorizzata ha priorità sulla serie del contatore predefinito (ignorata se l'utente sceglie un'altra serie dal combo).",
                max_length=16,
                verbose_name="Serie",
            ),
        ),
        migrations.AddField(
            model_name="tipodocumento",
            name="contatori",
            field=models.ManyToManyField(
                blank=True,
                help_text="Contatori selezionabili nella maschera documento (combo Serie). Il Contatore predefinito è usato all'apertura di Nuovo.",
                related_name="tipi_documento_multi",
                to="documenti.contatoredocumento",
                verbose_name="Contatori / serie",
            ),
        ),
        migrations.RunPython(copy_default_contatore_to_m2m, migrations.RunPython.noop),
    ]
