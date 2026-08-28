from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, UpdateView

from apps.aziende.forms import AziendaConfigForm, AziendaDatiForm, AziendaForm
from apps.aziende.models import Azienda, AziendaDati
from apps.aziende.sync import sync_aziende
from apps.core.mirror_crud import format_mirror_display_value, stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin


def _filter_aziende_queryset(request):
    qs = Azienda.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        filters = (
            Q(ragione_sociale__icontains=q)
            | Q(partita_iva__icontains=q)
            | Q(codice_fiscale__icontains=q)
            | Q(localita__icontains=q)
            | Q(email__icontains=q)
            | Q(telefono__icontains=q)
        )
        if q.isdigit():
            filters |= Q(id=int(q))
        qs = qs.filter(filters)

    return qs.order_by("ragione_sociale", "id")


def _aziende_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Azienda)
    return context


def _dati_by_azienda_ids(azienda_ids: list[int]) -> dict[int, AziendaDati]:
    if not azienda_ids:
        return {}
    return {
        d.azienda_id: d
        for d in AziendaDati.objects.filter(
            is_active=True, azienda_id__in=azienda_ids
        ).exclude(logo="")
    }


def fetch_azienda_row(azienda_id: int) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM aziende WHERE "ID" = %s', [azienda_id])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


def _is_displayable_value(value: object) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, (bytes, memoryview, bytearray)):
        return False
    return True


class AziendaListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Azienda
    template_name = "aziende/azienda_list.html"
    context_object_name = "aziende"
    sortable_fields = ("ragione_sociale", "partita_iva", "localita", "id")
    default_sort = "ragione_sociale"
    default_dir = "asc"
    sort_tiebreaker = "id"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_aziende_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context = _aziende_list_context(self, context)
        aziende = list(context.get("aziende") or [])
        dati_by_id = _dati_by_azienda_ids([a.id for a in aziende])
        for azienda in aziende:
            azienda.dati_locali = dati_by_id.get(azienda.id)
        return context


class AziendaPrintListView(MirrorPrintListView):
    print_title = "Azienda"
    print_subtitle = "Elenco dati azienda"
    filter_queryset = staticmethod(_filter_aziende_queryset)
    sortable_fields = ("ragione_sociale", "partita_iva", "localita", "id")
    default_sort = "ragione_sociale"
    default_dir = "asc"
    sort_tiebreaker = "id"
    print_columns = (
        {"field": "id", "label": "ID"},
        {"field": "ragione_sociale", "label": "Ragione sociale"},
        {"field": "partita_iva", "label": "P. IVA"},
        {"field": "codice_fiscale", "label": "Codice fiscale"},
        {"field": "localita", "label": "Località"},
        {"field": "provincia", "label": "Provincia"},
    )


class AziendaExportListView(ExportListMixin, AziendaPrintListView):
    export_filename = "aziende"


class AziendaDetailView(LoginRequiredMixin, DetailView):
    model = Azienda
    template_name = "aziende/azienda_detail.html"
    context_object_name = "azienda"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_azienda_row(self.object.id) or []
        context["campi"] = [
            (name, format_mirror_display_value(value))
            for name, value in row
            if name != "synced_at" and _is_displayable_value(value)
        ]
        context["azienda_dati"] = AziendaDati.objects.filter(
            is_active=True, azienda_id=self.object.id
        ).first()
        return context


def _get_azienda_dati_instance(azienda_id: int, user=None) -> AziendaDati:
    existing = AziendaDati.objects.filter(azienda_id=azienda_id).first()
    if existing:
        return existing
    dati = AziendaDati(azienda_id=azienda_id)
    if user:
        dati.created_by = user
    return dati


def _save_azienda_config(form: AziendaConfigForm, azienda_id: int, user) -> None:
    dati = form.save(commit=False)
    dati.azienda_id = azienda_id
    if not dati.created_by_id:
        dati.created_by = user
    dati.updated_by = user
    dati.save()


