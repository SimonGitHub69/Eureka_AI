from django.db import models


class Deposito(models.Model):
    """Mirror PostgreSQL della tabella 4D Depositi (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Numero")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "depositi"
        verbose_name = "Deposito"
        verbose_name_plural = "Depositi"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
