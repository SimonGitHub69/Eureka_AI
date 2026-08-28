from django.conf import settings
from django.db import models
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.documenti.layout import CAMPO_RIGA_CHOICES


def _default_esercizio() -> int:
    return timezone.localdate().year


class ContatoreDocumento(models.Model):
    """
    Contatore di numerazione documenti.

    Più tipi documento (ParametriDoc) possono condividere lo stesso contatore
    (sequenza unica) oppure usarne di distinti (sequenze indipendenti).
    """

    TIPO_DOCUMENTI = "DOCUMENTI"
    TIPO_PRIMANOTA = "PRIMANOTA"
    TIPO_CHOICES = (
        (TIPO_DOCUMENTI, "Documenti"),
        (TIPO_PRIMANOTA, "Primanota"),
    )

    codice = models.CharField(
        max_length=16,
        verbose_name="Codice",
        help_text="Codice breve (es. FAT, ORD, PN). Univoco insieme a esercizio e tipo.",
        db_index=True,
    )
    label = models.CharField("Descrizione", max_length=120)
    tipo_contatore = models.CharField(
        "Tipo contatore",
        max_length=16,
        choices=TIPO_CHOICES,
        default=TIPO_DOCUMENTI,
        db_index=True,
        help_text="Ambito di utilizzo: numerazione documenti o primanota.",
    )
    esercizio = models.PositiveSmallIntegerField(
        "Esercizio",
        default=_default_esercizio,
        help_text="Anno contabile/fiscale di riferimento per la numerazione.",
    )
    ultimo_numero = models.PositiveIntegerField(
        "Ultimo numero",
        default=0,
        help_text="Ultimo numero assegnato. Il prossimo documento riceve ultimo_numero + 1.",
    )
    serie_default = models.CharField(
        "Serie predefinita",
        max_length=16,
        blank=True,
        help_text="Opzionale: valorizzata sul documento in creazione se la serie è vuota.",
    )

    class Meta:
        db_table = "contatori_documento"
        verbose_name = "Contatore documento"
        verbose_name_plural = "Contatori documento"
        ordering = ["tipo_contatore", "esercizio", "codice"]
        constraints = [
            models.UniqueConstraint(
                fields=["codice", "esercizio", "tipo_contatore"],
                name="uniq_contatore_codice_esercizio_tipo",
            ),
        ]

    def __str__(self):
        return f"{self.codice} · {self.esercizio} — {self.label}"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("documenti:contatori_detail", kwargs={"pk": self.pk})

    @property
    def tipo_contatore_label(self) -> str:
        return dict(self.TIPO_CHOICES).get(self.tipo_contatore, self.tipo_contatore or "—")

    @property
    def prossimo_numero(self) -> int:
        return int(self.ultimo_numero or 0) + 1


