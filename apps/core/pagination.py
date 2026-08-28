import uuid
from datetime import timedelta

from django.utils import timezone

DEFAULT_PER_PAGE = 50
PER_PAGE_OPTIONS = (25, 50, 100, 250)
MAX_PER_PAGE = 250
AI_FILTER_SESSION_KEY = "ai_filter_sets"
AI_FILTER_TTL = timedelta(minutes=15)


LIST_COUNT_EXCLUDE_GET = frozenset(
    {
        "page",
        "per_page",
        "sort",
        "dir",
        "next",
    }
)


def list_filters_active(request, *, extra_exclude=()) -> bool:
    """True se la GET contiene filtri/ricerca oltre a paginazione e ordinamento."""
    if not request:
        return False
    if request.GET.get("ai") == "1":
        return True
    exclude = LIST_COUNT_EXCLUDE_GET | frozenset(extra_exclude)
    for key, value in request.GET.items():
        if key in exclude:
            continue
        if str(value or "").strip():
            return True
    return False


def resolve_list_filter_count(context, view) -> int | None:
    """Conteggio righe del queryset filtrato (paginator o lista corrente)."""
    page_obj = context.get("page_obj")
    if page_obj is not None and getattr(page_obj, "paginator", None) is not None:
        return page_obj.paginator.count
    name = getattr(view, "context_object_name", "object_list")
    items = context.get(name)
    if items is None:
        items = context.get("object_list")
    if items is not None:
        try:
            return len(items)
        except TypeError:
            pass
    return None


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


def safe_mirror_count(queryset_or_model, default=0):
    """
    COUNT su tabella mirror 4D.
    Se la relazione non esiste (es. dopo "Azzera tabelle"), restituisce default
    senza lasciare la connessione PostgreSQL in stato aborted.
    """
    from django.db import transaction
    from django.db.utils import OperationalError, ProgrammingError

    try:
        with transaction.atomic():
            if hasattr(queryset_or_model, "objects"):
                return queryset_or_model.objects.count()
            return queryset_or_model.count()
    except (ProgrammingError, OperationalError):
        return default


def _cleanup_ai_filters(storage):
    if not isinstance(storage, dict):
        return {}
    now = timezone.now()
    cleaned = {}
    changed = False
    for token, payload in storage.items():
        if not isinstance(payload, dict):
            changed = True
            continue
        expires_at = payload.get("expires_at")
        try:
            expires_dt = timezone.datetime.fromisoformat(expires_at) if expires_at else None
        except (TypeError, ValueError):
            expires_dt = None
        if expires_dt is None:
            changed = True
            continue
        if timezone.is_naive(expires_dt):
            expires_dt = timezone.make_aware(expires_dt, timezone.get_current_timezone())
        if expires_dt < now:
            changed = True
            continue
        cleaned[token] = payload
    return cleaned if changed or len(cleaned) != len(storage) else storage


def _session_ai_filters(request):
    storage = request.session.get(AI_FILTER_SESSION_KEY, {})
    cleaned = _cleanup_ai_filters(storage)
    if cleaned != storage:
        request.session[AI_FILTER_SESSION_KEY] = cleaned
    return cleaned


def store_ai_filter(request, *, table, pks):
    token = uuid.uuid4().hex
    now = timezone.now()
    storage = dict(_session_ai_filters(request))
    cleaned_pks = [str(pk).strip() for pk in pks if str(pk).strip()]
    storage[token] = {
        "table": (table or "").strip(),
        "pks": cleaned_pks,
        "count": len(cleaned_pks),
        "created_at": now.isoformat(),
        "expires_at": (now + AI_FILTER_TTL).isoformat(),
    }
    request.session[AI_FILTER_SESSION_KEY] = storage
    return token


def resolve_ai_filter(request, *, token, expected_table=None):
    if not token:
        return None
    storage = dict(_session_ai_filters(request))
    payload = storage.get(token)
    if not payload:
        return None
    table = (payload.get("table") or "").strip()
    if expected_table and table != expected_table:
        return None
    now = timezone.now()
    payload["expires_at"] = (now + AI_FILTER_TTL).isoformat()
    storage[token] = payload
    request.session[AI_FILTER_SESSION_KEY] = storage
    return payload


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
        context["filter_count"] = resolve_list_filter_count(context, self)
        if "has_filters" not in context:
            context["has_filters"] = list_filters_active(getattr(self, "request", None))
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
        from django.db import transaction
        from django.db.utils import OperationalError, ProgrammingError

        try:
            with transaction.atomic():
                qs = self.get_mirror_queryset()
                qs = self._apply_ai_filter(qs)
                qs.exists()
                return qs
        except (ProgrammingError, OperationalError):
            return self.model.objects.none()

    def _apply_ai_filter(self, qs):
        """Filtra per PK salvate dalla ricerca AI, se presente ?ai=1."""
        request = getattr(self, "request", None)
        if not request or request.GET.get("ai") != "1":
            return qs
        table = getattr(self.model._meta, "db_table", "")
        token = (request.GET.get("ai_token") or "").strip()
        payload = resolve_ai_filter(request, token=token, expected_table=table)
        if payload is None:
            return qs
        pks = payload.get("pks") or []
        self._ai_filter_count = payload.get("count") or len(pks)
        self._ai_filter_table = table
        pk_field = getattr(self.model, "_meta", None)
        if pk_field:
            pk_name = self.model._meta.pk.name
            qs = qs.filter(**{f"{pk_name}__in": pks})
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, "_ai_filter_count"):
            context["ai_filter_count"] = self._ai_filter_count
        return context
