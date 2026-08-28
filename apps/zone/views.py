from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.zone.forms import ZonaForm
from apps.zone.models import Zona
from apps.zone.sync import sync_zone


def _filter_zone_queryset(request):
    qs = Zona.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
    return qs.order_by("descrizione", "codice")


def _zone_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Zona.objects)
    return context


def fetch_zona_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM zone WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class ZonaListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Zona
    template_name = "zone/zona_list.html"
    context_object_name = "zone"
    sortable_fields = ("descrizione", "codice")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_zone_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _zone_list_context(self, context)


class ZonaPrintListView(MirrorPrintListView):
    print_title = "Zone"
    print_subtitle = "Elenco zone"
    filter_queryset = staticmethod(_filter_zone_queryset)
    sortable_fields = ("descrizione", "codice")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
    )


class ZonaExportListView(ExportListMixin, ZonaPrintListView):
    export_filename = "zone"


class ZonaDetailView(LoginRequiredMixin, DetailView):
    model = Zona
    template_name = "zone/zona_detail.html"
    context_object_name = "zona"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_zona_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class ZonaCreateView(LoginRequiredMixin, View):
    template_name = "zone/zona_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": ZonaForm(),
                "is_create": True,
                "page_heading": "Nuova zona",
            },
        )

    def post(self, request):
        form = ZonaForm(request.POST)
        if form.is_valid():
            zona = save_mirror_form_instance(form)
            messages.success(request, f"Zona {zona.codice} creata.")
            return redirect("zone:detail", codice=zona.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova zona",
            },
        )


class ZonaUpdateView(LoginRequiredMixin, View):
    template_name = "zone/zona_form.html"

    def get_object(self, codice):
        return get_object_or_404(Zona, pk=codice)

    def get(self, request, codice):
        zona = self.get_object(codice)
        form = ZonaForm(instance=zona, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "zona": zona,
                "is_create": False,
                "page_heading": "Modifica zona",
            },
        )

    def post(self, request, codice):
        zona = self.get_object(codice)
        form = ZonaForm(request.POST, instance=zona, codice_readonly=True)
        if form.is_valid():
            zona = save_mirror_form_instance(form)
            messages.success(request, f"Zona {zona.codice} aggiornata.")
            return redirect("zone:detail", codice=zona.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "zona": zona,
                "is_create": False,
                "page_heading": "Modifica zona",
            },
        )


class ZonaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        zona = get_object_or_404(Zona, pk=codice)
        label = zona.codice
        zona.delete()
        messages.success(request, f"Zona {label} eliminata.")
        return redirect("zone:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncZoneView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "zone/sync_zone.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "zone_count": _pg_table_count("zone"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_zone(full=sync_full_from_request(request))
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
