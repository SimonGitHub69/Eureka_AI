from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import mirror_row_to_campi, stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.gruppi_articoli.forms import STYLE_SECTIONS, GruppoArticoloForm
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
    context["totale"] = safe_mirror_count(GruppoArticolo.objects)
    return context


def fetch_gruppo_articolo_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM gruppi_articoli WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class GruppoArticoloListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = GruppoArticolo
    template_name = "gruppi_articoli/gruppo_articolo_list.html"
    context_object_name = "gruppi_articoli"
    sortable_fields = ("descrizione", "codice")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_gruppi_articoli_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _gruppi_articoli_list_context(self, context)


class GruppoArticoloPrintListView(MirrorPrintListView):
    print_title = "Gruppi articoli"
    print_subtitle = "Elenco gruppi articoli"
    filter_queryset = staticmethod(_filter_gruppi_articoli_queryset)
    sortable_fields = ("descrizione", "codice")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "f_disattivato", "label": "Disattivato", "bool": True},
    )

    def get_filter_summary(self):
        parts = []
        q = (self.request.GET.get("q") or "").strip()
        stato = (self.request.GET.get("stato") or "").strip()
        if q:
            parts.append(f'Ricerca: "{q}"')
        if stato == "attivi":
            parts.append("Solo attivi")
        elif stato == "disattivi":
            parts.append("Solo disattivi")
        return " · ".join(parts)


class GruppoArticoloExportListView(ExportListMixin, GruppoArticoloPrintListView):
    export_filename = "gruppi_articoli"


class GruppoArticoloDetailView(LoginRequiredMixin, DetailView):
    model = GruppoArticolo
    template_name = "gruppi_articoli/gruppo_articolo_detail.html"
    context_object_name = "gruppo_articolo"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        context["style_previews"] = [
            (
                title,
                getattr(obj, font_field, None) or "",
                getattr(obj, rgb_fore, None),
                getattr(obj, rgb_back, None),
            )
            for _suffix, title, font_field, rgb_fore, rgb_back in STYLE_SECTIONS
        ]
        row = fetch_gruppo_articolo_row(obj.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class GruppoArticoloCreateView(LoginRequiredMixin, View):
    template_name = "gruppi_articoli/gruppo_articolo_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": GruppoArticoloForm(),
                "is_create": True,
                "page_heading": "Nuovo gruppo articolo",
            },
        )

    def post(self, request):
        form = GruppoArticoloForm(request.POST)
        if form.is_valid():
            gruppo = form.save(commit=False)
            stamp_modifica(gruppo)
            gruppo.save()
            messages.success(request, f"Gruppo articolo {gruppo.codice} creato.")
            return redirect("gruppi_articoli:detail", codice=gruppo.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo gruppo articolo",
            },
        )


class GruppoArticoloUpdateView(LoginRequiredMixin, View):
    template_name = "gruppi_articoli/gruppo_articolo_form.html"

    def get_object(self, codice):
        return get_object_or_404(GruppoArticolo, pk=codice)

    def get(self, request, codice):
        gruppo = self.get_object(codice)
        form = GruppoArticoloForm(instance=gruppo, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "gruppo_articolo": gruppo,
                "is_create": False,
                "page_heading": "Modifica gruppo articolo",
            },
        )

    def post(self, request, codice):
        gruppo = self.get_object(codice)
        form = GruppoArticoloForm(request.POST, instance=gruppo, codice_readonly=True)
        if form.is_valid():
            gruppo = form.save(commit=False)
            stamp_modifica(gruppo)
            gruppo.save()
            messages.success(request, f"Gruppo articolo {gruppo.codice} aggiornato.")
            return redirect("gruppi_articoli:detail", codice=gruppo.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "gruppo_articolo": gruppo,
                "is_create": False,
                "page_heading": "Modifica gruppo articolo",
            },
        )


class GruppoArticoloDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        gruppo = get_object_or_404(GruppoArticolo, pk=codice)
        label = gruppo.codice
        gruppo.delete()
        messages.success(request, f"Gruppo articolo {label} eliminato.")
        return redirect("gruppi_articoli:list")


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