class TipoDocumento(models.Model):
    """
    Parametri documento (ispirato a PARAMETRIDOC / FCOLOR).

    Il codice è libero (ORV, ORA, PRV, DDT, FAT, NCR, NDB, …): la categoria
    raggruppa più codici della stessa famiglia (es. due ordini vendita).
    """

    CATEGORIA_ORDINI = "ORDINI"
    CATEGORIA_FATTURE = "FATTURE"
    CATEGORIA_NOTE_CREDITO = "NOTE_CREDITO"
    CATEGORIA_NOTE_DEBITO = "NOTE_DEBITO"
    CATEGORIA_PREVENTIVI = "PREVENTIVI"
    CATEGORIA_DDT = "DDT"
    CATEGORIA_ALTRO = "ALTRO"
    CATEGORIA_CHOICES = (
        (CATEGORIA_ORDINI, "Ordini"),
        (CATEGORIA_FATTURE, "Fatture"),
        (CATEGORIA_NOTE_CREDITO, "Note credito"),
        (CATEGORIA_NOTE_DEBITO, "Note debito"),
        (CATEGORIA_PREVENTIVI, "Preventivi"),
        (CATEGORIA_DDT, "DDT"),
        (CATEGORIA_ALTRO, "Altro"),
    )
    # Famiglie per il combo Serie in Nuovo documento: unione dei contatori
    # di tutti i tipi nelle categorie affini (es. Preventivi ↔ Ordini).
    CATEGORIE_CONTATORI_AFFINI: tuple[frozenset[str], ...] = (
        frozenset({CATEGORIA_PREVENTIVI, CATEGORIA_ORDINI}),
        frozenset(
            {CATEGORIA_FATTURE, CATEGORIA_NOTE_CREDITO, CATEGORIA_NOTE_DEBITO}
        ),
        frozenset({CATEGORIA_DDT}),
        frozenset({CATEGORIA_ALTRO}),
    )

    CLIFOR_CLIENTE = "C"
    CLIFOR_FORNITORE = "F"
    CLIFOR_CHOICES = (
        (CLIFOR_CLIENTE, "Cliente"),
        (CLIFOR_FORNITORE, "Fornitore"),
    )

    codice = models.CharField(
        max_length=8,
        primary_key=True,
        verbose_name="Codice",
        help_text="Codice breve univoco: ORV, ORA, PRV, DDT, FAT, NCR, NDB o altro personalizzato.",
    )
    label = models.CharField("Descrizione", max_length=120)
    descrizione = models.TextField("Note", blank=True)
    categoria = models.CharField(
        "Famiglia",
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default=CATEGORIA_ALTRO,
        db_index=True,
        help_text="Famiglia del documento: consente più codici per Ordini, Fatture, ecc.",
    )
    attivo = models.BooleanField(default=True)
    ordine = models.PositiveSmallIntegerField(default=0)
    # Tabelle 4D sorgente per sync ODBC
    source_table_4d = models.CharField("Tabella 4D testata", max_length=80, blank=True)
    source_detail_4d = models.CharField("Tabella 4D righe", max_length=80, blank=True)
    clifor_tipo = models.CharField(
        "Anagrafica",
        max_length=1,
        blank=True,
        choices=CLIFOR_CHOICES,
        help_text="Il documento è intestato a un cliente o a un fornitore.",
    )
    SCADENZE_FACOLTATIVE = "FACOLTATIVE"
    SCADENZE_OBBLIGATORIE = "OBBLIGATORIE"
    SCADENZE_CHOICES = (
        (SCADENZE_FACOLTATIVE, "Facoltative"),
        (SCADENZE_OBBLIGATORIE, "Obbligatorie"),
    )
    scadenze = models.CharField(
        "Scadenze",
        max_length=12,
        choices=SCADENZE_CHOICES,
        default=SCADENZE_FACOLTATIVE,
        help_text="Se obbligatorie, il documento non si salva senza almeno una data di scadenza.",
    )
    contatore = models.ForeignKey(
        ContatoreDocumento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tipi_documento",
        verbose_name="Contatore predefinito",
        help_text=(
            "Contatore predefinito in creazione (combo Serie). "
            "Vuoto = numerazione automatica per tipo se non ci sono contatori associati."
        ),
    )
    contatori = models.ManyToManyField(
        ContatoreDocumento,
        blank=True,
        related_name="tipi_documento_multi",
        verbose_name="Contatori / serie",
        help_text=(
            "Contatori selezionabili nella maschera documento (combo Serie), "
            "uniti a quelli dei tipi affini (es. Preventivi↔Ordini). "
            "Il Contatore predefinito è usato all'apertura di Nuovo."
        ),
    )
    serie = models.CharField(
        "Serie",
        max_length=16,
        blank=True,
        help_text=(
            "Opzionale: serie (alfa) precompilata sui nuovi documenti. "
            "Se valorizzata ha priorità sulla serie del contatore predefinito "
            "(ignorata se l'utente sceglie un'altra serie dal combo)."
        ),
    )
    testo_mail = models.TextField(
        "Testo mail",
        blank=True,
        default="",
        help_text=(
            "Testo precompilato in Invia mail. Segnaposto: "
            "{tipo} {numero} {data} {cliente} {totale} {destinatario} {codice}"
        ),
    )

    class Meta:
        db_table = "parametri_documento"
        verbose_name = "Parametro documento"
        verbose_name_plural = "Parametri documento"
        ordering = ["ordine", "codice"]

    def __str__(self):
        return f"{self.codice} — {self.label}"

    @property
    def categoria_label(self) -> str:
        return dict(self.CATEGORIA_CHOICES).get(self.categoria, self.categoria or "—")

    @property
    def clifor_label(self) -> str:
        return dict(self.CLIFOR_CHOICES).get(self.clifor_tipo, self.clifor_tipo or "—")

    @property
    def scadenze_label(self) -> str:
        return dict(self.SCADENZE_CHOICES).get(self.scadenze, self.scadenze or "—")

    @property
    def scadenze_obbligatorie(self) -> bool:
        return (self.scadenze or "") == self.SCADENZE_OBBLIGATORIE

    @property
    def contatore_label(self) -> str:
        if not self.contatore_id:
            return "—"
        c = self.contatore
        return f"{c.codice} · {c.esercizio} — {c.label}"

    @classmethod
    def categorie_affini_contatori(cls, categoria: str) -> frozenset[str]:
        """Categorie i cui contatori sono selezionabili insieme nel combo Serie."""
        cat = (categoria or "").strip().upper() or cls.CATEGORIA_ALTRO
        for gruppo in cls.CATEGORIE_CONTATORI_AFFINI:
            if cat in gruppo:
                return gruppo
        return frozenset({cat})

    def tipi_affini_contatori(self):
        """Tipi documento (stessa famiglia contatori) da cui unire le serie."""
        cats = self.categorie_affini_contatori(self.categoria)
        return (
            TipoDocumento.objects.filter(categoria__in=cats, attivo=True)
            .prefetch_related("contatori")
            .select_related("contatore")
            .order_by("ordine", "codice")
        )

    @staticmethod
    def _contatori_del_tipo(tipo: "TipoDocumento") -> list[ContatoreDocumento]:
        """Contatori configurati sul singolo tipo (M2M + predefinito)."""
        multi = list(tipo.contatori.all())
        if multi:
            if tipo.contatore_id:
                pks = {c.pk for c in multi}
                if tipo.contatore_id not in pks:
                    multi.insert(0, tipo.contatore)
            return multi
        if tipo.contatore_id:
            return [tipo.contatore]
        return []

    def contatori_disponibili(self):
        """Contatori usabili nel combo Serie.

        Unisce i contatori di questo tipo con quelli dei tipi affini
        (stessa famiglia: es. Preventivi + Ordini, Fatture + NC/ND).
        """
        by_pk: dict[int, ContatoreDocumento] = {}
        origin: dict[int, list[str]] = {}
        for tipo in self.tipi_affini_contatori():
            for c in self._contatori_del_tipo(tipo):
                if c.pk not in by_pk:
                    by_pk[c.pk] = c
                    origin[c.pk] = []
                if tipo.codice not in origin[c.pk]:
                    origin[c.pk].append(tipo.codice)
        # Se nessun affine attivo ha contatori, fallback sul solo self
        # (anche se inattivo) così create/edit restano coerenti.
        if not by_pk:
            for c in self._contatori_del_tipo(self):
                by_pk[c.pk] = c
                origin[c.pk] = [self.codice]
        ordered = sorted(
            by_pk.values(),
            key=lambda c: (
                int(c.esercizio or 0),
                (c.serie_default or "").strip(),
                c.codice,
                c.label or "",
            ),
        )
        for c in ordered:
            tipicodes = origin.get(c.pk) or []
            # Annotazione per label combo (PRV/ORV …): non persistita.
            c._tipi_origine_codici = tipicodes  # type: ignore[attr-defined]
        return ordered


