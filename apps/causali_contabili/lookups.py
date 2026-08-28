"""Collegamenti Causali Contabili → registri IVA e PDC."""

from __future__ import annotations

from django.db import transaction
from django.db.models import TextField
from django.db.models.functions import Trim, Upper
from django.db.utils import OperationalError, ProgrammingError
from django.urls import reverse

from apps.registri_iva.lookups import (
    attach_registri_iva,
    registro_iva_choices,
    resolve_registro_iva,
)

__all__ = (
    "attach_pdc_causale",
    "attach_registri_iva_causali",
    "build_conti_righe",
    "conto_url_label",
    "has_autofattura_fields",
    "linked_labels_for_causale",
    "registro_iva_choices",
    "resolve_registro_iva",
    "tipo_doc_fel_choices",
    "tipo_doc_fel_display",
    "tipo_doc_fel_matching_codes",
    "norm_tipo_doc_fel",
    "TIPO_DOC_FEL",
    "DETAIL_DB_EXCLUDE",
    "LINKED_FIELD_TIPI",
)

LINKED_FIELD_TIPI = {
    **{f"c_dare_{i}": "pdc_clifor" for i in range(1, 11)},
    **{f"c_avere_{i}": "pdc_clifor" for i in range(1, 11)},
    "cassa_corrispettivi": "pdc",
    "causale_colleg_auto_f": "causale_contabile",
    "cliente_auto_f": "cliente",
    "sotto_conto_iva_acq_auto_f": "pdc",
    "sotto_conto_iva_vend_auto_f": "pdc",
}

DETAIL_DB_EXCLUDE = frozenset(
    {
        "Codice",
        "Descrizione",
        "Desc_Pn",
        "PartiteAperte",
        "TipoCausale",
        "IncrementaDoc",
        "RegistroIva",
        "Desc_RegIva",
        "CassaCorrispettivi",
        "TipoDocFEL",
        "Testo_AutoFattura",
        "CausaleCollegAutoF",
        "ClienteAutoF",
        "SottoContoIvaAcqAutoF",
        "SottoContoIvaVendAutoF",
        "ContatoreAutoF",
        "Causale17_6",
        "Tipo_SA",
        "Flag_Red_Partitari",
        "Esterometro",
        "Autofattura",
        "IvaConAutofattura",
        "flag_CondPag",
        "ContAnalitica_NOControl",
        "XML_Default",
        "synced_at",
        *(f"CDare{i}" for i in range(1, 11)),
        *(f"CAvere{i}" for i in range(1, 11)),
    }
)

AUTOFATTURA_EXTRA_ATTRS = (
    "testo_auto_fattura",
    "causale_colleg_auto_f",
    "cliente_auto_f",
    "sotto_conto_iva_acq_auto_f",
    "sotto_conto_iva_vend_auto_f",
    "contatore_auto_f",
)

# Catalogo FatturaPA / 4D TipoDocFEL (TD13–TD15 non previsti).
TIPO_DOC_FEL = (
    ("TD01", "Fattura"),
    ("TD02", "Acconto/Anticipo su fattura"),
    ("TD03", "Acconto/Anticipo su parcella"),
    ("TD04", "Nota di Credito"),
    ("TD05", "Nota di Debito"),
    ("TD06", "Parcella"),
    ("TD07", "Fattura Semplificata"),
    ("TD08", "Nota di Credito Semplificata"),
    ("TD09", "Nota di Debito Semplificata"),
    ("TD10", "Fattura di acq. intracomunitario beni"),
    ("TD11", "Fattura di acq. intracomunitario servizi"),
    ("TD12", "Documento riepilogativo (art. 6 DPR 695/1996)"),
    ("TD16", "Integrazione fattura reverse charge interno"),
    ("TD17", "Integrazione/autofattura per acquisti servizi dall'estero"),
    ("TD18", "Integrazione per acquisto di beni intracomunitari"),
    ("TD19", "Integrazione per acquisto di beni ex. art. 17 c.2 DPR 633/72"),
    (
        "TD20",
        "Autofattura per regolarizzazione e integrazione delle fatture "
        "non coperte da TD28 e TD29",
    ),
    ("TD21", "Autofattura per splafonamento"),
    ("TD22", "Estrazione beni da Deposito IVA"),
    ("TD23", "Estrazione beni da Deposito IVA con versamento dell'IVA"),
    ("TD24", "Fattura differita di cui art. 21, comma 4 lett. a)"),
    ("TD25", "Fattura differita di cui art. 21, comma 4 terzo periodo lett. b)"),
    (
        "TD26",
        "Cessione di beni ammortizzabili e per passaggi interni "
        "(ex art. 36 DPR 633/72)",
    ),
    ("TD27", "Fattura per autoconsumo o per cessioni gratuite senza rivalsa"),
    (
        "TD28",
        "Autofattura per regolarizzare acquisti di servizi intracomunitari "
        "omessi o irregolari",
    ),
    (
        "TD29",
        "Autofattura per regolarizzare acquisti di beni intracomunitari "
        "con fattura non emessa o irregolare",
    ),
)
TIPO_DOC_FEL_CODES = {code for code, _label in TIPO_DOC_FEL}


def _norm_code(codice: str | None) -> str:
    return (codice or "").strip().upper()


def norm_tipo_doc_fel(value: str | None) -> str:
    """Estrae il codice TDxx da un valore salvato (codice o etichetta 4D)."""
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        return ""
    token = text.replace("—", "-").split("-", 1)[0].strip().upper()
    return token


