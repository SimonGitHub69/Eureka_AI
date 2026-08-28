from django.db import models
from django.urls import reverse


class CausaleContabile(models.Model):
    """Mirror PostgreSQL della tabella 4D CausaliC (Causali Contabili)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    c_dare_1 = models.TextField(null=True, blank=True, db_column="CDare1")
    c_avere_1 = models.TextField(null=True, blank=True, db_column="CAvere1")
    partite_aperte = models.TextField(null=True, blank=True, db_column="PartiteAperte")
    tipo_causale = models.TextField(null=True, blank=True, db_column="TipoCausale")
    incrementa_doc = models.TextField(null=True, blank=True, db_column="IncrementaDoc")
    registro_iva = models.TextField(null=True, blank=True, db_column="RegistroIva")
    desc_pn = models.TextField(null=True, blank=True, db_column="Desc_Pn")
    c_dare_2 = models.TextField(null=True, blank=True, db_column="CDare2")
    c_dare_3 = models.TextField(null=True, blank=True, db_column="CDare3")
    c_dare_4 = models.TextField(null=True, blank=True, db_column="CDare4")
    c_dare_5 = models.TextField(null=True, blank=True, db_column="CDare5")
    c_dare_6 = models.TextField(null=True, blank=True, db_column="CDare6")
    c_dare_7 = models.TextField(null=True, blank=True, db_column="CDare7")
    c_dare_8 = models.TextField(null=True, blank=True, db_column="CDare8")
    c_dare_9 = models.TextField(null=True, blank=True, db_column="CDare9")
    c_dare_10 = models.TextField(null=True, blank=True, db_column="CDare10")
    c_avere_2 = models.TextField(null=True, blank=True, db_column="CAvere2")
    c_avere_3 = models.TextField(null=True, blank=True, db_column="CAvere3")
    c_avere_4 = models.TextField(null=True, blank=True, db_column="CAvere4")
    c_avere_5 = models.TextField(null=True, blank=True, db_column="CAvere5")
    c_avere_6 = models.TextField(null=True, blank=True, db_column="CAvere6")
    c_avere_7 = models.TextField(null=True, blank=True, db_column="CAvere7")
    c_avere_8 = models.TextField(null=True, blank=True, db_column="CAvere8")
    c_avere_9 = models.TextField(null=True, blank=True, db_column="CAvere9")
    c_avere_10 = models.TextField(null=True, blank=True, db_column="CAvere10")
    causale_17_6 = models.BooleanField(null=True, blank=True, db_column="Causale17_6")
    tipo_sa = models.BooleanField(null=True, blank=True, db_column="Tipo_SA")
    flag_red_partitari = models.BooleanField(null=True, blank=True, db_column="Flag_Red_Partitari")
    tipo_doc_fel = models.TextField(null=True, blank=True, db_column="TipoDocFEL")
    testo_auto_fattura = models.TextField(null=True, blank=True, db_column="Testo_AutoFattura")
    causale_colleg_auto_f = models.TextField(null=True, blank=True, db_column="CausaleCollegAutoF")
    cliente_auto_f = models.TextField(null=True, blank=True, db_column="ClienteAutoF")
    sotto_conto_iva_acq_auto_f = models.TextField(null=True, blank=True, db_column="SottoContoIvaAcqAutoF")
    sotto_conto_iva_vend_auto_f = models.TextField(null=True, blank=True, db_column="SottoContoIvaVendAutoF")
    esterometro = models.BooleanField(null=True, blank=True, db_column="Esterometro")
    autofattura = models.BooleanField(null=True, blank=True, db_column="Autofattura")
    iva_con_autofattura = models.BooleanField(null=True, blank=True, db_column="IvaConAutofattura")
    contatore_auto_f = models.TextField(null=True, blank=True, db_column="ContatoreAutoF")
    flag_cond_pag = models.BooleanField(null=True, blank=True, db_column="flag_CondPag")
    desc_reg_iva = models.TextField(null=True, blank=True, db_column="Desc_RegIva")
    cont_analitica_no_control = models.BooleanField(null=True, blank=True, db_column="ContAnalitica_NOControl")
    xml_default = models.BooleanField(null=True, blank=True, db_column="XML_Default")
    cassa_corrispettivi = models.TextField(null=True, blank=True, db_column="CassaCorrispettivi")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "causali_contabili"
        verbose_name = "Causale contabile"
        verbose_name_plural = "Causali contabili"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} – {self.descrizione or ''}"

    def get_absolute_url(self):
        return reverse("causali_contabili:detail", kwargs={"codice": self.codice})

    @property
    def label(self) -> str:
        return (self.descrizione or self.desc_pn or "").strip()

    @property
    def tipo_doc_fel_label(self) -> str:
        from apps.causali_contabili.lookups import tipo_doc_fel_display

        return tipo_doc_fel_display(self.tipo_doc_fel) or "—"

    @property
    def tipo_doc_fel_code(self) -> str:
        from apps.causali_contabili.lookups import norm_tipo_doc_fel

        return norm_tipo_doc_fel(self.tipo_doc_fel)

    @property
    def tipo_doc_fel_caption(self) -> str:
        from apps.causali_contabili.lookups import tipo_doc_fel_caption

        return tipo_doc_fel_caption(self.tipo_doc_fel)
