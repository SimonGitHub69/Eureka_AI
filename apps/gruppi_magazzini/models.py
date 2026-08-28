from django.db import models


class GruppoMagazzino(models.Model):
    """Mirror PostgreSQL della tabella 4D RaggMagazzini (gestita dal sync)."""

    cod = models.TextField(primary_key=True, db_column="Cod")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    tipo_doc_alfa_ddt = models.TextField(null=True, blank=True, db_column="TipoDocAlfaDDT")
    tipo_doc_alfa_fat = models.TextField(null=True, blank=True, db_column="TipoDocAlfaFAT")
    tipo_doc_alfa_ord = models.TextField(null=True, blank=True, db_column="TipoDocAlfaORD")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "gruppi_magazzini"
        verbose_name = "Gruppo Magazzini"
        verbose_name_plural = "Gruppi Magazzini"
        ordering = ["descrizione", "cod"]

    def __str__(self):
        label = self.descrizione or self.cod
        return f"{label} ({self.cod})"
