from django.db import models


class Condizione(models.Model):
    """Mirror PostgreSQL della tabella 4D CondizioniPag (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    tipo_pagamento = models.TextField(null=True, blank=True, db_column="TipoPagamento")
    numero_rate = models.SmallIntegerField(null=True, blank=True, db_column="NumeroRate")
    prima_rata = models.SmallIntegerField(null=True, blank=True, db_column="PrimaRata")
    intervallo = models.SmallIntegerField(null=True, blank=True, db_column="Intervallo")
    giorno_fisso = models.SmallIntegerField(null=True, blank=True, db_column="GiornoFisso")
    codice_banca = models.TextField(null=True, blank=True, db_column="CodiceBanca")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "condizioni"
        verbose_name = "Condizione"
        verbose_name_plural = "Condizioni"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
