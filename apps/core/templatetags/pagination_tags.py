from django import template

register = template.Library()


def _pagination_window(page_obj, window=2):
    num_pages = page_obj.paginator.num_pages
    current = page_obj.number
    if num_pages <= 1:
        return []

    pages = {1, num_pages}
    for number in range(max(1, current - window), min(num_pages, current + window) + 1):
        pages.add(number)

    sorted_pages = sorted(pages)
    result = []
    previous = None
    for page_number in sorted_pages:
        if previous is not None and page_number - previous > 1:
            result.append("ellipsis")
        result.append(page_number)
        previous = page_number
    return result


@register.simple_tag
def pagination_window(page_obj, window=2):
    return _pagination_window(page_obj, window=window)


@register.simple_tag(takes_context=True)
def pagination_url(context, page=None, per_page=None):
    request = context["request"]
    params = request.GET.copy()

    if per_page is not None:
        params["per_page"] = str(per_page)
        params.pop("page", None)
    elif page is not None:
        if page <= 1:
            params.pop("page", None)
        else:
            params["page"] = str(page)

    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.simple_tag(takes_context=True)
def sort_url(context, field, default_dir="desc"):
    """URL per ordinare una colonna: click sullo stesso campo inverte la direzione."""
    request = context["request"]
    params = request.GET.copy()
    current = (context.get("sort") or params.get("sort") or "").strip()
    current_dir = (context.get("dir") or params.get("dir") or default_dir).strip().lower()
    if current_dir not in {"asc", "desc"}:
        current_dir = default_dir

    if current == field:
        new_dir = "asc" if current_dir == "desc" else "desc"
    else:
        new_dir = default_dir

    params["sort"] = field
    params["dir"] = new_dir
    params.pop("page", None)
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.inclusion_tag("partials/sort_th.html", takes_context=True)
def sort_th(context, field, label, align="", default_dir="desc"):
    request = context.get("request")
    current = (context.get("sort") or (request.GET.get("sort") if request else "") or "").strip()
    current_dir = (context.get("dir") or (request.GET.get("dir") if request else "") or "").strip().lower()
    active = current == field
    return {
        "field": field,
        "label": label,
        "align": align,
        "default_dir": default_dir,
        "active": active,
        "dir": current_dir if active else "",
        "request": request,
    }