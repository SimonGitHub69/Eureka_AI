from django.conf import settings
from django.db import models
from django.db.models import OuterRef, Subquery


class SyncFattureLog(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    fatture_count = models.PositiveIntegerField(default=0)
    dettaglio_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sync_fatture_logs",
    )

    class Meta:
        verbose_name = "Log sync fatture"
        verbose_name_plural = "Log sync fatture"
        ordering = ["-started_at"]

    def __str__(self):
        stato = "OK" if self.ok else "ERR"
        return f"Sync {self.started_at:%Y-%m-%d %H:%M} [{stato}]"


class Fattura(models.Model):
    """Mirror PostgreSQL della tabella 4D Fatture (gestita dal sync)."""

    id_testa = models.IntegerField(primary_key=True, db_column="ID_Testa")
    numero_fatt = models.IntegerField(null=True, blank=True, db_column="NumeroFatt")
    data_fattura = models.DateTimeField(null=True, blank=True, db_column="DataFattura")
    cliente = models.TextField(null=True, blank=True, db_column="Cliente")
    destinatario = models.TextField(null=True, blank=True, db_column="Destinatario")
    indirizzo = models.TextField(null=True, blank=True, db_column="Indirizzo")
    localita = models.TextField(null=True, blank=True, db_column="Localita")
    cap = models.TextField(null=True, blank=True, db_column="Cap")
    provincia = models.TextField(null=True, blank=True, db_column="Prov")
    nazione = models.TextField(null=True, blank=True, db_column="Nazione")
    cod_iso_dest = models.TextField(null=True, blank=True, db_column="CodISO_Dest")
    totale_fattura = models.FloatField(null=True, blank=True, db_column="TotaleFattura")
    imponibile = models.FloatField(null=True, blank=True, db_column="Imponibile")
    alfa = models.TextField(null=True, blank=True, db_column="Alfa")
    desc_nota_c = models.TextField(null=True, blank=True, db_column="DescNotaC")
    desc_causale = models.TextField(null=True, blank=True, db_column="Desc_Causale")
    tipo_doc_fe = models.TextField(null=True, blank=True, db_column="TipoDocFE")
    spese_imballo = models.FloatField(null=True, blank=True, db_column="SpeseImballo")
    spese_trasporto = models.FloatField(null=True, blank=True, db_column="SpeseTrasporto")
    spese_incasso = models.FloatField(null=True, blank=True, db_column="SpeseIncasso")
    spese_varie = models.FloatField(null=True, blank=True, db_column="SpeseVarie")
    spese_bolli = models.FloatField(null=True, blank=True, db_column="SpeseBolli")
    spese_e15 = models.FloatField(null=True, blank=True, db_column="Spese_E15")
    imp_spese_bollo_virtuale = models.FloatField(
        null=True, blank=True, db_column="ImpSpeseBolloVirtuale"
    )
    # Campi fattura elettronica SDI
    cod_sdi = models.TextField(null=True, blank=True, db_column="CodSDI")
    progressivo_invio = models.IntegerField(null=True, blank=True, db_column="ProgressivoInvio")
    email_pec = models.TextField(null=True, blank=True, db_column="Email_PEC")
    file_name = models.TextField(null=True, blank=True, db_column="FileName")
    iban = models.TextField(null=True, blank=True, db_column="IBAN")
    cod_pagamento = models.TextField(null=True, blank=True, db_column="CodPagamento")
    cig = models.TextField(null=True, blank=True, db_column="FattPA_CIG")
    cup = models.TextField(null=True, blank=True, db_column="CUP")
    num_ordine_acq = models.TextField(null=True, blank=True, db_column="NumOrdineAcq")
    data_ordine_acq = models.DateTimeField(null=True, blank=True, db_column="DataOrdineAcq")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "fatture"
        verbose_name = "Fattura"
        verbose_name_plural = "Fatture"
        ordering = ["-data_fattura", "-numero_fatt", "alfa"]

    def __str__(self):
        return f"{self.numero_documento} ({self.id_testa})"

    @property
    def alfa_serie(self):
        """Serie documento senza spazi inutili."""
        return (self.alfa or "").strip()

    @property
    def numero_documento(self):
        """Numero visualizzato: 47/A, 1/NZ; senza '/' se alfa è vuoto."""
        numero = self.numero_fatt
        serie = self.alfa_serie
        if numero is None and not serie:
            return "—"
        if numero is None:
            return serie
        if not serie:
            return str(numero)
        return f"{numero}/{serie}"

    @property
    def is_nota_credito(self):
        return (self.tipo_doc_fe or "").strip().upper() == "TD04"

    @property
    def totale_spese(self):
        """Somma spese di testata (imballo, trasporto, incasso, varie, bolli, E15)."""
        parts = (
            self.spese_imballo,
            self.spese_trasporto,
            self.spese_incasso,
            self.spese_varie,
            self.spese_bolli,
            self.spese_e15,
        )
        return float(sum(float(p or 0) for p in parts))

    @property
    def totale_spese_con_segno(self):
        """Compat: le spese restano sempre positive (anche su nota di credito)."""
        return abs(self.totale_spese)

    @property
    def imponibile_netto_spese(self):
        """Imponibile al netto delle spese di testata."""
        if self.imponibile is None:
            return None
        return float(self.imponibile) - self.totale_spese

    @property
    def cliente_ragione_sociale(self):
        """Ragione sociale del cliente collegato (richiede annotate_cliente_ragione_sociale)."""
        parts = [
            p
            for p in (
                getattr(self, "cliente_ragione_sociale1", None),
                getattr(self, "cliente_ragione_sociale2", None),
            )
            if p
        ]
        return " ".join(parts)


def annotate_cliente_ragione_sociale(queryset):
    """LEFT JOIN logico fatture.Cliente -> clienti.Codice via Subquery (no FK).

    Se la tabella mirror ``clienti`` manca (es. dopo Azzera tabelle), lascia il
    queryset senza annotation: in UI resta solo il codice cliente.
    """
    from apps.anagrafiche.models import Cliente, clienti_mirror_available

    if not clienti_mirror_available():
        return queryset

    cliente_base = Cliente.objects.filter(codice=OuterRef("cliente"))
    return queryset.annotate(
        cliente_ragione_sociale1=Subquery(
            cliente_base.values("ragione_sociale1")[:1]
        ),
        cliente_ragione_sociale2=Subquery(
            cliente_base.values("ragione_sociale2")[:1]
        ),
    )


class FatturaDettaglio(models.Model):
    """Mirror PostgreSQL della tabella 4D Fatture_Dettaglio (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    id_testa = models.IntegerField(
        null=True,
        blank=True,
        db_column="id_added_by_converter",
        db_index=True,
        verbose_name="ID testa fattura",
    )
    id_riga = models.IntegerField(null=True, blank=True, db_column="ID_Riga")
    codice = models.TextField(null=True, blank=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="DescAgg")
    quantita = models.FloatField(null=True, blank=True, db_column="Quantita")
    prezzo_unitario = models.FloatField(null=True, blank=True, db_column="PrezzoUnitario")
    iva = models.TextField(null=True, blank=True, db_column="Iva")
    unita_misura = models.TextField(null=True, blank=True, db_column="UnitaMisura")
    sconto = models.TextField(null=True, blank=True, db_column="Sconto")
    numero_riga = models.IntegerField(null=True, blank=True, db_column="NumeroRiga")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "fatture_dettaglio"
        verbose_name = "Riga fattura"
        verbose_name_plural = "Righe fattura"
        ordering = ["id_testa", "numero_riga", "id"]

    def __str__(self):
        return f"{self.codice or 'riga'} #{self.id}"
