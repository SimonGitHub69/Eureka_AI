"""
Mappatura campi 4D → modelli unificati TestaDocumento / RigaDocumento.

Ogni tabella 4D usa nomi colonna leggermente diversi: gli alias sono tentati in ordine.
Aggiornare le tuple alias quando si verifica lo schema ODBC reale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence

# TipoDoc FatturaPA → codice TipoDoc unificato
TIPO_DOC_FE_MAP = {
    "TD04": "NCR",
    "TD05": "NDB",
}

DEFAULT_TIPI_DOCUMENTO: tuple[dict[str, Any], ...] = (
    {
        "codice": "ORV",
        "label": "Ordini vendita",
        "descrizione": "Ordini verso clienti (4D: Ordini_Vendita)",
        "categoria": "ORDINI",
        "ordine": 10,
        "source_table_4d": "Ordini_Vendita",
        "source_detail_4d": "Ordini_Vendita_Dettaglio",
        "clifor_tipo": "C",
    },
    {
        "codice": "ORA",
        "label": "Ordini acquisto",
        "descrizione": "Ordini verso fornitori (4D: Ordini_Acquisto)",
        "categoria": "ORDINI",
        "ordine": 20,
        "source_table_4d": "Ordini_Acquisto",
        "source_detail_4d": "Ordini_Acquisto_Dettaglio",
        "clifor_tipo": "F",
    },
    {
        "codice": "PRV",
        "label": "Preventivi",
        "descrizione": "Preventivi clienti (4D: Preventivi)",
        "categoria": "PREVENTIVI",
        "ordine": 30,
        "source_table_4d": "Preventivi",
        "source_detail_4d": "Preventivi_Dettaglio",
        "clifor_tipo": "C",
    },
    {
        "codice": "DDT",
        "label": "DDT / Bolle",
        "descrizione": "Documenti di trasporto (4D: Bolle)",
        "categoria": "DDT",
        "ordine": 40,
        "source_table_4d": "Bolle",
        "source_detail_4d": "Bolle_Dettaglio",
        "clifor_tipo": "C",
    },
    {
        "codice": "FAT",
        "label": "Fatture",
        "descrizione": "Fatture attive (4D: Fatture, TipoDocFE ≠ TD04/TD05)",
        "categoria": "FATTURE",
        "ordine": 50,
        "source_table_4d": "Fatture",
        "source_detail_4d": "Fatture_Dettaglio",
        "clifor_tipo": "C",
    },
    {
        "codice": "NCR",
        "label": "Note di credito",
        "descrizione": "Note di credito (4D: Fatture con TipoDocFE = TD04)",
        "categoria": "NOTE_CREDITO",
        "ordine": 60,
        "source_table_4d": "Fatture",
        "source_detail_4d": "Fatture_Dettaglio",
        "clifor_tipo": "C",
    },
    {
        "codice": "NDB",
        "label": "Note di debito",
        "descrizione": "Note di debito (4D: Fatture con TipoDocFE = TD05)",
        "categoria": "NOTE_DEBITO",
        "ordine": 70,
        "source_table_4d": "Fatture",
        "source_detail_4d": "Fatture_Dettaglio",
        "clifor_tipo": "C",
    },
)


def tipo_documento_seed_defaults(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Campi da usare in update_or_create dei parametri documento."""
    return {
        "label": spec["label"],
        "descrizione": spec.get("descrizione", ""),
        "categoria": spec.get("categoria", "ALTRO"),
        "ordine": spec.get("ordine", 0),
        "source_table_4d": spec.get("source_table_4d", ""),
        "source_detail_4d": spec.get("source_detail_4d", ""),
        "clifor_tipo": spec.get("clifor_tipo", ""),
        "attivo": True,
    }


