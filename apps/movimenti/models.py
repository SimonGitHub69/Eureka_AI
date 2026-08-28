from django.db import models
from django.urls import reverse


class MovimentoT(models.Model):
    """Mirror PostgreSQL della tabella 4D MovimentiT (gestita dal sync)."""

    id_testa = models.IntegerField(primary_key=True, db_column="ID_Testa")
    num_registraz = models.IntegerField(null=True, blank=True, db_column="NumRegistraz")
    data_registraz = models.DateTimeField(
        null=True, blank=True, db_column="DataRegistraz"
    )
    causale = models.TextField(null=True, blank=True, db_column="Causale")
    num_doc = models.TextField(null=True, blank=True, db_column="NumDoc")
    data_doc = models.DateTimeField(null=True, blank=True, db_column="DataDoc")
    dep_entrata = models.TextField(null=True, blank=True, db_column="DepEntrata")
    fornitore = models.TextField(null=True, blank=True, db_column="Fornitore")
    cliente = models.TextField(null=True, blank=True, db_column="Cliente")
    dep_uscita = models.TextField(null=True, blank=True, db_column="DepUscita")
    tipo = models.SmallIntegerField(null=True, blank=True, db_column="Tipo")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "movimentit"
        verbose_name = "Movimento magazzino"
        verbose_name_plural = "Movimenti magazzino"
        ordering = ["-data_registraz", "-num_registraz", "-id_testa"]

    def __str__(self):
        return f"{self.num_registraz or '—'} ({self.id_testa})"

    def get_absolute_url(self):
        return reverse("movimenti:detail", kwargs={"pk": self.pk})


class MovimentoTDettaglio(models.Model):
    """Mirror PostgreSQL della tabella 4D MovimentiT_Dettaglio (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    id_testa = models.IntegerField(
        null=True, blank=True, db_column="id_added_by_converter"
    )
    pos = models.IntegerField(null=True, blank=True, db_column="Pos")
    codice_art = models.TextField(null=True, blank=True, db_column="CodiceArt")
    quantita = models.FloatField(null=True, blank=True, db_column="Quantita")
    flag_cd = models.SmallIntegerField(null=True, blank=True, db_column="Flag_CD")
    valore_un_netto = models.FloatField(
        null=True, blank=True, db_column="ValoreUnNetto"
    )
    valore_totale = models.FloatField(null=True, blank=True, db_column="ValoreTotale")
    sconto_cod_art_cli_for = models.TextField(
        null=True, blank=True, db_column="Sconto_CodArtCliFor"
    )
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    data_modifica = models.DateTimeField(
        null=True, blank=True, db_column="DataModifica"
    )
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "movimentit_dettaglio"
        verbose_name = "Riga movimento magazzino"
        verbose_name_plural = "Righe movimenti magazzino"
        ordering = ["id_testa", "pos", "id"]

    def __str__(self):
        return f"{self.codice_art or '—'} ({self.id})"
