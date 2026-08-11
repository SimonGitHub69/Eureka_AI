"""Generazione XML FatturaPA 1.2.2 per invio allo SDI."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from xml.etree.ElementTree import Element, SubElement, indent, tostring

from apps.anagrafiche.models import Cliente
from apps.aziende.models import Azienda
from apps.fatture.models import Fattura, FatturaDettaglio

NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
SCHEMA_LOCATION = (
    "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2 "
    "http://www.fatturapa.gov.it/export/fatturazione/sdi/fatturapa/v1.2/"
    "Schema_del_file_xml_FatturaPA_versione_1.2.xsd"
)

# Mappa codici IVA gestionale → (aliquota %, natura AdE opzionale).
# Natura obbligatoria quando aliquota = 0.
IVA_MAP: dict[str, tuple[Decimal, str | None]] = {
    "22": (Decimal("22"), None),
    "22A": (Decimal("22"), None),
    "22RC": (Decimal("22"), "N6.1"),
    "22SP": (Decimal("22"), "N6.1"),
    "22PM": (Decimal("22"), "N6.1"),
    "22PP": (Decimal("22"), None),
    "22XX": (Decimal("22"), None),
    "21": (Decimal("21"), None),
    "20": (Decimal("20"), None),
    "15": (Decimal("15"), None),
    "26": (Decimal("26"), None),
    "74RC": (Decimal("0"), "N6.1"),
    "8C": (Decimal("0"), "N3.5"),
    "8C-V": (Decimal("0"), "N3.5"),
    "8A": (Decimal("0"), "N3.1"),
    "41": (Decimal("0"), "N3.2"),
    "NI7": (Decimal("0"), "N7"),
    "FC": (Decimal("0"), "N2.2"),
    "FC2": (Decimal("0"), "N2.2"),
    "FC26": (Decimal("0"), "N2.2"),
}


class FatturaPAError(ValueError):
    """Dati insufficienti o inconsistenti per generare l'XML SDI."""


@dataclass(frozen=True)
class FatturaPAResult:
    xml_bytes: bytes
    filename: str
    formato: str  # FPR12 | FPA12
    warnings: tuple[str, ...]


