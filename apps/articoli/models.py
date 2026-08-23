from django.db import models


class Articolo(models.Model):
    """Mirror PostgreSQL della tabella 4D Articoli (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    cat_omogenea = models.TextField(null=True, blank=True, db_column="CatOmogenea")
    cod_gruppo = models.TextField(null=True, blank=True, db_column="CodGruppo")
    cod_iva = models.TextField(null=True, blank=True, db_column="CodIva")
    unita_misura = models.TextField(null=True, blank=True, db_column="UnitaMisura")
    cod_fornitore = models.TextField(null=True, blank=True, db_column="CodFornitore")
    codice_alternativo1 = models.TextField(null=True, blank=True, db_column="CodiceAlternativo1")
    codice_alternativo2 = models.TextField(null=True, blank=True, db_column="CodiceAlternativo2")
    cod_breve_art = models.TextField(null=True, blank=True, db_column="CodBreveArt")
    cod_magazzino = models.TextField(null=True, blank=True, db_column="CodMagazzino")
    descr_express = models.BooleanField(null=True, blank=True, db_column="DescrExpress")
    colli = models.FloatField(null=True, blank=True, db_column="Colli")

    listino1 = models.FloatField(null=True, blank=True, db_column="Listino1")
    sconto1 = models.FloatField(null=True, blank=True, db_column="Sconto1")
    listino2 = models.FloatField(null=True, blank=True, db_column="Listino2")
    sconto2 = models.FloatField(null=True, blank=True, db_column="Sconto2")
    listino3 = models.FloatField(null=True, blank=True, db_column="Listino3")
    sconto3 = models.FloatField(null=True, blank=True, db_column="Sconto3")
    prezzo_ult_car = models.FloatField(null=True, blank=True, db_column="PrezzoUltCar")
    prezzo_medio_acquisto = models.FloatField(null=True, blank=True, db_column="PrezzoMedioAcquisto")

    scorta_min = models.FloatField(null=True, blank=True, db_column="ScortaMin")
    volume = models.FloatField(null=True, blank=True, db_column="Volume_SpeseGenerali")
    peso_netto = models.FloatField(null=True, blank=True, db_column="PesoNetto")
    peso_lordo_manodopera = models.FloatField(
        null=True, blank=True, db_column="PesoLordo_Manodopera"
    )
    origine = models.TextField(null=True, blank=True, db_column="Chi2_Origine")
    chi1_natura = models.TextField(null=True, blank=True, db_column="Chi1_Natura")
    c_partita_vend = models.TextField(null=True, blank=True, db_column="CPartitaVend")
    c_partita_acq = models.TextField(null=True, blank=True, db_column="CPartitaAcq")
    data_creazione = models.DateTimeField(null=True, blank=True, db_column="DataCreazione")
    nomenclatura = models.TextField(null=True, blank=True, db_column="Nomenclatura")
    bene_servizio = models.TextField(null=True, blank=True, db_column="Bene_Servizio")

    giacenza = models.BooleanField(null=True, blank=True, db_column="Giacenza")
    disponibile = models.BooleanField(null=True, blank=True, db_column="Disponibile")
    fl_disattivato = models.BooleanField(null=True, blank=True, db_column="FlDisattivato")
    gest_lotti = models.BooleanField(null=True, blank=True, db_column="GestLotti")
    kit = models.BooleanField(null=True, blank=True, db_column="Kit")
    no_magazzino = models.BooleanField(null=True, blank=True, db_column="No_Magazzino")
    confezionato = models.BooleanField(null=True, blank=True, db_column="Confezionato")
    articolo_tag = models.BooleanField(null=True, blank=True, db_column="Articolo_TAG")
    richiesta_patentino = models.BooleanField(null=True, blank=True, db_column="Richiesta_patentino")

    # In PostgreSQL sono boolean (mirror 4D); non modificarli come numerici.
    prog_ord_v = models.BooleanField(null=True, blank=True, db_column="ProgOrdV")
    prog_ord_a = models.BooleanField(null=True, blank=True, db_column="ProgOrdA")
    data_ult_car = models.DateTimeField(null=True, blank=True, db_column="DataUltCar")
    data_ult_scar = models.DateTimeField(null=True, blank=True, db_column="DataUltScar")
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

    @property
    def chi1_natura_sdi_descrizione(self) -> str:
        from apps.aliquote.models import NATURE_SDI

        code = (self.chi1_natura or "").strip().upper()
        return NATURE_SDI.get(code, "")

    @property
    def chi1_natura_sdi_label(self) -> str:
        from apps.aliquote.models import label_natura_sdi

        return label_natura_sdi(self.chi1_natura)
