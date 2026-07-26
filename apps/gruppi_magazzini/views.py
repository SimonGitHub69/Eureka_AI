from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.pagination import PerPageListMixin
from apps.gruppi_magazzini.models import GruppoMagazzino
from apps.gruppi_magazzini.sync import sync_gruppi_magazzini


def _filter_gruppi_magazzini_queryset(request):
    qs = GruppoMagazzino.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(cod__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(tipo_doc_alfa_ddt__icontains=q)
            | Q(tipo_doc_alfa_fat__icontains=q)
            | Q(tipo_doc_alfa_ord__icontains=q)
        )

    return qs.order_by("descrizione", "cod")


def _gruppi_magazzini_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    try:
        context["totale"] = GruppoMagazzino.objects.count()
    except Exception:
        context["totale"] = 0
    return context


def fetch_gruppo_magazzino_row(cod: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM gruppi_magazzini WHERE "Cod" = %s', [cod])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class GruppoMagazzinoListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = GruppoMagazzino
    template_name = "gruppi_magazzini/gruppo_magazzino_list.html"
    context_object_name = "gruppi_magazzini"
    paginate_by = 50

    def get_queryset(self):
        return _filter_gruppi_magazzini_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _gruppi_magazzini_list_context(self, context)


class GruppoMagazzinoDetailView(LoginRequiredMixin, DetailView):
    model = GruppoMagazzino
    template_name = "gruppi_magazzini/gruppo_magazzino_detail.html"
    context_object_name = "gruppo_magazzino"
    pk_url_kwarg = "cod"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_gruppo_magazzino_row(self.object.cod) or []
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


class SyncGruppiMagazziniView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "gruppi_magazzini/sync_gruppi_magazzini.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "gruppi_magazzini_count": _pg_table_count("gruppi_magazzini"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_gruppi_magazzini()
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