def tipo_doc_fel_display(value: str | None) -> str:
    code = norm_tipo_doc_fel(value)
    mapping = dict(TIPO_DOC_FEL)
    if code in mapping:
        return f"{code} - {mapping[code]}"
    return value.strip() if isinstance(value, str) else ""


def tipo_doc_fel_caption(value: str | None) -> str:
    code = norm_tipo_doc_fel(value)
    return dict(TIPO_DOC_FEL).get(code, "")


def tipo_doc_fel_matching_codes(q: str | None) -> list[str]:
    """Codici TDxx il cui codice o descrizione contiene il testo cercato."""
    needle = q.strip().lower() if isinstance(q, str) else ""
    if not needle:
        return []
    return [
        code
        for code, label in TIPO_DOC_FEL
        if needle in code.lower() or needle in label.lower()
    ]


def tipo_doc_fel_choices(current: str | None = None) -> list[tuple[str, str]]:
    """Opzioni select FatturaPA, con eventuale valore corrente assente dal catalogo."""
    choices: list[tuple[str, str]] = [("", "—")]
    seen = {""}
    for code, label in TIPO_DOC_FEL:
        choices.append((code, f"{code} - {label}"))
        seen.add(code)
    current_raw = current.strip() if isinstance(current, str) else ""
    current_code = norm_tipo_doc_fel(current_raw)
    if current_code in seen:
        return choices
    if current_raw and current_raw not in seen:
        choices.append((current_raw, current_raw))
    return choices


def _pdc_by_codes(codici) -> dict:
    from apps.pdc.models import PianoConti

    keys = sorted({_norm_code(c) for c in codici if _norm_code(c)})
    if not keys:
        return {}
    try:
        with transaction.atomic():
            qs = PianoConti.objects.annotate(
                _n=Upper(Trim("codice"), output_field=TextField())
            ).filter(_n__in=keys)
            return {_norm_code(p.codice): p for p in qs}
    except (ProgrammingError, OperationalError):
        return {}


def attach_registri_iva_causali(causali) -> None:
    attach_registri_iva(
        causali,
        code_attr="registro_iva",
        target_attr="registro_collegato",
    )


def _as_code(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _form_field_code(form, name: str) -> str:
    if getattr(form, "is_bound", False):
        return _as_code(form.data.get(name))
    instance = getattr(form, "instance", None)
    if instance is not None:
        code = _as_code(getattr(instance, name, None))
        if code:
            return code
    initial = getattr(form, "initial", None) or {}
    return _as_code(initial.get(name))


def linked_labels_for_causale(form) -> dict[str, str]:
    from apps.articoli.lookups import resolve_descrizione

    return {
        name: resolve_descrizione(tipo, _form_field_code(form, name))
        for name, tipo in LINKED_FIELD_TIPI.items()
    }


def conto_url_label(codice, pdc_obj=None) -> tuple[str, str]:
    """URL e descrizione per un conto causale (PDC o cliente/fornitore)."""
    code = _as_code(codice)
    if pdc_obj is not None:
        pk = _as_code(getattr(pdc_obj, "codice", None)) or code
        label = _as_code(getattr(pdc_obj, "label", None))
        try:
            return reverse("pdc:detail", kwargs={"codice": pk}), label
        except Exception:
            return "", label
    if not code:
        return "", ""
    from apps.articoli.lookups import resolve_clifor

    info = resolve_clifor("clifor", code)
    if not info.get("found"):
        return "", ""
    kind = info.get("kind") or "cliente"
    url_name = (
        "anagrafiche:fornitore_detail"
        if kind == "fornitore"
        else "anagrafiche:cliente_detail"
    )
    pk = _as_code(info.get("codice")) or code
    try:
        url = reverse(url_name, kwargs={"codice": pk})
    except Exception:
        url = ""
    return url, _as_code(info.get("descrizione"))


def attach_pdc_causale(causale) -> None:
    codes = []
    for i in range(1, 11):
        codes.append(getattr(causale, f"c_dare_{i}", None))
        codes.append(getattr(causale, f"c_avere_{i}", None))
    mapping = _pdc_by_codes(codes)
    for i in range(1, 11):
        dare = _norm_code(getattr(causale, f"c_dare_{i}", None))
        avere = _norm_code(getattr(causale, f"c_avere_{i}", None))
        setattr(causale, f"pdc_dare_{i}", mapping.get(dare))
        setattr(causale, f"pdc_avere_{i}", mapping.get(avere))


def build_conti_righe(causale) -> list[dict]:
    righe = []
    for i in range(1, 11):
        dare = _as_code(getattr(causale, f"c_dare_{i}", None))
        avere = _as_code(getattr(causale, f"c_avere_{i}", None))
        if not dare and not avere:
            continue
        dare_url, dare_label = conto_url_label(
            dare, getattr(causale, f"pdc_dare_{i}", None)
        )
        avere_url, avere_label = conto_url_label(
            avere, getattr(causale, f"pdc_avere_{i}", None)
        )
        righe.append(
            {
                "n": i,
                "dare": dare,
                "avere": avere,
                "pdc_dare_url": dare_url,
                "pdc_dare_label": dare_label,
                "pdc_avere_url": avere_url,
                "pdc_avere_label": avere_label,
            }
        )
    return righe


def has_autofattura_fields(causale) -> bool:
    for name in AUTOFATTURA_EXTRA_ATTRS:
        value = getattr(causale, name, None)
        if value is True:
            return True
        if value not in (None, "", False):
            return True
    return False