# Alias colonna 4D per campi testata unificati
HEADER_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "id_4d": ("ID_Testa", "ID", "ID_Testata"),
    "numero": (
        "NumeroFatt",
        "NumeroOrd",
        "NumeroPrev",
        "NumeroBolla",
        "NumeroDoc",
        "Numero",
    ),
    "alfa": ("Alfa", "Serie", "SerieDoc"),
    "data_documento": (
        "DataFattura",
        "DataOrd",
        "DataOrdine",
        "DataPrev",
        "DataBolla",
        "DataDoc",
        "Data",
    ),
    "validita": ("Validita", "Validità", "ValiditaOfferta"),
    "data_consegna": ("DataConsegna", "Data_Consegna"),
    "tipo_preventivo": ("TipoPreventivo", "Tipo_Preventivo", "TipoPrev"),
    "confermato": ("Confermato",),
    "valuta": ("Valuta", "CodValuta", "CodiceValuta"),
    "cambio": ("Cambio", "cambio"),
    "codice_clifor_cliente": ("Cliente", "CodiceCliente"),
    "codice_clifor_fornitore": ("Fornitore", "CodiceFornitore"),
    "codice_agente": ("Agente", "CodAgente", "CodiceAgente", "Codice_Agente"),
    "destinatario": ("Destinatario",),
    "indirizzo": ("Indirizzo",),
    "localita": ("Localita", "Località"),
    "cap": ("Cap", "CAP"),
    "provincia": ("Prov", "Provincia"),
    "nazione": ("Nazione",),
    "telefono": ("Telefono", "Cellulare", "Tel"),
    "porto": ("Porto1", "Porto"),
    "cod_cau_trasp": (
        "Cod_CauTrasp",
        "CodCauTrasp",
        "CausaleTrasp",
        "Cod_Causale_Trasp",
    ),
    "cod_iso_dest": ("CodISO_Dest", "CodISO", "Codice_ISO"),
    "totale": (
        "TotaleFattura",
        "TotaleOrdine",
        "Totale",
        "TotaleDoc",
        "ImportoTotale",
    ),
    # Imponibile 4D ≈ Σ Tot. Netto castelletto; alias TotNetto se presente sullo schema
    "imponibile": ("Imponibile", "TotNetto", "Tot_Netto", "TotaleNetto"),
    "spese_imballo": ("SpeseImballo",),
    "spese_trasporto": ("SpeseTrasporto",),
    "spese_incasso": ("SpeseIncasso",),
    "spese_varie": ("SpeseVarie",),
    "spese_bolli": ("SpeseBolli",),
    "spese_e15": ("Spese_E15",),
    "add_spese": ("AddSpese", "Add_Spese"),
    "imp_spese_bollo_virtuale": ("ImpSpeseBolloVirtuale",),
    "tipo_doc_fe": ("TipoDocFE", "TipoDocFEL", "TipoDoc"),
    "cod_sdi": ("CodSDI",),
    "progressivo_invio": ("ProgressivoInvio",),
    "email_pec": ("Email_PEC", "EmailPEC", "PEC"),
    "file_name": ("FileName",),
    "iban": ("IBAN",),
    "cod_banca": ("Cod_Banca", "CodBanca", "CodiceBanca", "Banca"),
    "cod_pagamento": (
        "CodPagamento",
        "CondPaga",
        "CondPagamento",
        "CodicePagamento",
        "Pagamento",
    ),
    "cig": ("FattPA_CIG", "CIG"),
    "cup": ("CUP",),
    "num_ordine_acq": ("NumOrdineAcq",),
    "data_ordine_acq": ("DataOrdineAcq",),
    "desc_causale": ("Desc_Causale", "DescCausale"),
    "desc_nota_c": ("DescNotaC",),
    "note": ("Note", "NoteTesta", "NoteDoc"),
    "annotazioni": ("Annotazioni", "Annotazione", "NoteAnnotazioni"),
    **{
        f"scadenza_{i}": (
            f"Data{i}",
            f"DataScad{i}",
            f"Scadenza{i}",
            f"DataScadenza{i}",
            f"Scad{i}",
        )
        for i in range(1, 37)
    },
}

# Alias colonna 4D per campi riga unificati
LINE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    # Preventivi/Ordini_Vendita dettaglio: ID_Riga; Fatture/Bolle: ID (e spesso ID_Riga)
    "id_4d": ("ID", "ID_Riga"),
    "id_testa": ("id_added_by_converter", "ID_Testa", "ID_Testata"),
    "id_riga": ("ID_Riga",),
    "numero_riga": ("NumeroRiga", "NumRiga"),
    # Preventivi/Ordini_Vendita: Articolo; Fatture/Bolle: Codice
    "codice": ("Codice", "CodArticolo", "Articolo"),
    "descrizione": ("DescAgg", "Descrizione", "DescRiga"),
    "quantita": ("Quantita", "Qta"),
    "prezzo_unitario": ("PrezzoUnitario", "Prezzo", "PrezzoNetto"),
    "iva": ("Iva", "CodIva"),
    "unita_misura": ("UnitaMisura", "UM"),
    "sconto": ("Sconto",),
}


