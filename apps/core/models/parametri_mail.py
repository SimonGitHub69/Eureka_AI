from django.db import models

from apps.core.models.base import BaseModel


class ParametriMail(BaseModel):
    """Parametri SMTP globali per l'invio automatico di email (singleton pk=1)."""

    attiva = models.BooleanField(
        "Invio mail attivo",
        default=False,
        help_text="Se disattivo, Eureka non invia email automatiche.",
    )
    server_smtp = models.CharField(
        "Server SMTP",
        max_length=255,
        blank=True,
        default="",
        help_text="Solo hostname, senza http:// e senza porta. Es. smtp.gmail.com",
    )
    porta = models.PositiveIntegerField(
        "Porta",
        default=587,
        help_text="587 (STARTTLS), 465 (SSL) o 25.",
    )
    usa_tls = models.BooleanField(
        "Usa STARTTLS",
        default=True,
        help_text="Consigliato con porta 587.",
    )
    usa_ssl = models.BooleanField(
        "Usa SSL/TLS",
        default=False,
        help_text="Consigliato con porta 465. Non usare insieme a STARTTLS.",
    )
    utente = models.CharField(
        "Utente SMTP",
        max_length=255,
        blank=True,
        default="",
    )
    password = models.CharField(
        "Password SMTP",
        max_length=255,
        blank=True,
        default="",
    )
    mittente = models.EmailField(
        "Email mittente",
        blank=True,
        default="",
        help_text="Indirizzo From delle email automatiche.",
    )
    nome_mittente = models.CharField(
        "Nome mittente",
        max_length=255,
        blank=True,
        default="",
        help_text="Nome visualizzato (es. Eureka AI — Azienda).",
    )
    reply_to = models.EmailField(
        "Reply-To",
        blank=True,
        default="",
        help_text="Indirizzo di risposta (opzionale).",
    )
    copia_nascosta = models.CharField(
        "Copia conoscenza nascosta (BCC)",
        max_length=512,
        blank=True,
        default="",
        help_text="Indirizzi BCC predefiniti, separati da virgola o punto e virgola.",
    )
    email_test = models.EmailField(
        "Email di test",
        blank=True,
        default="",
        help_text="Destinatario per la prova di invio dalla maschera parametri.",
    )
    timeout_secondi = models.PositiveIntegerField(
        "Timeout (secondi)",
        default=30,
        help_text="Timeout connessione SMTP.",
    )

    class Meta:
        verbose_name = "Parametri mail"
        verbose_name_plural = "Parametri mail"

    def __str__(self):
        return "Parametri mail"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "porta": 587,
                "usa_tls": True,
                "timeout_secondi": 30,
            },
        )
        return obj

    def mittente_completo(self) -> str:
        email = (self.mittente or "").strip()
        nome = (self.nome_mittente or "").strip()
        if nome and email:
            return f"{nome} <{email}>"
        return email
