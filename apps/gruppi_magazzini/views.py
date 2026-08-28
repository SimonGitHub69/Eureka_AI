from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import delete_mirror_row, mirror_row_to_campi, stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.gruppi_magazzini.forms import GruppoMagazzinoForm
from apps.gruppi_magazzini.models import GruppoMagazzino
from apps.gruppi_magazzini.sync import sync_gruppi_magazzini


def _filter_gruppi_magazzini_queryset(request):
    qs = GruppoMagazzino.objects.all().exclude(cod__isnull=True).exclude(cod__exact="")

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
    context["totale"] = safe_mirror_count(GruppoMagazzino.objects)
    return context


def fetch_gruppo_magazzino_row(cod: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM gruppi_magazzini WHERE "Cod" = %s', [cod])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class GruppoMagazzinoListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = GruppoMagazzino
    template_name = "gruppi_magazzini/gruppo_magazzino_list.html"
    context_object_name = "gruppi_magazzini"
    sortable_fields = ("descrizione", "cod", "tipo_doc_alfa_ddt", "tipo_doc_alfa_fat", "tipo_doc_alfa_ord")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "cod"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_gruppi_magazzini_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _gruppi_magazzini_list_context(self, context)


class GruppoMagazzinoPrintListView(MirrorPrintListView):
    print_title = "Gruppi Magazzini"
    print_subtitle = "Elenco Gruppi Magazzini"
    filter_queryset = staticmethod(_filter_gruppi_magazzini_queryset)
    sortable_fields = ("descrizione", "cod", "tipo_doc_alfa_ddt", "tipo_doc_alfa_fat", "tipo_doc_alfa_ord")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "cod"
    print_columns = (
        {"field": "cod", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "tipo_doc_alfa_ddt", "label": "Tipo doc. DDT"},
        {"field": "tipo_doc_alfa_fat", "label": "Tipo doc. fattura"},
        {"field": "tipo_doc_alfa_ord", "label": "Tipo doc. ordine"},
    )


class GruppoMagazzinoExportListView(ExportListMixin, GruppoMagazzinoPrintListView):
    export_filename = "gruppi_magazzini"


class GruppoMagazzinoDetailView(LoginRequiredMixin, DetailView):
    model = GruppoMagazzino
    template_name = "gruppi_magazzini/gruppo_magazzino_detail.html"
    context_object_name = "gruppo_magazzino"
    pk_url_kwarg = "cod"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_gruppo_magazzino_row(self.object.cod) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class GruppoMagazzinoCreateView(LoginRequiredMixin, View):
    template_name = "gruppi_magazzini/gruppo_magazzino_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": GruppoMagazzinoForm(),
                "is_create": True,
                "page_heading": "Nuovo Gruppo Magazzini",
            },
        )

    def post(self, request):
        form = GruppoMagazzinoForm(request.POST)
        if form.is_valid():
            gruppo = form.save(commit=False)
            stamp_modifica(gruppo)
            gruppo.save()
            messages.success(request, f"Gruppo Magazzini {gruppo.cod} creato.")
            return redirect("gruppi_magazzini:detail", cod=gruppo.cod)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo Gruppo Magazzini",
            },
        )


class GruppoMagazzinoUpdateView(LoginRequiredMixin, View):
    template_name = "gruppi_magazzini/gruppo_magazzino_form.html"

    def get_object(self, cod):
        return get_object_or_404(GruppoMagazzino, pk=cod)

    def get(self, request, cod):
        gruppo = self.get_object(cod)
        form = GruppoMagazzinoForm(instance=gruppo, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "gruppo_magazzino": gruppo,
                "is_create": False,
                "page_heading": "Modifica Gruppo Magazzini",
            },
        )

    def post(self, request, cod):
        gruppo = self.get_object(cod)
        form = GruppoMagazzinoForm(request.POST, instance=gruppo, codice_readonly=True)
        if form.is_valid():
            gruppo = form.save(commit=False)
            stamp_modifica(gruppo)
            gruppo.save()
            messages.success(request, f"Gruppo Magazzini {gruppo.cod} aggiornato.")
            return redirect("gruppi_magazzini:detail", cod=gruppo.cod)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "gruppo_magazzino": gruppo,
                "is_create": False,
                "page_heading": "Modifica Gruppo Magazzini",
            },
        )


class GruppoMagazzinoDeleteView(LoginRequiredMixin, View):
    def post(self, request, cod):
        gruppo = get_object_or_404(GruppoMagazzino, pk=cod)
        label = gruppo.cod
        try:
            delete_mirror_row(GruppoMagazzino, label)
        except RuntimeError as exc:
            messages.error(request, str(exc))
            return redirect("gruppi_magazzini:detail", cod=label)
        messages.success(
            request,
            f"Gruppo Magazzini {label} eliminato da PostgreSQL. "
            "Un sync completo da 4D lo reimporterà se esiste ancora in RaggMagazzini.",
        )
        return redirect("gruppi_magazzini:list")


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