class ColonnaRigaDocumento(models.Model):
    """Colonna della riga di dettaglio, per tipo documento (posizione + campo)."""

    tipo_doc = models.ForeignKey(
        TipoDocumento,
        on_delete=models.CASCADE,
        related_name="colonne_riga",
        to_field="codice",
    )
    campo = models.CharField("Campo", max_length=40, choices=CAMPO_RIGA_CHOICES)
    posizione = models.PositiveSmallIntegerField("Posizione", default=10)
    etichetta = models.CharField(
        "Etichetta",
        max_length=40,
        blank=True,
        help_text="Vuoto = etichetta predefinita del campo.",
    )
    larghezza = models.CharField(
        "Larghezza",
        max_length=16,
        blank=True,
        help_text="Es. 8rem, 120px. Vuoto = automatica.",
    )

    class Meta:
        db_table = "parametri_documento_colonne_riga"
        verbose_name = "Colonna riga documento"
        verbose_name_plural = "Colonne riga documento"
        ordering = ["tipo_doc_id", "posizione", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_doc", "campo"],
                name="uniq_colonna_riga_tipo_campo",
            ),
        ]

    def __str__(self):
        return f"{self.tipo_doc_id} {self.posizione} {self.campo}"

    def save(self, *args, **kwargs):
        from apps.documenti.layout import CAMPI_RIGA

        self.campo = (self.campo or "").strip()
        if self.campo not in CAMPI_RIGA:
            raise ValueError(f"Campo riga non valido: {self.campo}")
        super().save(*args, **kwargs)

    @property
    def etichetta_display(self) -> str:
        from apps.documenti.layout import campo_label

        return (self.etichetta or "").strip() or campo_label(self.campo)

    @property
    def icon(self) -> str:
        from apps.documenti.layout import campo_icon

        return campo_icon(self.campo)

    @property
    def align_class(self) -> str:
        from apps.documenti.layout import campo_align_class

        return campo_align_class(self.campo)

    @property
    def larghezza_css(self) -> str:
        from apps.documenti.layout import campo_larghezza

        return (self.larghezza or "").strip() or campo_larghezza(self.campo)


