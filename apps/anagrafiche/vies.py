from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
VIES_TIMEOUT = 15

# Paesi UE supportati da VIES (codice VIES, non sempre ISO).
EU_VIES_COUNTRIES = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "EL",
        "ES",
        "FI",
        "FR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
        "XI",
    }
)

# Mapping ISO / Eureka → codice VIES.
COUNTRY_TO_VIES = {
    "GR": "EL",
    "GRC": "EL",
    "EL": "EL",
    "IT": "IT",
    "ITA": "IT",
    "DE": "DE",
    "DEU": "DE",
    "FR": "FR",
    "FRA": "FR",
    "ES": "ES",
    "ESP": "ES",
    "NL": "NL",
    "NLD": "NL",
    "BE": "BE",
    "BEL": "BE",
    "AT": "AT",
    "AUT": "AT",
    "PT": "PT",
    "PRT": "PT",
    "PL": "PL",
    "POL": "PL",
    "RO": "RO",
    "ROU": "RO",
    "HU": "HU",
    "HUN": "HU",
    "CZ": "CZ",
    "CZE": "CZ",
    "SK": "SK",
    "SVK": "SK",
    "SI": "SI",
    "SVN": "SI",
    "HR": "HR",
    "HRV": "HR",
    "BG": "BG",
    "BGR": "BG",
    "DK": "DK",
    "DNK": "DK",
    "SE": "SE",
    "SWE": "SE",
    "FI": "FI",
    "FIN": "FI",
    "IE": "IE",
    "IRL": "IE",
    "LT": "LT",
    "LTU": "LT",
    "LV": "LV",
    "LVA": "LV",
    "EE": "EE",
    "EST": "EE",
    "CY": "CY",
    "CYP": "CY",
    "LU": "LU",
    "LUX": "LU",
    "MT": "MT",
    "MLT": "MT",
    "XI": "XI",
}

VIES_ERROR_MESSAGES = {
    "INVALID_INPUT": "Partita IVA o paese non validi.",
    "MS_UNAVAILABLE": "Servizio VIES del paese temporaneamente non disponibile.",
    "MS_MAX_CONCURRENT_REQ": "Troppe richieste al servizio del paese. Riprova tra poco.",
    "GLOBAL_MAX_CONCURRENT_REQ": "Servizio VIES sovraccarico. Riprova tra poco.",
    "TIMEOUT": "Timeout nella risposta del servizio VIES.",
    "SERVICE_UNAVAILABLE": "Servizio VIES non raggiungibile.",
    "VAT_BLOCKED": "Partita IVA bloccata per le verifiche VIES.",
    "IP_BLOCKED": "Accesso al servizio VIES bloccato.",
}


@dataclass
class ViesCheckInput:
    country_code: str
    vat_number: str
    display_country: str
    display_vat: str


@dataclass
class ViesResult:
    ok: bool
    valid: bool | None = None
    country_code: str = ""
    vat_number: str = ""
    name: str = ""
    address: str = ""
    request_date: str = ""
    message: str = ""
    eligible: bool = True

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "valid": self.valid,
            "country_code": self.country_code,
            "vat_number": self.vat_number,
            "name": self.name,
            "address": self.address,
            "request_date": self.request_date,
            "message": self.message,
            "eligible": self.eligible,
        }


def _clean_vat(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (value or "").upper())


def normalize_country_code(value: str | None, default: str = "IT") -> str:
    raw = (value or "").strip().upper()
    if not raw:
        raw = default
    if raw in COUNTRY_TO_VIES:
        return COUNTRY_TO_VIES[raw]
    if len(raw) >= 2:
        two = raw[:2]
        if two in COUNTRY_TO_VIES:
            return COUNTRY_TO_VIES[two]
    return raw[:2]


def parse_vat_input(
    partita_iva: str | None,
    cod_nazione: str | None,
    *,
    default_country: str = "IT",
) -> ViesCheckInput | None:
    vat_raw = _clean_vat(partita_iva)
    if not vat_raw:
        return None

    country = normalize_country_code(cod_nazione, default_country)
    vat_number = vat_raw

    if re.match(r"^[A-Z]{2}", vat_number):
        prefix = vat_number[:2]
        rest = vat_number[2:]
        if prefix in EU_VIES_COUNTRIES or prefix in COUNTRY_TO_VIES:
            country = normalize_country_code(prefix, default_country)
            vat_number = rest

    vat_number = re.sub(r"[^0-9A-Z]", "", vat_number)
    if not vat_number:
        return None

    if country not in EU_VIES_COUNTRIES:
        return None

    return ViesCheckInput(
        country_code=country,
        vat_number=vat_number,
        display_country=country,
        display_vat=vat_number,
    )


