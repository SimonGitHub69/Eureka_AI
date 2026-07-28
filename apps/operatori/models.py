from django.db import models


class Operatore(models.Model):
    """Mirror PostgreSQL della tabella 4D Operatori (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "operatori"
        verbose_name = "Operatore"
        verbose_name_plural = "Operatori"
        ordering = ["codice"]

    def __str__(self):
        return str(self.codice)
