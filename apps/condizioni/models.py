from django.db import models

# Codici ModalitaPagamento FatturaPA / SDI (Agenzia delle Entrate).
MODALITA_PAGAMENTO_SDI = {
    "MP01": "Contanti",
    "MP02": "Assegno",
    "MP03": "Assegno circolare",
    "MP04": "Contanti presso Tesoreria",
    "MP05": "Bonifico",
    "MP06": "Vaglia cambiario",
    "MP07": "Bollettino bancario",
    "MP08": "Carta di pagamento",
    "MP09": "RID",
    "MP10": "RID utenze",
    "MP11": "RID veloce",
    "MP12": "Ri.Ba.",
    "MP13": "MAV",
    "MP14": "Quietanza erario",
    "MP15": "Giroconto su conti di contabilità speciale",
    "MP16": "Domiciliazione bancaria",
    "MP17": "Domiciliazione postale",
    "MP18": "Bollettino di c/c postale",
    "MP19": "SEPA Direct Debit",
    "MP20": "SEPA Direct Debit CORE",
    "MP21": "SEPA Direct Debit B2B",
    "MP22": "Trattenuta su somme già riscosse",
    "MP23": "PagoPA",
}


def label_modalita_pagamento_sdi(code: str | None) -> str:
    """Ritorna 'MP05 - Bonifico' oppure il codice grezzo se sconosciuto."""
    raw = (code or "").strip().upper()
    if not raw:
        return ""
    descrizione = MODALITA_PAGAMENTO_SDI.get(raw)
    if descrizione:
        return f"{raw} - {descrizione}"
    return raw


class Condizione(models.Model):
    """Mirror PostgreSQL della tabella 4D CondizioniPag (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    tipo_pagamento = models.TextField(null=True, blank=True, db_column="TipoPagamento")
    numero_rate = models.SmallIntegerField(null=True, blank=True, db_column="NumeroRate")
    prima_rata = models.SmallIntegerField(null=True, blank=True, db_column="PrimaRata")
    intervallo = models.SmallIntegerField(null=True, blank=True, db_column="Intervallo")
    giorno_fisso = models.SmallIntegerField(null=True, blank=True, db_column="GiornoFisso")
    fine_mese = models.BooleanField(null=True, blank=True, db_column="FineMese", verbose_name="Fine mese")
    mese_esclusione = models.SmallIntegerField(null=True, blank=True, db_column="MeseEsclusione")
    mese_esclusione2 = models.SmallIntegerField(null=True, blank=True, db_column="MeseEsclusione2")
    gg_mese_esclus = models.SmallIntegerField(null=True, blank=True, db_column="GGMeseEsclus")
    gg_mese_esclus2 = models.SmallIntegerField(null=True, blank=True, db_column="GGMeseEsclus2")
    codice_banca = models.TextField(null=True, blank=True, db_column="CodiceBanca")
    pag_fatt_elett_pa = models.TextField(
        null=True,
        blank=True,
        db_column="PagFattElettPA",
        verbose_name="Modalità pagamento SDI",
    )
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "condizioni"
        verbose_name = "Condizione di Pagamento"
        verbose_name_plural = "Condizioni di Pagamento"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"

    @property
    def pag_fatt_elett_pa_label(self) -> str:
        return label_modalita_pagamento_sdi(self.pag_fatt_elett_pa)

    @property
    def pag_fatt_elett_pa_descrizione(self) -> str:
        raw = (self.pag_fatt_elett_pa or "").strip().upper()
        return MODALITA_PAGAMENTO_SDI.get(raw, "")
