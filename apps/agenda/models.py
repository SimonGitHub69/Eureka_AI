from django.db import models

from apps.core.models.base import BaseModel


class EventoAgenda(BaseModel):
    class Colore(models.TextChoices):
        BLU = "#3b82f6", "Blu"
        VERDE = "#22c55e", "Verde"
        ROSSO = "#ef4444", "Rosso"
        ARANCIONE = "#f97316", "Arancione"
        VIOLA = "#a855f7", "Viola"
        TEAL = "#14b8a6", "Teal"
        ROSA = "#ec4899", "Rosa"
        GRIGIO = "#64748b", "Grigio"

    titolo = models.CharField("Titolo", max_length=200)
    descrizione = models.TextField("Descrizione", blank=True)
    inizio = models.DateTimeField("Inizio")
    fine = models.DateTimeField("Fine")
    tutto_il_giorno = models.BooleanField("Tutto il giorno", default=False)
    luogo = models.CharField("Luogo", max_length=200, blank=True)
    colore = models.CharField(
        "Colore",
        max_length=20,
        choices=Colore.choices,
        default=Colore.BLU,
    )

    class Meta:
        verbose_name = "Evento agenda"
        verbose_name_plural = "Eventi agenda"
        ordering = ["inizio", "id"]
        indexes = [
            models.Index(fields=["inizio", "fine"]),
            models.Index(fields=["is_active", "inizio"]),
        ]

    def __str__(self):
        return self.titolo

    def to_fullcalendar(self):
        data = {
            "id": str(self.pk),
            "title": self.titolo,
            "start": self.inizio.isoformat(),
            "end": self.fine.isoformat(),
            "allDay": self.tutto_il_giorno,
            "backgroundColor": self.colore,
            "borderColor": self.colore,
            "extendedProps": {
                "descrizione": self.descrizione,
                "luogo": self.luogo,
                "colore": self.colore,
            },
        }
        return data
