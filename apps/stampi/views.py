from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import RequireExtraMixin
from apps.core.mirror_crud import mirror_row_to_campi
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.sorting import SortableListMixin
from apps.stampi.forms import StampoArticoliCdForm
from apps.stampi.models import Stampo
from apps.stampi.sync import sync_stampi


def _filter_stampi_queryset(request):
    qs = Stampo.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        filters = (
            Q(cod_stampo__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(cod_cliente__icontains=q)
            | Q(progetto__icontains=q)
            | Q(componente__icontains=q)
            | Q(cod_reparto__icontains=q)
            | Q(codice_art_stampo__icontains=q)
            | Q(tipo_attrezzatura__icontains=q)
        )
        for field_name in Stampo.ARTICOLI_CD_FIELDS:
            filters |= Q(**{f"{field_name}__icontains": q})
        if q.isdigit():
            filters |= Q(id=int(q))
        qs = qs.filter(filters)

    return qs.order_by("cod_stampo", "id")


def _stampi_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Stampo.objects)
    return context


def fetch_stampo_row(stampo_id: int) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM stampi WHERE "ID" = %s', [stampo_id])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class StampoListView(
    LoginRequiredMixin, RequireExtraMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = Stampo
    template_name = "stampi/stampo_list.html"
    context_object_name = "stampi"
    sortable_fields = (
        "id",
        "cod_stampo",
        "descrizione",
        "tipo_attrezzatura",
        "cod_cliente",
        "cod_reparto",
        "progetto",
    )
    default_sort = "cod_stampo"
    default_dir = "asc"
    sort_tiebreaker = "id"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_stampi_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _stampi_list_context(self, context)


class StampoDetailView(LoginRequiredMixin, RequireExtraMixin, DetailView):
    model = Stampo
    template_name = "stampi/stampo_detail.html"
    context_object_name = "stampo"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_stampo_row(self.object.id) or []
        art_cd_names = {f"CodArtCD{i}" for i in range(1, 17)}
        context["articoli_cd"] = self.object.articoli_cd_list()
        context["campi"] = mirror_row_to_campi(row, exclude=art_cd_names)
        return context


class StampoUpdateView(LoginRequiredMixin, RequireExtraMixin, View):
    template_name = "stampi/stampo_edit.html"

    def get_stampo(self, pk):
        return get_object_or_404(Stampo, pk=pk)

    def get(self, request, pk):
        stampo = self.get_stampo(pk)
        form = StampoArticoliCdForm(instance=stampo)
        return render(
            request,
            self.template_name,
            {
                "stampo": stampo,
                "form": form,
                "articoli_cd_fields": [
                    (f"{i:02d}", form[name])
                    for i, name in enumerate(Stampo.ARTICOLI_CD_FIELDS, start=1)
                ],
            },
        )

    def post(self, request, pk):
        stampo = self.get_stampo(pk)
        form = StampoArticoliCdForm(request.POST, instance=stampo)
        if form.is_valid():
            form.save()
            messages.success(request, "Articoli CD salvati.")
            return redirect("stampi:detail", pk=stampo.pk)
        return render(
            request,
            self.template_name,
            {
                "stampo": stampo,
                "form": form,
                "articoli_cd_fields": [
                    (f"{i:02d}", form[name])
                    for i, name in enumerate(Stampo.ARTICOLI_CD_FIELDS, start=1)
                ],
            },
        )


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncStampiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "stampi/sync_stampi.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "stampi_count": _pg_table_count("stampi"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_stampi()
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
