from django.db import migrations, models


def seed_provvigione_colonne_preventivi(apps, schema_editor):
    TipoDocumento = apps.get_model("documenti", "TipoDocumento")
    ColonnaRigaDocumento = apps.get_model("documenti", "ColonnaRigaDocumento")
    to_create = []
    for tipo in TipoDocumento.objects.filter(categoria="PREVENTIVI"):
        if ColonnaRigaDocumento.objects.filter(
            tipo_doc=tipo, campo="provvigione"
        ).exists():
            continue
        to_create.append(
            ColonnaRigaDocumento(
                tipo_doc=tipo,
                campo="provvigione",
                posizione=75,
                etichetta="",
                larghezza="",
            )
        )
    if to_create:
        ColonnaRigaDocumento.objects.bulk_create(to_create)


def unseed_provvigione_colonne_preventivi(apps, schema_editor):
    ColonnaRigaDocumento = apps.get_model("documenti", "ColonnaRigaDocumento")
    ColonnaRigaDocumento.objects.filter(campo="provvigione").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0028_sconto_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="rigadocumento",
            name="provvigione",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.RunPython(
            seed_provvigione_colonne_preventivi,
            unseed_provvigione_colonne_preventivi,
        ),
    ]
