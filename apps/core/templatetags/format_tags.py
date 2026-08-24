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


@register.filter(name="intit")
def intit(value):
    """Intero con separatore migliaia italiano: 12.345"""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "—"
    return f"{number:,}".replace(",", ".")
