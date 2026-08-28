"""Invio email di un documento (SMTP da Parametri mail)."""

from __future__ import annotations

from typing import Any

from apps.core.mail import parse_address_list
from apps.documenti.castelletto import format_euro


def _txt(value: Any) -> str:
    return (str(value) if value is not None else "").strip()


def resolve_documento_email(documento) -> str:
    """Email destinatario: anagrafica cliente/fornitore, poi PEC del documento."""
    pec = _txt(getattr(documento, "email_pec", None))
    code = _txt(getattr(documento, "codice_clifor", None))
    tipo = _txt(getattr(documento, "clifor_tipo", None)).upper()
    if not tipo:
        tipo_doc = getattr(documento, "tipo_doc", None)
        tipo = _txt(getattr(tipo_doc, "clifor_tipo", None)).upper() or "C"

    obj = None
    if code:
        try:
            from apps.anagrafiche.models import Cliente, Fornitore, get_by_codice

            model = Fornitore if tipo == "F" else Cliente
            obj = get_by_codice(
                model,
                code,
                only=("codice", "email", "email_commerciale", "pec"),
            )
        except Exception:
            obj = None

    if obj is not None:
        for attr in ("email", "email_commerciale", "pec"):
            val = _txt(getattr(obj, attr, None))
            if "@" in val:
                return val
    if "@" in pec:
        return pec
    return ""


def documento_mail_title(documento) -> str:
    tipo = getattr(documento, "tipo_doc", None)
    codice = _txt(
        getattr(tipo, "codice", None) or getattr(documento, "tipo_doc_id", None)
    ).upper()
    if codice == "PRV" or _txt(getattr(tipo, "categoria", None)) == "PREVENTIVI":
        return "Preventivo"
    return _txt(getattr(tipo, "label", None)) or "Documento"


def _intestatario(documento) -> str:
    nome = _txt(getattr(documento, "cliente_ragione_sociale", None))
    if nome:
        return nome
    dest = _txt(getattr(documento, "destinatario", None))
    if dest:
        return dest
    return _txt(getattr(documento, "codice_clifor", None))


def mail_placeholders(documento) -> dict[str, str]:
    label = documento_mail_title(documento)
    numero = _txt(getattr(documento, "numero_documento", None)) or "—"
    dt = getattr(documento, "data_documento", None)
    data = dt.strftime("%d/%m/%Y") if dt else "—"
    intest = _intestatario(documento) or "—"
    totale = getattr(documento, "totale", None)
    tot_s = f"€ {format_euro(totale)}" if totale is not None else "—"
    return {
        "tipo": label,
        "numero": numero,
        "data": data,
        "cliente": intest,
        "intestatario": intest,
        "destinatario": _txt(getattr(documento, "destinatario", None)) or intest,
        "totale": tot_s,
        "codice": _txt(getattr(documento, "codice_clifor", None)),
    }


def apply_mail_template(template: str, documento) -> str:
    text = template.replace("\r\n", "\n")
    for key, val in mail_placeholders(documento).items():
        text = text.replace("{{" + key + "}}", val)
        text = text.replace("{" + key + "}", val)
    return text


def default_mail_subject(documento) -> str:
    numero = _txt(getattr(documento, "numero_documento", None)) or "—"
    return f"{documento_mail_title(documento)} {numero}"


def default_mail_body(documento) -> str:
    tipo = getattr(documento, "tipo_doc", None)
    template = _txt(getattr(tipo, "testo_mail", None))
    if template:
        return apply_mail_template(template, documento)
    ph = mail_placeholders(documento)
    return (
        f"Buongiorno,\n\n"
        f"in riferimento al documento {ph['tipo']} n. {ph['numero']} del {ph['data']}.\n"
        f"Intestatario: {ph['cliente']}\n"
        f"Totale: {ph['totale']}\n\n"
        f"Cordiali saluti\n"
    )


def parse_destinatari(raw: str | None) -> list[str]:
    return [a for a in parse_address_list(raw) if "@" in a]
