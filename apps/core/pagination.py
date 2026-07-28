DEFAULT_PER_PAGE = 50
PER_PAGE_OPTIONS = (25, 50, 100)
MAX_PER_PAGE = 100


def filter_query_from_request(request, exclude=("page",)):
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


def resolve_per_page(request, default=DEFAULT_PER_PAGE, options=PER_PAGE_OPTIONS, max_per_page=MAX_PER_PAGE):
    raw = request.GET.get("per_page")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value not in options:
        return default
    return min(value, max_per_page)


class PerPageListMixin:
    paginate_by = DEFAULT_PER_PAGE
    per_page_options = PER_PAGE_OPTIONS
    max_per_page = MAX_PER_PAGE

    def get_paginate_by(self, queryset):
        return resolve_per_page(
            self.request,
            default=self.paginate_by,
            options=self.per_page_options,
            max_per_page=self.max_per_page,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["per_page"] = self.get_paginate_by(None)
        context["per_page_options"] = self.per_page_options
        return context


class SafeMirrorListMixin:
    """
    ListView su tabelle mirror 4D.
    Se la tabella non esiste (es. dopo azzeramento), mostra elenco vuoto.
    Le subclass devono implementare get_mirror_queryset() invece di get_queryset().
    """

    def get_mirror_queryset(self):
        return super().get_queryset()

    def get_queryset(self):
        from django.db.utils import OperationalError, ProgrammingError

        try:
            qs = self.get_mirror_queryset()
            qs.exists()
            return qs
        except (ProgrammingError, OperationalError):
            return self.model.objects.none()
