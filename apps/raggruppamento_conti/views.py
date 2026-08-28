from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.raggruppamento_conti.forms import RaggruppamentoContoForm
from apps.pdc.models import PianoConti
from apps.raggruppamento_conti.models import RaggruppamentoConto
from apps.raggruppamento_conti.sync import sync_raggruppamento_conti


def _filter_raggruppamento_queryset(request):
    qs = RaggruppamentoConto.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
    return qs.order_by("codice")


def _raggruppamento_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(RaggruppamentoConto.objects)
    return context


def fetch_raggruppamento_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM raggruppamento_conti WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class RaggruppamentoContoListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = RaggruppamentoConto
    template_name = "raggruppamento_conti/raggruppamento_list.html"
    context_object_name = "raggruppamenti"
    sortable_fields = ("codice", "descrizione")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_raggruppamento_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _raggruppamento_list_context(self, context)


class RaggruppamentoContoPrintListView(MirrorPrintListView):
    print_title = "Raggruppamento Conti"
    print_subtitle = "Elenco raggruppamenti conti"
    filter_queryset = staticmethod(_filter_raggruppamento_queryset)
    sortable_fields = ("codice", "descrizione")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
    )


class RaggruppamentoContoDetailView(LoginRequiredMixin, DetailView):
    model = RaggruppamentoConto
    template_name = "raggruppamento_conti/raggruppamento_detail.html"
    context_object_name = "raggruppamento"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_raggruppamento_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        try:
            with transaction.atomic():
                pdc_qs = PianoConti.objects.filter(gruppo=self.object.codice).order_by(
                    "codice"
                )
                context["pdc_totale"] = pdc_qs.count()
                context["pdc_conti"] = list(pdc_qs[:30])
        except Exception:
            context["pdc_totale"] = 0
            context["pdc_conti"] = []
        return context


class RaggruppamentoContoCreateView(LoginRequiredMixin, View):
    template_name = "raggruppamento_conti/raggruppamento_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": RaggruppamentoContoForm(),
                "is_create": True,
                "page_heading": "Nuovo raggruppamento",
            },
        )

    def post(self, request):
        form = RaggruppamentoContoForm(request.POST)
        if form.is_valid():
            item = save_mirror_form_instance(form)
            messages.success(request, f"Raggruppamento {item.codice} creato.")
            return redirect("raggruppamento_conti:detail", codice=item.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo raggruppamento",
            },
        )


class RaggruppamentoContoUpdateView(LoginRequiredMixin, View):
    template_name = "raggruppamento_conti/raggruppamento_form.html"

    def get_object(self, codice):
        return get_object_or_404(RaggruppamentoConto, pk=codice)

    def get(self, request, codice):
        item = self.get_object(codice)
        form = RaggruppamentoContoForm(instance=item, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "raggruppamento": item,
                "is_create": False,
                "page_heading": "Modifica raggruppamento",
            },
        )

    def post(self, request, codice):
        item = self.get_object(codice)
        form = RaggruppamentoContoForm(
            request.POST, instance=item, codice_readonly=True
        )
        if form.is_valid():
            item = save_mirror_form_instance(form)
            messages.success(request, f"Raggruppamento {item.codice} aggiornato.")
            return redirect("raggruppamento_conti:detail", codice=item.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "raggruppamento": item,
                "is_create": False,
                "page_heading": "Modifica raggruppamento",
            },
        )


class RaggruppamentoContoDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        item = get_object_or_404(RaggruppamentoConto, pk=codice)
        label = item.codice
        item.delete()
        messages.success(request, f"Raggruppamento {label} eliminato.")
        return redirect("raggruppamento_conti:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncRaggruppamentoContiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "raggruppamento_conti/sync_raggruppamento.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "raggruppamento_count": _pg_table_count("raggruppamento_conti"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_raggruppamento_conti()
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