def _txt(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _money(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _qty(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _fmt_money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _fmt_qty(value: Decimal) -> str:
    q = value.normalize()
    text = format(q, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _fmt_aliquota(value: Decimal) -> str:
    return _fmt_qty(value)


def _only_digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def _clean_cf(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def _truncate(value: str, max_len: int) -> str:
    value = _txt(value)
    return value[:max_len] if len(value) > max_len else value


def _sub(parent: Element, tag: str, text: str | None = None) -> Element:
    el = SubElement(parent, tag)
    if text is not None:
        el.text = text
    return el


def _progressivo_hex(progressivo: int | None, fallback: int) -> str:
    n = int(progressivo or fallback or 1)
    if n < 1:
        n = 1
    return f"{n:05X}"[-5:]


def resolve_iva(codice: str | None) -> tuple[Decimal, str | None]:
    code = _txt(codice).upper()
    if not code:
        return Decimal("22"), None
    if code in IVA_MAP:
        return IVA_MAP[code]
    m = re.match(r"^(\d{1,2}(?:\.\d+)?)", code)
    if m:
        aliq = Decimal(m.group(1))
        natura = None
        if aliq == 0:
            natura = "N2.2"
        elif any(x in code for x in ("RC", "PM", "SP")):
            natura = "N6.1"
        return aliq, natura
    return Decimal("0"), "N2.2"


def _parse_sconto(raw: str | None) -> Decimal | None:
    text = _txt(raw).replace(",", ".")
    if not text:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    val = Decimal(m.group(0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if val == 0:
        return None
    return abs(val)


def _is_pa(cliente: Cliente | None, codice_dest: str) -> bool:
    if cliente and cliente.flag_pa:
        return True
    return len(codice_dest) == 6 and codice_dest not in {"000000", "XXXXXX"}


def _codice_destinatario(
    fattura: Fattura,
    cliente: Cliente | None,
) -> tuple[str, str]:
    """Ritorna (CodiceDestinatario, PECDestinatario)."""
    pec = _txt(fattura.email_pec) or (_txt(cliente.pec) if cliente else "")
    cod = _txt(fattura.cod_sdi) or (_txt(cliente.codice_ufficio) if cliente else "")
    cod = re.sub(r"[^A-Za-z0-9]", "", cod).upper()

    nazione = _txt(getattr(cliente, "cod_nazione", None) if cliente else "") or "IT"
    nazione = nazione.upper()
    if nazione and nazione != "IT":
        return "XXXXXXX", ""

    if len(cod) in {6, 7}:
        return cod, pec

    if pec:
        return "0000000", pec
    return "0000000", ""


def _tipo_documento(fattura: Fattura) -> str:
    tipo = _txt(fattura.tipo_doc_fe).upper()
    if re.fullmatch(r"TD\d{2}", tipo):
        return tipo
    return "TD04" if fattura.is_nota_credito else "TD01"


def _numero_documento(fattura: Fattura) -> str:
    return _truncate(fattura.numero_documento.replace("—", "").strip() or str(fattura.id_testa), 20)


def _id_paese(azienda: Azienda, cliente: Cliente | None = None, fallback: str = "IT") -> str:
    if cliente and _txt(cliente.cod_nazione):
        return _txt(cliente.cod_nazione).upper()[:2]
    paese = _txt(azienda.cod_paese).upper()
    return (paese or fallback)[:2]


def _sede_from(
    *,
    indirizzo: str,
    cap: str,
    localita: str,
    provincia: str,
    nazione: str,
) -> dict[str, str]:
    return {
        "indirizzo": _truncate(indirizzo or "N/D", 60),
        "cap": _truncate(_only_digits(cap) or "00000", 5).ljust(5, "0")[:5],
        "comune": _truncate(localita or "N/D", 60),
        "provincia": _truncate(provincia, 2).upper(),
        "nazione": (_txt(nazione).upper() or "IT")[:2],
    }


def _add_sede(parent: Element, sede: dict[str, str]) -> None:
    block = _sub(parent, "Sede")
    _sub(block, "Indirizzo", sede["indirizzo"])
    _sub(block, "CAP", sede["cap"])
    _sub(block, "Comune", sede["comune"])
    if sede["provincia"] and sede["nazione"] == "IT":
        _sub(block, "Provincia", sede["provincia"])
    _sub(block, "Nazione", sede["nazione"])


def _add_anagrafica(
    parent: Element,
    *,
    denominazione: str | None = None,
    nome: str | None = None,
    cognome: str | None = None,
) -> None:
    ana = _sub(parent, "Anagrafica")
    if _txt(cognome) and _txt(nome):
        _sub(ana, "Nome", _truncate(nome, 60))
        _sub(ana, "Cognome", _truncate(cognome, 60))
    else:
        _sub(ana, "Denominazione", _truncate(denominazione or "N/D", 80))


def _load_azienda(azienda: Azienda | None = None) -> Azienda:
    if azienda is not None:
        return azienda
    obj = Azienda.objects.order_by("id").first()
    if obj is None:
        raise FatturaPAError("Nessuna azienda trovata: impossibile generare la fattura elettronica.")
    return obj


def _load_cliente(fattura: Fattura) -> Cliente | None:
    codice = _txt(fattura.cliente)
    if not codice:
        return None
    return Cliente.objects.filter(codice=codice).first()


def build_fatturapa(
    fattura: Fattura,
    *,
    azienda: Azienda | None = None,
    cliente: Cliente | None = None,
    righe: list[FatturaDettaglio] | None = None,
) -> FatturaPAResult:
    """Costruisce l'XML FatturaPA pronto per lo SDI (senza firma digitale)."""
    warnings: list[str] = []
    azienda = _load_azienda(azienda)
    if cliente is None:
        cliente = _load_cliente(fattura)
    if righe is None:
        righe = list(
            FatturaDettaglio.objects.filter(id_testa=fattura.id_testa).order_by(
                "numero_riga", "id"
            )
        )
    if not righe:
        raise FatturaPAError("La fattura non ha righe di dettaglio.")

    piva_cedente = _only_digits(_txt(azienda.partita_iva))
    if not piva_cedente:
        raise FatturaPAError("Partita IVA azienda mancante.")
    cf_cedente = _clean_cf(_txt(azienda.codice_fiscale)) or piva_cedente
    regime = _txt(azienda.cod_regime_fiscale).upper() or "RF01"
    if not re.fullmatch(r"RF\d{2}", regime):
        regime = "RF01"

    codice_dest, pec_dest = _codice_destinatario(fattura, cliente)
    is_pa = _is_pa(cliente, codice_dest)
    formato = "FPA12" if is_pa else "FPR12"
    if len(codice_dest) == 6 and formato == "FPR12":
        # Codice PA a 6 caratteri → forzare FPA12
        formato = "FPA12"
        is_pa = True
    if formato == "FPR12" and len(codice_dest) == 6:
        codice_dest = codice_dest.ljust(7, "0")[:7]

    if not codice_dest or codice_dest in {"0000000", "000000"}:
        if not pec_dest:
            warnings.append(
                "Codice SDI e PEC destinatario assenti: usato 0000000 (verificare inoltro)."
            )

    progressivo = _progressivo_hex(fattura.progressivo_invio, fattura.id_testa)
    filename = _txt(fattura.file_name)
    if not filename:
        filename = f"IT{piva_cedente}_{progressivo}.xml"
    if not filename.lower().endswith(".xml"):
        filename = f"{filename}.xml"

    data_doc = fattura.data_fattura
    if data_doc is None:
        raise FatturaPAError("Data fattura mancante.")
    data_str = data_doc.date().isoformat() if hasattr(data_doc, "date") else str(data_doc)[:10]
    tipo_doc = _tipo_documento(fattura)
    numero_doc = _numero_documento(fattura)

    # --- Root ---
    root = Element(
        "p:FatturaElettronica",
        {
            "versione": formato,
            "xmlns:ds": "http://www.w3.org/2000/09/xmldsig#",
            "xmlns:p": NS,
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": SCHEMA_LOCATION,
        },
    )

    header = _sub(root, "FatturaElettronicaHeader")

    if formato == "FPA12":
        codice_dest_xml = (codice_dest[:6] if len(codice_dest) >= 6 else codice_dest.ljust(6, "0"))
    elif codice_dest == "XXXXXXX":
        codice_dest_xml = "XXXXXXX"
    else:
        codice_dest_xml = (
            codice_dest[:7] if len(codice_dest) >= 7 else codice_dest.ljust(7, "0")
        )

    # DatiTrasmissione
    dt = _sub(header, "DatiTrasmissione")
    id_trasm = _sub(dt, "IdTrasmittente")
    _sub(id_trasm, "IdPaese", _id_paese(azienda))
    _sub(id_trasm, "IdCodice", piva_cedente)
    _sub(dt, "ProgressivoInvio", progressivo)
    _sub(dt, "FormatoTrasmissione", formato)
    _sub(dt, "CodiceDestinatario", codice_dest_xml)
    if pec_dest and codice_dest_xml in {"0000000", "000000"}:
        _sub(dt, "PECDestinatario", _truncate(pec_dest.lower(), 256))

    # CedentePrestatore
    cedente = _sub(header, "CedentePrestatore")
    dati_ana_c = _sub(cedente, "DatiAnagrafici")
    id_fisc_c = _sub(dati_ana_c, "IdFiscaleIVA")
    _sub(id_fisc_c, "IdPaese", _id_paese(azienda))
    _sub(id_fisc_c, "IdCodice", piva_cedente)
    if cf_cedente:
        _sub(dati_ana_c, "CodiceFiscale", cf_cedente)
    if azienda.persona_fisica and _txt(azienda.cognome) and _txt(azienda.nome):
        _add_anagrafica(dati_ana_c, nome=azienda.nome, cognome=azienda.cognome)
    else:
        _add_anagrafica(dati_ana_c, denominazione=_txt(azienda.ragione_sociale) or "Azienda")
    _sub(dati_ana_c, "RegimeFiscale", regime)
    _add_sede(
        cedente,
        _sede_from(
            indirizzo=_txt(azienda.indirizzo),
            cap=_txt(azienda.cap),
            localita=_txt(azienda.localita),
            provincia=_txt(azienda.provincia),
            nazione=_txt(azienda.cod_paese) or "IT",
        ),
    )
    if _txt(azienda.prov_rea) and _txt(azienda.num_iscrizione_rea):
        iscrizione = _sub(cedente, "IscrizioneREA")
        _sub(iscrizione, "Ufficio", _truncate(azienda.prov_rea, 2).upper())
        _sub(iscrizione, "NumeroREA", _truncate(azienda.num_iscrizione_rea, 20))
        if azienda.capitale_soc is not None:
            _sub(iscrizione, "CapitaleSociale", _fmt_money(_money(azienda.capitale_soc)))
        if azienda.socio_unico is not None:
            _sub(iscrizione, "SocioUnico", "SU" if azienda.socio_unico else "SM")
        _sub(iscrizione, "StatoLiquidazione", "LS" if azienda.in_liquidazione else "LN")
    contatti = {}
    if _txt(azienda.telefono):
        contatti["Telefono"] = _truncate(azienda.telefono, 12)
    if _txt(azienda.email):
        contatti["Email"] = _truncate(azienda.email, 256)
    if contatti:
        cblock = _sub(cedente, "Contatti")
        for k, v in contatti.items():
            _sub(cblock, k, v)

    # CessionarioCommittente
    cessionario = _sub(header, "CessionarioCommittente")
    dati_ana_s = _sub(cessionario, "DatiAnagrafici")
    piva_cli = _only_digits(_txt(cliente.partita_iva) if cliente else "")
    cf_cli = _clean_cf(_txt(cliente.cod_fiscale) if cliente else "")
    nazione_cli = (_txt(cliente.cod_nazione) if cliente else "") or "IT"
    nazione_cli = nazione_cli.upper()[:2]
    if piva_cli:
        id_fisc_s = _sub(dati_ana_s, "IdFiscaleIVA")
        _sub(id_fisc_s, "IdPaese", nazione_cli)
        _sub(id_fisc_s, "IdCodice", piva_cli)
    if cf_cli and nazione_cli == "IT":
        _sub(dati_ana_s, "CodiceFiscale", cf_cli)
    if not piva_cli and not cf_cli:
        raise FatturaPAError(
            "Cliente senza Partita IVA né Codice Fiscale: impossibile generare XML SDI."
        )
    denom = (
        (_txt(cliente.ragione_sociale) if cliente else "")
        or _txt(fattura.destinatario)
        or _txt(fattura.cliente)
        or "Cliente"
    )
    if cliente and cliente.persona_fisica and _txt(cliente.cognome) and _txt(cliente.nome):
        _add_anagrafica(dati_ana_s, nome=cliente.nome, cognome=cliente.cognome)
    else:
        _add_anagrafica(dati_ana_s, denominazione=denom)

    sede_cli = _sede_from(
        indirizzo=_txt(fattura.indirizzo) or (_txt(cliente.indirizzo) if cliente else ""),
        cap=_txt(fattura.cap) or (_txt(cliente.cap) if cliente else ""),
        localita=_txt(fattura.localita) or (_txt(cliente.localita) if cliente else ""),
        provincia=_txt(fattura.provincia) or (_txt(cliente.provincia) if cliente else ""),
        nazione=_txt(fattura.cod_iso_dest)
        or _txt(fattura.nazione)
        or nazione_cli,
    )
    _add_sede(cessionario, sede_cli)

    # Body
    body = _sub(root, "FatturaElettronicaBody")
    dati_gen = _sub(body, "DatiGenerali")
    dgd = _sub(dati_gen, "DatiGeneraliDocumento")
    _sub(dgd, "TipoDocumento", tipo_doc)
    _sub(dgd, "Divisa", "EUR")
    _sub(dgd, "Data", data_str)
    _sub(dgd, "Numero", numero_doc)

    bollo = _money(fattura.imp_spese_bollo_virtuale)
    if bollo > 0:
        dati_bollo = _sub(dgd, "DatiBollo")
        _sub(dati_bollo, "BolloVirtuale", "SI")
        _sub(dati_bollo, "ImportoBollo", _fmt_money(bollo))

    # Placeholder: ImportoTotaleDocumento e Causale dopo le righe (ordine schema)
    importo_el = _sub(dgd, "ImportoTotaleDocumento", "0.00")
    causale = _txt(fattura.desc_causale) or _txt(fattura.desc_nota_c)
    if causale:
        _sub(dgd, "Causale", _truncate(causale, 200))

    # Ordine acquisto / CIG / CUP
    if _txt(fattura.num_ordine_acq) or _txt(fattura.cig) or _txt(fattura.cup):
        dao = _sub(dati_gen, "DatiOrdineAcquisto")
        if _txt(fattura.num_ordine_acq):
            _sub(dao, "IdDocumento", _truncate(fattura.num_ordine_acq, 20))
        if fattura.data_ordine_acq:
            dord = fattura.data_ordine_acq
            _sub(
                dao,
                "Data",
                dord.date().isoformat() if hasattr(dord, "date") else str(dord)[:10],
            )
        if _txt(fattura.cup):
            _sub(dao, "CodiceCUP", _truncate(fattura.cup, 15))
        if _txt(fattura.cig):
            _sub(dao, "CodiceCIG", _truncate(fattura.cig, 15))

    # Righe + riepilogo
    beni = _sub(body, "DatiBeniServizi")
    riepilogo: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: {"imponibile": Decimal("0.00"), "imposta": Decimal("0.00")}
    )
    totale_doc = Decimal("0.00")
    line_no = 0

    spese_lines = [
        ("Spese imballo", fattura.spese_imballo),
        ("Spese trasporto", fattura.spese_trasporto),
        ("Spese incasso", fattura.spese_incasso),
        ("Spese varie", fattura.spese_varie),
        ("Spese bolli", fattura.spese_bolli),
        ("Spese E15", fattura.spese_e15),
    ]

    def add_line(
        *,
        descrizione: str,
        quantita: Decimal,
        prezzo: Decimal,
        iva_code: str,
        um: str = "NR",
        sconto_perc: Decimal | None = None,
        codice_art: str = "",
    ) -> None:
        nonlocal line_no, totale_doc
        if quantita == 0 and prezzo == 0:
            return
        line_no += 1
        aliq, natura = resolve_iva(iva_code)

        linea = _sub(beni, "DettaglioLinee")
        _sub(linea, "NumeroLinea", str(line_no))
        if _txt(codice_art) and codice_art not in {"-", "."}:
            cod = _sub(linea, "CodiceArticolo")
            _sub(cod, "CodiceTipo", "CODICE")
            _sub(cod, "CodiceValore", _truncate(codice_art, 35))
        _sub(linea, "Descrizione", _truncate(descrizione or "Bene/servizio", 1000))
        _sub(linea, "Quantita", _fmt_qty(quantita if quantita != 0 else Decimal("1")))
        if um:
            _sub(linea, "UnitaMisura", _truncate(um, 10))
        _sub(linea, "PrezzoUnitario", _fmt_money(prezzo))
        prezzo_tot = (quantita * prezzo).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if sconto_perc is not None and sconto_perc > 0:
            sc = _sub(linea, "ScontoMaggiorazione")
            _sub(sc, "Tipo", "SC")
            _sub(sc, "Percentuale", _fmt_aliquota(sconto_perc))
            prezzo_tot = (
                prezzo_tot * (Decimal("100") - sconto_perc) / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        _sub(linea, "PrezzoTotale", _fmt_money(prezzo_tot))
        _sub(linea, "AliquotaIVA", _fmt_aliquota(aliq))
        # In reverse charge con natura N6.x l'imposta non è a carico del cessionario sul XML
        # ma aliquota resta valorizzata; Natura va indicata.
        if natura:
            _sub(linea, "Natura", natura)

        key_nat = natura or ""
        key = (_fmt_aliquota(aliq), key_nat)
        riepilogo[key]["imponibile"] += prezzo_tot
        if not natura or natura.startswith("N6"):
            # Per N6 (RC) l'imposta nel riepilogo è comunque calcolata a 0 per il totale documento
            # secondo prassi: Imposta = 0 con Natura N6.*
            if natura and natura.startswith("N6"):
                riepilogo[key]["imposta"] += Decimal("0.00")
            else:
                imposta = (prezzo_tot * aliq / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                riepilogo[key]["imposta"] += imposta
                totale_doc += prezzo_tot + imposta
                return
        totale_doc += prezzo_tot

    for riga in righe:
        add_line(
            descrizione=_txt(riga.descrizione) or _txt(riga.codice) or "Riga",
            quantita=_qty(riga.quantita if riga.quantita not in (None, 0) else 1),
            prezzo=_money(riga.prezzo_unitario),
            iva_code=_txt(riga.iva) or "22",
            um=_txt(riga.unita_misura) or "NR",
            sconto_perc=_parse_sconto(riga.sconto),
            codice_art=_txt(riga.codice),
        )

    # Spese di testata come righe (stessa IVA prevalente della prima riga, o 22)
    default_iva = _txt(righe[0].iva) if righe else "22"
    for label, importo in spese_lines:
        amount = _money(importo)
        if amount == 0:
            continue
        add_line(
            descrizione=label,
            quantita=Decimal("1"),
            prezzo=amount,
            iva_code=default_iva,
            um="NR",
        )

    if line_no == 0:
        raise FatturaPAError("Nessuna riga valorizzabile per la fattura elettronica.")

    for (aliq_s, natura), totals in sorted(riepilogo.items(), key=lambda x: x[0]):
        dr = _sub(beni, "DatiRiepilogo")
        _sub(dr, "AliquotaIVA", aliq_s)
        if natura:
            _sub(dr, "Natura", natura)
        _sub(dr, "ImponibileImporto", _fmt_money(totals["imponibile"]))
        _sub(dr, "Imposta", _fmt_money(totals["imposta"]))
        if natura:
            _sub(dr, "EsigibilitaIVA", "I")
        else:
            _sub(dr, "EsigibilitaIVA", "I")

    importo_el.text = _fmt_money(totale_doc)

    # Pagamento (opzionale)
    iban = _txt(fattura.iban)
    if iban or _txt(fattura.cod_pagamento):
        pag = _sub(body, "DatiPagamento")
        _sub(pag, "CondizioniPagamento", "TP02")
        dett = _sub(pag, "DettaglioPagamento")
        _sub(dett, "ModalitaPagamento", "MP05" if iban else "MP01")
        _sub(dett, "ImportoPagamento", _fmt_money(totale_doc))
        if iban:
            _sub(dett, "IBAN", re.sub(r"\s+", "", iban).upper())

    indent(root, space="  ")
    xml_bytes = tostring(root, encoding="utf-8", xml_declaration=True)
    # ElementTree usa single quotes a volte; SDI accetta UTF-8 declaration standard
    if not xml_bytes.startswith(b"<?xml"):
        xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
    else:
        # Normalizza declaration
        xml_bytes = re.sub(
            br"<\?xml[^?]*\?>",
            b'<?xml version="1.0" encoding="UTF-8"?>',
            xml_bytes,
            count=1,
        )

    return FatturaPAResult(
        xml_bytes=xml_bytes,
        filename=filename,
        formato=formato,
        warnings=tuple(warnings),
    )
