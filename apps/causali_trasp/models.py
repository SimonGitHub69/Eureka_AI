from django.db import models


class CausaleTrasporto(models.Model):
    """Mirror PostgreSQL della tabella 4D CausaliTrasp (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Desc")
    fatturabile = models.BooleanField(null=True, blank=True, db_column="Fatturabile")
    causale_maga = models.TextField(null=True, blank=True, db_column="CausaleMaga")
    reparto_ecr = models.TextField(null=True, blank=True, db_column="RepartoECR")
    c_partita_vend = models.TextField(null=True, blank=True, db_column="CPartitaVend")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "causali_trasp"
        verbose_name = "Causale trasporto"
        verbose_name_plural = "Causali trasporto"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