class TestaDocumento(models.Model):
    """
    Testata documento unificata (PostgreSQL: teste_documenti).

    Campi mappati dalle testate 4D:
    - Fatture: ID_Testa, NumeroFatt, DataFattura, Cliente, Alfa, Destinatario, …
    - Ordini_Vendita / Preventivi: ID_Testa, NumeroOrd/NumeroPrev, DataOrd/DataPrev, Cliente, Agente
    - Ordini_Acquisto: ID_Testa, NumeroOrd, DataOrd, Fornitore
    - Bolle: ID_Testa, NumeroBolla/Numero, DataBolla/Data, Cliente
    """

    CLIFOR_CLIENTE = "C"
    CLIFOR_FORNITORE = "F"
    CLIFOR_CHOICES = (
        (CLIFOR_CLIENTE, "Cliente"),
        (CLIFOR_FORNITORE, "Fornitore"),
    )

    tipo_doc = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        related_name="teste",
        db_column="tipo_doc",
        to_field="codice",
    )
    # ID_Testa (o equivalente) nella tabella 4D sorgente
    id_4d = models.IntegerField(db_index=True)
    source_table_4d = models.CharField(max_length=80, blank=True)

    numero = models.IntegerField(null=True, blank=True)
    alfa = models.TextField(blank=True)  # 4D: Alfa — serie documento
    data_documento = models.DateTimeField(null=True, blank=True)
    validita = models.TextField(blank=True)  # 4D: Validita (Preventivi; testo libero)
    data_consegna = models.DateTimeField(
        null=True, blank=True
    )  # 4D: DataConsegna (Preventivi / Ordini / Fatture)
    tipo_preventivo = models.TextField(blank=True)  # 4D: TipoPreventivo (solo Preventivi)
    confermato = models.BooleanField(default=False)  # 4D: Confermato (solo Preventivi)
    valuta = models.TextField(blank=True)  # 4D: Valuta (es. Euro)
    cambio = models.FloatField(null=True, blank=True)  # 4D: Cambio (FAT/ORA; altrimenti da Valuta)

    codice_clifor = models.TextField(blank=True)  # 4D: Cliente / Fornitore
    clifor_tipo = models.CharField(
        max_length=1,
        blank=True,
        choices=CLIFOR_CHOICES,
    )
    codice_agente = models.TextField(blank=True)  # 4D: Agente
    destinatario = models.TextField(blank=True)  # 4D: Destinatario
    indirizzo = models.TextField(blank=True)  # 4D: Indirizzo
    localita = models.TextField(blank=True)  # 4D: Localita
    cap = models.TextField(blank=True)  # 4D: Cap
    provincia = models.TextField(blank=True)  # 4D: Prov
    nazione = models.TextField(blank=True)  # 4D: Nazione
    telefono = models.TextField(blank=True)  # 4D: Telefono (DestCliFor / anagrafica)
    porto = models.TextField(blank=True)  # 4D: Porto1 / Porto (TabPorto.Descrizione)
    cod_cau_trasp = models.TextField(blank=True)  # 4D: Cod_CauTrasp (CausaliTrasp.Codice)
    cod_iso_dest = models.TextField(blank=True)  # 4D: CodISO_Dest

    totale = models.FloatField(null=True, blank=True)  # 4D: TotaleFattura / Totale / TotaleDoc (= Σ Netto + Σ IVA)
    imponibile = models.FloatField(null=True, blank=True)  # 4D: Imponibile / TotNetto (= Σ Tot. Netto castelletto)

    spese_imballo = models.FloatField(null=True, blank=True)  # 4D: SpeseImballo
    spese_trasporto = models.FloatField(null=True, blank=True)  # 4D: SpeseTrasporto
    spese_incasso = models.FloatField(null=True, blank=True)  # 4D: SpeseIncasso
    spese_varie = models.FloatField(null=True, blank=True)  # 4D: SpeseVarie
    spese_bolli = models.FloatField(null=True, blank=True)  # 4D: SpeseBolli
    spese_e15 = models.FloatField(null=True, blank=True)  # 4D: Spese_E15
    add_spese = models.BooleanField(default=False)  # 4D: AddSpese (Si/No)
    imp_spese_bollo_virtuale = models.FloatField(
        null=True, blank=True
    )  # 4D: ImpSpeseBolloVirtuale

    tipo_doc_fe = models.TextField(blank=True)  # 4D: TipoDocFE (FatturaPA)
    cod_sdi = models.TextField(blank=True)  # 4D: CodSDI
    progressivo_invio = models.IntegerField(null=True, blank=True)  # 4D: ProgressivoInvio
    email_pec = models.TextField(blank=True)  # 4D: Email_PEC
    file_name = models.TextField(blank=True)  # 4D: FileName
    iban = models.TextField(blank=True)  # 4D: IBAN
    cod_banca = models.TextField(blank=True)  # 4D: Cod_Banca / Banca
    codice_sconto = models.TextField(blank=True)  # 4D: Sconto (codice Tabella Sconti)
    sconto = models.TextField(blank=True)  # % da Sconti.Sconto (o Sconto1+2+3)
    cod_pagamento = models.TextField(blank=True)  # 4D: CodPagamento
    cig = models.TextField(blank=True)  # 4D: FattPA_CIG
    cup = models.TextField(blank=True)  # 4D: CUP

    num_ordine_acq = models.TextField(blank=True)  # 4D: NumOrdineAcq
    data_ordine_acq = models.DateTimeField(null=True, blank=True)  # 4D: DataOrdineAcq
    desc_causale = models.TextField(blank=True)  # 4D: Desc_Causale
    desc_nota_c = models.TextField(blank=True)  # 4D: DescNotaC
    note = models.TextField(blank=True)  # 4D: Note / NoteTesta (se presente)
    annotazioni = models.TextField(blank=True)  # 4D: Annotazioni

    # Date scadenza (ISO), una per rata — numero libero (10, 15, 24, …)
    scadenze = models.JSONField(default=list, blank=True)

    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "teste_documenti"
        verbose_name = "Testata documento"
        verbose_name_plural = "Testate documenti"
        ordering = ["-data_documento", "-numero", "alfa", "-id_4d"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_doc", "id_4d"],
                name="uniq_testa_tipo_id4d",
            ),
        ]
        indexes = [
            models.Index(fields=["tipo_doc", "data_documento"]),
            models.Index(fields=["codice_clifor"]),
        ]

    def __str__(self):
        return f"{self.tipo_doc_id} {self.numero_documento} ({self.id_4d})"

    @property
    def alfa_serie(self):
        return (self.alfa or "").strip()

    @property
    def numero_documento(self):
        from apps.documenti.numerazione import format_numero_documento

        return format_numero_documento(self.numero, self.alfa_serie, empty="—")

    @property
    def is_nota_credito(self):
        return self.tipo_doc_id == "NCR" or (
            (self.tipo_doc_fe or "").strip().upper() == "TD04"
        )

    @property
    def is_nota_debito(self):
        return self.tipo_doc_id == "NDB" or (
            (self.tipo_doc_fe or "").strip().upper() == "TD05"
        )

    @property
    def totale_spese(self):
        if not self.add_spese:
            return 0.0
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
    def cliente_ragione_sociale(self):
        parts = [
            p
            for p in (
                getattr(self, "cliente_ragione_sociale1", None),
                getattr(self, "cliente_ragione_sociale2", None),
            )
            if p
        ]
        return " ".join(parts)


