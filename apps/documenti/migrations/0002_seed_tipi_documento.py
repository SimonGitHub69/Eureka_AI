from django.db import migrations

from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO


def seed_tipi_documento(apps, schema_editor):
    TipoDocumento = apps.get_model("documenti", "TipoDocumento")
    for spec in DEFAULT_TIPI_DOCUMENTO:
        TipoDocumento.objects.update_or_create(
            codice=spec["codice"],
            defaults={
                "label": spec["label"],
                "descrizione": spec["descrizione"],
                "ordine": spec["ordine"],
                "source_table_4d": spec["source_table_4d"],
                "source_detail_4d": spec["source_detail_4d"],
                "clifor_tipo": spec["clifor_tipo"],
                "attivo": True,
            },
        )


def unseed_tipi_documento(apps, schema_editor):
    TipoDocumento = apps.get_model("documenti", "TipoDocumento")
    codes = [spec["codice"] for spec in DEFAULT_TIPI_DOCUMENTO]
    TipoDocumento.objects.filter(codice__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("documenti", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_tipi_documento, unseed_tipi_documento),
    ]
