from django.db import models


class Vettore(models.Model):
    """Mirror PostgreSQL della tabella 4D Vettori (spedizionieri; gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="CodiceVet")
    denominazione = models.TextField(null=True, blank=True, db_column="Denominazione")
    indirizzo = models.TextField(null=True, blank=True, db_column="Indirizzo")
    citta = models.TextField(null=True, blank=True, db_column="Citta")
    telefono = models.TextField(null=True, blank=True, db_column="Telefono")
    partita_iva = models.TextField(null=True, blank=True, db_column="PartitaIva")
    iscrizione_albo = models.TextField(null=True, blank=True, db_column="IscrizioneAlbo")
    email = models.TextField(null=True, blank=True, db_column="Email")
    id_paese = models.TextField(null=True, blank=True, db_column="IDPaese")
    nazione = models.TextField(null=True, blank=True, db_column="Nazione")
    cod_eori = models.TextField(null=True, blank=True, db_column="CodEORI")
    codice_fiscale = models.TextField(null=True, blank=True, db_column="CodFiscale")
    sigla_abbreviata = models.TextField(null=True, blank=True, db_column="Sigla_Abbreviata")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "vettori"
        verbose_name = "Spedizioniere"
        verbose_name_plural = "Spedizionieri"
        ordering = ["denominazione", "codice"]

    def __str__(self):
        label = self.denominazione or self.codice
        return f"{label} ({self.codice})"
