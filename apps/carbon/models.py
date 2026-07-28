from django.db import models


class Reparto(models.Model):
    """Mirror PostgreSQL della tabella 4D Reparti (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    stampante_etichette = models.TextField(null=True, blank=True, db_column="StampanteEtichette")
    priorita = models.IntegerField(null=True, blank=True, db_column="Priorita")
    stampante_scheda = models.TextField(null=True, blank=True, db_column="StampanteScheda")
    stampante_scheda_fr = models.TextField(null=True, blank=True, db_column="StampanteSchedaFR")
    visualizza_palmare = models.BooleanField(null=True, blank=True, db_column="VisualizzaPalmare")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    numero_fase = models.SmallIntegerField(null=True, blank=True, db_column="NumeroFase")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "reparti"
        verbose_name = "Reparto"
        verbose_name_plural = "Reparti"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} · {self.descrizione or ''}".strip(" ·")


class LavorazionePartita(models.Model):
    """Mirror PostgreSQL della tabella 4D Lavorazioni_Partite (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    num_partita = models.IntegerField(null=True, blank=True, db_column="NumPartita")
    cod_lavorazione = models.TextField(null=True, blank=True, db_column="CodLavorazione")
    data = models.DateTimeField(null=True, blank=True, db_column="Data")
    ora = models.TimeField(null=True, blank=True, db_column="Ora")
    codope1 = models.TextField(null=True, blank=True, db_column="CodOpe1")
    codope2 = models.TextField(null=True, blank=True, db_column="CodOpe2")
    codope3 = models.TextField(null=True, blank=True, db_column="CodOpe3")
    codope4 = models.TextField(null=True, blank=True, db_column="CodOpe4")
    codope5 = models.TextField(null=True, blank=True, db_column="CodOpe5")
    codope6 = models.TextField(null=True, blank=True, db_column="CodOpe6")
    codope7 = models.TextField(null=True, blank=True, db_column="CodOpe7")
    codope8 = models.TextField(null=True, blank=True, db_column="CodOpe8")
    codope9 = models.TextField(null=True, blank=True, db_column="CodOpe9")
    codope10 = models.TextField(null=True, blank=True, db_column="CodOpe10")
    stato = models.TextField(null=True, blank=True, db_column="Stato")
    pos = models.SmallIntegerField(null=True, blank=True, db_column="Pos")
    codart_ser = models.TextField(null=True, blank=True, db_column="CodArtSer")
    cod_reparto = models.TextField(null=True, blank=True, db_column="CodReparto")
    codart = models.TextField(null=True, blank=True, db_column="CodArt")
    cod_lav_extra = models.TextField(null=True, blank=True, db_column="CodLavExtra")
    note = models.TextField(null=True, blank=True, db_column="Note")
    cod_stampo = models.TextField(null=True, blank=True, db_column="CodStampo")
    key_lav = models.TextField(null=True, blank=True, db_column="Key_lav")
    rilavorazione = models.BooleanField(null=True, blank=True, db_column="Rilavorazione")
    da_cancellare = models.BooleanField(null=True, blank=True, db_column="DaCancellare")
    cod_sacco = models.TextField(null=True, blank=True, db_column="CodSacco")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "lavorazioni_partite"
        verbose_name = "Lavorazione partita"
        verbose_name_plural = "Lavorazioni partite"
        ordering = ["-id"]

    def __str__(self):
        return self.codart_ser or self.codart or f"ID {self.id}"


class StampoSerialePartita(models.Model):
    """Mirror PostgreSQL della tabella 4D TabStampi_Seriali_Partite (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    aggiornato = models.BooleanField(null=True, blank=True, db_column="Aggiornato")
    codart_ser1 = models.TextField(null=True, blank=True, db_column="CodArtSer1")
    codart_ser2 = models.TextField(null=True, blank=True, db_column="CodArtSer2")
    codart_ser3 = models.TextField(null=True, blank=True, db_column="CodArtSer3")
    codart_ser4 = models.TextField(null=True, blank=True, db_column="CodArtSer4")
    codart_ser5 = models.TextField(null=True, blank=True, db_column="CodArtSer5")
    codart_ser6 = models.TextField(null=True, blank=True, db_column="CodArtSer6")
    codart_ser7 = models.TextField(null=True, blank=True, db_column="CodArtSer7")
    codart_ser8 = models.TextField(null=True, blank=True, db_column="CodArtSer8")
    codart_ser9 = models.TextField(null=True, blank=True, db_column="CodArtSer9")
    codart_ser10 = models.TextField(null=True, blank=True, db_column="CodArtSer10")
    codart_ser11 = models.TextField(null=True, blank=True, db_column="CodArtSer11")
    codart_ser12 = models.TextField(null=True, blank=True, db_column="CodArtSer12")
    codart_ser13 = models.TextField(null=True, blank=True, db_column="CodArtSer13")
    codart_ser14 = models.TextField(null=True, blank=True, db_column="CodArtSer14")
    codart_ser15 = models.TextField(null=True, blank=True, db_column="CodArtSer15")
    codart_ser16 = models.TextField(null=True, blank=True, db_column="CodArtSer16")
    codice_stampo = models.TextField(null=True, blank=True, db_column="CodiceStampo")
    cod_sacco = models.TextField(null=True, blank=True, db_column="CodSacco")
    key_lav_partite = models.TextField(null=True, blank=True, db_column="key_Lav_Partite")
    stato = models.SmallIntegerField(null=True, blank=True, db_column="Stato")
    synced_at = models.DateTimeField(null=True, blank=True)

    SERIALI_FIELDS = tuple(f"codart_ser{i}" for i in range(1, 17))

    class Meta:
        managed = False
        db_table = "stampi_seriali_partite"
        verbose_name = "Stampo seriale partita"
        verbose_name_plural = "Stampi seriali partite"
        ordering = ["-id"]

    def __str__(self):
        return self.codice_stampo or f"ID {self.id}"

    def seriali_list(self):
        items = []
        for i, name in enumerate(self.SERIALI_FIELDS, start=1):
            items.append((f"{i:02d}", getattr(self, name) or ""))
        return items
