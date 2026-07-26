from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.categorie.models import Categoria
from apps.categorie.sync import sync_categorie
from apps.core.pagination import PerPageListMixin


def _filter_categorie_queryset(request):
    qs = Categoria.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(c_vendita_prop__icontains=q)
            | Q(categoria_utf__icontains=q)
        )

    return qs.order_by("descrizione", "codice")


def _categorie_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    try:
        context["totale"] = Categoria.objects.count()
    except Exception:
        context["totale"] = 0
    return context


def fetch_categoria_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM categorie WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class CategoriaListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Categoria
    template_name = "categorie/categoria_list.html"
    context_object_name = "categorie"
    paginate_by = 50

    def get_queryset(self):
        return _filter_categorie_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _categorie_list_context(self, context)


class CategoriaDetailView(LoginRequiredMixin, DetailView):
    model = Categoria
    template_name = "categorie/categoria_detail.html"
    context_object_name = "categoria"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_categoria_row(self.object.codice) or []
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


class SyncCategorieView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "categorie/sync_categorie.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "categorie_count": _pg_table_count("categorie"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_categorie()
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
