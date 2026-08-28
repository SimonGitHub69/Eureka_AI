from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.navigation import related_back
from apps.core.mirror_crud import delete_mirror_row, mirror_row_to_campi, stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.magazzini.forms import MagazzinoForm
from apps.magazzini.models import Magazzino
from apps.magazzini.sync import sync_magazzini


def _filter_magazzini_queryset(request):
    qs = Magazzino.objects.all().exclude(codice__isnull=True).exclude(codice__exact="")

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
    context["totale"] = safe_mirror_count(Magazzino.objects)
    return context


def fetch_magazzino_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM magazzini WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class MagazzinoListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Magazzino
    template_name = "magazzini/magazzino_list.html"
    context_object_name = "magazzini"
    sortable_fields = ("descrizione", "codice", "cod_ragg_mag")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_magazzini_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _magazzini_list_context(self, context)


class MagazzinoPrintListView(MirrorPrintListView):
    print_title = "Magazzini"
    print_subtitle = "Elenco magazzini"
    filter_queryset = staticmethod(_filter_magazzini_queryset)
    sortable_fields = ("descrizione", "codice", "cod_ragg_mag")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "cod_ragg_mag", "label": "Gruppo Magazzini"},
    )


class MagazzinoExportListView(ExportListMixin, MagazzinoPrintListView):
    export_filename = "magazzini"


class MagazzinoDetailView(LoginRequiredMixin, DetailView):
    model = Magazzino
    template_name = "magazzini/magazzino_detail.html"
    context_object_name = "magazzino"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_magazzino_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context


class MagazzinoCreateView(LoginRequiredMixin, View):
    template_name = "magazzini/magazzino_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": MagazzinoForm(),
                "is_create": True,
                "page_heading": "Nuovo magazzino",
            },
        )

    def post(self, request):
        form = MagazzinoForm(request.POST)
        if form.is_valid():
            magazzino = form.save(commit=False)
            stamp_modifica(magazzino)
            magazzino.save()
            messages.success(request, f"Magazzino {magazzino.codice} creato.")
            return redirect("magazzini:detail", codice=magazzino.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo magazzino",
            },
        )


class MagazzinoUpdateView(LoginRequiredMixin, View):
    template_name = "magazzini/magazzino_form.html"

    def get_object(self, codice):
        return get_object_or_404(Magazzino, pk=codice)

    def get(self, request, codice):
        magazzino = self.get_object(codice)
        form = MagazzinoForm(instance=magazzino, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "magazzino": magazzino,
                "is_create": False,
                "page_heading": "Modifica magazzino",
            },
        )

    def post(self, request, codice):
        magazzino = self.get_object(codice)
        form = MagazzinoForm(request.POST, instance=magazzino, codice_readonly=True)
        if form.is_valid():
            magazzino = form.save(commit=False)
            stamp_modifica(magazzino)
            magazzino.save()
            messages.success(request, f"Magazzino {magazzino.codice} aggiornato.")
            return redirect("magazzini:detail", codice=magazzino.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "magazzino": magazzino,
                "is_create": False,
                "page_heading": "Modifica magazzino",
            },
        )


class MagazzinoDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        magazzino = get_object_or_404(Magazzino, pk=codice)
        label = magazzino.codice
        try:
            delete_mirror_row(Magazzino, label)
        except RuntimeError as exc:
            messages.error(request, str(exc))
            return redirect("magazzini:detail", codice=label)
        messages.success(request, f"Magazzino {label} eliminato.")
        return redirect("magazzini:list")


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