class RigaDocumento(models.Model):
    """
    Riga documento unificata (PostgreSQL: righe_documenti).

    Campi mappati dai dettagli 4D (*_Dettaglio):
    - ID → id_4d
    - id_added_by_converter → FK testa (ID_Testa testata)
    - ID_Riga, NumeroRiga, Codice, DescAgg, Quantita, PrezzoUnitario, Iva, UnitaMisura, Sconto, Provvigione
    """

    testa = models.ForeignKey(
        TestaDocumento,
        on_delete=models.CASCADE,
        related_name="righe",
    )
    id_4d = models.IntegerField()  # 4D: ID
    id_riga = models.IntegerField(null=True, blank=True)  # 4D: ID_Riga
    numero_riga = models.IntegerField(null=True, blank=True)  # 4D: NumeroRiga
    codice = models.TextField(blank=True)  # 4D: Codice
    descrizione = models.TextField(blank=True)  # 4D: DescAgg / Descrizione
    quantita = models.FloatField(null=True, blank=True)  # 4D: Quantita
    # 4D: PrezzoUnitario — display/edit a 3 decimali (Float conserva precisione sync)
    prezzo_unitario = models.FloatField(null=True, blank=True)
    iva = models.TextField(blank=True)  # 4D: Iva
    unita_misura = models.TextField(blank=True)  # 4D: UnitaMisura
    sconto = models.TextField(blank=True)  # 4D: Sconto
    provvigione = models.FloatField(
        null=True, blank=True
    )  # 4D: Provvigione (Preventivi_Dettaglio)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "righe_documenti"
        verbose_name = "Riga documento"
        verbose_name_plural = "Righe documenti"
        ordering = ["testa_id", "numero_riga", "id_4d"]
        constraints = [
            models.UniqueConstraint(
                fields=["testa", "id_4d"],
                name="uniq_riga_testa_id4d",
            ),
        ]

    def __str__(self):
        return f"{self.codice or 'riga'} #{self.id_4d}"


