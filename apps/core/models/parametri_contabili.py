from django.db import models

from apps.core.models.base import BaseModel

SPESE_CONTROPARTITA_FIELDS: tuple[tuple[str, str], ...] = (
    ("contropartita_spese_imballo", "Spese imballo"),
    ("contropartita_spese_trasporto", "Spese trasporto"),
    ("contropartita_spese_incasso", "Spese incasso"),
    ("contropartita_spese_varie", "Spese varie"),
    ("contropartita_spese_bolli", "Spese bolli"),
    ("contropartita_spese_e15", "Spese art. 15"),
)


class ParametriContabili(BaseModel):
    """Parametri contabili globali (singleton pk=1)."""

    aliquota_iva_spese = models.CharField(
        "Aliquota IVA (spese)",
        max_length=32,
        blank=True,
        default="",
        help_text="Codice aliquota IVA usata per le spese in castelletto. "
        "Se vuoto, si usa l'aliquota della prima riga merce.",
    )
    contropartita_spese_imballo = models.CharField(
        "Contropartita PDC — spese imballo",
        max_length=64,
        blank=True,
        default="",
    )
    contropartita_spese_trasporto = models.CharField(
        "Contropartita PDC — spese trasporto",
        max_length=64,
        blank=True,
        default="",
    )
    contropartita_spese_incasso = models.CharField(
        "Contropartita PDC — spese incasso",
        max_length=64,
        blank=True,
        default="",
    )
    contropartita_spese_varie = models.CharField(
        "Contropartita PDC — spese varie",
        max_length=64,
        blank=True,
        default="",
    )
    contropartita_spese_bolli = models.CharField(
        "Contropartita PDC — spese bolli",
        max_length=64,
        blank=True,
        default="",
    )
    contropartita_spese_e15 = models.CharField(
        "Contropartita PDC — spese art. 15",
        max_length=64,
        blank=True,
        default="",
    )

    class Meta:
        verbose_name = "Parametri contabili"
        verbose_name_plural = "Parametri contabili"

    def __str__(self):
        return "Parametri contabili"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def aliquota_iva_spese_codice(self) -> str:
        return (self.aliquota_iva_spese or "").strip()
