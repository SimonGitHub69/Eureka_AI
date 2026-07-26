from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import DetailView, ListView

from apps.anagrafiche.models import Agente, Cliente, Fornitore
from apps.core.pagination import PerPageListMixin


def _filter_anagrafica_queryset(model, request):
    qs = model.objects.all()

    q = (request.GET.get("q") or "").strip()
    stato = (request.GET.get("stato") or "").strip()

    if q:
        filters = (
            Q(codice__icontains=q)
            | Q(ragione_sociale1__icontains=q)
            | Q(ragione_sociale2__icontains=q)
            | Q(partita_iva__icontains=q)
            | Q(cod_fiscale__icontains=q)
            | Q(localita__icontains=q)
            | Q(email__icontains=q)
            | Q(telefono__icontains=q)
        )
        qs = qs.filter(filters)

    if stato == "attivi":
        qs = qs.filter(Q(fl_disattivato=False) | Q(fl_disattivato__isnull=True))
    elif stato == "disattivi":
        qs = qs.filter(fl_disattivato=True)

    return qs.order_by("ragione_sociale1", "codice")


def _anagrafica_list_context(view, model, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["stato"] = (view.request.GET.get("stato") or "").strip()
    context["has_filters"] = bool(context["q"] or context["stato"])
    try:
        context["totale"] = model.objects.count()
    except Exception:
        context["totale"] = 0
    return context


class ClienteListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Cliente
    template_name = "anagrafiche/cliente_list.html"
    context_object_name = "clienti"
    paginate_by = 50

    def get_queryset(self):
        return _filter_anagrafica_queryset(Cliente, self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _anagrafica_list_context(self, Cliente, context)


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = "anagrafiche/cliente_detail.html"
    context_object_name = "cliente"
    pk_url_kwarg = "codice"


class FornitoreListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Fornitore
    template_name = "anagrafiche/fornitore_list.html"
    context_object_name = "fornitori"
    paginate_by = 50

    def get_queryset(self):
        return _filter_anagrafica_queryset(Fornitore, self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _anagrafica_list_context(self, Fornitore, context)


class FornitoreDetailView(LoginRequiredMixin, DetailView):
    model = Fornitore
    template_name = "anagrafiche/fornitore_detail.html"
    context_object_name = "fornitore"
    pk_url_kwarg = "codice"


def _filter_agente_queryset(request):
    qs = Agente.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(ragione_sociale__icontains=q)
            | Q(email__icontains=q)
        )

    return qs.order_by("ragione_sociale", "codice")


def _agente_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    try:
        context["totale"] = Agente.objects.count()
    except Exception:
        context["totale"] = 0
    return context


class AgenteListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Agente
    template_name = "anagrafiche/agente_list.html"
    context_object_name = "agenti"
    paginate_by = 50

    def get_queryset(self):
        return _filter_agente_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _agente_list_context(self, context)


class AgenteDetailView(LoginRequiredMixin, DetailView):
    model = Agente
    template_name = "anagrafiche/agente_detail.html"
    context_object_name = "agente"
    pk_url_kwarg = "codice"
