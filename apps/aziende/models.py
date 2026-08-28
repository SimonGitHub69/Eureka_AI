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
    # Campi fattura elettronica (SDI / FatturaPA)
    cod_regime_fiscale = models.TextField(null=True, blank=True, db_column="CodRegimeFiscale")
    cod_unico_sdi = models.TextField(null=True, blank=True, db_column="CodUnicoSDI")
    cod_paese = models.TextField(null=True, blank=True, db_column="CodPaese")
    persona_fisica = models.BooleanField(null=True, blank=True, db_column="PersonaFisica")
    cognome = models.TextField(null=True, blank=True, db_column="Cognome")
    nome = models.TextField(null=True, blank=True, db_column="Nome")
    num_civico = models.TextField(null=True, blank=True, db_column="NumCivico")
    prov_rea = models.TextField(null=True, blank=True, db_column="Prov_REA")
    num_iscrizione_rea = models.TextField(null=True, blank=True, db_column="NumIscrizione_REA")
    capitale_soc = models.FloatField(null=True, blank=True, db_column="CapitaleSoc")
    socio_unico = models.BooleanField(null=True, blank=True, db_column="SocioUnico")
    in_liquidazione = models.BooleanField(null=True, blank=True, db_column="InLiquidazione")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
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


def azienda_logo_documenti_upload_to(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".png"
    return f"aziende/loghi_documenti/{instance.azienda_id}/{uuid4().hex}{ext}"


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
        help_text="Logo generale (elenchi, UI). Formato PNG o JPG.",
    )
    logo_documenti = models.ImageField(
        "Logo stampe documenti",
        upload_to=azienda_logo_documenti_upload_to,
        blank=True,
        null=True,
        help_text="Intestazione nelle stampe di preventivi, fatture e altri documenti. Formato PNG o JPG.",
    )
    azienda_noleggio = models.BooleanField(
        "Azienda di noleggio",
        default=False,
        help_text="Abilita Nomenclatura Intrastat, Bene o servizio e Tipo noleggio nel Piano dei Conti.",
    )

    class Meta:
        verbose_name = "Dati locali azienda"
        verbose_name_plural = "Dati locali aziende"
        ordering = ["azienda_id"]

    def __str__(self):
        return f"Dati azienda {self.azienda_id}"
