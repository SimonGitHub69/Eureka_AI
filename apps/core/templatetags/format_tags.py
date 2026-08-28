from django import template

register = template.Library()


@register.filter(name="euro")
def euro(value, decimals=2):
    """Formatta un importo in stile italiano: 1.234.567,89"""
    try:
        decimals = int(decimals)
    except (TypeError, ValueError):
        decimals = 2
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    formatted = f"{number:,.{decimals}f}"
    # 1,234,567.89 -> 1.234.567,89
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter(name="prezzo")
def prezzo(value):
    """Prezzo unitario in stile italiano, decimali da Parametri programma."""
    from apps.core.prezzi import get_prezzo_decimali

    return euro(value, get_prezzo_decimali())


@register.filter(name="qtyit")
def qtyit(value, max_decimals=3):
    """Quantità stile stampa 4D: 2.535 oppure 1,5 (senza zeri inutili)."""
    try:
        max_decimals = int(max_decimals)
    except (TypeError, ValueError):
        max_decimals = 3
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}".replace(",", ".")
    formatted = f"{number:,.{max_decimals}f}".rstrip("0").rstrip(".")
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter(name="intit")
def intit(value):
    """Intero con separatore migliaia italiano: 12.345"""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "—"
    return f"{number:,}".replace(",", ".")


@register.filter(name="mp_sdi")
def mp_sdi(value):
    """Traduce un codice ModalitaPagamento SDI: MP05 → MP05 - Bonifico."""
    from apps.condizioni.models import label_modalita_pagamento_sdi

    label = label_modalita_pagamento_sdi(value)
    return label or "—"


_MP_SDI_ICONS = {
    "MP01": "ti-cash",
    "MP02": "ti-file-check",
    "MP03": "ti-file-check",
    "MP04": "ti-building-bank",
    "MP05": "ti-building-bank",
    "MP06": "ti-mail",
    "MP07": "ti-receipt",
    "MP08": "ti-credit-card",
    "MP09": "ti-repeat",
    "MP10": "ti-repeat",
    "MP11": "ti-bolt",
    "MP12": "ti-file-invoice",
    "MP13": "ti-bell",
    "MP14": "ti-receipt",
    "MP15": "ti-arrows-exchange",
    "MP16": "ti-home",
    "MP17": "ti-mail",
    "MP18": "ti-receipt",
    "MP19": "ti-repeat",
    "MP20": "ti-repeat",
    "MP21": "ti-building",
    "MP22": "ti-scissors",
    "MP23": "ti-qrcode",
}

_MP_SDI_COLORS = {
    "MP01": "bg-green-lt text-green",
    "MP02": "bg-azure-lt text-azure",
    "MP03": "bg-azure-lt text-azure",
    "MP04": "bg-teal-lt text-teal",
    "MP05": "bg-blue-lt text-blue",
    "MP06": "bg-indigo-lt text-indigo",
    "MP07": "bg-cyan-lt text-cyan",
    "MP08": "bg-purple-lt text-purple",
    "MP09": "bg-orange-lt text-orange",
    "MP10": "bg-orange-lt text-orange",
    "MP11": "bg-yellow-lt text-yellow",
    "MP12": "bg-blue-lt text-blue",
    "MP13": "bg-pink-lt text-pink",
    "MP14": "bg-red-lt text-red",
    "MP15": "bg-teal-lt text-teal",
    "MP16": "bg-green-lt text-green",
    "MP17": "bg-indigo-lt text-indigo",
    "MP18": "bg-cyan-lt text-cyan",
    "MP19": "bg-orange-lt text-orange",
    "MP20": "bg-orange-lt text-orange",
    "MP21": "bg-azure-lt text-azure",
    "MP22": "bg-secondary-lt text-secondary",
    "MP23": "bg-lime-lt text-lime",
}


@register.filter(name="mp_sdi_icon")
def mp_sdi_icon(value):
    """Icona Tabler per codice ModalitaPagamento SDI."""
    raw = (value or "").strip().upper()
    return _MP_SDI_ICONS.get(raw, "ti-cash")


@register.filter(name="mp_sdi_color")
def mp_sdi_color(value):
    """Classi colore avatar per codice ModalitaPagamento SDI."""
    raw = (value or "").strip().upper()
    return _MP_SDI_COLORS.get(raw, "bg-secondary-lt text-secondary")


@register.filter(name="currency_symbol")
def currency_symbol_filter(value):
    """Simbolo valuta per elenco/maschere (USD → $, EUR → €)."""
    from apps.valute.lookups import currency_symbol

    if value is None:
        return "¤"
    return currency_symbol(value)


@register.filter(name="packed_rgb_hex")
def packed_rgb_hex(value):
    """Intero COLORREF 4D/Windows → #rrggbb per swatch CSS."""
    from apps.core.mirror_crud import packed_rgb_to_hex

    if value in (None, ""):
        return ""
    return packed_rgb_to_hex(value)


@register.filter(name="si_no")
def si_no(value):
    """True/False (o stringhe) → Si/No."""
    from apps.core.mirror_crud import format_mirror_display_value

    formatted = format_mirror_display_value(value)
    if formatted in ("Si", "No"):
        return formatted
    if value in (None, ""):
        return "—"
    return formatted


@register.filter(name="display_value")
def display_value(value):
    """Formattazione valore per maschere dettaglio (boolean → Si/No)."""
    from apps.core.mirror_crud import format_mirror_display_value

    return format_mirror_display_value(value)

    """Flag FontStyle 4D (es. 1000) → etichetta leggibile."""
    from apps.gruppi_articoli.forms import label_font_style

    return label_font_style(value)