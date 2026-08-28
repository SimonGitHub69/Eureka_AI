from django.db import models


class PianoConti(models.Model):
    """Mirror PostgreSQL della tabella 4D PDC (Piano dei Conti)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    tipo_conto = models.TextField(null=True, blank=True, db_column="TipoConto")
    gruppo = models.TextField(null=True, blank=True, db_column="Gruppo")
    tipo_controllo = models.TextField(null=True, blank=True, db_column="TipoControllo")
    dare = models.FloatField(null=True, blank=True, db_column="Dare")
    avere = models.FloatField(null=True, blank=True, db_column="Avere")
    categ_fiscale_dare = models.TextField(null=True, blank=True, db_column="CategFiscaleDare")
    tipo = models.SmallIntegerField(null=True, blank=True, db_column="Tipo")
    desc_conto = models.TextField(null=True, blank=True, db_column="DescConto")
    dare_p = models.FloatField(null=True, blank=True, db_column="DareP")
    avere_p = models.FloatField(null=True, blank=True, db_column="AvereP")
    filler = models.TextField(null=True, blank=True, db_column="filler")
    gruppo_cee = models.TextField(null=True, blank=True, db_column="Gruppo_CEE")
    codice_art_edifir = models.TextField(null=True, blank=True, db_column="CodiceArtEDIFIR")
    modifica_cespiti = models.BooleanField(null=True, blank=True, db_column="ModificaCespiti")
    dare_p_sez = models.FloatField(null=True, blank=True, db_column="DarePSez")
    avere_p_sez = models.FloatField(null=True, blank=True, db_column="AverePSez")
    categ_fiscale_avere = models.TextField(null=True, blank=True, db_column="CategFiscaleAvere")
    bene_servizio = models.TextField(null=True, blank=True, db_column="Bene_Servizio")
    nomenclatura = models.TextField(null=True, blank=True, db_column="Nomenclatura")
    tipo_noleggio = models.SmallIntegerField(null=True, blank=True, db_column="TipoNoleggio")
    disabilitato = models.BooleanField(null=True, blank=True, db_column="Disabilitato")
    cod_voce_analitica = models.TextField(null=True, blank=True, db_column="CodVoceAnalitica")
    cod_centro_analisi = models.TextField(null=True, blank=True, db_column="CodCentroAnalisi")
    f_non_integrare = models.BooleanField(null=True, blank=True, db_column="F_NonIntegrare")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "pdc"
        verbose_name = "Piano dei Conti"
        verbose_name_plural = "Piano dei Conti"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} – {self.descrizione or ''}"

    @property
    def label(self) -> str:
        return (self.descrizione or self.desc_conto or "").strip()

    @property
    def livello(self) -> int:
        return self.codice.count(".")

    @property
    def livello_label(self) -> str:
        labels = ("Mastro", "Conto", "Sottoconto")
        return labels[self.livello] if self.livello < len(labels) else "Sottoconto"

    @property
    def codice_mastro(self) -> str:
        return self.codice.split(".")[0]

    @property
    def codice_conto(self) -> str | None:
        parts = self.codice.split(".")
        if len(parts) < 2:
            return None
        return f"{parts[0]}.{parts[1]}"
