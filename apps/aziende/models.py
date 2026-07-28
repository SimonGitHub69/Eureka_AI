from pathlib import Path
from uuid import uuid4

from django.db import models

from apps.core.models.base import BaseModel


class Azienda(models.Model):
    """Mirror PostgreSQL della tabella 4D Azienda (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    ragione_sociale = models.TextField(null=True, blank=True, db_column="RagioneSociale")
    indirizzo = models.TextField(null=True, blank=True, db_column="Indirizzo")
    localita = models.TextField(null=True, blank=True, db_column="Localita")
    provincia = models.TextField(null=True, blank=True, db_column="Provincia")
    cap = models.TextField(null=True, blank=True, db_column="Cap")
    partita_iva = models.TextField(null=True, blank=True, db_column="PartitaIva")
    codice_fiscale = models.TextField(null=True, blank=True, db_column="CodiceFiscale")
    telefono = models.TextField(null=True, blank=True, db_column="Telefono")
    fax = models.TextField(null=True, blank=True, db_column="Fax")
    email = models.TextField(null=True, blank=True, db_column="email")
    email_pec = models.TextField(null=True, blank=True, db_column="Email_PEC")
    anno_competenza = models.TextField(null=True, blank=True, db_column="AnnoCompetenza")
    cod_attivita = models.TextField(null=True, blank=True, db_column="CodAttivita")
    desc_attivita = models.TextField(null=True, blank=True, db_column="DescAttivita")
    note = models.TextField(null=True, blank=True, db_column="Note")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "aziende"
        verbose_name = "Azienda"
        verbose_name_plural = "Aziende"
        ordering = ["ragione_sociale", "id"]

    def __str__(self):
        label = self.ragione_sociale or f"ID {self.id}"
        return f"{label} ({self.id})"


def azienda_logo_upload_to(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".png"
    return f"aziende/loghi/{instance.azienda_id}/{uuid4().hex}{ext}"


class AziendaDati(BaseModel):
    """Dati locali Eureka collegati all'azienda 4D (logo escluso dallo sync)."""

    azienda_id = models.PositiveIntegerField(
        "ID azienda 4D",
        unique=True,
        db_index=True,
        help_text="Riferimento all'ID della tabella mirror aziende.",
    )
    logo = models.ImageField(
        "Logo",
        upload_to=azienda_logo_upload_to,
        blank=True,
        null=True,
        help_text="Formato PNG o JPG.",
    )

    class Meta:
        verbose_name = "Dati locali azienda"
        verbose_name_plural = "Dati locali aziende"
        ordering = ["azienda_id"]

    def __str__(self):
        return f"Dati azienda {self.azienda_id}"
