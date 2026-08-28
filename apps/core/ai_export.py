"""Export XLSX dei risultati SQL dell'assistente AI."""

from __future__ import annotations

import re
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from django.apps import apps
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.export import build_csv_bytes, build_xlsx_bytes

EXPORT_MAX_ROWS = 10000
_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")

_DEFAULT_ARTICOLI_COLUMNS = ("Codice", "Descrizione")
_DEFAULT_AGENTI_COLUMNS = ("Codice", "RagioneSociale")
_DEFAULT_PDC_COLUMNS = ("Codice", "Descrizione")
_DEFAULT_CLIENTI_COLUMNS = ("Codice", "RagioneSociale")
_DEFAULT_PRIMANOTA_COLUMNS = ("ContoDare", "Dare", "ContoAvere", "Avere")
_DEFAULT_CAUSALI_CONTABILI_COLUMNS = ("Codice", "Descrizione")

# Colonne export virtuali (richiedono JOIN, non presenti su articoli).
_ARTICOLI_VIRTUAL_COLUMNS: frozenset[str] = frozenset(
    {"RagioneSocialeFornitore", "DescrizioneCategoria"}
)
_CLIENTI_VIRTUAL_COLUMNS: frozenset[str] = frozenset(
    {"RagioneSociale", "DescrizionePagamento"}
)
_FORNITORI_VIRTUAL_COLUMNS: frozenset[str] = frozenset(
    {"RagioneSociale", "DescrizionePagamento"}
)

# Etichette XLSX per colonne articoli (incluso fornitore/categoria).
_ARTICOLI_EXPORT_LABELS: dict[str, str] = {
    "CodFornitore": "Codice fornitore",
    "RagioneSocialeFornitore": "Ragione sociale fornitore",
    "CatOmogenea": "Categoria",
    "DescrizioneCategoria": "Descrizione categoria",
    "UnitaMisura": "Unità di misura",
    "PesoNetto": "Peso netto",
    "PesoLordo_Manodopera": "Peso lordo",
    "CodiceAlternativo1": "Codice alternativo 1",
}

# Alias italiani / etichette comuni → colonna DB (tabella articoli).
_ARTICOLI_COLUMN_ALIASES: dict[str, str] = {
    "codice": "Codice",
    "descrizione": "Descrizione",
    "categoria": "CatOmogenea",
    "catomogenea": "CatOmogenea",
    "cat omogenea": "CatOmogenea",
    "gruppo": "CodGruppo",
    "codgruppo": "CodGruppo",
    "iva": "CodIva",
    "fornitore": "CodFornitore",
    "codice fornitore": "CodFornitore",
    "codfornitore": "CodFornitore",
    "ragione sociale fornitore": "RagioneSocialeFornitore",
    "ragionesocialefornitore": "RagioneSocialeFornitore",
    "ragione sociale del fornitore": "RagioneSocialeFornitore",
    "unita": "UnitaMisura",
    "unitamisura": "UnitaMisura",
    "unita misura": "UnitaMisura",
    "um": "UnitaMisura",
    "peso netto": "PesoNetto",
    "pesonetto": "PesoNetto",
    "peso lordo": "PesoLordo_Manodopera",
    "pesolordo": "PesoLordo_Manodopera",
    "peso_lordo": "PesoLordo_Manodopera",
    "codicealternativo1": "CodiceAlternativo1",
    "codice alternativo 1": "CodiceAlternativo1",
    "codice alternativo": "CodiceAlternativo1",
    "codicealternativo": "CodiceAlternativo1",
    "descrizione categoria": "DescrizioneCategoria",
    "descrizione_categoria": "DescrizioneCategoria",
    "descrizionecategoria": "DescrizioneCategoria",
    "desc categoria": "DescrizioneCategoria",
    "prezzo": "Listino1",
    "prezzovendita": "Listino1",
    "listino": "Listino1",
    "listino1": "Listino1",
    "listino2": "Listino2",
    "listino3": "Listino3",
    "prezzoultcar": "PrezzoUltCar",
    "prezzo ultimo carico": "PrezzoUltCar",
    "giacenza": "Giacenza",
    "disponibile": "Disponibile",
    "disattivato": "FlDisattivato",
    "fldisattivato": "FlDisattivato",
    "magazzino": "CodMagazzino",
}

_AGENTI_COLUMN_ALIASES: dict[str, str] = {
    "codice": "Codice",
    "codice agente": "Codice",
    "codiceagente": "Codice",
    "agente": "Codice",
    "ragione sociale": "RagioneSociale",
    "ragionesociale": "RagioneSociale",
    "provvigione": "Provvigione",
    "email": "email",
}

_AGENTI_EXPORT_LABELS: dict[str, str] = {
    "Codice": "Codice agente",
    "RagioneSociale": "Ragione sociale",
}

_PDC_COLUMN_ALIASES: dict[str, str] = {
    "codice": "Codice",
    "descrizione": "Descrizione",
    "tipo": "Tipo",
    "tipo conto": "TipoConto",
    "tipoconto": "TipoConto",
    "gruppo": "Gruppo",
}

_PDC_EXPORT_LABELS: dict[str, str] = {
    "Codice": "Codice",
    "Descrizione": "Descrizione",
    "Tipo": "Tipo",
    "TipoConto": "Tipo conto",
    "Gruppo": "Gruppo",
}

_CLIENTI_COLUMN_ALIASES: dict[str, str] = {
    "codice": "Codice",
    "ragione sociale": "RagioneSociale",
    "ragionesociale": "RagioneSociale",
    "ragione sociale 1": "RagioneSociale1",
    "ragionesociale1": "RagioneSociale1",
    "provincia": "Provincia",
    "localita": "Localita",
    "località": "Localita",
    "indirizzo": "Indirizzo",
    "cap": "Cap",
    "partita iva": "PartitaIva",
    "partitaiva": "PartitaIva",
    "codice fiscale": "CodFiscale",
    "codfiscale": "CodFiscale",
    "email": "Email",
    "telefono": "Telefono",
    "agente": "Agente",
    "zona": "Zona",
    "gruppo": "Gruppo",
    "cond pagamento": "CondPaga",
    "cond. pagamento": "CondPaga",
    "condpagamento": "CondPaga",
    "cond paga": "CondPaga",
    "condpaga": "CondPaga",
    "condizione pagamento": "CondPaga",
    "condizione di pagamento": "CondPaga",
    "pagamento": "CondPaga",
    "descrizione pagamento": "DescrizionePagamento",
    "descrizione_pagamento": "DescrizionePagamento",
    "descrizionepagamento": "DescrizionePagamento",
    "desc pagamento": "DescrizionePagamento",
}

_CLIENTI_EXPORT_LABELS: dict[str, str] = {
    "Codice": "Codice",
    "RagioneSociale": "Ragione sociale",
    "RagioneSociale1": "Ragione sociale",
    "Provincia": "Provincia",
    "Localita": "Località",
    "CondPaga": "Cond. pagamento",
    "DescrizionePagamento": "Descrizione pagamento",
}

_FORNITORI_COLUMN_ALIASES: dict[str, str] = {
    "codice": "Codice",
    "ragione sociale": "RagioneSociale",
    "ragionesociale": "RagioneSociale",
    "provincia": "Provincia",
    "localita": "Localita",
    "località": "Localita",
    "cond pagamento": "CondPaga",
    "cond. pagamento": "CondPaga",
    "condpagamento": "CondPaga",
    "cond paga": "CondPaga",
    "condpaga": "CondPaga",
    "descrizione pagamento": "DescrizionePagamento",
    "descrizione_pagamento": "DescrizionePagamento",
    "descrizionepagamento": "DescrizionePagamento",
}

_FORNITORI_EXPORT_LABELS: dict[str, str] = {
    "Codice": "Codice",
    "RagioneSociale": "Ragione sociale",
    "Provincia": "Provincia",
    "CondPaga": "Cond. pagamento",
    "DescrizionePagamento": "Descrizione pagamento",
}