@dataclass(frozen=True)
class HeaderSourceSpec:
    source: str
    tipo_doc: str | None  # None = risolto dinamicamente (Fatture)
    pk: str
    clifor_tipo: str


@dataclass(frozen=True)
class DetailSourceSpec:
    source: str
    tipo_doc: str | None
    pk: str
    header_pk: str


HEADER_SOURCES: tuple[HeaderSourceSpec, ...] = (
    HeaderSourceSpec("Ordini_Vendita", "ORV", "ID_Testa", "C"),
    HeaderSourceSpec("Ordini_Acquisto", "ORA", "ID_Testa", "F"),
    HeaderSourceSpec("Preventivi", "PRV", "ID_Testa", "C"),
    HeaderSourceSpec("Bolle", "DDT", "ID_Testa", "C"),
    HeaderSourceSpec("Fatture", None, "ID_Testa", "C"),
)


DETAIL_SOURCES: tuple[DetailSourceSpec, ...] = (
    DetailSourceSpec("Ordini_Vendita_Dettaglio", "ORV", "ID", "id_added_by_converter"),
    DetailSourceSpec("Ordini_Acquisto_Dettaglio", "ORA", "ID", "id_added_by_converter"),
    # Preventivi_Dettaglio non espone id_added_by_converter: FK testata = ID_Testa
    DetailSourceSpec("Preventivi_Dettaglio", "PRV", "ID", "ID_Testa"),
    DetailSourceSpec("Bolle_Dettaglio", "DDT", "ID", "id_added_by_converter"),
    DetailSourceSpec("Fatture_Dettaglio", None, "ID", "id_added_by_converter"),
)


def pick_value(row: Mapping[str, Any], *aliases: str) -> Any:
    """Primo valore non vuoto tra alias colonna 4D (match case-insensitive)."""
    by_fold = {str(key).casefold(): key for key in row.keys()}
    for name in aliases:
        key = by_fold.get(name.casefold())
        if key is None:
            continue
        value = row[key]
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def pick_mapped(row: Mapping[str, Any], field: str, aliases: Mapping[str, Sequence[str]]) -> Any:
    return pick_value(row, *aliases.get(field, ()))


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "s", "si"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return default


def normalize_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d/%m/%y",
    ):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def normalize_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _collect_scadenze(row: Mapping[str, Any]) -> list[str]:
    """Raccoglie Data1..DataN (fino a 36) in una lista ISO, senza padding."""
    dates: list[str] = []
    for i in range(1, 37):
        parsed = normalize_date(pick_mapped(row, f"scadenza_{i}", HEADER_FIELD_ALIASES))
        if parsed:
            dates.append(parsed.isoformat())
    return dates


def resolve_fattura_tipo_doc(row: Mapping[str, Any]) -> str:
    """
    Distinzione FAT / NCR / NDB dalla tabella 4D Fatture.
    Campo primario: TipoDocFE (FatturaPA TD01/TD04/TD05).
    """
    tfe = normalize_text(pick_mapped(row, "tipo_doc_fe", HEADER_FIELD_ALIASES)).upper()
    if tfe in TIPO_DOC_FE_MAP:
        return TIPO_DOC_FE_MAP[tfe]
    # Fallback legacy: campo Alfa o flag non standard (da verificare su ODBC reale)
    alfa = normalize_text(pick_mapped(row, "alfa", HEADER_FIELD_ALIASES)).upper()
    if alfa in {"NC", "NCR", "N/C"}:
        return "NCR"
    if alfa in {"ND", "NDB", "N/D"}:
        return "NDB"
    return "FAT"


def resolve_header_tipo_doc(spec: HeaderSourceSpec, row: Mapping[str, Any]) -> str:
    if spec.tipo_doc:
        return spec.tipo_doc
    return resolve_fattura_tipo_doc(row)


