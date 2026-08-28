"""Stampa HTML documento (preventivo e simili)."""

from __future__ import annotations

from typing import Any

from django.db.utils import OperationalError, ProgrammingError

from apps.aziende.configurazione import (
    resolve_azienda_dati,
    resolve_print_azienda_context,
)
from apps.aziende.models import Azienda
from apps.documenti.castelletto import (
    _line_amounts,
    calcola_castelletto_documento,
    resolve_aliquota,
)
from apps.documenti.sconto import resolve_sconto_percentuale


def _txt(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_linefeeds(value: Any) -> str:
    """Normalizza CR/LF 4D (spesso solo ``\\r``) in newline Unix."""
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    # trim solo spazi esterni, non i line feed interni
    return text.strip(" \t")


def _cliente_fiscali(clifor_tipo: str | None, codice: str | None) -> dict[str, str]:
    code = _txt(codice)
    empty = {"partita_iva": "", "codice_fiscale": ""}
    if not code:
        return empty
    try:
        from apps.anagrafiche.models import Cliente, Fornitore, get_by_codice

        model = Fornitore if (clifor_tipo or "").upper() == "F" else Cliente
        obj = get_by_codice(
            model, code, only=("codice", "partita_iva", "cod_fiscale")
        )
        if obj is None:
            return empty
        return {
            "partita_iva": _txt(getattr(obj, "partita_iva", None)),
            "codice_fiscale": _txt(getattr(obj, "cod_fiscale", None)),
        }
    except Exception:
        return empty


def _resolve_azienda() -> Azienda | None:
    try:
        dati = resolve_azienda_dati()
        if dati:
            return Azienda.objects.filter(pk=dati.azienda_id).first()
        aziende = list(Azienda.objects.order_by("id")[:2])
        if len(aziende) == 1:
            return aziende[0]
    except (ProgrammingError, OperationalError):
        return None
    return None


def _banca_detail(cod_banca: str | None) -> dict[str, str]:
    code = _txt(cod_banca)
    empty = {
        "codice": code,
        "descrizione": "",
        "abi": "",
        "cab": "",
        "iban": "",
        "swift": "",
        "line": "",
    }
    if not code:
        return empty
    try:
        from apps.banche.models import Banca

        banca = (
            Banca.objects.filter(codice__iexact=code)
            .only(
                "codice",
                "descrizione",
                "codice_abi",
                "codice_cab",
                "iban",
                "swift_code",
            )
            .first()
        )
    except (ProgrammingError, OperationalError):
        return empty
    if banca is None:
        return empty
    desc = _txt(banca.descrizione) or code
    abi = _txt(banca.codice_abi)
    cab = _txt(banca.codice_cab)
    parts = [desc]
    if abi:
        parts.append(f"ABI {abi}")
    if cab:
        parts.append(f"CAB {cab}")
    return {
        "codice": _txt(banca.codice) or code,
        "descrizione": desc,
        "abi": abi,
        "cab": cab,
        "iban": _txt(banca.iban),
        "swift": _txt(banca.swift_code),
        "line": " - ".join(parts),
    }


def build_righe_print(
    documento,
    righe,
) -> list[dict[str, Any]]:
    """Righe stampa: Importo = imponibile netto di riga (q×p − sconto riga)."""
    cache: dict = {}
    rows: list[dict[str, Any]] = []
    for riga in righe:
        sconto_riga = resolve_sconto_percentuale(
            getattr(riga, "sconto", None)
        ) or _txt(getattr(riga, "sconto", None))
        # Importo colonna stampa 4D: solo sconto riga (lo sconto testata sta nel piede).
        merce, sconto_imp, imponibile_netto = _line_amounts(
            quantita=getattr(riga, "quantita", None),
            prezzo_unitario=getattr(riga, "prezzo_unitario", None),
            sconto=sconto_riga,
        )
        iva_code = _txt(getattr(riga, "iva", None))
        aliquota = resolve_aliquota(iva_code, cache) if iva_code else None
        pct = aliquota.percentuale if aliquota else None
        # Riga solo testo (note): senza qta/prezzo
        is_note = (
            merce == 0
            and imponibile_netto == 0
            and not getattr(riga, "quantita", None)
            and not getattr(riga, "prezzo_unitario", None)
        )
        rows.append(
            {
                "riga": riga,
                "codice": _txt(getattr(riga, "codice", None)),
                "descrizione": _normalize_linefeeds(getattr(riga, "descrizione", None)),
                "um": _txt(getattr(riga, "unita_misura", None)),
                "quantita": getattr(riga, "quantita", None),
                "prezzo_unitario": getattr(riga, "prezzo_unitario", None),
                "sconto": sconto_riga,
                "imponibile_lordo": None if is_note else merce,
                "sconto_importo": None if is_note else sconto_imp,
                # Colonna Importo = imponibile netto (dopo sconto, senza IVA)
                "imponibile_netto": None if is_note else imponibile_netto,
                "importo": None if is_note else imponibile_netto,
                "iva_pct": None if is_note else pct,
                "is_note": is_note,
            }
        )
    return rows


def build_documento_print_context(documento, *, autoprint: bool = False) -> dict[str, Any]:
    """Context completo per template stampa documento."""
    from apps.anagrafiche.lookups import condizione_display
    from apps.articoli.lookups import resolve_clifor, resolve_descrizione
    from apps.documenti.models import RigaDocumento

    tipo = documento.tipo_doc
    righe = list(
        RigaDocumento.objects.filter(testa=documento).order_by("numero_riga", "id_4d")
    )
    castelletto = calcola_castelletto_documento(documento, with_peso=True)

    lookup = "fornitore" if (documento.clifor_tipo or "").upper() == "F" else "cliente"
    clifor = resolve_clifor(lookup, documento.codice_clifor)

    codice_pag = _txt(documento.cod_pagamento)
    if not codice_pag:
        codice_pag = _txt(clifor.get("cond_paga"))

    branding = resolve_print_azienda_context(branding="documenti")
    azienda = _resolve_azienda()

    destinazione_nome = _txt(documento.destinatario) or _txt(
        clifor.get("destinatario") or clifor.get("descrizione")
    )
    destinazione = {
        "nome": destinazione_nome,
        "indirizzo": _txt(documento.indirizzo) or _txt(clifor.get("indirizzo")),
        "cap": _txt(documento.cap) or _txt(clifor.get("cap")),
        "localita": _txt(documento.localita) or _txt(clifor.get("localita")),
        "provincia": _txt(documento.provincia) or _txt(clifor.get("provincia")),
        "nazione": _txt(documento.nazione) or _txt(clifor.get("nazione")),
    }

    banca = _banca_detail(documento.cod_banca)
    if _txt(documento.iban) and not banca["iban"]:
        banca["iban"] = _txt(documento.iban)

    if tipo.codice == "PRV" or getattr(tipo, "categoria", "") == "PREVENTIVI":
        title_it = "Preventivo"
        title_en = "Offer"
    else:
        title_it = (tipo.label or "Documento").strip()
        title_en = ""

    clifor_label = "Fornitore" if lookup == "fornitore" else "Cliente"
    fiscali = _cliente_fiscali(documento.clifor_tipo, documento.codice_clifor)
    valuta = _txt(documento.valuta) or "Euro"
    rif_ordine = _txt(documento.num_ordine_acq)

    # Spazio sotto le merce (stessa tabella): solo se poche righe, altrimenti
    # occuperebbe inutilmente la pagina successiva.
    n_righe = len(righe)
    if n_righe <= 0:
        lines_fill_mm = 70
    elif n_righe < 28:
        lines_fill_mm = max(10, 72 - n_righe * 2)
    else:
        lines_fill_mm = 0

    return {
        "documento": documento,
        "tipo": tipo,
        "righe_print": build_righe_print(documento, righe),
        "castelletto": castelletto,
        "azienda": azienda,
        "pagamento_display": condizione_display(codice_pag),
        "agente_label": resolve_descrizione("agente", documento.codice_agente),
        "banca": banca,
        "banca_label": banca["line"]
        or resolve_descrizione("banca", documento.cod_banca),
        "cliente_piva": fiscali["partita_iva"],
        "cliente_cf": fiscali["codice_fiscale"],
        "valuta": valuta,
        "rif_ordine": rif_ordine,
        "destinazione": destinazione,
        "destinazione_nome": destinazione_nome,
        "clifor_label": clifor_label,
        "print_title_it": title_it,
        "print_title_en": title_en,
        "lines_fill_mm": lines_fill_mm,
        "autoprint": autoprint,
        **branding,
    }
