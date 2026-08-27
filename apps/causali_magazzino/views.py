from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.causali_magazzino.forms import (
    CausaleMagazzinoForm,
    linked_labels_for_causale,
    si_no_label,
)
from apps.causali_magazzino.models import CausaleMagazzino
from apps.causali_magazzino.sync import sync_causali_magazzino
from apps.core.navigation import related_back
from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from django.urls import reverse


def _form_context(form, *, is_create: bool, causale=None):
    return {
        "form": form,
        "causale": causale,
        "is_create": is_create,
        "page_heading": (
            "Nuova causale magazzino" if is_create else "Modifica causale magazzino"
        ),
        "labels": linked_labels_for_causale(form),
        "lookup_url": reverse("articoli:lookup_codice"),
    }

def _filter_causali_queryset(request):
    qs = CausaleMagazzino.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(tipo_causale__icontains=q)
            | Q(deposito_entrata__icontains=q)
            | Q(deposito_uscita__icontains=q)
            | Q(cod_market__icontains=q)
        )
    return qs.order_by("descrizione", "codice")


def _causali_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(CausaleMagazzino.objects)
    return context


def fetch_causale_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM causali_maga WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class CausaleMagazzinoListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = CausaleMagazzino
    template_name = "causali_magazzino/causale_list.html"
    context_object_name = "causali"
    sortable_fields = (
        "descrizione",
        "codice",
        "tipo_causale",
        "deposito_entrata",
        "deposito_uscita",
    )
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_causali_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _causali_list_context(self, context)


class CausaleMagazzinoPrintListView(MirrorPrintListView):
    print_title = "Causali magazzino"
    print_subtitle = "Elenco causali magazzino"
    filter_queryset = staticmethod(_filter_causali_queryset)
    sortable_fields = ("descrizione", "codice", "tipo_causale", "deposito_entrata", "deposito_uscita")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "tipo_causale", "label": "Tipo"},
        {"field": "deposito_entrata", "label": "Dep. entrata"},
        {"field": "deposito_uscita", "label": "Dep. uscita"},
    )


class CausaleMagazzinoExportListView(ExportListMixin, CausaleMagazzinoPrintListView):
    export_filename = "causali_magazzino"


class CausaleMagazzinoDetailView(LoginRequiredMixin, DetailView):
    model = CausaleMagazzino
    template_name = "causali_magazzino/causale_detail.html"
    context_object_name = "causale"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_causale_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        context["labels"] = linked_labels_for_causale(self.object)
        context["scar_db_label"] = si_no_label(self.object.scar_db)
        context["update_listino_label"] = si_no_label(self.object.update_listino)
        context["update_prezzo_medio_label"] = si_no_label(
            self.object.update_prezzo_medio
        )
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context


class CausaleMagazzinoCreateView(LoginRequiredMixin, View):
    template_name = "causali_magazzino/causale_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            _form_context(CausaleMagazzinoForm(), is_create=True),
        )

    def post(self, request):
        form = CausaleMagazzinoForm(request.POST)
        if form.is_valid():
            causale = save_mirror_form_instance(form)
            messages.success(request, f"Causale magazzino {causale.codice} creata.")
            return redirect("causali_magazzino:detail", codice=causale.codice)
        return render(
            request,
            self.template_name,
            _form_context(form, is_create=True),
        )


class CausaleMagazzinoUpdateView(LoginRequiredMixin, View):
    template_name = "causali_magazzino/causale_form.html"

    def get_object(self, codice):
        return get_object_or_404(CausaleMagazzino, pk=codice)

    def get(self, request, codice):
        causale = self.get_object(codice)
        form = CausaleMagazzinoForm(instance=causale, codice_readonly=True)
        return render(
            request,
            self.template_name,
            _form_context(form, is_create=False, causale=causale),
        )

    def post(self, request, codice):
        causale = self.get_object(codice)
        form = CausaleMagazzinoForm(request.POST, instance=causale, codice_readonly=True)
        if form.is_valid():
            causale = save_mirror_form_instance(form)
            messages.success(request, f"Causale magazzino {causale.codice} aggiornata.")
            return redirect("causali_magazzino:detail", codice=causale.codice)
        return render(
            request,
            self.template_name,
            _form_context(form, is_create=False, causale=causale),
        )


class CausaleMagazzinoDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        causale = get_object_or_404(CausaleMagazzino, pk=codice)
        label = causale.codice
        causale.delete()
        messages.success(request, f"Causale magazzino {label} eliminata.")
        return redirect("causali_magazzino:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncCausaliMagazzinoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "causali_magazzino/sync_causali.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "causali_count": _pg_table_count("causali_maga"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_causali_magazzino(full=sync_full_from_request(request))
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
