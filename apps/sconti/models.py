from django.db import models


class Sconto(models.Model):
    """Mirror PostgreSQL della tabella 4D Sconti (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    sconto = models.TextField(null=True, blank=True, db_column="Sconto")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "sconti"
        verbose_name = "Sconto"
        verbose_name_plural = "Sconti"
        ordering = ["codice"]

    def __str__(self):
        label = self.sconto or self.codice
        return f"{self.codice} ({label})"
