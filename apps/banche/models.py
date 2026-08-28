from django.db import models


class Banca(models.Model):
    """Mirror PostgreSQL della tabella 4D Banche (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    indirizzo = models.TextField(null=True, blank=True, db_column="Indirizzo")
    cap = models.TextField(null=True, blank=True, db_column="Cap")
    localita = models.TextField(null=True, blank=True, db_column="Localita")
    provincia = models.TextField(null=True, blank=True, db_column="Provincia")
    telefono = models.TextField(null=True, blank=True, db_column="Telefono")
    fax = models.TextField(null=True, blank=True, db_column="Fax")
    codice_abi = models.TextField(null=True, blank=True, db_column="CodiceABI")
    codice_cab = models.TextField(null=True, blank=True, db_column="CodiceCAB")
    numero_cc = models.TextField(null=True, blank=True, db_column="NumeroCC")
    agenzia = models.TextField(null=True, blank=True, db_column="Agenzia")
    note = models.TextField(null=True, blank=True, db_column="Note")
    fido = models.FloatField(null=True, blank=True, db_column="Fido")
    cin = models.TextField(null=True, blank=True, db_column="CIN")
    iban = models.TextField(null=True, blank=True, db_column="IBAN")
    swift_code = models.TextField(null=True, blank=True, db_column="SwiftCode")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "banche"
        verbose_name = "Banca"
        verbose_name_plural = "Banche"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
