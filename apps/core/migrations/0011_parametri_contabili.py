# Generated manually for ParametriContabili

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_sync_watermark"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametriContabili",
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
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name="UUID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Creato il"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Modificato il"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Eliminato il"
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Attivo"),
                ),
                ("note", models.TextField(blank=True, verbose_name="Note")),
                (
                    "aliquota_iva_spese",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Codice aliquota IVA usata per le spese in castelletto. "
                            "Se vuoto, si usa l'aliquota della prima riga merce."
                        ),
                        max_length=32,
                        verbose_name="Aliquota IVA (spese)",
                    ),
                ),
                (
                    "contropartita_spese_imballo",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Contropartita PDC — spese imballo",
                    ),
                ),
                (
                    "contropartita_spese_trasporto",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Contropartita PDC — spese trasporto",
                    ),
                ),
                (
                    "contropartita_spese_incasso",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Contropartita PDC — spese incasso",
                    ),
                ),
                (
                    "contropartita_spese_varie",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Contropartita PDC — spese varie",
                    ),
                ),
                (
                    "contropartita_spese_bolli",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Contropartita PDC — spese bolli",
                    ),
                ),
                (
                    "contropartita_spese_e15",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Contropartita PDC — spese art. 15",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creato da",
                    ),
                ),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_deleted",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Eliminato da",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Modificato da",
                    ),
                ),
            ],
            options={
                "verbose_name": "Parametri contabili",
                "verbose_name_plural": "Parametri contabili",
            },
        ),
    ]