def resolve_detail_tipo_doc(
    spec: DetailSourceSpec,
    row: Mapping[str, Any],
    header_tipo_by_id_4d: Mapping[int, str],
) -> str | None:
    if spec.tipo_doc:
        return spec.tipo_doc
    id_testa = normalize_int(
        pick_value(row, spec.header_pk, "ID_Testa", "id_added_by_converter")
    )
    if id_testa is None:
        return None
    return header_tipo_by_id_4d.get(id_testa, "FAT")


def map_header_row(
    row: Mapping[str, Any],
    *,
    tipo_doc: str,
    source_table: str,
    clifor_tipo: str,
) -> dict[str, Any]:
    """Converte dict colonna→valore 4D in kwargs TestaDocumento (senza FK tipo_doc)."""
    codice_clifor = ""
    if clifor_tipo == "F":
        codice_clifor = normalize_text(
            pick_mapped(row, "codice_clifor_fornitore", HEADER_FIELD_ALIASES)
        )
    else:
        codice_clifor = normalize_text(
            pick_mapped(row, "codice_clifor_cliente", HEADER_FIELD_ALIASES)
        )

    return {
        "tipo_doc_id": tipo_doc,
        "id_4d": normalize_int(pick_mapped(row, "id_4d", HEADER_FIELD_ALIASES)),
        "source_table_4d": source_table,
        "numero": normalize_int(pick_mapped(row, "numero", HEADER_FIELD_ALIASES)),
        "alfa": normalize_text(pick_mapped(row, "alfa", HEADER_FIELD_ALIASES)),
        "data_documento": normalize_datetime(
            pick_mapped(row, "data_documento", HEADER_FIELD_ALIASES)
        ),
        "validita": normalize_text(pick_mapped(row, "validita", HEADER_FIELD_ALIASES)),
        "data_consegna": normalize_datetime(
            pick_mapped(row, "data_consegna", HEADER_FIELD_ALIASES)
        ),
        "tipo_preventivo": normalize_text(
            pick_mapped(row, "tipo_preventivo", HEADER_FIELD_ALIASES)
        ),
        "confermato": normalize_bool(
            pick_mapped(row, "confermato", HEADER_FIELD_ALIASES)
        ),
        "valuta": normalize_text(pick_mapped(row, "valuta", HEADER_FIELD_ALIASES)),
        "cambio": normalize_float(pick_mapped(row, "cambio", HEADER_FIELD_ALIASES)),
        "codice_clifor": codice_clifor,
        "clifor_tipo": clifor_tipo,
        "codice_agente": normalize_text(
            pick_mapped(row, "codice_agente", HEADER_FIELD_ALIASES)
        ),
        "destinatario": normalize_text(pick_mapped(row, "destinatario", HEADER_FIELD_ALIASES)),
        "indirizzo": normalize_text(pick_mapped(row, "indirizzo", HEADER_FIELD_ALIASES)),
        "localita": normalize_text(pick_mapped(row, "localita", HEADER_FIELD_ALIASES)),
        "cap": normalize_text(pick_mapped(row, "cap", HEADER_FIELD_ALIASES)),
        "provincia": normalize_text(pick_mapped(row, "provincia", HEADER_FIELD_ALIASES)),
        "nazione": normalize_text(pick_mapped(row, "nazione", HEADER_FIELD_ALIASES)),
        "telefono": normalize_text(pick_mapped(row, "telefono", HEADER_FIELD_ALIASES)),
        "porto": normalize_text(pick_mapped(row, "porto", HEADER_FIELD_ALIASES)),
        "cod_cau_trasp": normalize_text(
            pick_mapped(row, "cod_cau_trasp", HEADER_FIELD_ALIASES)
        ),
        "cod_iso_dest": normalize_text(
            pick_mapped(row, "cod_iso_dest", HEADER_FIELD_ALIASES)
        ),
        "totale": normalize_float(pick_mapped(row, "totale", HEADER_FIELD_ALIASES)),
        "imponibile": normalize_float(pick_mapped(row, "imponibile", HEADER_FIELD_ALIASES)),
        "spese_imballo": normalize_float(
            pick_mapped(row, "spese_imballo", HEADER_FIELD_ALIASES)
        ),
        "spese_trasporto": normalize_float(
            pick_mapped(row, "spese_trasporto", HEADER_FIELD_ALIASES)
        ),
        "spese_incasso": normalize_float(
            pick_mapped(row, "spese_incasso", HEADER_FIELD_ALIASES)
        ),
        "spese_varie": normalize_float(pick_mapped(row, "spese_varie", HEADER_FIELD_ALIASES)),
        "spese_bolli": normalize_float(pick_mapped(row, "spese_bolli", HEADER_FIELD_ALIASES)),
        "spese_e15": normalize_float(pick_mapped(row, "spese_e15", HEADER_FIELD_ALIASES)),
        "add_spese": normalize_bool(pick_mapped(row, "add_spese", HEADER_FIELD_ALIASES)),
        "imp_spese_bollo_virtuale": normalize_float(
            pick_mapped(row, "imp_spese_bollo_virtuale", HEADER_FIELD_ALIASES)
        ),
        "tipo_doc_fe": normalize_text(pick_mapped(row, "tipo_doc_fe", HEADER_FIELD_ALIASES)),
        "cod_sdi": normalize_text(pick_mapped(row, "cod_sdi", HEADER_FIELD_ALIASES)),
        "progressivo_invio": normalize_int(
            pick_mapped(row, "progressivo_invio", HEADER_FIELD_ALIASES)
        ),
        "email_pec": normalize_text(pick_mapped(row, "email_pec", HEADER_FIELD_ALIASES)),
        "file_name": normalize_text(pick_mapped(row, "file_name", HEADER_FIELD_ALIASES)),
        "iban": normalize_text(pick_mapped(row, "iban", HEADER_FIELD_ALIASES)),
        "cod_banca": normalize_text(pick_mapped(row, "cod_banca", HEADER_FIELD_ALIASES)),
        "cod_pagamento": normalize_text(
            pick_mapped(row, "cod_pagamento", HEADER_FIELD_ALIASES)
        ),
        "cig": normalize_text(pick_mapped(row, "cig", HEADER_FIELD_ALIASES)),
        "cup": normalize_text(pick_mapped(row, "cup", HEADER_FIELD_ALIASES)),
        "num_ordine_acq": normalize_text(
            pick_mapped(row, "num_ordine_acq", HEADER_FIELD_ALIASES)
        ),
        "data_ordine_acq": normalize_datetime(
            pick_mapped(row, "data_ordine_acq", HEADER_FIELD_ALIASES)
        ),
        "desc_causale": normalize_text(
            pick_mapped(row, "desc_causale", HEADER_FIELD_ALIASES)
        ),
        "desc_nota_c": normalize_text(pick_mapped(row, "desc_nota_c", HEADER_FIELD_ALIASES)),
        "note": normalize_text(pick_mapped(row, "note", HEADER_FIELD_ALIASES)),
        "annotazioni": normalize_text(
            pick_mapped(row, "annotazioni", HEADER_FIELD_ALIASES)
        ),
        "scadenze": _collect_scadenze(row),
    }