_PRIMANOTA_COLUMN_ALIASES: dict[str, str] = {
    "contodare": "ContoDare",
    "conto dare": "ContoDare",
    "conto_dare": "ContoDare",
    "contoavere": "ContoAvere",
    "conto avere": "ContoAvere",
    "conto_avere": "ContoAvere",
    "dare": "Dare",
    "avere": "Avere",
    "avere imponibile": "Avere",
    "avere_imponibile": "Avere",
    "descontodare": "DesContoDare",
    "des conto dare": "DesContoDare",
    "descontoavere": "DesContoAvere",
    "des conto avere": "DesContoAvere",
    "descrizione dare": "DescrizioneDare",
    "descrizione_dare": "DescrizioneDare",
    "descrizionedare": "DescrizioneDare",
    "desc dare": "DescrizioneDare",
    "descrizione avere": "DescrizioneAvere",
    "descrizione_avere": "DescrizioneAvere",
    "descrizioneavere": "DescrizioneAvere",
    "desc avere": "DescrizioneAvere",
    "descrizione causale contabile": "DescrizioneCausaleContabile",
    "descrizione_causale_contabile": "DescrizioneCausaleContabile",
    "descrizionecausalecontabile": "DescrizioneCausaleContabile",
    "descrizione causale": "DescrizioneCausaleContabile",
    "descrizione_causale": "DescrizioneCausaleContabile",
    "des causale": "DescrizioneCausaleContabile",
    "codiceiva": "CodiceIva",
    "codice iva": "CodiceIva",
    "codice_iva": "CodiceIva",
    "importoiva": "ImportoIva",
    "importo iva": "ImportoIva",
    "importo_iva": "ImportoIva",
    "totaledoc": "TotaleDoc",
    "totale doc": "TotaleDoc",
    "totale_doc": "TotaleDoc",
    "totaledocumento": "TotaleDoc",
    "totale documento": "TotaleDoc",
    "descrizione": "Descrizione",
    "numeroreg": "NumeroReg",
    "numero reg": "NumeroReg",
    "numero registrazione": "NumeroReg",
    "datareg": "DataReg",
    "data reg": "DataReg",
    "data registrazione": "DataReg",
    "causale": "Causale",
    "codicepartita": "CodicePartita",
    "codice partita": "CodicePartita",
    "codice_partita": "CodicePartita",
    "cod. partita": "CodicePartita",
    "c/partita": "CodicePartita",
    "ragionesociale": "RagioneSocialePartita",
    "ragione sociale": "RagioneSocialePartita",
    "ragione_sociale": "RagioneSocialePartita",
    "ragionesociale partita": "RagioneSocialePartita",
    "ragione sociale partita": "RagioneSocialePartita",
    "ragione_sociale_partita": "RagioneSocialePartita",
    "descrizione codice partita": "RagioneSocialePartita",
    "descrizione_codice_partita": "RagioneSocialePartita",
    "des codice partita": "RagioneSocialePartita",
    "tipo": "Tipo",
    "numerodoc": "NumeroDoc",
    "numero doc": "NumeroDoc",
    "datadoc": "DataDoc",
    "data doc": "DataDoc",
}

_PRIMANOTA_EXPORT_LABELS: dict[str, str] = {
    "ContoDare": "Conto dare",
    "ContoAvere": "Conto avere",
    "Dare": "Dare",
    "Avere": "Avere",
    "Avere_Imponibile": "Avere",
    "DesContoDare": "Des. conto dare",
    "DesContoAvere": "Des. conto avere",
    "DescrizioneDare": "Descrizione dare",
    "DescrizioneAvere": "Descrizione avere",
    "DescrizioneCausaleContabile": "Descrizione causale contabile",
    "Descrizione": "Descrizione",
    "NumeroReg": "N. registrazione",
    "DataReg": "Data registrazione",
    "Causale": "Causale",
    "CodicePartita": "Codice partita",
    "RagioneSocialePartita": "Ragione sociale",
    "Tipo": "Tipo",
    "NumeroDoc": "N. documento",
    "DataDoc": "Data documento",
    "CodiceIva": "Codice IVA",
    "ImportoIva": "Importo IVA",
    "TotaleDoc": "Totale doc",
}

# Colonne di testa primanota (filtrate/selezionate con alias p.).
_PRIMANOTA_TESTA_COLUMNS: frozenset[str] = frozenset(
    {
        "ID",
        "NumeroReg",
        "DataReg",
        "NumeroDoc",
        "DataDoc",
        "NumeroProt",
        "AlfaProt",
        "Causale",
        "Registro",
        "Tipo",
        "CodicePartita",
        "CodicePaga",
        "Valuta",
        "CodiceAgente",
        "FornitoreCEE",
        "DataValuta",
        "TotaleDoc_Controllo",
        "Acconto",
    }
)

_PRIMANOTA_TIPO_LABELS: dict[str, int] = {
    "generico": 1,
    "iva": 2,
    "corrispettivi": 3,
    "corrispettivo": 3,
    "autofattura": 4,
    "iva autofattura": 4,
    "iva con autofattura": 4,
}

_EXPORT_TABLE_ALIASES: dict[str, tuple[str, ...]] = {
    "articoli": ("articoli", "articolo"),
    "agenti": ("agenti", "agente"),
    "pdc": ("pdc", "piano dei conti", "piano conti"),
    "clienti": ("clienti", "cliente"),
    "fornitori": ("fornitori", "fornitore"),
    "primanota": ("primanota", "prima nota"),
    "causali_contabili": (
        "causali contabili",
        "causali_contabili",
        "causali contabile",
        "causale contabile",
    ),
}

# Modelli Django per risolvere colonne ed etichette (estendibile).
_TABLE_MODELS: dict[str, str] = {
    "articoli": "articoli.Articolo",
    "agenti": "anagrafiche.Agente",
    "pdc": "pdc.PianoConti",
    "clienti": "anagrafiche.Cliente",
    "fornitori": "anagrafiche.Fornitore",
    # Export primanota: colonne riga + filtri testa (JOIN in build_primanota_export_sql).
    "primanota": "primanota.PrimanotaDettaglio",
    "causali_contabili": "causali_contabili.CausaleContabile",
}

_EXPORT_STOP_WORDS = frozenset(
    {
        "articoli",
        "articolo",
        "agenti",
        "agente",
        "pdc",
        "piano",
        "conti",
        "conto",
        "clienti",
        "cliente",
        "fornitori",
        "fornitore",
        "primanota",
        "causali",
        "contabili",
        "contabile",
        "lista",
        "elenco",
        "tabella",
        "dalla",
        "formato",
        "dove",
        "where",
        "prodotto",
        "prodotti",
        "esporta",
        "esportare",
        "esportazione",
        "export",
        "genera",
        "scarica",
        "download",
        "file",
        "xlsx",
        "excel",
        "csv",
        "con",
        "i",
        "il",
        "la",
        "le",
        "gli",
        "dei",
        "del",
        "della",
        "delle",
        "e",
        "campi",
        "colonne",
        "includi",
        "include",
        "sinonimi",
        "sinonimo",
        "nella",
        "contiene",
        "cerca",
        "mostra",
        "mostrami",
        "calzature",
        "calzatura",
        "attivi",
        "attivo",
        "disattivati",
        "disattivato",
        "generico",
        "corrispettivi",
        "autofattura",
        "dal",
        "fino",
    }
)


def get_ai_export_dir() -> Path:
    override = getattr(settings, "AI_EXPORT_DIR", None)
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "eureka-ai-exports"


def is_valid_export_token(token: str) -> bool:
    return bool(token and _TOKEN_RE.fullmatch(token))


def export_path_for_token(token: str, fmt: str = "xlsx") -> Path:
    ext = "csv" if (fmt or "").strip().lower() == "csv" else "xlsx"
    return get_ai_export_dir() / f"{token}.{ext}"


def resolve_saved_export_path(token: str) -> Path | None:
    """Percorso file export salvato (.xlsx o .csv)."""
    if not is_valid_export_token(token):
        return None
    directory = get_ai_export_dir()
    for ext in ("xlsx", "csv"):
        path = directory / f"{token}.{ext}"
        if path.is_file():
            return path
    return None


def filename_path_for_token(token: str) -> Path:
    return get_ai_export_dir() / f"{token}.name"