def vies_eligible(partita_iva: str | None, cod_nazione: str | None) -> bool:
    return parse_vat_input(partita_iva, cod_nazione) is not None


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _find_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if _local_name(child.tag) == name:
            return child
    return None


def _find_text(parent: ET.Element, name: str) -> str:
    node = _find_child(parent, name)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _parse_vies_response(xml_text: str, country_code: str, vat_number: str) -> ViesResult:
    root = ET.fromstring(xml_text)
    body = None
    for node in root.iter():
        if _local_name(node.tag) == "Body":
            body = node
            break
    if body is None:
        return ViesResult(ok=False, message="Risposta VIES non valida.")

    fault = _find_child(body, "Fault")
    if fault is not None:
        fault_string = _find_text(fault, "faultstring") or "Errore VIES."
        code = ""
        for node in fault.iter():
            if _local_name(node.tag) == "faultstring" and node.text:
                fault_string = node.text.strip()
            if _local_name(node.tag) == "value" and node.text:
                code = node.text.strip().upper()
        message = VIES_ERROR_MESSAGES.get(code, fault_string)
        return ViesResult(ok=False, message=message, country_code=country_code, vat_number=vat_number)

    response = None
    for node in body:
        if _local_name(node.tag) == "checkVatResponse":
            response = node
            break
    if response is None:
        return ViesResult(ok=False, message="Risposta VIES incompleta.")

    valid_text = _find_text(response, "valid").lower()
    valid = valid_text == "true"
    return ViesResult(
        ok=True,
        valid=valid,
        country_code=_find_text(response, "countryCode") or country_code,
        vat_number=_find_text(response, "vatNumber") or vat_number,
        name=_find_text(response, "name"),
        address=_find_text(response, "address"),
        request_date=_find_text(response, "requestDate"),
        message="Partita IVA valida su VIES." if valid else "Partita IVA non valida su VIES.",
    )


def check_vat(country_code: str, vat_number: str) -> ViesResult:
    country_code = normalize_country_code(country_code)
    vat_number = re.sub(r"[^0-9A-Z]", "", (vat_number or "").upper())

    if country_code not in EU_VIES_COUNTRIES:
        return ViesResult(
            ok=False,
            eligible=False,
            message="Il paese non rientra nel sistema VIES UE.",
            country_code=country_code,
            vat_number=vat_number,
        )

    if not vat_number:
        return ViesResult(
            ok=False,
            eligible=False,
            message="Partita IVA mancante.",
            country_code=country_code,
        )

    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
  <soapenv:Header/>
  <soapenv:Body>
    <urn:checkVat>
      <urn:countryCode>{country_code}</urn:countryCode>
      <urn:vatNumber>{vat_number}</urn:vatNumber>
    </urn:checkVat>
  </soapenv:Body>
</soapenv:Envelope>"""

    request = Request(
        VIES_URL,
        data=envelope.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "Accept": "text/xml",
            "SOAPAction": "",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=VIES_TIMEOUT) as response:
            xml_text = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return ViesResult(
            ok=False,
            message=f"Errore HTTP VIES ({exc.code}).",
            country_code=country_code,
            vat_number=vat_number,
        )
    except URLError:
        return ViesResult(
            ok=False,
            message=VIES_ERROR_MESSAGES["SERVICE_UNAVAILABLE"],
            country_code=country_code,
            vat_number=vat_number,
        )
    except TimeoutError:
        return ViesResult(
            ok=False,
            message=VIES_ERROR_MESSAGES["TIMEOUT"],
            country_code=country_code,
            vat_number=vat_number,
        )

    return _parse_vies_response(xml_text, country_code, vat_number)


def check_anagrafica_vat(partita_iva: str | None, cod_nazione: str | None) -> ViesResult:
    parsed = parse_vat_input(partita_iva, cod_nazione)
    if parsed is None:
        if not _clean_vat(partita_iva):
            return ViesResult(ok=False, eligible=False, message="Partita IVA mancante.")
        return ViesResult(
            ok=False,
            eligible=False,
            message="Verifica VIES non disponibile per questo paese o formato P. IVA.",
        )
    return check_vat(parsed.country_code, parsed.vat_number)