def map_line_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id_4d": normalize_int(pick_mapped(row, "id_4d", LINE_FIELD_ALIASES)),
        "id_riga": normalize_int(pick_mapped(row, "id_riga", LINE_FIELD_ALIASES)),
        "numero_riga": normalize_int(pick_mapped(row, "numero_riga", LINE_FIELD_ALIASES)),
        "codice": normalize_text(pick_mapped(row, "codice", LINE_FIELD_ALIASES)),
        "descrizione": normalize_text(pick_mapped(row, "descrizione", LINE_FIELD_ALIASES)),
        "quantita": normalize_float(pick_mapped(row, "quantita", LINE_FIELD_ALIASES)),
        "prezzo_unitario": normalize_float(
            pick_mapped(row, "prezzo_unitario", LINE_FIELD_ALIASES)
        ),
        "iva": normalize_text(pick_mapped(row, "iva", LINE_FIELD_ALIASES)),
        "unita_misura": normalize_text(pick_mapped(row, "unita_misura", LINE_FIELD_ALIASES)),
        "sconto": normalize_text(pick_mapped(row, "sconto", LINE_FIELD_ALIASES)),
    }


def line_id_testa(row: Mapping[str, Any], header_pk: str) -> int | None:
    return normalize_int(
        pick_value(row, header_pk, "id_added_by_converter", "ID_Testa", "ID_Testata")
    )


def iter_source_labels(sources: Iterable[Any]) -> list[str]:
    return [getattr(s, "source", str(s)) for s in sources]
