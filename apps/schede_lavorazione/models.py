from django.db import models
from django.db.models import Max

from apps.core.models.base import BaseModel


class SchedaLavorazione(BaseModel):
    data = models.DateField("Data")
    operatore_codice = models.CharField("Codice operatore", max_length=50)
    operatore_nome = models.CharField("Operatore", max_length=200, blank=True)
    matricola = models.CharField("Matricola", max_length=50, blank=True)

    class Meta:
        verbose_name = "Scheda di lavorazione"
        verbose_name_plural = "Schede di lavorazione"
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"Scheda {self.data:%d/%m/%Y} · {self.operatore_nome or self.operatore_codice}"

    @property
    def n_righe(self):
        return self.righe.filter(is_active=True).count()


class RigaSchedaLavorazione(BaseModel):
    scheda = models.ForeignKey(
        SchedaLavorazione,
        on_delete=models.CASCADE,
        related_name="righe",
        verbose_name="Scheda",
    )
    ordine = models.PositiveIntegerField("Ordine", default=1)
    codice_pezzo = models.CharField("Codice pezzo", max_length=80)
    cliente = models.CharField("Cliente", max_length=80, blank=True)
    cod_art_cliente = models.CharField("Cod. Art. Cliente", max_length=80, blank=True)
    descrizione_componente = models.CharField(
        "Descrizione componente",
        max_length=500,
        blank=True,
    )
    tempo_distinta = models.DecimalField(
        "Tempo distinta",
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    class Meta:
        verbose_name = "Riga scheda di lavorazione"
        verbose_name_plural = "Righe scheda di lavorazione"
        ordering = ["ordine", "id"]

    def __str__(self):
        return f"{self.codice_pezzo} ({self.scheda_id})"

    @classmethod
    def next_ordine(cls, scheda):
        current = (
            cls.objects.filter(scheda=scheda, is_active=True).aggregate(m=Max("ordine"))["m"]
            or 0
        )
        return current + 1
