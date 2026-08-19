from django.db import models
from django.urls import reverse


def _scadenza_data(value):
    """Date 4D vuote (00/00/00, anno < 1901) → None."""
    if value is None:
        return None
    year = getattr(value, "year", None)
    if year is None or year < 1901:
        return None
    return value


class Primanota(models.Model):
    """Mirror PostgreSQL della tabella 4D Primanota (gestita dal sync)."""

    TIPO_GENERICO = 1
    TIPO_IVA = 2
    TIPO_CORRISPETTIVI = 3
    TIPO_IVA_AUTOFATTURA = 4
    TIPO_CHOICES = (
        (TIPO_GENERICO, "Generico"),
        (TIPO_IVA, "IVA"),
        (TIPO_CORRISPETTIVI, "Corrispettivi"),
        (TIPO_IVA_AUTOFATTURA, "Iva con Autofattura"),
    )

    id = models.IntegerField(primary_key=True, db_column="ID")
    numero_reg = models.IntegerField(null=True, blank=True, db_column="NumeroReg")
    data_reg = models.DateTimeField(null=True, blank=True, db_column="DataReg")
    numero_doc = models.TextField(null=True, blank=True, db_column="NumeroDoc")
    data_doc = models.DateTimeField(null=True, blank=True, db_column="DataDoc")
    numero_prot = models.IntegerField(null=True, blank=True, db_column="NumeroProt")
    alfa_prot = models.TextField(null=True, blank=True, db_column="AlfaProt")
    causale = models.TextField(null=True, blank=True, db_column="Causale")
    registro = models.TextField(null=True, blank=True, db_column="Registro")
    tipo = models.SmallIntegerField(
        null=True, blank=True, db_column="Tipo", choices=TIPO_CHOICES
    )
    codice_partita = models.TextField(null=True, blank=True, db_column="CodicePartita")
    codice_paga = models.TextField(null=True, blank=True, db_column="CodicePaga")
    valuta = models.TextField(null=True, blank=True, db_column="Valuta")
    codice_agente = models.TextField(null=True, blank=True, db_column="CodiceAgente")
    fornitore_cee = models.TextField(null=True, blank=True, db_column="FornitoreCEE")
    data_valuta = models.DateTimeField(null=True, blank=True, db_column="DataValuta")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    totale_doc_controllo = models.FloatField(
        null=True, blank=True, db_column="TotaleDoc_Controllo"
    )
    acconto = models.FloatField(null=True, blank=True, db_column="Acconto")
    scadenze_ins = models.BooleanField(null=True, blank=True, db_column="ScadenzeIns")
    nr_fatt_anno = models.TextField(null=True, blank=True, db_column="Nr_Fatt_Anno")
    guid = models.TextField(null=True, blank=True, db_column="GUID")
    synced_at = models.DateTimeField(null=True, blank=True)

    for _i in range(1, 11):
        locals()[f"scad{_i}"] = models.DateTimeField(
            null=True, blank=True, db_column=f"Scad{_i}"
        )
        locals()[f"imp_scad{_i}"] = models.FloatField(
            null=True, blank=True, db_column=f"ImpScad{_i}"
        )
        locals()[f"flag_ra{_i:02d}"] = models.BooleanField(
            null=True, blank=True, db_column=f"Flag_RA{_i:02d}"
        )
    del _i

    class Meta:
        managed = False
        db_table = "primanota"
        verbose_name = "Registrazione prima nota"
        verbose_name_plural = "Prima nota"
        ordering = ["-data_reg", "-numero_reg", "-id"]

    def __str__(self):
        return f"{self.numero_registrazione} ({self.id})"

    def get_absolute_url(self):
        return reverse("primanota:detail", kwargs={"pk": self.pk})

    @property
    def numero_registrazione(self) -> str:
        if self.numero_reg is None:
            return "—"
        return str(self.numero_reg)

    @property
    def tipo_label(self) -> str:
        if self.tipo is None or self.tipo == "":
            return "—"
        try:
            key = int(self.tipo)
        except (TypeError, ValueError):
            return str(self.tipo)
        return dict(self.TIPO_CHOICES).get(key, str(self.tipo))

    @property
    def is_iva(self) -> bool:
        try:
            return int(self.tipo) in (self.TIPO_IVA, self.TIPO_IVA_AUTOFATTURA)
        except (TypeError, ValueError):
            return False

    @property
    def is_generico(self) -> bool:
        try:
            return int(self.tipo) == self.TIPO_GENERICO
        except (TypeError, ValueError):
            return False

    @property
    def is_corrispettivi(self) -> bool:
        try:
            return int(self.tipo) == self.TIPO_CORRISPETTIVI
        except (TypeError, ValueError):
            return False

    @property
    def is_iva_autofattura(self) -> bool:
        try:
            return int(self.tipo) == self.TIPO_IVA_AUTOFATTURA
        except (TypeError, ValueError):
            return False

    @property
    def protocollo(self) -> str:
        numero = self.numero_prot
        serie = (self.alfa_prot or "").strip()
        if numero is None and not serie:
            return "—"
        if numero is None:
            return serie
        if not serie:
            return str(numero)
        return f"{numero}/{serie}"

    @property
    def scadenze_righe(self) -> list[dict]:
        rows = []
        for i in range(1, 11):
            importo = getattr(self, f"imp_scad{i}", None)
            rows.append(
                {
                    "n": i,
                    "data": _scadenza_data(getattr(self, f"scad{i}", None)),
                    "importo": float(importo or 0),
                    "rit_acc": bool(getattr(self, f"flag_ra{i:02d}", False)),
                }
            )
        return rows

    @property
    def totale_scadenze(self) -> float:
        return float(sum(r["importo"] for r in self.scadenze_righe))


class PrimanotaDettaglio(models.Model):
    """Mirror PostgreSQL della tabella 4D Primanota_Dettaglio (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    id_testa = models.BigIntegerField(
        null=True,
        blank=True,
        db_column="id_added_by_converter",
        db_index=True,
        verbose_name="ID testa prima nota",
    )
    pos = models.SmallIntegerField(null=True, blank=True, db_column="Pos")
    conto_dare = models.TextField(null=True, blank=True, db_column="ContoDare")
    conto_avere = models.TextField(null=True, blank=True, db_column="ContoAvere")
    des_conto_dare = models.TextField(null=True, blank=True, db_column="DesContoDare")
    des_conto_avere = models.TextField(null=True, blank=True, db_column="DesContoAvere")
    dare = models.FloatField(null=True, blank=True, db_column="Dare")
    avere = models.FloatField(null=True, blank=True, db_column="Avere_Imponibile")
    imp_val = models.FloatField(null=True, blank=True, db_column="Imp_Val")
    codice_iva = models.TextField(null=True, blank=True, db_column="CodiceIva")
    importo_iva = models.FloatField(null=True, blank=True, db_column="ImportoIva")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    anno_doc = models.TextField(null=True, blank=True, db_column="AnnoDoc")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    dummy = models.BooleanField(null=True, blank=True, db_column="dummy")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "primanota_dettaglio"
        verbose_name = "Riga prima nota"
        verbose_name_plural = "Righe prima nota"
        ordering = ["id_testa", "pos", "id"]

    def __str__(self):
        return f"riga #{self.id}"

    @property
    def conto_partita(self) -> str:
        return (self.conto_avere or self.conto_dare or "").strip()

    @property
    def imponibile(self) -> float:
        if (self.conto_avere or "").strip():
            return float(self.avere or 0)
        return float(self.dare or 0)

    @property
    def imponibile_valuta(self) -> float:
        val = float(self.imp_val or 0)
        return val if val else self.imponibile
