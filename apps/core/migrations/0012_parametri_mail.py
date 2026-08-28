# Generated manually for ParametriMail

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_parametri_contabili"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametriMail",
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
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("note", models.TextField(blank=True, verbose_name="Note")),
                (
                    "attiva",
                    models.BooleanField(
                        default=False,
                        help_text="Se disattivo, Eureka non invia email automatiche.",
                        verbose_name="Invio mail attivo",
                    ),
                ),
                (
                    "server_smtp",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Es. smtp.provider.it oppure smtp.gmail.com",
                        max_length=255,
                        verbose_name="Server SMTP",
                    ),
                ),
                (
                    "porta",
                    models.PositiveIntegerField(
                        default=587,
                        help_text="587 (STARTTLS), 465 (SSL) o 25.",
                        verbose_name="Porta",
                    ),
                ),
                (
                    "usa_tls",
                    models.BooleanField(
                        default=True,
                        help_text="Consigliato con porta 587.",
                        verbose_name="Usa STARTTLS",
                    ),
                ),
                (
                    "usa_ssl",
                    models.BooleanField(
                        default=False,
                        help_text="Consigliato con porta 465. Non usare insieme a STARTTLS.",
                        verbose_name="Usa SSL/TLS",
                    ),
                ),
                (
                    "utente",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Utente SMTP",
                    ),
                ),
                (
                    "password",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Password SMTP",
                    ),
                ),
                (
                    "mittente",
                    models.EmailField(
                        blank=True,
                        default="",
                        help_text="Indirizzo From delle email automatiche.",
                        max_length=254,
                        verbose_name="Email mittente",
                    ),
                ),
                (
                    "nome_mittente",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Nome visualizzato (es. Eureka AI — Azienda).",
                        max_length=255,
                        verbose_name="Nome mittente",
                    ),
                ),
                (
                    "reply_to",
                    models.EmailField(
                        blank=True,
                        default="",
                        help_text="Indirizzo di risposta (opzionale).",
                        max_length=254,
                        verbose_name="Reply-To",
                    ),
                ),
                (
                    "copia_nascosta",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Indirizzi BCC predefiniti, separati da virgola o punto e virgola.",
                        max_length=512,
                        verbose_name="Copia conoscenza nascosta (BCC)",
                    ),
                ),
                (
                    "email_test",
                    models.EmailField(
                        blank=True,
                        default="",
                        help_text="Destinatario per la prova di invio dalla maschera parametri.",
                        max_length=254,
                        verbose_name="Email di test",
                    ),
                ),
                (
                    "timeout_secondi",
                    models.PositiveIntegerField(
                        default=30,
                        help_text="Timeout connessione SMTP.",
                        verbose_name="Timeout (secondi)",
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
                    ),
                ),
            ],
            options={
                "verbose_name": "Parametri mail",
                "verbose_name_plural": "Parametri mail",
            },
        ),
    ]
