from __future__ import annotations

import re
from dataclasses import dataclass

_ODD_VALUES = {
    "0": 1,
    "1": 0,
    "2": 5,
    "3": 7,
    "4": 9,
    "5": 13,
    "6": 15,
    "7": 17,
    "8": 19,
    "9": 21,
    "A": 1,
    "B": 0,
    "C": 5,
    "D": 7,
    "E": 9,
    "F": 13,
    "G": 15,
    "H": 17,
    "I": 19,
    "J": 21,
    "K": 2,
    "L": 4,
    "M": 18,
    "N": 20,
    "O": 11,
    "P": 3,
    "Q": 6,
    "R": 8,
    "S": 12,
    "T": 14,
    "U": 16,
    "V": 10,
    "W": 22,
    "X": 25,
    "Y": 24,
    "Z": 23,
}
_CHECK_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ITALIAN_COUNTRY_CODES = frozenset({"IT", "ITA", "I", "ITALIA"})


@dataclass
class CfResult:
    ok: bool
    valid: bool | None = None
    normalized: str = ""
    kind: str = ""
    message: str = ""
    eligible: bool = True

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "valid": self.valid,
            "normalized": self.normalized,
            "kind": self.kind,
            "message": self.message,
            "eligible": self.eligible,
        }


def normalize_cf(value: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (value or "").upper())


def normalize_country(value: str | None) -> str:
    return (value or "").strip().upper()


def is_italian_fiscal_subject(cod_nazione: str | None) -> bool:
    country = normalize_country(cod_nazione)
    return not country or country in _ITALIAN_COUNTRY_CODES


def cf_eligible(cod_fiscale: str | None, cod_nazione: str | None) -> bool:
    if not normalize_cf(cod_fiscale):
        return False
    return is_italian_fiscal_subject(cod_nazione)


def _even_value(char: str) -> int:
    if char.isdigit():
        return int(char)
    return ord(char) - ord("A")


def _validate_cf_persona(value: str) -> bool:
    if len(value) != 16 or not re.fullmatch(r"[A-Z0-9]{16}", value):
        return False
    total = 0
    for index, char in enumerate(value[:15]):
        if index % 2 == 0:
            total += _ODD_VALUES.get(char, -1)
        else:
            total += _even_value(char)
        if total < 0:
            return False
    return _CHECK_CHARS[total % 26] == value[15]


def _validate_cf_numerico(value: str) -> bool:
    """Cifra di controllo P.IVA / CF persona giuridica (Agenzia delle Entrate).

    Sulle prime 10 cifre, da sinistra (posizione 1):
    dispari = valore della cifra; pari = cifra × 2 (se > 9, sottrai 9).
    Cifra di controllo = complemento a 10 della somma modulo 10.
    """
    if len(value) != 11 or not value.isdigit():
        return False
    total = 0
    for index in range(10):
        digit = int(value[index])
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    check = (10 - (total % 10)) % 10
    return check == int(value[10])


def validate_codice_fiscale(
    cod_fiscale: str | None,
    *,
    cod_nazione: str | None = None,
    partita_iva: str | None = None,
    persona_fisica: bool | None = None,
) -> CfResult:
    normalized = normalize_cf(cod_fiscale)
    if not normalized:
        return CfResult(ok=True, valid=None, normalized="", kind="empty", message="Codice fiscale non inserito.")

    if not is_italian_fiscal_subject(cod_nazione):
        return CfResult(
            ok=True,
            valid=None,
            normalized=normalized,
            kind="foreign",
            eligible=False,
            message="Controllo formale italiano non applicato per anagrafiche estere.",
        )

    piva = re.sub(r"\D+", "", (partita_iva or ""))
    if len(normalized) == 16:
        valid = _validate_cf_persona(normalized)
        message = (
            "Codice fiscale valido (persona fisica)."
            if valid
            else "Codice fiscale non valido: carattere di controllo errato."
        )
        if valid and persona_fisica is False:
            message = "Codice fiscale valido (formato persona fisica)."
        return CfResult(
            ok=True,
            valid=valid,
            normalized=normalized,
            kind="persona",
            message=message,
        )

    if len(normalized) == 11 and normalized.isdigit():
        valid = _validate_cf_numerico(normalized)
        message = (
            "Codice fiscale valido (persona giuridica / numerico)."
            if valid
            else "Codice fiscale numerico non valido: cifra di controllo errata."
        )
        if valid and piva and piva != normalized:
            message = "Codice fiscale valido, ma diverso dalla partita IVA indicata."
        if persona_fisica:
            message = (
                "Codice fiscale numerico valido, tipico di persona giuridica."
                if valid
                else message
            )
        return CfResult(
            ok=True,
            valid=valid,
            normalized=normalized,
            kind="partita_iva",
            message=message,
        )

    if persona_fisica:
        expected = "16 caratteri alfanumerici"
    else:
        expected = "16 caratteri (persona fisica) o 11 cifre (persona giuridica)"
    return CfResult(
        ok=True,
        valid=False,
        normalized=normalized,
        kind="invalid",
        message=f"Formato codice fiscale non valido: attesi {expected}.",
    )


def check_anagrafica_cf(
    cod_fiscale: str | None,
    cod_nazione: str | None,
    *,
    partita_iva: str | None = None,
    persona_fisica: bool | None = None,
) -> CfResult:
    return validate_codice_fiscale(
        cod_fiscale,
        cod_nazione=cod_nazione,
        partita_iva=partita_iva,
        persona_fisica=persona_fisica,
    )
