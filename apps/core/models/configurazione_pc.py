from django.db import models

from apps.core.models.base import BaseModel


class ConfigurazionePC(BaseModel):
    """Parametri per postazione (sovrascrivono Parametri programma)."""

    nome_pc = models.CharField(
        "Nome PC",
        max_length=100,
        db_index=True,
        help_text="Nome fisico del computer (es. DESKTOP-UFFICIO01).",
    )
    descrizione = models.CharField(
        "Descrizione",
        max_length=200,
        blank=True,
        help_text="Etichetta aggiuntiva per riconoscere la postazione.",
    )
    assistente_vocale_attivo = models.BooleanField(
        "Assistente vocale",
        default=True,
        help_text="Se disattivo, microfono e comandi vocali non sono disponibili su questa postazione.",
    )
    navbar_fissa = models.BooleanField(
        "Barra superiore fissa",
        default=True,
        help_text="Se attivo, la barra con menu e utente resta in alto durante lo scorrimento (utile su tablet).",
    )
    liste_fisse = models.BooleanField(
        "Intestazione liste fissa",
        default=True,
        help_text="Se attivo, titolo e filtri delle liste e la barra delle schede restano in alto durante lo scorrimento.",
    )
    dashboard_shortcuts = models.JSONField(
        "Scorciatoie Dashboard / barra",
        default=dict,
        blank=True,
        help_text=(
            "Per ogni voce: mode (off|dash|bar|both), gruppo (1,2,… da sinistra), "
            "posizione (ordine nell’icona del gruppo)."
        ),
    )

    class Meta:
        verbose_name = "Parametri PC"
        verbose_name_plural = "Parametri PC"
        ordering = ["nome_pc"]

    def __str__(self):
        label = self.descrizione.strip() if self.descrizione else ""
        if label:
            return f"{self.nome_pc} ({label})"
        return self.nome_pc

    def save(self, *args, **kwargs):
        self.nome_pc = (self.nome_pc or "").strip()
        self.descrizione = (self.descrizione or "").strip()
        super().save(*args, **kwargs)