def _normalize_token(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", (value or "").strip().casefold())


def _normalize_user_text(value: str) -> str:
    """Normalizza testo utente per confronti case-insensitive."""
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


def _is_camel_case_identifier(value: str) -> bool:
    """True per identificatori compatti tipo PrezzoUltCar (non parole separate)."""
    compact = re.sub(r"[\s_\-]+", "", value or "")
    return bool(
        compact
        and re.search(r"[a-z]", compact)
        and re.search(r"[A-Z]", compact)
    )


def _match_column(keys: Sequence[str], wanted: str) -> str | None:
    wanted_lower = wanted.lower()
    for key in keys:
        if str(key).lower() == wanted_lower:
            return key
    return None


@lru_cache(maxsize=32)
def _get_model_for_table(table: str) -> type[models.Model] | None:
    model_path = _TABLE_MODELS.get((table or "").strip().lower())
    if not model_path:
        return None
    try:
        return apps.get_model(model_path)
    except LookupError:
        return None


def get_table_db_columns(table: str | None) -> list[str]:
    """Colonne DB disponibili per la tabella (da modello Django se registrato)."""
    model = _get_model_for_table(table or "")
    if not model:
        return []
    columns: list[str] = []
    for field in model._meta.get_fields():
        if getattr(field, "column", None):
            columns.append(field.column)
        elif hasattr(field, "db_column") and field.db_column:
            columns.append(field.db_column)
    return columns


def _column_aliases_for_table(table: str | None) -> dict[str, str]:
    normalized = (table or "").strip().lower()
    if normalized == "articoli":
        return _ARTICOLI_COLUMN_ALIASES
    if normalized == "agenti":
        return _AGENTI_COLUMN_ALIASES
    if normalized == "pdc":
        return _PDC_COLUMN_ALIASES
    if normalized == "clienti":
        return _CLIENTI_COLUMN_ALIASES
    if normalized == "fornitori":
        return _FORNITORI_COLUMN_ALIASES
    if normalized == "primanota":
        return _PRIMANOTA_COLUMN_ALIASES
    return {}


def _virtual_columns_for_table(table: str | None) -> frozenset[str]:
    normalized = (table or "").strip().lower()
    if normalized == "articoli":
        return _ARTICOLI_VIRTUAL_COLUMNS
    if normalized == "clienti":
        return _CLIENTI_VIRTUAL_COLUMNS
    if normalized == "fornitori":
        return _FORNITORI_VIRTUAL_COLUMNS
    if normalized == "primanota":
        return frozenset(
            {
                "Avere",
                "DescrizioneDare",
                "DescrizioneAvere",
                "DescrizioneCausaleContabile",
                "TotaleDoc",
                "RagioneSocialePartita",
                "ID",
                "NumeroReg",
                "DataReg",
                "NumeroDoc",
                "DataDoc",
                "Causale",
                "Registro",
                "Tipo",
                "CodicePartita",
                "CodicePaga",
                "Valuta",
            }
        )
    return frozenset()


def detect_export_table_from_prompt(prompt: str) -> str | None:
    """Rileva la tabella target da un prompt di export (es. 'tabella Agenti')."""
    normalized = _export_prompt_fold(prompt)
    # Frasi multi-parola prima (piano dei conti), poi "tabella/lista X".
    for table, aliases in _EXPORT_TABLE_ALIASES.items():
        if table not in _TABLE_MODELS:
            continue
        for alias in aliases:
            if " " in alias and alias in normalized:
                return table
    match = re.search(
        r"(?:dalla\s+)?(?:tabella|lista|elenco)\s+(?:dei\s+|degli\s+|delle\s+)?"
        r"([\wàèéìòù]+)",
        normalized,
    )
    if match:
        token = _normalize_token(match.group(1))
        for table, aliases in _EXPORT_TABLE_ALIASES.items():
            if table not in _TABLE_MODELS:
                continue
            names = {_normalize_token(table), *(_normalize_token(a) for a in aliases)}
            if token in names:
                return table
    for table, aliases in _EXPORT_TABLE_ALIASES.items():
        if table not in _TABLE_MODELS:
            continue
        for alias in (table, *aliases):
            if " " in alias:
                continue
            if re.search(rf"\b{re.escape(alias)}\b", normalized):
                return table
    return None


def resolve_column_name(token: str, table: str | None, *, fuzzy: bool = True) -> str | None:
    """
    Risolve un token del prompt al nome colonna DB (case-insensitive, fuzzy).

    L'input utente è confrontato senza distinzione maiuscole/minuscole; il valore
    restituito è sempre il nome colonna DB canonico (CamelCase) da usare negli
    identificatori SQL quotati, es. ``"Codice"`` non ``"codice"``.
    Restituisce None se non trovato.
    """
    token = (token or "").strip()
    if not token:
        return None

    db_columns = get_table_db_columns(table)
    if not db_columns:
        return None

    token_fold = _normalize_user_text(token)
    norm_token = _normalize_token(token)
    aliases = _column_aliases_for_table(table)

    # Alias espliciti (es. "prezzo" → Listino1, "ragione sociale fornitore" → JOIN).
    alias_hit = aliases.get(token_fold) or aliases.get(norm_token)
    if alias_hit:
        if alias_hit in db_columns:
            return alias_hit
        if alias_hit in _virtual_columns_for_table(table):
            return alias_hit

    # Match esatto su nome colonna DB.
    for col in db_columns:
        if _normalize_user_text(col) == token_fold or _normalize_token(col) == norm_token:
            return col

    model = _get_model_for_table(table or "")
    if model:
        for field in model._meta.get_fields():
            col = getattr(field, "column", None) or getattr(field, "db_column", None)
            if not col:
                continue
            field_name = getattr(field, "name", "") or ""
            verbose = str(getattr(field, "verbose_name", "") or "")
            if (
                _normalize_user_text(field_name) == token_fold
                or _normalize_token(field_name) == norm_token
                or _normalize_user_text(verbose) == token_fold
                or _normalize_token(verbose) == norm_token
            ):
                return col

    if not fuzzy:
        return None

    # Fuzzy: token contenuto nel nome colonna o viceversa (solo token brevi / una parola).
    if " " in token_fold or len(norm_token) > 32:
        return None
    fuzzy_matches: list[str] = []
    for col in db_columns:
        norm_col = _normalize_token(col)
        if norm_token in norm_col or norm_col in norm_token:
            fuzzy_matches.append(col)
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    if len(fuzzy_matches) > 1:
        fuzzy_matches.sort(key=lambda c: (len(c), c.lower()))
        return fuzzy_matches[0]

    return None


def default_export_columns(table: str | None) -> list[str]:
    """Colonne di default se l'utente non ne specifica."""
    normalized = (table or "").strip().lower()
    if normalized == "articoli":
        return list(_DEFAULT_ARTICOLI_COLUMNS)
    if normalized == "agenti":
        return list(_DEFAULT_AGENTI_COLUMNS)
    if normalized == "pdc":
        return list(_DEFAULT_PDC_COLUMNS)
    if normalized == "clienti":
        return list(_DEFAULT_CLIENTI_COLUMNS)
    if normalized == "fornitori":
        return list(_DEFAULT_CLIENTI_COLUMNS)
    if normalized == "primanota":
        return list(_DEFAULT_PRIMANOTA_COLUMNS)
    if normalized == "causali_contabili":
        return list(_DEFAULT_CAUSALI_CONTABILI_COLUMNS)

    db_columns = get_table_db_columns(table)
    if not db_columns:
        return []

    # PK comune + prima colonna testuale tipo Descrizione.
    pk_candidates = ("Codice", "ID", "id")
    selected: list[str] = []
    for pk in pk_candidates:
        if pk in db_columns:
            selected.append(pk)
            break
    for name in db_columns:
        if name in selected:
            continue
        if "descri" in name.lower() or name.lower() in ("ragionesociale", "ragionesociale1"):
            selected.append(name)
            break
    return selected or db_columns[:2]


_HEADER_ALIAS_KEYWORD_RE = re.compile(
    r"\s+(?:come|as|alias|intitolato|rinominato(?:\s+in)?|:|->)\s+",
    flags=re.IGNORECASE,
)
_SINGLE_ALIAS_KEYWORDS = frozenset({"come", "as", "alias", "intitolato", "rinominato", ":"})


def _has_header_alias_syntax(text: str) -> bool:
    return bool(_HEADER_ALIAS_KEYWORD_RE.search(text))


def _alias_keyword_span(words: Sequence[str], index: int) -> int:
    """Restituisce la lunghezza (1 o 2) della parola chiave alias a ``index``."""
    if index >= len(words):
        return 0
    word = words[index].lower()
    if word in _SINGLE_ALIAS_KEYWORDS or word == "->":
        return 1
    if word == "rinominato" and index + 1 < len(words) and words[index + 1].lower() == "in":
        return 2
    return 0


def _longest_resolvable_field_end(
    words: Sequence[str], start: int, table: str | None
) -> int | None:
    best: int | None = None
    for end in range(start + 1, len(words) + 1):
        candidate = " ".join(words[start:end])
        if resolve_column_name(candidate, table, fuzzy=False):
            best = end
    return best


def _find_label_end(words: Sequence[str], start: int, table: str | None) -> int:
    """
    Indice fine etichetta alias (inizio del prossimo campo risolvibile).

    Il campo successivo è riconosciuto solo se seguito da una parola chiave alias
    (``come``, ``as``, ``alias``, …), così testi come ``Listino`` o ``Fornitore``
    restano nell'intestazione personalizzata.
    """
    for index in range(start, len(words)):
        field_end = _longest_resolvable_field_end(words, index, table)
        if field_end is not None and _alias_keyword_span(words, field_end):
            return index
    return len(words)


def _parse_export_field_word_stream(
    words: Sequence[str], table: str | None
) -> list[str]:
    """
    Analizza una sequenza di parole in token ``campo [alias intestazione]``.

    Gestisce prompt senza virgole, es.::
        codice come Cod Art descrizione as Desc breve prezzo alias Listino
    """
    tokens: list[str] = []
    index = 0
    while index < len(words):
        field_end = _longest_resolvable_field_end(words, index, table)
        if field_end is None:
            index += 1
            continue

        field_text = " ".join(words[index:field_end])
        alias_len = _alias_keyword_span(words, field_end)
        if alias_len:
            label_start = field_end + alias_len
            label_end = _find_label_end(words, label_start, table)
            alias_text = " ".join(words[field_end:field_end + alias_len])
            label_text = " ".join(words[label_start:label_end]).strip()
            tokens.append(f"{field_text} {alias_text} {label_text}".strip())
            index = label_end
        else:
            tokens.append(field_text)
            index = field_end
    return tokens


def _split_field_tokens(segment: str, table: str | None = None) -> list[str]:
    """Spezza un segmento in token campo (virgola, ' e ', spazi, alias intestazione)."""
    segment = (segment or "").strip()
    if not segment:
        return []

    # Normalizza separatori.
    segment = re.sub(r"\s+e\s+", ",", segment, flags=re.IGNORECASE)
    segment = re.sub(r"\s*,\s*", ",", segment)
    tokens: list[str] = []
    for part in segment.split(","):
        part = part.strip()
        if not part:
            continue
        # Espressioni calcolate (es. somma(avere+importo_iva) as totaledoc):
        # non spezzare sul word-stream.
        if _looks_like_primanota_computed_expr(part):
            tokens.append(part)
            continue
        if " " in part:
            tokens.extend(_parse_export_field_word_stream(part.split(), table))
        else:
            tokens.append(part)
    return tokens


_PRIMANOTA_AVERE_IMPORTO_IVA_RE = re.compile(
    r"""
    ^\s*
    (?:somma\s*\(\s*)?
    (?:
        (?:avere(?:_imponibile)?|avere\s+imponibile)
        \s*\+\s*
        (?:importo_?iva|importo\s+iva)
      |
        (?:importo_?iva|importo\s+iva)
        \s*\+\s*
        (?:avere(?:_imponibile)?|avere\s+imponibile)
    )
    \s*\)?
    \s*$
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def _looks_like_primanota_computed_expr(token: str) -> bool:
    field_part, _ = _parse_export_field_token(token)
    candidate = (field_part or token or "").strip()
    if not candidate:
        return False
    if _PRIMANOTA_AVERE_IMPORTO_IVA_RE.match(candidate):
        return True
    folded = re.sub(r"[\s_]+", "", candidate.casefold())
    return folded in {
        "totaledoc",
        "totaledocumento",
        "totaledocumentoiva",
        "sommaavereimportoiva",
    }


def _try_resolve_primanota_computed(
    token: str,
) -> tuple[str, str | None] | None:
    """Risolve somma(avere+importo_iva) / totaledoc → TotaleDoc (+ etichetta)."""
    field_part, header_label = _parse_export_field_token(token)
    candidate = (field_part or token or "").strip()
    if not candidate:
        return None
    if _PRIMANOTA_AVERE_IMPORTO_IVA_RE.match(candidate):
        return "TotaleDoc", header_label or "Totale doc"
    folded = re.sub(r"[\s_]+", "", candidate.casefold())
    if folded in {
        "totaledoc",
        "totaledocumento",
        "totaledocumentoiva",
        "sommaavereimportoiva",
    }:
        return "TotaleDoc", header_label or "Totale doc"
    return None


def _export_prompt_fold(prompt: str) -> str:
    return re.sub(r"\s+", " ", (prompt or "").strip().casefold())


def _export_keyword_index(prompt: str) -> int:
    """Indice dell'ultima parola chiave export nel prompt (per limitare l'estrazione campi)."""
    lowered = _export_prompt_fold(prompt)
    keywords = (
        "genera un file csv",
        "genera file csv",
        "genera csv",
        "crea un file csv",
        "crea file csv",
        "genera un file xlsx",
        "genera file xlsx",
        "genera xlsx",
        "export in xlsx",
        "export in excel",
        "export in csv",
        "file csv",
        "file xlsx",
        "file excel",
        "esporta",
        "export",
        "scarica",
        "xlsx",
        "excel",
        "csv",
    )
    last = -1
    for kw in keywords:
        pos = lowered.rfind(kw)
        if pos > last:
            last = pos
    return last


def _strip_export_filter_suffix(segment: str) -> str:
    """Rimuove da un segmento campi la parte filtro (dove/where …) e mapping."""
    if not segment:
        return segment
    cleaned = re.split(
        r"\s+(?:dove|where)\s+",
        segment,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    # Es. «tipo sostituisci (tipo=2 come 'mastro', …)»
    cleaned = re.split(
        r"\s+sostituisci\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    # Es. «… avere dal 1/6/2026» / «fino al 31/12/2026»
    cleaned = re.split(
        r"\s+(?:dal|fino(?:\s+al)?)\s+\d",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    # Es. «tipo generico contodare, …» → lascia solo le colonne
    cleaned = re.sub(
        r"\btipo\s+(?:generico|iva(?:\s+con\s+autofattura)?|corrispettivi|autofattura)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:tabella|lista|elenco)\s+(?:della\s+|dei\s+|degli\s+)?"
        r"(?:primanota|prima\s+nota|causali\s+contabili|pdc|clienti|fornitori|agenti|articoli)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Testo libero dopo le colonne (es. «a questa richiesta vorrei…»).
    cleaned = re.split(
        r"\s+a\s+questa\s+richiesta\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    return re.sub(r"\s+", " ", cleaned).strip(" ,;")


def _parse_it_date_token(token: str) -> str | None:
    """Converte date IT/ISO in YYYY-MM-DD."""
    raw = (token or "").strip().strip("'\"")
    if not raw:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if match:
        y, m, d = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        match = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})", raw)
        if not match:
            return None
        d, m, y = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if y < 100:
            y += 2000
    if not (1 <= m <= 12 and 1 <= d <= 31 and y >= 1900):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def extract_primanota_export_filters(prompt: str) -> list[str]:
    """
    Filtri tipici export primanota: tipo generico/IVA, dal/fino a data.

    Clausole già qualificate su alias ``p`` (testa).
    """
    normalized = re.sub(r"\s+", " ", (prompt or "").strip())
    lowered = normalized.casefold()
    clauses: list[str] = []

    tipo_match = re.search(
        r"\btipo\s*=\s*(\d+)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if tipo_match:
        clauses.append(f'p."Tipo" = {int(tipo_match.group(1))}')
    else:
        for label, value in _PRIMANOTA_TIPO_LABELS.items():
            if re.search(rf"\btipo\s+{re.escape(label)}\b", lowered):
                clauses.append(f'p."Tipo" = {value}')
                break
            if re.search(rf"\btipo\s*=\s*{re.escape(label)}\b", lowered):
                clauses.append(f'p."Tipo" = {value}')
                break

    dal_match = re.search(
        r"\bdal\s+(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if dal_match:
        iso = _parse_it_date_token(dal_match.group(1))
        if iso:
            clauses.append(f'p."DataReg" >= TIMESTAMP \'{iso}\'')

    fino_match = re.search(
        r"\bfino(?:\s+al)?\s+(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if fino_match:
        iso = _parse_it_date_token(fino_match.group(1))
        if iso:
            clauses.append(
                f'p."DataReg" < TIMESTAMP \'{iso}\' + INTERVAL \'1 day\''
            )

    for clause in extract_export_where_clauses(prompt, "primanota"):
        m = re.match(r'^"([^"]+)"(\s*=\s*.+)$', clause)
        if not m:
            # Case-insensitive UPPER("Col") = …
            m2 = re.match(r'^UPPER\("([^"]+)"\)(\s*=\s*.+)$', clause)
            if not m2:
                continue
            col, rest = m2.group(1), m2.group(2)
            if col in _PRIMANOTA_TESTA_COLUMNS:
                qualified = f'UPPER(p."{col}"){rest}'
                if qualified not in clauses:
                    clauses.append(qualified)
            continue
        col = m.group(1)
        rest = m.group(2)
        if col in _PRIMANOTA_TESTA_COLUMNS:
            qualified = f'p."{col}"{rest}'
            if qualified not in clauses:
                clauses.append(qualified)
    return clauses


def primanota_export_wants_conto_links(prompt: str) -> bool:
    """True se il prompt chiede il collegamento C→clienti / F→fornitori / altrimenti PDC."""
    lowered = _export_prompt_fold(prompt)
    markers = (
        "collegamento",
        "collega",
        "collegare",
        "inizia per",
        "inizia con",
        "descrizione_avere",
        "descrizione_dare",
        "descrizione avere",
        "descrizione dare",
    )
    return any(marker in lowered for marker in markers)


def primanota_export_wants_causale_link(prompt: str) -> bool:
    """True se il prompt chiede la descrizione della causale contabile."""
    lowered = _export_prompt_fold(prompt)
    markers = (
        "descrizione_causale_contabile",
        "descrizione causale contabile",
        "descrizione_causale",
        "descrizione causale",
        "causale contabile",
        "collegamento alla descrizione della causale",
    )
    return any(marker in lowered for marker in markers)


def primanota_export_wants_partita_link(prompt: str) -> bool:
    """True se il prompt chiede la ragione sociale del codice partita."""
    lowered = _export_prompt_fold(prompt)
    markers = (
        "ragionesociale",
        "ragione sociale",
        "ragione_sociale",
        "decodifica",
        "descrizione_codice_partita",
        "descrizione codice partita",
    )
    return any(marker in lowered for marker in markers)


def enrich_primanota_export_columns(
    prompt: str,
    columns: Sequence[str],
) -> list[str]:
    """
    Inserisce DescrizioneDare/DescrizioneAvere, DescrizioneCausaleContabile
    e RagioneSocialePartita quando richiesto (o se CodicePartita è presente).
    """
    cols = list(columns)

    def _insert_after(anchor: str, new_col: str) -> None:
        if new_col in cols:
            return
        if anchor in cols:
            cols.insert(cols.index(anchor) + 1, new_col)
        else:
            cols.append(new_col)

    if primanota_export_wants_conto_links(prompt):
        if "ContoDare" in cols:
            _insert_after("ContoDare", "DescrizioneDare")
        if "ContoAvere" in cols:
            # Preferisci dopo Avere se presente, altrimenti dopo ContoAvere.
            if "Avere" in cols and "DescrizioneAvere" not in cols:
                cols.insert(cols.index("Avere") + 1, "DescrizioneAvere")
            else:
                _insert_after("ContoAvere", "DescrizioneAvere")

    if primanota_export_wants_causale_link(prompt) or (
        "DescrizioneCausaleContabile" in cols
    ):
        if "Causale" in cols:
            _insert_after("Causale", "DescrizioneCausaleContabile")
        elif "DescrizioneCausaleContabile" not in cols:
            cols.append("DescrizioneCausaleContabile")

    # Codice partita: sempre C→clienti / F→fornitori quando la colonna è presente.
    if "CodicePartita" in cols:
        _insert_after("CodicePartita", "RagioneSocialePartita")
    return cols


_RAGIONE_SOCIALE_EXPR = (
    "TRIM(BOTH FROM CONCAT(COALESCE({alias}.\"RagioneSociale1\", ''), ' ', "
    "COALESCE({alias}.\"RagioneSociale2\", '')))"
)


def _primanota_conto_prefix_expr(conto_ref: str) -> str:
    return f"UPPER(LEFT(TRIM(BOTH FROM COALESCE({conto_ref}, '')), 1))"


def _primanota_linked_descrizione_sql(conto_ref: str, *, side: str) -> str:
    """
    Descrizione collegata: F→fornitori, C→clienti, altrimenti PDC.

    ``side`` è ``dare`` o ``avere`` (suffisso alias JOIN).
    """
    prefix = _primanota_conto_prefix_expr(conto_ref)
    f_alias = f"f_{side}"
    c_alias = f"c_{side}"
    p_alias = f"pdc_{side}"
    rs_f = _RAGIONE_SOCIALE_EXPR.format(alias=f_alias)
    rs_c = _RAGIONE_SOCIALE_EXPR.format(alias=c_alias)
    as_name = "DescrizioneDare" if side == "dare" else "DescrizioneAvere"
    return (
        f"CASE "
        f"WHEN {prefix} = 'F' THEN NULLIF({rs_f}, '') "
        f"WHEN {prefix} = 'C' THEN NULLIF({rs_c}, '') "
        f"ELSE NULLIF(TRIM(BOTH FROM COALESCE({p_alias}.\"Descrizione\", '')), '') "
        f'END AS "{as_name}"'
    )


def _primanota_ragione_sociale_partita_sql() -> str:
    """Ragione sociale codice partita: F→fornitori, C→clienti."""
    partita = 'p."CodicePartita"'
    prefix = _primanota_conto_prefix_expr(partita)
    rs_f = _RAGIONE_SOCIALE_EXPR.format(alias="f_partita")
    rs_c = _RAGIONE_SOCIALE_EXPR.format(alias="c_partita")
    return (
        f"CASE "
        f"WHEN {prefix} = 'F' THEN NULLIF({rs_f}, '') "
        f"WHEN {prefix} = 'C' THEN NULLIF({rs_c}, '') "
        f"ELSE NULL "
        f'END AS "RagioneSocialePartita"'
    )


def build_primanota_conto_joins(columns: Sequence[str]) -> str:
    """LEFT JOIN clienti/fornitori/pdc (+ causali / partita) per descrizioni."""
    parts: list[str] = []
    if "DescrizioneCausaleContabile" in columns:
        parts.append(
            'LEFT JOIN causali_contabili cc '
            'ON UPPER(TRIM(BOTH FROM COALESCE(cc."Codice", \'\'))) = '
            'UPPER(TRIM(BOTH FROM COALESCE(p."Causale", \'\')))'
        )
    if "RagioneSocialePartita" in columns:
        partita = 'p."CodicePartita"'
        prefix = _primanota_conto_prefix_expr(partita)
        parts.extend(
            [
                f"LEFT JOIN fornitori f_partita ON {prefix} = 'F' "
                f'AND UPPER(f_partita."Codice") = UPPER(TRIM(BOTH FROM {partita}))',
                f"LEFT JOIN clienti c_partita ON {prefix} = 'C' "
                f'AND UPPER(c_partita."Codice") = UPPER(TRIM(BOTH FROM {partita}))',
            ]
        )
    if "DescrizioneDare" in columns:
        conto = 'pd."ContoDare"'
        prefix = _primanota_conto_prefix_expr(conto)
        parts.extend(
            [
                f"LEFT JOIN fornitori f_dare ON {prefix} = 'F' "
                f'AND UPPER(f_dare."Codice") = UPPER(TRIM(BOTH FROM {conto}))',
                f"LEFT JOIN clienti c_dare ON {prefix} = 'C' "
                f'AND UPPER(c_dare."Codice") = UPPER(TRIM(BOTH FROM {conto}))',
                f"LEFT JOIN pdc pdc_dare ON {prefix} NOT IN ('C', 'F') "
                f'AND UPPER(pdc_dare."Codice") = UPPER(TRIM(BOTH FROM {conto}))',
            ]
        )
    if "DescrizioneAvere" in columns:
        conto = 'pd."ContoAvere"'
        prefix = _primanota_conto_prefix_expr(conto)
        parts.extend(
            [
                f"LEFT JOIN fornitori f_avere ON {prefix} = 'F' "
                f'AND UPPER(f_avere."Codice") = UPPER(TRIM(BOTH FROM {conto}))',
                f"LEFT JOIN clienti c_avere ON {prefix} = 'C' "
                f'AND UPPER(c_avere."Codice") = UPPER(TRIM(BOTH FROM {conto}))',
                f"LEFT JOIN pdc pdc_avere ON {prefix} NOT IN ('C', 'F') "
                f'AND UPPER(pdc_avere."Codice") = UPPER(TRIM(BOTH FROM {conto}))',
            ]
        )
    return " ".join(parts)


def build_primanota_select_list(columns: Sequence[str]) -> str:
    """SELECT list export primanota (testa p. + dettaglio pd. + link conti/causale)."""
    parts: list[str] = []
    for col in columns:
        if col == "Avere":
            parts.append('pd."Avere_Imponibile" AS "Avere"')
        elif col == "DescrizioneDare":
            parts.append(
                _primanota_linked_descrizione_sql('pd."ContoDare"', side="dare")
            )
        elif col == "DescrizioneAvere":
            parts.append(
                _primanota_linked_descrizione_sql('pd."ContoAvere"', side="avere")
            )
        elif col == "DescrizioneCausaleContabile":
            parts.append(
                'NULLIF(TRIM(BOTH FROM COALESCE(cc."Descrizione", \'\')), \'\') '
                'AS "DescrizioneCausaleContabile"'
            )
        elif col == "RagioneSocialePartita":
            parts.append(_primanota_ragione_sociale_partita_sql())
        elif col == "TotaleDoc":
            parts.append(
                '(COALESCE(pd."Avere_Imponibile", 0) + COALESCE(pd."ImportoIva", 0)) '
                'AS "TotaleDoc"'
            )
        elif col in _PRIMANOTA_TESTA_COLUMNS:
            parts.append(f'p."{col}"')
        else:
            parts.append(f'pd."{col}"')
    return ", ".join(parts)


def build_primanota_export_sql(
    columns: Sequence[str],
    where_clauses: Sequence[str] | None = None,
) -> str:
    """SELECT righe dettaglio JOIN testa (+ clienti/fornitori/pdc/causali se serve)."""
    select_list = build_primanota_select_list(columns)
    sql = (
        f"SELECT {select_list} "
        "FROM primanota p "
        'JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter"'
    )
    joins = build_primanota_conto_joins(columns)
    if joins:
        sql += " " + joins
    clauses = [c for c in (where_clauses or []) if c]
    if not any("dummy" in c.lower() for c in clauses):
        clauses.append('pd."dummy" IS NOT TRUE')
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += ' ORDER BY p."DataReg", p."NumeroReg", pd."Pos", pd."ID"'
    return sql


def _sql_literal(value: str) -> str | None:
    """Converte un valore testo utente in letterale SQL sicuro (numero o stringa)."""
    raw = (value or "").strip()
    if not raw:
        return None
    if (
        (raw.startswith("'") and raw.endswith("'"))
        or (raw.startswith('"') and raw.endswith('"'))
    ):
        inner = raw[1:-1].replace("'", "''")
        return f"'{inner}'"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return raw
    if re.fullmatch(r"[\wàèéìòù.\-]+", raw, flags=re.IGNORECASE):
        return f"'{raw.replace(chr(39), chr(39)+chr(39))}'"
    return None


def _resolve_filter_column(field_token: str, table: str | None, value: str) -> str | None:
    """
    Risolve la colonna filtro.

    Su PDC, «tipoconto = 1» (valore numerico) punta a ``Tipo`` perché
    ``TipoConto`` è testuale (Attivita'/Passivita'/…).
    """
    field = (field_token or "").strip()
    col = resolve_column_name(field, table, fuzzy=False)
    numeric_value = re.fullmatch(r"-?\d+", (value or "").strip().strip("'\""))
    # Su PDC TipoConto è testo; «tipoconto = 1» significa il campo numerico Tipo.
    if (
        (table or "").strip().lower() == "pdc"
        and numeric_value
        and (
            col == "TipoConto"
            or _normalize_token(field) == "tipoconto"
        )
    ):
        return "Tipo"
    return col


def extract_export_where_clauses(prompt: str, table: str | None) -> list[str]:
    """
    Estrae filtri uguaglianza dal prompt (es. ``dove tipoconto = 1``).

    Restituisce clausole SQL già quotate, es. ``"Tipo" = 1``.
    """
    normalized = re.sub(r"\s+", " ", (prompt or "").strip())
    clauses: list[str] = []
    for match in re.finditer(
        r"\b(?:dove|where)\s+([A-Za-zÀ-ÿ_][\wÀ-ÿ]*(?:\s+[A-Za-zÀ-ÿ_][\wÀ-ÿ]*){0,2})"
        r"\s*=\s*('([^']*)'|\"([^\"]*)\"|[^\s,;]+)",
        normalized,
        flags=re.IGNORECASE,
    ):
        field_token = match.group(1).strip()
        value_token = match.group(2).strip()
        col = _resolve_filter_column(field_token, table, value_token)
        literal = _sql_literal(value_token)
        if not col or literal is None:
            continue
        # Confronti testuali case-insensitive (es. provincia = LU).
        if literal.startswith("'") and not re.fullmatch(r"-?\d+(?:\.\d+)?", literal):
            clauses.append(f'UPPER("{col}") = UPPER({literal})')
        else:
            clauses.append(f'"{col}" = {literal}')
    return clauses


def _extract_export_segment(prompt: str) -> str | None:
    """Estrae dal prompt il segmento che elenca i campi da esportare."""
    normalized = re.sub(r"\s+", " ", (prompt or "").strip())
    lowered = _export_prompt_fold(prompt)
    export_pos = _export_keyword_index(lowered)

    # Fine segmento: filtro dove/where, mapping «sostituisci …», oppure punto di
    # fine frase seguito da maiuscola. (?-i:...) evita che re.I faccia matchare
    # [A-Z] su abbreviazioni tipo "cond. pagamento".
    # Cercare su testo con case preservato (normalized), non su casefold.
    _segment_end = (
        r"(?:\s+(?:dove|where|sostituisci|dal|fino|a\s+questa\s+richiesta)\b|"
        r"(?-i:\.\s+(?=[A-ZÀÈÉÌÒÙ]))|$)"
    )
    explicit_patterns = (
        rf"(?:campi|colonne|fields?)\s*[:\-]\s*(.+?){_segment_end}",
        rf"(?:includi|include)\s+(?:i\s+)?(?:campi\s+)?(.+?){_segment_end}",
        rf"\bcon\s+campi\s+(.+?){_segment_end}",
    )
    for pattern in explicit_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            segment = match.group(1).strip()
            segment = _strip_export_filter_suffix(segment)
            if segment and len(segment) >= 2:
                return segment

    # Altri pattern solo nella parte export del prompt (dopo xlsx/esporta/...).
    # export_pos è calcolato su lowered; whitespace già normalizzato → stessi indici.
    # Ordine: pattern specifici prima; «… con la/il …» non è elenco campi.
    tail_origin = normalized[export_pos:] if export_pos >= 0 else normalized
    tail_patterns = (
        rf"(?:export|esporta)\s+in\s+(?:xlsx|excel|csv)\s+(.+?){_segment_end}",
        rf"(?:genera|crea)\s+(?:un\s+)?(?:file\s+)?(?:xlsx|excel|csv)\s+(?:con\s+)?(.+?){_segment_end}",
        rf"(?:xlsx|excel|csv|esporta|export)\s+(?:con\s+)?(?:i\s+campi\s+)?(.+?){_segment_end}",
        rf"(?:xlsx|excel|csv)\b.*?\bcon\s+"
        rf"(?!(?:la|il|lo|le|i|gli|un|una|questa|questo|quella|quello)\b)(.+?){_segment_end}",
        rf"\bcon\s+((?:[\wàèéìòù]+(?:\s+e\s+[\wàèéìòù]+)+)){_segment_end}",
    )
    for pattern in tail_patterns:
        match = re.search(pattern, tail_origin, flags=re.IGNORECASE)
        if match:
            segment = match.group(1).strip()
            segment = _strip_export_filter_suffix(segment)
            if segment and len(segment) >= 3:
                return segment

    if export_pos >= 0:
        match = re.search(
            r"\b(?:esporta|scarica)\s+([\wàèéìòù0-9_,\s]+?)(?:\s+(?:dove|where|sostituisci|dal|fino)\b|(?-i:\.\s+(?=[A-ZÀÈÉÌÒÙ]))|$)",
            tail_origin,
            flags=re.IGNORECASE,
        )
        if match:
            segment = match.group(1).strip()
            segment = re.sub(
                r"^(?:articoli|articolo|prodotti|prodotto)\s+",
                "",
                segment,
                flags=re.IGNORECASE,
            )
            segment = _strip_export_filter_suffix(segment)
            if segment:
                return segment

    return None


def _parse_export_field_token(token: str) -> tuple[str, str | None]:
    """
    Estrae campo e alias intestazione XLSX opzionale.

    Esempi: ``codice come Cod Art``, ``descrizione as Descrizione breve``,
    ``prezzo alias Prezzo vendita``.
    """
    cleaned = token.strip().strip('"\'')
    if not cleaned:
        return "", None
    match = re.search(
        r"\s+(?:come|as|alias|intitolato|rinominato(?:\s+in)?|:|->)\s+(?P<label>.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if match:
        field = cleaned[: match.start()].strip()
        label = match.group("label").strip().strip('"\'')
        if field and label:
            return field, label
    return cleaned, None


def _extract_export_columns(
    prompt: str, table: str | None
) -> tuple[list[str], list[str], dict[str, str]]:
    """
    Estrae e risolve i nomi colonna dal prompt.

    Returns:
        (colonne_risolte, token_sconosciuti, alias_intestazioni_xlsx)
    """
    segment = _extract_export_segment(prompt)
    if not segment:
        return [], [], {}

    raw_tokens = _split_field_tokens(segment, table)
    resolved: list[str] = []
    unknown: list[str] = []
    header_overrides: dict[str, str] = {}
    seen: set[str] = set()

    for token in raw_tokens:
        field_part, header_label = _parse_export_field_token(token)
        if not field_part or field_part.lower() in _EXPORT_STOP_WORDS:
            continue
        computed = None
        if (table or "").strip().lower() == "primanota":
            computed = _try_resolve_primanota_computed(token)
        if computed:
            col, computed_label = computed
            if header_label is None and computed_label:
                header_label = computed_label
        else:
            col = resolve_column_name(field_part, table)
        if col:
            key = col.lower()
            if key not in seen:
                seen.add(key)
                resolved.append(col)
                if header_label:
                    header_overrides[col] = header_label
        else:
            unknown.append(field_part)

    return resolved, unknown, header_overrides


def resolve_export_columns(
    prompt: str,
    table: str | None,
    *,
    for_export: bool = False,
) -> tuple[list[str], list[str], dict[str, str]]:
    """
    Colonne da usare per export/SQL.

    Returns:
        (colonne, token_sconosciuti, alias_intestazioni_xlsx)
    """
    if for_export or _prompt_mentions_export_fields(prompt):
        requested, unknown, header_overrides = _extract_export_columns(prompt, table)
        if requested:
            if (table or "").strip().lower() == "primanota":
                requested = enrich_primanota_export_columns(prompt, requested)
            return requested, unknown, header_overrides
    return default_export_columns(table), [], {}


def _prompt_mentions_export_fields(prompt: str) -> bool:
    lowered = _export_prompt_fold(prompt)
    markers = (
        "campi:",
        "colonne:",
        "includi ",
        "include ",
        " con codice",
        "genera xlsx con",
        "genera un file xlsx con",
        "file xlsx con",
        "file excel con",
        "genera csv con",
        "crea un file csv con",
        "file csv con",
        "csv con",
        "esporta codice",
        "esporta con",
        "export ",
        "export in",
        "tabella primanota",
        "contodare",
        "contoavere",
    )
    return any(marker in lowered for marker in markers)


def column_display_labels(
    table: str | None,
    columns: Sequence[str],
    header_overrides: dict[str, str] | None = None,
) -> list[str]:
    """Etichette human-readable per intestazioni XLSX."""
    model = _get_model_for_table(table or "")
    col_to_label: dict[str, str] = {}
    if model:
        for field in model._meta.get_fields():
            col = getattr(field, "column", None) or getattr(field, "db_column", None)
            if not col:
                continue
            verbose = getattr(field, "verbose_name", None)
            if verbose:
                col_to_label[col] = str(verbose).title()
            else:
                col_to_label[col] = col
    if (table or "").strip().lower() == "articoli":
        col_to_label.update(_ARTICOLI_EXPORT_LABELS)
    if (table or "").strip().lower() == "agenti":
        col_to_label.update(_AGENTI_EXPORT_LABELS)
    if (table or "").strip().lower() == "pdc":
        col_to_label.update(_PDC_EXPORT_LABELS)
    if (table or "").strip().lower() == "clienti":
        col_to_label.update(_CLIENTI_EXPORT_LABELS)
    if (table or "").strip().lower() == "fornitori":
        col_to_label.update(_FORNITORI_EXPORT_LABELS)
    if (table or "").strip().lower() == "primanota":
        col_to_label.update(_PRIMANOTA_EXPORT_LABELS)

    overrides = header_overrides or {}
    overrides_lower = {key.lower(): value for key, value in overrides.items()}
    labels: list[str] = []
    for col in columns:
        if col in overrides:
            labels.append(overrides[col])
        elif str(col).lower() in overrides_lower:
            labels.append(overrides_lower[str(col).lower()])
        else:
            labels.append(col_to_label.get(col, col))
    return labels


def select_export_columns(
    rows: list[dict],
    table: str | None,
    requested_columns: Sequence[str] | None = None,
) -> list[str]:
    """Colonne da esportare: richieste, default tabella, o tutte."""
    if not rows:
        return list(requested_columns or [])

    keys = list(rows[0].keys())
    if requested_columns:
        selected: list[str] = []
        for name in requested_columns:
            match = _match_column(keys, name)
            if match and match not in selected:
                selected.append(match)
        if selected:
            return selected

    normalized = (table or "").strip().lower()
    if normalized == "articoli":
        selected = []
        for name in _DEFAULT_ARTICOLI_COLUMNS:
            match = _match_column(keys, name)
            if match:
                selected.append(match)
        if selected:
            return selected

    return keys


def rows_to_xlsx_payload(
    rows: list[dict],
    *,
    table: str | None,
    requested_columns: Sequence[str] | None = None,
    header_overrides: dict[str, str] | None = None,
    sheet_title: str = "Dati",
    fmt: str = "xlsx",
) -> tuple[list[str], list[str], list[list[Any]], bytes]:
    db_columns = select_export_columns(rows, table, requested_columns)
    header_labels = column_display_labels(table, db_columns, header_overrides)
    data_rows = [[row.get(col) for col in db_columns] for row in rows]
    if (fmt or "").strip().lower() == "csv":
        content = build_csv_bytes(
            headers=header_labels, rows=data_rows, delimiter="\t"
        )
    else:
        content = build_xlsx_bytes(
            headers=header_labels, rows=data_rows, sheet_title=sheet_title
        )
    return db_columns, header_labels, data_rows, content


def save_ai_export(
    *,
    rows: list[dict],
    table: str | None,
    requested_columns: Sequence[str] | None = None,
    header_overrides: dict[str, str] | None = None,
    filename_stem: str | None = None,
    sheet_title: str = "Dati",
    fmt: str = "xlsx",
) -> dict[str, Any]:
    """
    Salva un export temporaneo (XLSX o CSV) e restituisce token/filename/colonne.
    """
    fmt = "csv" if (fmt or "").strip().lower() == "csv" else "xlsx"
    db_columns, header_labels, _, content = rows_to_xlsx_payload(
        rows,
        table=table,
        requested_columns=requested_columns,
        header_overrides=header_overrides,
        sheet_title=sheet_title,
        fmt=fmt,
    )
    stem = filename_stem or (table or "export")
    stem = re.sub(r"[^\w\-]+", "_", stem, flags=re.UNICODE).strip("_") or "export"
    filename = f"{stem}_{timezone.localdate():%Y-%m-%d}.{fmt}"
    token = uuid.uuid4().hex
    directory = get_ai_export_dir()
    directory.mkdir(parents=True, exist_ok=True)
    export_path_for_token(token, fmt).write_bytes(content)
    filename_path_for_token(token).write_text(filename, encoding="utf-8")
    return {
        "token": token,
        "filename": filename,
        "headers": header_labels,
        "db_columns": db_columns,
        "rows": len(rows),
        "fmt": fmt,
    }


def save_ai_xlsx(
    *,
    rows: list[dict],
    table: str | None,
    requested_columns: Sequence[str] | None = None,
    header_overrides: dict[str, str] | None = None,
    filename_stem: str | None = None,
    sheet_title: str = "Dati",
) -> dict[str, Any]:
    """Salva un XLSX temporaneo (wrapper di ``save_ai_export``)."""
    return save_ai_export(
        rows=rows,
        table=table,
        requested_columns=requested_columns,
        header_overrides=header_overrides,
        filename_stem=filename_stem,
        sheet_title=sheet_title,
        fmt="xlsx",
    )


def read_saved_filename(token: str) -> str:
    path = filename_path_for_token(token)
    if path.is_file():
        name = path.read_text(encoding="utf-8").strip()
        if name:
            return name
    saved = resolve_saved_export_path(token)
    if saved and saved.suffix.lower() == ".csv":
        return "export.csv"
    return "export.xlsx"


def format_export_columns_warning(unknown_tokens: Sequence[str]) -> str:
    if not unknown_tokens:
        return ""
    names = ", ".join(unknown_tokens)
    return f" Campi non riconosciuti e ignorati: {names}."


def articoli_export_needs_fornitore_join(columns: Sequence[str]) -> bool:
    """True se l'export articoli richiede JOIN alla tabella fornitori."""
    return "RagioneSocialeFornitore" in columns


def articoli_export_needs_categoria_join(columns: Sequence[str]) -> bool:
    """True se l'export articoli richiede JOIN alla tabella categorie."""
    return "DescrizioneCategoria" in columns


def articoli_export_needs_any_join(columns: Sequence[str]) -> bool:
    """True se l'export articoli richiede almeno un JOIN (fornitore/categoria)."""
    return articoli_export_needs_fornitore_join(columns) or articoli_export_needs_categoria_join(
        columns
    )


_RAGIONE_SOCIALE_FORNITORE_SQL = (
    'TRIM(BOTH FROM CONCAT(COALESCE(fornitori."RagioneSociale1", \'\'), \' \', '
    'COALESCE(fornitori."RagioneSociale2", \'\'))) AS "RagioneSocialeFornitore"'
)

_RAGIONE_SOCIALE_ANAGRAFICA_SQL = (
    'TRIM(BOTH FROM CONCAT(COALESCE({prefix}"RagioneSociale1", \'\'), \' \', '
    'COALESCE({prefix}"RagioneSociale2", \'\'))) AS "RagioneSociale"'
)

_DESCRIZIONE_PAGAMENTO_SQL = 'condizioni."Descrizione" AS "DescrizionePagamento"'

_DESCRIZIONE_CATEGORIA_SQL = 'categorie."Descrizione" AS "DescrizioneCategoria"'

# PDC.Tipo (4D): 2=mastro, 0=conto, 1=sottoconto/contropartita.
_PDC_TIPO_LABEL_SQL = (
    'CASE {prefix}"Tipo" '
    "WHEN 2 THEN 'mastro' "
    "WHEN 0 THEN 'conto' "
    "WHEN 1 THEN 'sottoconto' "
    'ELSE CAST({prefix}"Tipo" AS TEXT) '
    'END AS "Tipo"'
)

_ANAGRAFICA_CONDIZIONI_JOIN_ON = (
    'UPPER(condizioni."Codice") = UPPER({table}."CondPaga")'
)


def anagrafica_export_needs_condizioni_join(columns: Sequence[str]) -> bool:
    """True se l'export clienti/fornitori richiede JOIN condizioni."""
    return "DescrizionePagamento" in columns


def build_table_select_list(
    table: str,
    columns: Sequence[str],
    *,
    qualified: bool = False,
) -> str:
    """SELECT list per export tabella, con colonne virtuali anagrafiche."""
    prefix = f"{table}." if qualified else ""
    parts: list[str] = []
    for col in columns:
        if col == "RagioneSociale" and table in {"clienti", "fornitori"}:
            parts.append(_RAGIONE_SOCIALE_ANAGRAFICA_SQL.format(prefix=prefix))
        elif col == "DescrizionePagamento" and table in {"clienti", "fornitori"}:
            parts.append(_DESCRIZIONE_PAGAMENTO_SQL)
        elif col == "Tipo" and table == "pdc":
            parts.append(_PDC_TIPO_LABEL_SQL.format(prefix=prefix))
        else:
            parts.append(f'{prefix}"{col}"')
    return ", ".join(parts)


def build_table_from_clause(table: str, columns: Sequence[str]) -> str:
    """FROM tabella, con JOIN condizioni se serve descrizione pagamento."""
    parts = [table]
    if table in {"clienti", "fornitori"} and anagrafica_export_needs_condizioni_join(
        columns
    ):
        parts.append(
            "LEFT JOIN condizioni ON "
            + _ANAGRAFICA_CONDIZIONI_JOIN_ON.format(table=table)
        )
    return " ".join(parts)


def qualify_table_where_clause(table: str, clause: str) -> str:
    """Qualifica colonne della tabella principale nel WHERE quando c'è JOIN."""
    for col in get_table_db_columns(table):
        clause = re.sub(
            rf'(?<!\.)(?<!\w)"{re.escape(col)}"',
            f'{table}."{col}"',
            clause,
        )
    return clause


def build_table_export_sql(
    table: str,
    columns: Sequence[str],
    where_clauses: Sequence[str] | None = None,
) -> str:
    """SELECT per export tabella mirror, con JOIN opzionale condizioni."""
    needs_join = table in {"clienti", "fornitori"} and anagrafica_export_needs_condizioni_join(
        columns
    )
    select_list = build_table_select_list(table, columns, qualified=needs_join)
    from_clause = build_table_from_clause(table, columns)
    sql = f"SELECT {select_list} FROM {from_clause}"
    clauses = [c for c in (where_clauses or []) if c]
    if clauses:
        if needs_join:
            clauses = [qualify_table_where_clause(table, c) for c in clauses]
        sql += " WHERE " + " AND ".join(clauses)
    return sql


def build_articoli_sql_select_list(
    columns: Sequence[str],
    *,
    qualified: bool = False,
) -> str:
    """SELECT articoli (+ fornitore se colonne virtuali) con alias quotati."""
    parts: list[str] = []
    prefix = "articoli." if qualified else ""
    for col in columns:
        if col == "RagioneSocialeFornitore":
            parts.append(_RAGIONE_SOCIALE_FORNITORE_SQL)
        elif col == "DescrizioneCategoria":
            parts.append(_DESCRIZIONE_CATEGORIA_SQL)
        else:
            parts.append(f'{prefix}"{col}"')
    return ", ".join(parts)


_ARTICOLI_FORNITORI_JOIN_ON = (
    'UPPER(fornitori."Codice") = UPPER(articoli."CodFornitore")'
)

_ARTICOLI_CATEGORIA_JOIN_ON = (
    'UPPER(categorie."Codice") = UPPER(articoli."CatOmogenea")'
)


def build_articoli_sql_from_clause(columns: Sequence[str]) -> str:
    """FROM articoli, con JOIN fornitori/categorie se servono colonne virtuali."""
    parts = ["articoli"]
    if articoli_export_needs_fornitore_join(columns):
        parts.append(f"LEFT JOIN fornitori ON {_ARTICOLI_FORNITORI_JOIN_ON}")
    if articoli_export_needs_categoria_join(columns):
        parts.append(f"LEFT JOIN categorie ON {_ARTICOLI_CATEGORIA_JOIN_ON}")
    return " ".join(parts)


def qualify_articoli_where_clause(clause: str) -> str:
    """Qualifica colonne articoli nel WHERE quando la query ha JOIN."""
    for col in get_table_db_columns("articoli"):
        clause = re.sub(
            rf'(?<!\.)(?<!\w)"{re.escape(col)}"',
            f'articoli."{col}"',
            clause,
        )
    return clause


def build_articoli_fast_path_sql(
    columns: Sequence[str],
    where_clauses: Sequence[str],
) -> str:
    """Query fast-path articoli con optional JOIN fornitori/categorie per export."""
    needs_join = articoli_export_needs_any_join(columns)
    select_list = build_articoli_sql_select_list(columns, qualified=needs_join)
    from_clause = build_articoli_sql_from_clause(columns)
    where_parts = (
        [qualify_articoli_where_clause(clause) for clause in where_clauses]
        if needs_join
        else list(where_clauses)
    )
    return f"SELECT {select_list} FROM {from_clause} WHERE {' AND '.join(where_parts)}"


def build_sql_select_list(columns: Sequence[str]) -> str:
    """Lista SELECT quotata per colonne CamelCase."""
    return ", ".join(f'"{col}"' for col in columns)


_MAIN_FROM_RE = re.compile(
    r"\bFROM\s+([a-zA-Z_][\w]*)(?:\s+(?:AS\s+)?[a-zA-Z_][\w]*)?\s*(?:"
    r"(?:LEFT|RIGHT|INNER|CROSS|FULL)?\s*(?:OUTER\s+)?JOIN\b|"
    r"WHERE\b|GROUP\s+BY\b|ORDER\s+BY\b|HAVING\b|LIMIT\b|OFFSET\b|;|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _find_main_from_start(sql: str, *, start: int = 0) -> int | None:
    """Indice del FROM principale (salta FROM dentro TRIM/EXTRACT/CONCAT)."""
    match = _MAIN_FROM_RE.search(sql, start)
    return match.start() if match else None


def _build_missing_select_columns(columns: Sequence[str], *, sql: str = "") -> str:
    """Espressioni SELECT per colonne mancanti (incluse virtuali articoli/fornitore)."""
    if re.search(r"\bFROM\s+primanota\b", sql, re.IGNORECASE) and re.search(
        r"\bJOIN\s+primanota_dettaglio\b", sql, re.IGNORECASE
    ):
        return build_primanota_select_list(columns)
    has_articoli_joins = bool(
        re.search(r"\bJOIN\s+(?:fornitori|categorie)\b", sql, re.IGNORECASE)
    )
    regular_cols = [col for col in columns if col not in _ARTICOLI_VIRTUAL_COLUMNS]
    virtual_cols = [col for col in columns if col in _ARTICOLI_VIRTUAL_COLUMNS]
    parts: list[str] = []
    if regular_cols:
        parts.append(build_sql_select_list(regular_cols))
    if virtual_cols:
        parts.append(
            build_articoli_sql_select_list(
                virtual_cols,
                qualified=has_articoli_joins,
            )
        )
    return ", ".join(parts)


def ensure_sql_select_columns(sql: str, columns: Sequence[str]) -> str:
    """
    Aggiunge colonne mancanti al SELECT di una query (solo SELECT semplici).
    """
    if not sql or not columns:
        return sql

    select_kw = re.search(r"\bSELECT\s+(?:DISTINCT\s+)?", sql, flags=re.IGNORECASE)
    if not select_kw:
        return sql

    from_start = _find_main_from_start(sql, start=select_kw.end())
    if from_start is None:
        return sql

    select_start = select_kw.end()
    select_part = sql[select_start:from_start].strip()
    existing_lower = {c.lower() for c in re.findall(r'"([^"]+)"', select_part)}
    if "*" in select_part.replace(" ", ""):
        return sql

    missing = [col for col in columns if col.lower() not in existing_lower]
    if not missing:
        return sql

    extra = _build_missing_select_columns(missing, sql=sql)
    new_select = f"{select_part}, {extra}" if select_part else extra
    return sql[:select_start] + new_select + " " + sql[from_start:]
