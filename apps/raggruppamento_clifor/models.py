from django.db import models


class RaggruppamentoClifor(models.Model):
    """Mirror PostgreSQL della tabella 4D Gruppo_Cli_For (Tab_CliFor)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    escludi_regola_newcli = models.BooleanField(
        null=True, blank=True, db_column="Escludi_Regola_NewCli"
    )
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "raggruppamento_clifor"
        verbose_name = "Raggruppamento clienti-fornitori"
        verbose_name_plural = "Raggruppamento clienti-fornitori"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} – {self.descrizione or ''}"
