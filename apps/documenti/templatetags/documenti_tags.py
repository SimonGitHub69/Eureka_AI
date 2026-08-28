from django import template

from apps.documenti.layout import CAMPI_RIGA
from apps.documenti.numerazione import format_numero_documento as _format_numero_documento

register = template.Library()


@register.simple_tag
def format_numero_documento(numero, serie=""):
    return _format_numero_documento(numero, serie)


@register.filter
def form_field(form, name):
    try:
        return form[name]
    except Exception:
        return ""


@register.filter
def riga_attr(riga, campo):
    return getattr(riga, campo, None)


@register.filter
def is_money_campo(campo):
    return campo == "prezzo_unitario"


@register.filter
def is_qty_campo(campo):
    return campo in {"quantita", "numero_riga"}


@register.filter
def campo_in_catalogo(campo):
    return campo in CAMPI_RIGA
