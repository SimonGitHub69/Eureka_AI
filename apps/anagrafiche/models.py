from django.db import models, transaction
from django.db.models import TextField
from django.db.models.functions import Trim, Upper
from django.db.utils import OperationalError, ProgrammingError


def _codice_norm_expr(field="codice"):
    """Upper(Trim(...)) su TextField: output_field evita mixed types vs CharField."""
    return Upper(Trim(field), output_field=TextField())


def get_by_codice(model, codice: str | None, *, only: tuple[str, ...] | None = None):
    """Trova record per codice, tollerando spazi residui da campi ALPHA 4D.

    I documenti Eureka normalizzano ``codice_clifor`` con strip; i PK mirror
    Clienti/Fornitori possono ancora avere padding → ``iexact`` puro fallisce.
    """
    code = (codice or "").strip()
    if not code:
        return None
    qs = model.objects.all()
    exact_qs = qs.only(*only) if only else qs
    obj = exact_qs.filter(codice__iexact=code).first()
    if obj is not None:
        return obj
    # Fallback padding: evita only()+annotate (Django li gestisce male insieme).
    return (
        qs.annotate(_codice_norm=_codice_norm_expr())
        .filter(_codice_norm=code.upper())
        .first()
    )


class Cliente(models.Model):
    """Mirror PostgreSQL della tabella 4D Clienti (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    ragione_sociale1 = models.TextField(null=True, blank=True, db_column="RagioneSociale1")
    ragione_sociale2 = models.TextField(null=True, blank=True, db_column="RagioneSociale2")
    indirizzo = models.TextField(null=True, blank=True, db_column="Indirizzo")
    localita = models.TextField(null=True, blank=True, db_column="Localita")
    cap = models.TextField(null=True, blank=True, db_column="Cap")
    provincia = models.TextField(null=True, blank=True, db_column="Provincia")
    cod_nazione = models.TextField(null=True, blank=True, db_column="CodNazione")
    partita_iva = models.TextField(null=True, blank=True, db_column="PartitaIva")
    cod_fiscale = models.TextField(null=True, blank=True, db_column="CodFiscale")
    telefono = models.TextField(null=True, blank=True, db_column="Telefono")
    fax = models.TextField(null=True, blank=True, db_column="Fax")
    cellulare = models.TextField(null=True, blank=True, db_column="Cellulare")
    email = models.TextField(null=True, blank=True, db_column="Email")
    pec = models.TextField(null=True, blank=True, db_column="PEC")
    email_commerciale = models.TextField(null=True, blank=True, db_column="Email_Commerciale")
    www = models.TextField(null=True, blank=True, db_column="www")
    agente = models.TextField(null=True, blank=True, db_column="Agente")
    agente2 = models.TextField(null=True, blank=True, db_column="Agente2")
    zona = models.TextField(null=True, blank=True, db_column="Zona")
    gruppo = models.TextField(null=True, blank=True, db_column="Gruppo")
    cond_paga = models.TextField(null=True, blank=True, db_column="CondPaga")
    listino = models.SmallIntegerField(null=True, blank=True, db_column="Listino")
    annotazioni = models.TextField(null=True, blank=True, db_column="Annotazioni")
    note = models.TextField(null=True, blank=True, db_column="Note")
    fl_disattivato = models.BooleanField(null=True, blank=True, db_column="Fl_Disattivato")
    cliente_fittizio = models.BooleanField(null=True, blank=True, db_column="Cliente_Fittizio")
    # Campi fattura elettronica
    codice_ufficio = models.TextField(null=True, blank=True, db_column="CodiceUfficio")
    flag_pa = models.BooleanField(null=True, blank=True, db_column="Flag_PA")
    persona_fisica = models.BooleanField(null=True, blank=True, db_column="PersonaFisica")
    cognome = models.TextField(null=True, blank=True, db_column="Cognome")
    nome = models.TextField(null=True, blank=True, db_column="Nome")
    cod_esenz_iva = models.TextField(null=True, blank=True, db_column="CodEsenzIva")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "clienti"
        verbose_name = "Cliente"
        verbose_name_plural = "Clienti"
        ordering = ["ragione_sociale1", "codice"]

    @property
    def ragione_sociale(self):
        parts = [p for p in (self.ragione_sociale1, self.ragione_sociale2) if p]
        return " ".join(parts)

    def __str__(self):
        label = self.ragione_sociale or self.codice
        return f"{label} ({self.codice})"


def clienti_mirror_available() -> bool:
    """True se la tabella mirror ``clienti`` esiste ed è interrogabile."""
    try:
        with transaction.atomic():
            Cliente.objects.exists()
        return True
    except (ProgrammingError, OperationalError):
        return False


class Fornitore(models.Model):
    """Mirror PostgreSQL della tabella 4D Fornitori (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    ragione_sociale1 = models.TextField(null=True, blank=True, db_column="RagioneSociale1")
    ragione_sociale2 = models.TextField(null=True, blank=True, db_column="RagioneSociale2")
    indirizzo = models.TextField(null=True, blank=True, db_column="Indirizzo")
    localita = models.TextField(null=True, blank=True, db_column="Localita")
    cap = models.TextField(null=True, blank=True, db_column="Cap")
    provincia = models.TextField(null=True, blank=True, db_column="Provincia")
    cod_nazione = models.TextField(null=True, blank=True, db_column="CodNazione")
    partita_iva = models.TextField(null=True, blank=True, db_column="PartitaIva")
    cod_fiscale = models.TextField(null=True, blank=True, db_column="CodFiscale")
    telefono = models.TextField(null=True, blank=True, db_column="Telefono")
    fax = models.TextField(null=True, blank=True, db_column="Fax")
    cellulare = models.TextField(null=True, blank=True, db_column="Cellulare")
    email = models.TextField(null=True, blank=True, db_column="E_Mail")
    pec = models.TextField(null=True, blank=True, db_column="PEC")
    email_commerciale = models.TextField(null=True, blank=True, db_column="Email_commerciale")
    www = models.TextField(null=True, blank=True, db_column="www")
    agente = models.TextField(null=True, blank=True, db_column="Agente")
    zona = models.TextField(null=True, blank=True, db_column="Zona")
    gruppo = models.TextField(null=True, blank=True, db_column="Gruppo")
    cond_paga = models.TextField(null=True, blank=True, db_column="CondPaga")
    banca = models.TextField(null=True, blank=True, db_column="Banca")
    listino = models.SmallIntegerField(null=True, blank=True, db_column="Listino")
    annotazioni = models.TextField(null=True, blank=True, db_column="Annotazioni")
    note = models.TextField(null=True, blank=True, db_column="Note")
    fl_disattivato = models.BooleanField(null=True, blank=True, db_column="Fl_Disattivato")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "fornitori"
        verbose_name = "Fornitore"
        verbose_name_plural = "Fornitori"
        ordering = ["ragione_sociale1", "codice"]

    @property
    def ragione_sociale(self):
        parts = [p for p in (self.ragione_sociale1, self.ragione_sociale2) if p]
        return " ".join(parts)

    def __str__(self):
        label = self.ragione_sociale or self.codice
        return f"{label} ({self.codice})"


def fornitori_mirror_available() -> bool:
    """True se la tabella mirror ``fornitori`` esiste ed è interrogabile."""
    try:
        with transaction.atomic():
            Fornitore.objects.exists()
        return True
    except (ProgrammingError, OperationalError):
        return False


class Agente(models.Model):
    """Mirror PostgreSQL della tabella 4D Agenti (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    ragione_sociale = models.TextField(null=True, blank=True, db_column="RagioneSociale")
    provvigione = models.FloatField(null=True, blank=True, db_column="Provvigione")
    progr_fatt = models.FloatField(null=True, blank=True, db_column="ProgrFatt")
    progr_provv = models.FloatField(null=True, blank=True, db_column="ProgrProvv")
    sconto_base = models.FloatField(null=True, blank=True, db_column="ScontoBase")
    ritenuta_acconto = models.FloatField(null=True, blank=True, db_column="RitenutaAcconto")
    progr_enasarco = models.FloatField(null=True, blank=True, db_column="ProgrENASARCO")
    flag_mono_mandatario = models.BooleanField(null=True, blank=True, db_column="FlagMonoMandatario")
    flag_agente_venditore = models.BooleanField(null=True, blank=True, db_column="FlagAgenteVenditore")
    flag_soc_capitale = models.BooleanField(null=True, blank=True, db_column="FlagSocCapitale")
    perc_imp_rit_acc = models.FloatField(null=True, blank=True, db_column="PercImpRitAcc")
    listino_art = models.SmallIntegerField(null=True, blank=True, db_column="ListinoArt")
    data_ultimo_conguaglio_shopping = models.DateTimeField(
        null=True, blank=True, db_column="DataUltimoConguaglioSHOPPING"
    )
    target_annuale1 = models.FloatField(null=True, blank=True, db_column="Target_Annuale1")
    target_annuale2 = models.FloatField(null=True, blank=True, db_column="Target_Annuale2")
    target_annuale3 = models.FloatField(null=True, blank=True, db_column="Target_Annuale3")
    email = models.TextField(null=True, blank=True, db_column="email")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "agenti"
        verbose_name = "Agente"
        verbose_name_plural = "Agenti"
        ordering = ["ragione_sociale", "codice"]

    def __str__(self):
        label = self.ragione_sociale or self.codice
        return f"{label} ({self.codice})"
