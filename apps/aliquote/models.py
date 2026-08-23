from decimal import Decimal, ROUND_HALF_UP

from django.db import models

# Codici Natura FatturaPA (specifiche AdE v1.2.2+)
NATURE_SDI = {
    "N1": "Escluse ex art. 15",
    "N2.1": "Non soggette ad IVA artt. da 7 a 7-septies DPR 633/72",
    "N2.2": "Non soggette - altri casi",
    "N3.1": "Non imponibili - esportazioni",
    "N3.2": "Non imponibili - cessioni intracomunitarie",
    "N3.3": "Non imponibili - cessioni verso San Marino",
    "N3.4": "Non imponibili - operazioni assimilate alle cessioni all'esportazione",
    "N3.5": "Non imponibili - a seguito di dichiarazioni d'intento",
    "N3.6": "Non imponibili - altre operazioni che non concorrono al plafond",
    "N4": "Esenti",
    "N5": "Regime del margine / IVA non esposta in fattura",
    "N6.1": "Inversione contabile - rottami e materiali di recupero",
    "N6.2": "Inversione contabile - oro e argento puro",
    "N6.3": "Inversione contabile - subappalto settore edile",
    "N6.4": "Inversione contabile - cessione di fabbricati",
    "N6.5": "Inversione contabile - telefoni cellulari",
    "N6.6": "Inversione contabile - prodotti elettronici",
    "N6.7": "Inversione contabile - prestazioni comparto edile",
    "N6.8": "Inversione contabile - settore energetico",
    "N6.9": "Inversione contabile - altri casi",
    "N7": "IVA assolta in altro stato UE",
}


def label_natura_sdi(code: str | None) -> str:
    """Ritorna 'N3.5 - …' oppure il codice grezzo se sconosciuto."""
    raw = (code or "").strip().upper()
    if not raw:
        return ""
    descrizione = NATURE_SDI.get(raw)
    if descrizione:
        return f"{raw} - {descrizione}"
    return raw


# Valori tipici campo Riferimento (4D AliquoteIva)
RIFERIMENTO_CHOICES_VALUES = (
    "Somma alla riga Imponibile",
    "Somma alla riga non Imponibile",
    "Somma alla riga Esente",
    "Non somma elenchi Cli/For",
)


class Aliquota(models.Model):
    """Mirror PostgreSQL della tabella 4D AliquoteIva (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    percentuale = models.FloatField(null=True, blank=True, db_column="Percentuale")
    percentuale_ind = models.FloatField(null=True, blank=True, db_column="PercentualeInd")
    riferimento = models.TextField(null=True, blank=True, db_column="Riferimento")
    natura_cod_ese_edi = models.TextField(
        null=True,
        blank=True,
        db_column="Natura_CodEse_EDI",
        verbose_name="Natura SDI",
    )
    des_ese_edi = models.TextField(null=True, blank=True, db_column="DesEse_EDI")
    desc_fattura1 = models.TextField(null=True, blank=True, db_column="Desc_Fattura1")
    desc_fattura2 = models.TextField(null=True, blank=True, db_column="Desc_Fattura2")
    desc_fattura_corpo = models.TextField(null=True, blank=True, db_column="Desc_FatturaCorpo")
    flag_vp2_2 = models.BooleanField(null=True, blank=True, db_column="Flag_VP2_2")
    fl_reverse_charge = models.BooleanField(
        null=True, blank=True, db_column="Fl_Reverse_Charge17_6"
    )
    flag_omaggio = models.BooleanField(null=True, blank=True, db_column="Flag_Omaggio")
    cod_reparto = models.TextField(null=True, blank=True, db_column="CodReparto")
    tipo_esigibilita = models.TextField(
        null=True, blank=True, db_column="Tipo_Esigibilita"
    )
    calc_spese_bolli = models.BooleanField(null=True, blank=True, db_column="Calc_SpeseBolli")
    flag_certificaz_esp = models.BooleanField(
        null=True, blank=True, db_column="Flag_CertificazEsp"
    )
    disabilitato = models.BooleanField(null=True, blank=True, db_column="Disabilitato")
    non_visibile = models.BooleanField(null=True, blank=True, db_column="NonVisibile")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "aliquote"
        verbose_name = "Aliquota IVA"
        verbose_name_plural = "Aliquote IVA"
        ordering = ["codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"

    @property
    def label(self) -> str:
        desc = (self.descrizione or "").strip()
        if desc:
            return desc
        if self.percentuale is not None:
            return f"IVA {self.percentuale:g}%"
        return (self.codice or "").strip()

    @property
    def aliquota_sdi(self) -> Decimal:
        """Percentuale normalizzata per FatturaPA (max 2 decimali, senza quirk split)."""
        raw = Decimal(str(self.percentuale or 0))
        # Es. 22.01101 (split) → 22.00
        if raw > 100:
            raw = Decimal("0")
        # Se ha millesimi anomali oltre 2 decimali utili, arrotonda a intero/2 dec
        quantized = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # 22.01 tipicamente split spurio → 22
        if quantized == Decimal("22.01"):
            return Decimal("22.00")
        return quantized

    @property
    def natura_sdi(self) -> str:
        return (self.natura_cod_ese_edi or "").strip().upper()

    @property
    def natura_sdi_label(self) -> str:
        return label_natura_sdi(self.natura_cod_ese_edi)

    @property
    def natura_sdi_descrizione(self) -> str:
        return NATURE_SDI.get(self.natura_sdi, "")

    @property
    def esigibilita_sdi(self) -> str:
        """I=immediata, D=differita, S=scissione pagamenti."""
        raw = (self.tipo_esigibilita or "").strip().upper()
        if raw in {"I", "D", "S"}:
            return raw
        return "I"
