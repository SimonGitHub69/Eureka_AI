from django.db import models


class Valuta(models.Model):
    """Mirror PostgreSQL della tabella 4D Valuta (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    abbrev = models.TextField(null=True, blank=True, db_column="Abbrev")
    cambio = models.FloatField(null=True, blank=True, db_column="Cambio")
    dummy = models.BooleanField(null=True, blank=True, db_column="Dummy")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "valuta"
        verbose_name = "Valuta"
        verbose_name_plural = "Valute"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"


class ValutaDet(models.Model):
    """Mirror PostgreSQL della tabella 4D Valuta_Det (cambi storici)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    valuta = models.ForeignKey(
        Valuta,
        on_delete=models.CASCADE,
        db_column="Cod_Valuta",
        to_field="codice",
        related_name="cambi",
        db_constraint=False,
    )
    data = models.DateTimeField(null=True, blank=True, db_column="Data")
    cambio = models.FloatField(null=True, blank=True, db_column="Cambio")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "valuta_det"
        verbose_name = "Cambio valuta"
        verbose_name_plural = "Cambi valuta"
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"{self.valuta_id} {self.data} = {self.cambio}"

    @property
    def data_locale(self):
        """Data di calendario (4D mezzanotte UTC → giorno locale, es. 31/12 23:00 → 01/01)."""
        from apps.valute.forms import det_value_to_date

        return det_value_to_date(self.data)
