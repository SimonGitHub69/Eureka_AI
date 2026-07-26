from django.db import models


class Articolo(models.Model):
    """Mirror PostgreSQL della tabella 4D Articoli (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    cat_omogenea = models.TextField(null=True, blank=True, db_column="CatOmogenea")
    cod_iva = models.TextField(null=True, blank=True, db_column="CodIva")
    unita_misura = models.TextField(null=True, blank=True, db_column="UnitaMisura")
    cod_fornitore = models.TextField(null=True, blank=True, db_column="CodFornitore")
    codice_alternativo1 = models.TextField(null=True, blank=True, db_column="CodiceAlternativo1")
    codice_alternativo2 = models.TextField(null=True, blank=True, db_column="CodiceAlternativo2")
    cod_breve_art = models.TextField(null=True, blank=True, db_column="CodBreveArt")
    listino1 = models.FloatField(null=True, blank=True, db_column="Listino1")
    prezzo_ult_car = models.FloatField(null=True, blank=True, db_column="PrezzoUltCar")
    prezzo_medio_acquisto = models.FloatField(null=True, blank=True, db_column="PrezzoMedioAcquisto")
    cod_magazzino = models.TextField(null=True, blank=True, db_column="CodMagazzino")
    giacenza = models.BooleanField(null=True, blank=True, db_column="Giacenza")
    disponibile = models.BooleanField(null=True, blank=True, db_column="Disponibile")
    fl_disattivato = models.BooleanField(null=True, blank=True, db_column="FlDisattivato")
    data_ult_car = models.DateTimeField(null=True, blank=True, db_column="DataUltCar")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "articoli"
        verbose_name = "Articolo"
        verbose_name_plural = "Articoli"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
