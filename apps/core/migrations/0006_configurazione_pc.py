# Generated manually for ConfigurazionePC

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0005_configurazioneprogramma_navbar_fissa"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigurazionePC",
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
                ("is_active", models.BooleanField(default=True, verbose_name="Attivo")),
                ("note", models.TextField(blank=True, verbose_name="Note")),
                (
                    "nome_pc",
                    models.CharField(
                        db_index=True,
                        help_text="Nome fisico del computer (es. DESKTOP-UFFICIO01).",
                        max_length=100,
                        verbose_name="Nome PC",
                    ),
                ),
                (
                    "descrizione",
                    models.CharField(
                        blank=True,
                        help_text="Etichetta aggiuntiva per riconoscere la postazione.",
                        max_length=200,
                        verbose_name="Descrizione",
                    ),
                ),
                (
                    "assistente_vocale_attivo",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Se disattivo, microfono e comandi vocali non sono "
                            "disponibili su questa postazione."
                        ),
                        verbose_name="Assistente vocale",
                    ),
                ),
                (
                    "navbar_fissa",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Se attivo, la barra con menu e utente resta in alto "
                            "durante lo scorrimento (utile su tablet)."
                        ),
                        verbose_name="Barra superiore fissa",
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
                "verbose_name": "Parametri PC",
                "verbose_name_plural": "Parametri PC",
                "ordering": ["nome_pc"],
            },
        ),
    ]
