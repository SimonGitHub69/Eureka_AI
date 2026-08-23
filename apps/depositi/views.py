from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import mirror_row_to_campi
from apps.core.navigation import related_back
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.sorting import SortableListMixin
from apps.depositi.models import Deposito
from apps.depositi.sync import sync_depositi


def _filter_depositi_queryset(request):
    qs = Deposito.objects.all().exclude(codice__isnull=True).exclude(codice__exact="")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
    return qs


def _depositi_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Deposito.objects)
    return context


def fetch_deposito_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM depositi WHERE "Numero" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


def _pg_table_count(table: str) -> int:
    with connection.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return int(cur.fetchone()[0])


class DepositoListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Deposito
    template_name = "depositi/deposito_list.html"
    context_object_name = "depositi"
    sortable_fields = ("codice", "descrizione")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "descrizione"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_depositi_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _depositi_list_context(self, context)


class DepositoDetailView(LoginRequiredMixin, DetailView):
    model = Deposito
    template_name = "depositi/deposito_detail.html"
    context_object_name = "deposito"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_deposito_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context


class SyncDepositiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "depositi/sync_depositi.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "depositi_count": _pg_table_count("depositi"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_depositi()
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
