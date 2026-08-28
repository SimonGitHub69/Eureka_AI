from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.categorie.forms import CategoriaForm
from apps.categorie.models import Categoria
from apps.categorie.sync import sync_categorie
from apps.core.mirror_crud import mirror_row_to_campi, stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin


def _filter_categorie_queryset(request):
    qs = Categoria.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(c_vendita_prop__icontains=q)
        )

    return qs.order_by("descrizione", "codice")


def _categorie_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Categoria.objects)
    return context


def fetch_categoria_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM categorie WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class CategoriaListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Categoria
    template_name = "categorie/categoria_list.html"
    context_object_name = "categorie"
    sortable_fields = ("descrizione", "codice", "provvigione")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_categorie_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _categorie_list_context(self, context)


class CategoriaPrintListView(MirrorPrintListView):
    print_title = "Categorie"
    print_subtitle = "Elenco categorie merce"
    filter_queryset = staticmethod(_filter_categorie_queryset)
    sortable_fields = ("descrizione", "codice", "provvigione")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "provvigione", "label": "Provvigione"},
        {"field": "c_vendita_prop", "label": "C. vendita"},
    )


class CategoriaExportListView(ExportListMixin, CategoriaPrintListView):
    export_filename = "categorie"


class CategoriaDetailView(LoginRequiredMixin, DetailView):
    model = Categoria
    template_name = "categorie/categoria_detail.html"
    context_object_name = "categoria"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_categoria_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class CategoriaCreateView(LoginRequiredMixin, View):
    template_name = "categorie/categoria_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": CategoriaForm(),
                "is_create": True,
                "page_heading": "Nuova categoria",
            },
        )

    def post(self, request):
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save(commit=False)
            stamp_modifica(categoria)
            categoria.save()
            messages.success(request, f"Categoria {categoria.codice} creata.")
            return redirect("categorie:detail", codice=categoria.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova categoria",
            },
        )


class CategoriaUpdateView(LoginRequiredMixin, View):
    template_name = "categorie/categoria_form.html"

    def get_object(self, codice):
        return get_object_or_404(Categoria, pk=codice)

    def get(self, request, codice):
        categoria = self.get_object(codice)
        form = CategoriaForm(instance=categoria, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "categoria": categoria,
                "is_create": False,
                "page_heading": "Modifica categoria",
            },
        )

    def post(self, request, codice):
        categoria = self.get_object(codice)
        form = CategoriaForm(request.POST, instance=categoria, codice_readonly=True)
        if form.is_valid():
            categoria = form.save(commit=False)
            stamp_modifica(categoria)
            categoria.save()
            messages.success(request, f"Categoria {categoria.codice} aggiornata.")
            return redirect("categorie:detail", codice=categoria.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "categoria": categoria,
                "is_create": False,
                "page_heading": "Modifica categoria",
            },
        )


class CategoriaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        categoria = get_object_or_404(Categoria, pk=codice)
        label = categoria.codice
        categoria.delete()
        messages.success(request, f"Categoria {label} eliminata.")
        return redirect("categorie:list")


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
