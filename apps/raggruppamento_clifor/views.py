from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.anagrafiche.models import Cliente, Fornitore
from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin
from apps.raggruppamento_clifor.forms import RaggruppamentoCliforForm
from apps.raggruppamento_clifor.models import RaggruppamentoClifor
from apps.raggruppamento_clifor.sync import sync_raggruppamento_clifor


def _filter_raggruppamento_clifor_queryset(request):
    qs = RaggruppamentoClifor.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
    return qs.order_by("codice")


def _raggruppamento_clifor_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    try:
        context["totale"] = RaggruppamentoClifor.objects.count()
    except Exception:
        context["totale"] = 0
    return context


def fetch_raggruppamento_clifor_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM raggruppamento_clifor WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class RaggruppamentoCliforListView(
    LoginRequiredMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = RaggruppamentoClifor
    template_name = "raggruppamento_clifor/raggruppamento_list.html"
    context_object_name = "raggruppamenti"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_raggruppamento_clifor_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _raggruppamento_clifor_list_context(self, context)


class RaggruppamentoCliforDetailView(LoginRequiredMixin, DetailView):
    model = RaggruppamentoClifor
    template_name = "raggruppamento_clifor/raggruppamento_detail.html"
    context_object_name = "raggruppamento"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_raggruppamento_clifor_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        try:
            clienti_qs = Cliente.objects.filter(gruppo=self.object.codice).order_by(
                "ragione_sociale1", "codice"
            )
            context["clienti_totale"] = clienti_qs.count()
            context["clienti"] = list(clienti_qs[:20])
        except Exception:
            context["clienti_totale"] = 0
            context["clienti"] = []
        try:
            fornitori_qs = Fornitore.objects.filter(gruppo=self.object.codice).order_by(
                "ragione_sociale1", "codice"
            )
            context["fornitori_totale"] = fornitori_qs.count()
            context["fornitori"] = list(fornitori_qs[:20])
        except Exception:
            context["fornitori_totale"] = 0
            context["fornitori"] = []
        return context


class RaggruppamentoCliforCreateView(LoginRequiredMixin, View):
    template_name = "raggruppamento_clifor/raggruppamento_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": RaggruppamentoCliforForm(),
                "is_create": True,
                "page_heading": "Nuovo raggruppamento",
            },
        )

    def post(self, request):
        form = RaggruppamentoCliforForm(request.POST)
        if form.is_valid():
            item = save_mirror_form_instance(form)
            messages.success(request, f"Raggruppamento {item.codice} creato.")
            return redirect("raggruppamento_clifor:detail", codice=item.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo raggruppamento",
            },
        )


class RaggruppamentoCliforUpdateView(LoginRequiredMixin, View):
    template_name = "raggruppamento_clifor/raggruppamento_form.html"

    def get_object(self, codice):
        return get_object_or_404(RaggruppamentoClifor, pk=codice)

    def get(self, request, codice):
        item = self.get_object(codice)
        form = RaggruppamentoCliforForm(instance=item, codice_readonly=True)
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
        form = RaggruppamentoCliforForm(
            request.POST, instance=item, codice_readonly=True
        )
        if form.is_valid():
            item = save_mirror_form_instance(form)
            messages.success(request, f"Raggruppamento {item.codice} aggiornato.")
            return redirect("raggruppamento_clifor:detail", codice=item.codice)
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


class RaggruppamentoCliforDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        item = get_object_or_404(RaggruppamentoClifor, pk=codice)
        label = item.codice
        item.delete()
        messages.success(request, f"Raggruppamento {label} eliminato.")
        return redirect("raggruppamento_clifor:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncRaggruppamentoCliforView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "raggruppamento_clifor/sync_raggruppamento.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "raggruppamento_count": _pg_table_count("raggruppamento_clifor"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_raggruppamento_clifor()
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
