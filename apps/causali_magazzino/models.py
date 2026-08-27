from django.db import models


class CausaleMagazzino(models.Model):
    """Mirror PostgreSQL della tabella 4D CausaliMaga (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    tipo_causale = models.TextField(null=True, blank=True, db_column="Tipo_Causale")
    deposito_entrata = models.TextField(null=True, blank=True, db_column="DepositoEntrata")
    deposito_uscita = models.TextField(null=True, blank=True, db_column="DepositoUscita")
    scar_db = models.TextField(null=True, blank=True, db_column="Scar_DB")
    update_listino = models.TextField(null=True, blank=True, db_column="Update_Listino")
    update_prezzo_medio = models.TextField(
        null=True, blank=True, db_column="Update_Prezzo_Medio"
    )
    cod_market = models.TextField(null=True, blank=True, db_column="CodMarket")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "causali_maga"
        verbose_name = "Causale magazzino"
        verbose_name_plural = "Causali magazzino"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
