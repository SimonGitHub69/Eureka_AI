from django.db import models

from apps.core.models.base import BaseModel


class ConfigurazioneProgramma(BaseModel):
    """Parametri generali dell'applicazione (singleton pk=1)."""

    assistente_vocale_attivo = models.BooleanField(
        "Assistente vocale",
        default=True,
        help_text="Se disattivo, microfono e comandi vocali non sono disponibili.",
    )
    navbar_fissa = models.BooleanField(
        "Barra superiore fissa",
        default=True,
        help_text="Se attivo, la barra con menu e utente resta in alto durante lo scorrimento (utile su tablet).",
    )

    class Meta:
        verbose_name = "Parametri programma"
        verbose_name_plural = "Parametri programma"

    def __str__(self):
        return "Parametri programma"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "assistente_vocale_attivo": True,
                "navbar_fissa": True,
            },
        )
        return obj
