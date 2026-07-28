from django.db import models


class DistintaBase(models.Model):
    """Mirror PostgreSQL della tabella 4D Distinte_Base (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    codice_db = models.TextField(
        null=True,
        blank=True,
        db_column="CodiceDB",
        db_index=True,
        help_text="Articolo padre / codice distinta",
    )
    codice_art = models.TextField(
        null=True,
        blank=True,
        db_column="Codice_Art",
        db_index=True,
        help_text="Articolo componente",
    )
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    qta = models.FloatField(null=True, blank=True, db_column="Qta")
    um = models.TextField(null=True, blank=True, db_column="UM")
    qta2 = models.FloatField(null=True, blank=True, db_column="Qta2")
    um2 = models.TextField(null=True, blank=True, db_column="UM2")
    costo = models.FloatField(null=True, blank=True, db_column="Costo")
    costo_medio = models.FloatField(null=True, blank=True, db_column="CostoMedio")
    listino = models.FloatField(null=True, blank=True, db_column="Listino")
    ricarico = models.FloatField(null=True, blank=True, db_column="Ricarico")
    totale_costo = models.FloatField(null=True, blank=True, db_column="TotaleCosto")
    costo_manuale = models.FloatField(null=True, blank=True, db_column="CostoManuale")
    fase = models.TextField(null=True, blank=True, db_column="Fase")
    lavoraz_mater = models.TextField(null=True, blank=True, db_column="LavorazMater")
    anno_ordine = models.TextField(null=True, blank=True, db_column="AnnoOrdine")
    cod_gruppo_art = models.TextField(null=True, blank=True, db_column="CodGruppoArt")
    cod_cat_merc = models.TextField(null=True, blank=True, db_column="CodCatMerc")
    cod_forn = models.TextField(null=True, blank=True, db_column="CodForn")
    da_cancellare = models.BooleanField(null=True, blank=True, db_column="Da_Cancellare")
    data_revisione = models.DateTimeField(null=True, blank=True, db_column="DataRevisione")
    data_creazione = models.DateTimeField(null=True, blank=True, db_column="DataCreazione")
    utente_creazione = models.TextField(null=True, blank=True, db_column="UtenteCreazione")
    ora_creazione = models.TimeField(null=True, blank=True, db_column="OraCreazione")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "distinte_base"
        verbose_name = "Riga distinta base"
        verbose_name_plural = "Distinte base"
        ordering = ["codice_db", "fase", "codice_art", "id"]

    def __str__(self):
        return f"{self.codice_db or '?'} → {self.codice_art or '?'} ({self.id})"
