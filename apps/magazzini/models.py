from django.db import models


class Magazzino(models.Model):
    """Mirror PostgreSQL della tabella 4D Magazzini (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    cod_ragg_mag = models.TextField(null=True, blank=True, db_column="CodRaggMag")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "magazzini"
        verbose_name = "Magazzino"
        verbose_name_plural = "Magazzini"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
