from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin
from apps.lavorazioni_extra.models import LavorazioneExtra
from apps.lavorazioni_extra.sync import sync_lavorazioni_extra


def _filter_queryset(request):
    qs = LavorazioneExtra.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(cod__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(cod_reparto__icontains=q)
        )
        if q.isdigit():
            qs = qs.filter(Q(id=int(q)))
    return qs.order_by("cod", "id")


def _list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    try:
        context["totale"] = LavorazioneExtra.objects.count()
    except Exception:
        context["totale"] = 0
    return context


def fetch_lavorazione_extra_row(pk: int) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM lavorazioni_extra WHERE "ID" = %s', [pk])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class LavorazioneExtraListView(LoginRequiredMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = LavorazioneExtra
    template_name = "lavorazioni_extra/lavorazione_extra_list.html"
    context_object_name = "lavorazioni"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _list_context(self, context)


class LavorazioneExtraDetailView(LoginRequiredMixin, DetailView):
    model = LavorazioneExtra
    template_name = "lavorazioni_extra/lavorazione_extra_detail.html"
    context_object_name = "lavorazione"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_lavorazione_extra_row(self.object.id) or []
        context["campi"] = [
            (name, value)
            for name, value in row
            if name != "synced_at" and value not in (None, "")
        ]
        return context


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncLavorazioniExtraView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "core.access_parametri_4d"
    raise_exception = True
    template_name = "lavorazioni_extra/sync_lavorazioni_extra.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "lavorazioni_extra_count": _pg_table_count("lavorazioni_extra"),
            },
        )

    def post(self, request):
        result = sync_lavorazioni_extra()
        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)
        return redirect("lavorazioni_extra:sync")
