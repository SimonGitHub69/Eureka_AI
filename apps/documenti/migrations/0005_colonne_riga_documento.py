from django.db import migrations, models
import django.db.models.deletion


DEFAULT_COLONNE = (
    ("numero_riga", 10),
    ("codice", 20),
    ("descrizione", 30),
    ("quantita", 40),
    ("unita_misura", 50),
    ("prezzo_unitario", 60),
    ("sconto", 70),
    ("iva", 80),
)


def seed_colonne_riga(apps, schema_editor):
    TipoDocumento = apps.get_model("documenti", "TipoDocumento")
    ColonnaRigaDocumento = apps.get_model("documenti", "ColonnaRigaDocumento")
    to_create = []
    for tipo in TipoDocumento.objects.all():
        if ColonnaRigaDocumento.objects.filter(tipo_doc=tipo).exists():
            continue
        for campo, posizione in DEFAULT_COLONNE:
            to_create.append(
                ColonnaRigaDocumento(
                    tipo_doc=tipo,
                    campo=campo,
                    posizione=posizione,
                    etichetta="",
                    larghezza="",
                )
            )
    if to_create:
        ColonnaRigaDocumento.objects.bulk_create(to_create)


def unseed_colonne_riga(apps, schema_editor):
    ColonnaRigaDocumento = apps.get_model("documenti", "ColonnaRigaDocumento")
    ColonnaRigaDocumento.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documenti", "0004_parametri_documento"),
    ]

    operations = [
        migrations.CreateModel(
            name="ColonnaRigaDocumento",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "campo",
                    models.CharField(
                        choices=[
                            ("numero_riga", "#"),
                            ("codice", "Codice"),
                            ("descrizione", "Descrizione"),
                            ("quantita", "Qtà"),
                            ("unita_misura", "U.M."),
                            ("prezzo_unitario", "Prezzo"),
                            ("sconto", "Sconto"),
                            ("iva", "IVA"),
                        ],
                        max_length=40,
                        verbose_name="Campo",
                    ),
                ),
                (
                    "posizione",
                    models.PositiveSmallIntegerField(
                        default=10, verbose_name="Posizione"
                    ),
                ),
                (
                    "etichetta",
                    models.CharField(
                        blank=True,
                        help_text="Vuoto = etichetta predefinita del campo.",
                        max_length=40,
                        verbose_name="Etichetta",
                    ),
                ),
                (
                    "larghezza",
                    models.CharField(
                        blank=True,
                        help_text="Es. 8rem, 120px. Vuoto = automatica.",
                        max_length=16,
                        verbose_name="Larghezza",
                    ),
                ),
                (
                    "tipo_doc",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="colonne_riga",
                        to="documenti.tipodocumento",
                        to_field="codice",
                    ),
                ),
            ],
            options={
                "verbose_name": "Colonna riga documento",
                "verbose_name_plural": "Colonne riga documento",
                "db_table": "parametri_documento_colonne_riga",
                "ordering": ["tipo_doc_id", "posizione", "pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tipo_doc", "campo"),
                        name="uniq_colonna_riga_tipo_campo",
                    ),
                ],
            },
        ),
        migrations.RunPython(seed_colonne_riga, unseed_colonne_riga),
    ]
