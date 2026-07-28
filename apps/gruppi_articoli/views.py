from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin
from apps.gruppi_articoli.models import GruppoArticolo
from apps.gruppi_articoli.sync import sync_gruppi_articoli


def _filter_gruppi_articoli_queryset(request):
    qs = GruppoArticolo.objects.all()

    q = (request.GET.get("q") or "").strip()
    stato = (request.GET.get("stato") or "").strip()

    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(font_style__icontains=q)
            | Q(font_style_gz__icontains=q)
            | Q(font_style_mz__icontains=q)
        )

    if stato == "attivi":
        qs = qs.filter(Q(f_disattivato=False) | Q(f_disattivato__isnull=True))
    elif stato == "disattivi":
        qs = qs.filter(f_disattivato=True)

    return qs.order_by("descrizione", "codice")


def _gruppi_articoli_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["stato"] = (view.request.GET.get("stato") or "").strip()
    context["has_filters"] = bool(context["q"] or context["stato"])
    try:
        context["totale"] = GruppoArticolo.objects.count()
    except Exception:
        context["totale"] = 0
    return context


def fetch_gruppo_articolo_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM gruppi_articoli WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class GruppoArticoloListView(LoginRequiredMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = GruppoArticolo
    template_name = "gruppi_articoli/gruppo_articolo_list.html"
    context_object_name = "gruppi_articoli"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_gruppi_articoli_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _gruppi_articoli_list_context(self, context)


class GruppoArticoloDetailView(LoginRequiredMixin, DetailView):
    model = GruppoArticolo
    template_name = "gruppi_articoli/gruppo_articolo_detail.html"
    context_object_name = "gruppo_articolo"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_gruppo_articolo_row(self.object.codice) or []
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


class SyncGruppiArticoliView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "gruppi_articoli/sync_gruppi_articoli.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "gruppi_articoli_count": _pg_table_count("gruppi_articoli"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_gruppi_articoli()
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
