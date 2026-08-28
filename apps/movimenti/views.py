from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection, transaction
from django.db.models import DateField, Exists, OuterRef, Q
from django.db.models.functions import Cast
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import render
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

from apps.articoli.movimenti_magazzino import attach_prezzi_movimento_righe
from apps.core.navigation import related_back
from apps.depositi.lookups import depositi_by_codes
from apps.core.export_list import ExportListMixin
from apps.core.mirror_crud import mirror_row_to_campi
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.movimenti.lookups import (
    attach_movimento_labels,
    format_anagrafica_display,
    format_causale_display,
)
from apps.movimenti.models import MovimentoT, MovimentoTDettaglio
from apps.movimenti.sync import sync_movimenti


def _movimenti_articolo_filter(q: str) -> Q:
    """Movimenti con almeno una riga dettaglio che matcha codice o descrizione articolo."""
    from apps.articoli.models import Articolo

    text = (q or "").strip()
    if not text:
        return Q()
    dettaglio_codice = MovimentoTDettaglio.objects.filter(
        id_testa=OuterRef("pk"),
        codice_art__icontains=text,
    )
    dettaglio_desc = MovimentoTDettaglio.objects.filter(
        id_testa=OuterRef("pk"),
        codice_art__in=Articolo.objects.filter(descrizione__icontains=text).values(
            "codice"
        ),
    )
    return Q(Exists(dettaglio_codice)) | Q(Exists(dettaglio_desc))


def _filter_movimenti_queryset(request):
    qs = MovimentoT.objects.all()
    q = (request.GET.get("q") or "").strip()
    causale = (request.GET.get("causale") or "").strip()
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())

    if q:
        filters = (
            Q(causale__icontains=q)
            | Q(num_doc__icontains=q)
            | Q(cliente__icontains=q)
            | Q(fornitore__icontains=q)
            | Q(dep_entrata__icontains=q)
            | Q(dep_uscita__icontains=q)
        )
        if q.isdigit():
            n = int(q)
            filters |= Q(num_registraz=n) | Q(id_testa=n)
        filters |= _movimenti_articolo_filter(q)
        qs = qs.filter(filters)
    if causale:
        qs = qs.filter(causale__iexact=causale)
    if data_da or data_a:
        qs = qs.annotate(_data_reg_cal=Cast("data_registraz", DateField()))
    if data_da:
        qs = qs.filter(_data_reg_cal__gte=data_da)
    if data_a:
        qs = qs.filter(_data_reg_cal__lte=data_a)
    return qs.order_by("-data_registraz", "-num_registraz", "-id_testa")


def fetch_movimento_row(pk: int) -> list[tuple[str, object]] | None:
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute('SELECT * FROM movimentit WHERE "ID_Testa" = %s', [pk])
                row = cur.fetchone()
                if row is None:
                    return None
                columns = [col[0] for col in cur.description]
            return list(zip(columns, row))
    except (ProgrammingError, OperationalError):
        return None


def load_movimento_righe(id_testa: int) -> tuple[list, bool]:
    try:
        with transaction.atomic():
            righe = list(
                MovimentoTDettaglio.objects.filter(id_testa=id_testa).order_by(
                    "pos", "id"
                )
            )
            attach_prezzi_movimento_righe(righe)
            return righe, False
    except (ProgrammingError, OperationalError):
        return [], True


def _pg_table_count(table: str) -> int:
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                return cur.fetchone()[0]
    except (ProgrammingError, OperationalError):
        return 0


def _movimenti_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["causale"] = (view.request.GET.get("causale") or "").strip()
    context["data_da"] = (view.request.GET.get("data_da") or "").strip()
    context["data_a"] = (view.request.GET.get("data_a") or "").strip()
    context["has_filters"] = bool(
        context["q"] or context["causale"] or context["data_da"] or context["data_a"]
    )
    context["totale"] = safe_mirror_count(MovimentoT)
    return context


class MovimentoListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = MovimentoT
    template_name = "movimenti/movimento_list.html"
    context_object_name = "movimenti"
    sortable_fields = (
        "num_registraz",
        "data_registraz",
        "causale",
        "num_doc",
        "cliente",
        "fornitore",
        "id_testa",
    )
    default_sort = "data_registraz"
    default_dir = "desc"
    sort_tiebreaker = ("-num_registraz", "-id_testa")
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_movimenti_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attach_movimento_labels(context.get("movimenti") or [])
        return _movimenti_list_context(self, context)


class MovimentoPrintListView(MirrorPrintListView):
    print_title = "Movimenti magazzino"
    print_subtitle = "Elenco movimenti"
    filter_queryset = staticmethod(_filter_movimenti_queryset)
    sortable_fields = (
        "num_registraz",
        "data_registraz",
        "causale",
        "num_doc",
        "cliente",
        "fornitore",
        "id_testa",
    )
    default_sort = "data_registraz"
    default_dir = "desc"
    sort_tiebreaker = ("-num_registraz", "-id_testa")
    print_columns = (
        {"field": "num_registraz", "label": "N. reg."},
        {"field": "data_registraz", "label": "Data", "date": True},
        {"label": "Causale", "value": format_causale_display},
        {"field": "num_doc", "label": "Documento"},
        {
            "label": "Cliente",
            "value": lambda m: format_anagrafica_display(
                m.cliente, getattr(m, "cliente_ragione_sociale", "")
            ),
        },
        {
            "label": "Fornitore",
            "value": lambda m: format_anagrafica_display(
                m.fornitore, getattr(m, "fornitore_ragione_sociale", "")
            ),
        },
        {"field": "dep_entrata", "label": "Dep. entrata"},
        {"field": "dep_uscita", "label": "Dep. uscita"},
    )

    def get_queryset(self):
        if not self.print_preview_ready():
            return []
        rows = list(super().get_queryset())
        attach_movimento_labels(rows)
        return rows


class MovimentoExportListView(ExportListMixin, MovimentoPrintListView):
    export_filename = "movimenti"


class MovimentoDetailView(LoginRequiredMixin, DetailView):
    model = MovimentoT
    template_name = "movimenti/movimento_detail.html"
    context_object_name = "movimento"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attach_movimento_labels([self.object])
        row = fetch_movimento_row(self.object.pk) or []
        context["campi"] = mirror_row_to_campi(row)
        righe, dettaglio_mancante = load_movimento_righe(self.object.pk)
        context["righe"] = righe
        context["dettaglio_mancante"] = dettaglio_mancante
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        depositi = depositi_by_codes([self.object.dep_entrata, self.object.dep_uscita])
        context["dep_entrata_deposito"] = depositi.get((self.object.dep_entrata or "").strip().upper(), "")
        context["dep_uscita_deposito"] = depositi.get((self.object.dep_uscita or "").strip().upper(), "")
        return context


class SyncMovimentiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "movimenti/sync_movimenti.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "movimentit_count": _pg_table_count("movimentit"),
            "dettaglio_count": _pg_table_count("movimentit_dettaglio"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_movimenti(full=sync_full_from_request(request))
        message = "\n".join(t.message for t in result.tables) or result.message
        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)
        return render(request, self.template_name, self.get_context(message))
