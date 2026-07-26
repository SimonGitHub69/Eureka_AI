from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.pagination import PerPageListMixin
from apps.magazzini.models import Magazzino
from apps.magazzini.sync import sync_magazzini


def _filter_magazzini_queryset(request):
    qs = Magazzino.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(cod_ragg_mag__icontains=q)
        )

    return qs.order_by("descrizione", "codice")


def _magazzini_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    try:
        context["totale"] = Magazzino.objects.count()
    except Exception:
        context["totale"] = 0
    return context


def fetch_magazzino_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM magazzini WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class MagazzinoListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Magazzino
    template_name = "magazzini/magazzino_list.html"
    context_object_name = "magazzini"
    paginate_by = 50

    def get_queryset(self):
        return _filter_magazzini_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _magazzini_list_context(self, context)


class MagazzinoDetailView(LoginRequiredMixin, DetailView):
    model = Magazzino
    template_name = "magazzini/magazzino_detail.html"
    context_object_name = "magazzino"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_magazzino_row(self.object.codice) or []
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


class SyncMagazziniView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "magazzini/sync_magazzini.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "magazzini_count": _pg_table_count("magazzini"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_magazzini()
        message = "\n".join(t.message for t in result.tables) or result.message

        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)

        return render(
            request,
            self.template_name,
            self.get_context(last_message=message),
        )
