from __future__ import annotations

from django.db import models
from django.db.models import TextField, Value
from django.db.models.functions import Replace
from django.db.utils import OperationalError, ProgrammingError
from django.urls import reverse


def compact_codice(value: str | None) -> str:
    """Normalizza il codice Cli/For (C 3203 → C3203)."""
    return (value or "").replace(" ", "").strip().upper()


def _codice_without_spaces(field="codice"):
    """Replace spazi su TextField: Value() default è CharField → serve output_field."""
    return Replace(
        field,
        Value(" ", output_field=TextField()),
        Value("", output_field=TextField()),
        output_field=TextField(),
    )


def tipo_clifor(codice: str | None) -> str:
    letter = compact_codice(codice)[:1]
    return letter if letter in {"C", "F"} else ""


def destinazioni_for_anagrafica(codice: str | None):
    """Destinazioni DestCliFor collegate a un Cliente/Fornitore."""
    compact = compact_codice(codice)
    if not compact:
        return DestinazioneDiversa.objects.none()
    return (
        DestinazioneDiversa.objects.annotate(_compact=_codice_without_spaces())
        .filter(_compact__iexact=compact)
        .order_by("codice_dest", "id")
    )


class DestinazioneDiversa(models.Model):
    """Mirror PostgreSQL della tabella 4D DestCliFor (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    codice = models.TextField(null=True, blank=True, db_column="Codice")
    ragione_sociale = models.TextField(null=True, blank=True, db_column="RagioneSociale")
    indirizzo = models.TextField(null=True, blank=True, db_column="Indirizzo")
    cap = models.TextField(null=True, blank=True, db_column="Cap")
    citta = models.TextField(null=True, blank=True, db_column="Citta")
    provincia = models.TextField(null=True, blank=True, db_column="Provincia")
    codice_dest = models.TextField(null=True, blank=True, db_column="CodiceDest")
    telefono = models.TextField(null=True, blank=True, db_column="Telefono")
    codice_filconad = models.TextField(null=True, blank=True, db_column="CodiceFilconad")
    gruppo_cadla = models.TextField(null=True, blank=True, db_column="GruppoCADLA")
    prezzi_bolle = models.BooleanField(null=True, blank=True, db_column="PrezziBolle")
    black_list = models.BooleanField(null=True, blank=True, db_column="BlackList")
    cod_esenz_iva = models.TextField(null=True, blank=True, db_column="CodEsenzIva")
    email = models.TextField(null=True, blank=True, db_column="Email")
    cod_nazione = models.TextField(null=True, blank=True, db_column="CodNazione")
    codice_iso = models.TextField(null=True, blank=True, db_column="CodiceISO")
    punto_vendita = models.TextField(null=True, blank=True, db_column="PuntoVendita")
    desc_nazione = models.TextField(null=True, blank=True, db_column="DescNazione")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "DestCliFor"
        verbose_name = "Destinazione diversa"
        verbose_name_plural = "Destinazioni diverse"
        ordering = ["codice", "codice_dest", "id"]

    def __str__(self):
        label = self.ragione_sociale or self.codice_dest or str(self.id)
        return f"{self.codice or '?'} {self.codice_dest or ''} – {label}".strip()

    @property
    def tipo(self) -> str:
        return tipo_clifor(self.codice)

    @property
    def tipo_label(self) -> str:
        if self.tipo == "C":
            return "Cliente"
        if self.tipo == "F":
            return "Fornitore"
        return "Conto"

    @property
    def codice_anagrafica(self) -> str:
        return compact_codice(self.codice)

    def get_absolute_url(self):
        return reverse("destinazioni:detail", kwargs={"pk": self.pk})

    def anagrafica_url(self) -> str:
        code = self.codice_anagrafica or (self.codice or "").strip()
        if not code:
            return ""
        if self.tipo == "F":
            return reverse("anagrafiche:fornitore_detail", kwargs={"codice": code})
        return reverse("anagrafiche:cliente_detail", kwargs={"codice": code})


def resolve_anagrafica(codice: str | None):
    """Ritorna Cliente o Fornitore collegato, se il mirror esiste."""
    from apps.anagrafiche.models import Cliente, Fornitore

    compact = compact_codice(codice)
    if not compact:
        return None
    model = {"C": Cliente, "F": Fornitore}.get(compact[0])
    if model is None:
        return None
    candidates = [(codice or "").strip(), compact]
    try:
        seen: set[str] = set()
        for code in candidates:
            if not code or code in seen:
                continue
            seen.add(code)
            try:
                return model.objects.get(pk=code)
            except model.DoesNotExist:
                continue
        return (
            model.objects.annotate(_compact=_codice_without_spaces())
            .filter(_compact__iexact=compact)
            .first()
        )
    except (ProgrammingError, OperationalError):
        return None
