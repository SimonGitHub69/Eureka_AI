from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.carbon.models import LavorazionePartita, Reparto, StampoSerialePartita
from apps.carbon.sync import sync_carbon
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin


def _list_context(view, context, *, totale_qs=None):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    try:
        context["totale"] = (totale_qs or view.get_queryset().model.objects).count()
    except Exception:
        context["totale"] = 0
    return context


def _pg_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


def fetch_row(table: str, pk_col: str, pk) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute(f'SELECT * FROM "{table}" WHERE "{pk_col}" = %s', [pk])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class CarbonHubView(LoginRequiredMixin, View):
    template_name = "carbon/hub.html"

    def get(self, request):
        tables = [
            {
                "title": "Dashboard seriali",
                "source": "INIZIO / FINE",
                "url_name": "carbon:seriali_dashboard",
                "icon": "ti-chart-histogram",
                "count": None,
            },
            {
                "title": "Reparti",
                "source": "Reparti",
                "url_name": "carbon:reparti_list",
                "icon": "ti-building-factory",
                "count": _pg_count("reparti"),
            },
            {
                "title": "Lavorazioni partite",
                "source": "Lavorazioni_Partite",
                "url_name": "carbon:lavorazioni_list",
                "icon": "ti-list-details",
                "count": _pg_count("lavorazioni_partite"),
            },
            {
                "title": "Stampi seriali",
                "source": "TabStampi_Seriali_Partite",
                "url_name": "carbon:stampi_seriali_list",
                "icon": "ti-barcode",
                "count": _pg_count("stampi_seriali_partite"),
            },
            {
                "title": "Lavorazioni extra",
                "source": "TabLavorazioniExtra",
                "url_name": "lavorazioni_extra:list",
                "icon": "ti-tools",
                "count": _pg_count("lavorazioni_extra"),
            },
        ]
        return render(
            request,
            self.template_name,
            {
                "tables": tables,
                "carbon_url": "",
            },
        )


class RepartoListView(LoginRequiredMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Reparto
    template_name = "carbon/reparto_list.html"
    context_object_name = "reparti"
    paginate_by = 50

    def get_mirror_queryset(self):
        qs = Reparto.objects.all()
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
        return qs.order_by("codice")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _list_context(self, context, totale_qs=Reparto.objects)


class RepartoDetailView(LoginRequiredMixin, DetailView):
    model = Reparto
    template_name = "carbon/reparto_detail.html"
    context_object_name = "reparto"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_row("reparti", "Codice", self.object.pk) or []
        context["campi"] = [
            (name, value)
            for name, value in row
            if name != "synced_at" and value not in (None, "")
        ]
        return context


class LavorazionePartitaListView(
    LoginRequiredMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = LavorazionePartita
    template_name = "carbon/lavorazione_list.html"
    context_object_name = "lavorazioni"
    paginate_by = 50

    def get_mirror_queryset(self):
        qs = LavorazionePartita.objects.all()
        q = (self.request.GET.get("q") or "").strip()
        if q:
            filters = (
                Q(codart__icontains=q)
                | Q(codart_ser__icontains=q)
                | Q(cod_reparto__icontains=q)
                | Q(cod_stampo__icontains=q)
                | Q(stato__icontains=q)
                | Q(key_lav__icontains=q)
                | Q(cod_sacco__icontains=q)
                | Q(cod_lavorazione__icontains=q)
            )
            if q.isdigit():
                filters |= Q(id=int(q)) | Q(num_partita=int(q))
            qs = qs.filter(filters)
        return qs.order_by("-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _list_context(self, context, totale_qs=LavorazionePartita.objects)


class LavorazionePartitaDetailView(LoginRequiredMixin, DetailView):
    model = LavorazionePartita
    template_name = "carbon/lavorazione_detail.html"
    context_object_name = "lavorazione"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_row("lavorazioni_partite", "ID", self.object.pk) or []
        context["campi"] = [
            (name, value)
            for name, value in row
            if name != "synced_at" and value not in (None, "")
        ]
        return context


class StampoSerialeListView(LoginRequiredMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = StampoSerialePartita
    template_name = "carbon/stampo_seriale_list.html"
    context_object_name = "righe"
    paginate_by = 50

    def get_mirror_queryset(self):
        qs = StampoSerialePartita.objects.all()
        q = (self.request.GET.get("q") or "").strip()
        if q:
            filters = (
                Q(codice_stampo__icontains=q)
                | Q(cod_sacco__icontains=q)
                | Q(key_lav_partite__icontains=q)
            )
            for name in StampoSerialePartita.SERIALI_FIELDS:
                filters |= Q(**{f"{name}__icontains": q})
            if q.isdigit():
                filters |= Q(id=int(q))
            qs = qs.filter(filters)
        return qs.order_by("-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _list_context(self, context, totale_qs=StampoSerialePartita.objects)


class StampoSerialeDetailView(LoginRequiredMixin, DetailView):
    model = StampoSerialePartita
    template_name = "carbon/stampo_seriale_detail.html"
    context_object_name = "riga"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["seriali"] = self.object.seriali_list()
        row = fetch_row("stampi_seriali_partite", "ID", self.object.pk) or []
        context["campi"] = [
            (name, value)
            for name, value in row
            if name != "synced_at" and value not in (None, "")
        ]
        return context


class SyncCarbonView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "core.access_parametri_4d"
    raise_exception = True
    template_name = "carbon/sync_carbon.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "reparti_count": _pg_count("reparti"),
                "lavorazioni_count": _pg_count("lavorazioni_partite"),
                "stampi_seriali_count": _pg_count("stampi_seriali_partite"),
            },
        )

    def post(self, request):
        only = (request.POST.get("only") or "").strip() or None
        result = sync_carbon(only=only)
        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)
        return redirect("carbon:sync")
