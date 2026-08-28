from django.db import models


class RaggruppamentoConto(models.Model):
    """Mirror PostgreSQL della tabella 4D Raggruppamento."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "raggruppamento_conti"
        verbose_name = "Raggruppamento conto"
        verbose_name_plural = "Raggruppamento conti"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} – {self.descrizione or ''}"