class AziendaCreateView(LoginRequiredMixin, View):
    template_name = "aziende/azienda_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": AziendaForm(),
                "config_form": AziendaConfigForm(),
                "is_create": True,
                "page_heading": "Nuova azienda",
            },
        )

    def post(self, request):
        form = AziendaForm(request.POST)
        config_form = AziendaConfigForm(request.POST)
        if form.is_valid() and config_form.is_valid():
            azienda = form.save(commit=False)
            azienda.pk = form.cleaned_data["id"]
            stamp_modifica(azienda)
            azienda.save(force_insert=True)
            _save_azienda_config(config_form, azienda.id, request.user)
            messages.success(request, f"Azienda {azienda.id} creata.")
            return redirect("aziende:detail", pk=azienda.id)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "config_form": config_form,
                "is_create": True,
                "page_heading": "Nuova azienda",
            },
        )


class AziendaUpdateView(LoginRequiredMixin, View):
    template_name = "aziende/azienda_form.html"

    def get_object(self, pk):
        return get_object_or_404(Azienda, pk=pk)

    def get(self, request, pk):
        azienda = self.get_object(pk)
        form = AziendaForm(instance=azienda, id_readonly=True)
        config_form = AziendaConfigForm(instance=_get_azienda_dati_instance(azienda.id))
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "config_form": config_form,
                "azienda": azienda,
                "is_create": False,
                "page_heading": azienda.ragione_sociale or "Modifica anagrafica",
            },
        )

    def post(self, request, pk):
        azienda = self.get_object(pk)
        form = AziendaForm(request.POST, instance=azienda, id_readonly=True)
        config_form = AziendaConfigForm(
            request.POST,
            instance=_get_azienda_dati_instance(azienda.id, request.user),
        )
        if form.is_valid() and config_form.is_valid():
            azienda = form.save(commit=False)
            stamp_modifica(azienda)
            azienda.save()
            _save_azienda_config(config_form, azienda.id, request.user)
            messages.success(request, f"Azienda {azienda.id} aggiornata.")
            return redirect("aziende:detail", pk=azienda.id)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "config_form": config_form,
                "azienda": azienda,
                "is_create": False,
                "page_heading": azienda.ragione_sociale or "Modifica anagrafica",
            },
        )


class AziendaDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        label = azienda.id
        azienda.delete()
        messages.success(request, f"Azienda {label} eliminata.")
        return redirect("aziende:list")


class AziendaDatiUpdateView(LoginRequiredMixin, UpdateView):
    """Maschera locale per logo e note Eureka (l'anagrafica resta mirror 4D)."""

    model = AziendaDati
    form_class = AziendaDatiForm
    template_name = "aziende/azienda_dati_form.html"
    context_object_name = "azienda_dati"

    def dispatch(self, request, *args, **kwargs):
        self.azienda = get_object_or_404(Azienda, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        existing = AziendaDati.objects.filter(azienda_id=self.azienda.id).first()
        if existing:
            return existing
        return AziendaDati(azienda_id=self.azienda.id, created_by=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["azienda"] = self.azienda
        return context

    def form_valid(self, form):
        if not form.instance.created_by_id:
            form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.instance.azienda_id = self.azienda.id

        old_logo = None
        old_logo_documenti = None
        if form.instance.pk:
            old = (
                AziendaDati.objects.filter(pk=form.instance.pk)
                .only("logo", "logo_documenti")
                .first()
            )
            if old:
                if old.logo:
                    old_logo = old.logo.name
                if old.logo_documenti:
                    old_logo_documenti = old.logo_documenti.name

        response = super().form_valid(form)

        storage = form.instance.logo.storage
        new_logo = form.instance.logo.name if form.instance.logo else ""
        if old_logo and old_logo != new_logo and storage.exists(old_logo):
            storage.delete(old_logo)

        new_logo_doc = (
            form.instance.logo_documenti.name if form.instance.logo_documenti else ""
        )
        if (
            old_logo_documenti
            and old_logo_documenti != new_logo_doc
            and storage.exists(old_logo_documenti)
        ):
            storage.delete(old_logo_documenti)

        messages.success(self.request, "Dati azienda salvati correttamente.")
        return response

    def get_success_url(self):
        return reverse("aziende:detail", kwargs={"pk": self.azienda.id})


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncAziendeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "aziende/sync_aziende.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "aziende_count": _pg_table_count("aziende"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_aziende()
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
