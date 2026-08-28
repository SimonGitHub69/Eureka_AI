from urllib.parse import urlencode

from django import template

register = template.Library()


@register.filter
def append_list_next(url, request):
    """Aggiunge ``next=<elenco corrente>`` al link verso un dettaglio."""
    if not url or not request:
        return url
    param = urlencode({"next": request.get_full_path()})
    if "?" in url:
        return f"{url}&{param}"
    return f"{url}?{param}"