class SyncDocumentiLog(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    cancel_requested = models.BooleanField(default=False)
    teste_count = models.PositiveIntegerField(default=0)
    righe_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sync_documenti_logs",
    )

    class Meta:
        verbose_name = "Log sync documenti"
        verbose_name_plural = "Log sync documenti"
        ordering = ["-started_at"]

    def __str__(self):
        stato = "OK" if self.ok else "ERR"
        return f"Sync documenti {self.started_at:%Y-%m-%d %H:%M} [{stato}]"


class Porto(models.Model):
    """Mirror PostgreSQL della tabella 4D TabPorto (sync 4D globale + documenti)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    cod_incoterm = models.TextField(null=True, blank=True, db_column="Cod_Incoterm")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "tab_porto"
        verbose_name = "Porto"
        verbose_name_plural = "Porti"
        ordering = ["descrizione", "id"]

    def __str__(self):
        label = self.descrizione or self.cod_incoterm or str(self.id)
        return f"{label} ({self.cod_incoterm or self.id})"


def annotate_clifor_ragione_sociale(
    queryset, *, clifor_field="codice_clifor", clifor_tipo: str | None = None
):
    """LEFT JOIN logico verso clienti/fornitori via Subquery (no FK).

    Se la tabella mirror manca (es. dopo Azzera tabelle), lascia il
    queryset senza annotation: in UI resta solo il codice clifor.

    ``clifor_tipo``: ``"F"`` → Fornitori, altrimenti Clienti.
    """
    from apps.anagrafiche.models import (
        Cliente,
        Fornitore,
        _codice_norm_expr,
        clienti_mirror_available,
        fornitori_mirror_available,
    )

    use_fornitore = (clifor_tipo or "").upper() == "F"
    if use_fornitore:
        if not fornitori_mirror_available():
            return queryset
        model = Fornitore
    else:
        if not clienti_mirror_available():
            return queryset
        model = Cliente

    # Match anche se il PK mirror ha padding ALPHA 4D e codice_clifor è stripped.
    base = model.objects.annotate(_codice_norm=_codice_norm_expr()).filter(
        _codice_norm=_codice_norm_expr(OuterRef(clifor_field))
    )

    return queryset.annotate(
        cliente_ragione_sociale1=Subquery(base.values("ragione_sociale1")[:1]),
        cliente_ragione_sociale2=Subquery(base.values("ragione_sociale2")[:1]),
    )
