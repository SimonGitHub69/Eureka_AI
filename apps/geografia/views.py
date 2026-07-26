from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from apps.core.pagination import PerPageListMixin
from apps.geografia.models import Citta, Provincia, Regione


class RegioneListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Regione
    template_name = "geografia/regione_list.html"
    context_object_name = "regioni"
    paginate_by = 50

    def get_queryset(self):
        qs = Regione.objects.annotate(
            n_province=Count("province", distinct=True),
            n_citta=Count("province__citta", distinct=True),
        )
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(codice__icontains=q) | Q(nome__icontains=q))
        return qs.order_by("nome")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["has_filters"] = bool(context["q"])
        context["totale"] = Regione.objects.count()
        return context


class RegioneDetailView(LoginRequiredMixin, DetailView):
    model = Regione
    template_name = "geografia/regione_detail.html"
    context_object_name = "regione"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["province"] = (
            self.object.province.annotate(n_citta=Count("citta"))
            .order_by("nome")
        )
        return context


class ProvinciaListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Provincia
    template_name = "geografia/provincia_list.html"
    context_object_name = "province"
    paginate_by = 50

    def get_queryset(self):
        qs = Provincia.objects.select_related("regione").annotate(
            n_citta=Count("citta")
        )
        q = (self.request.GET.get("q") or "").strip()
        regione = (self.request.GET.get("regione") or "").strip()
        if q:
            qs = qs.filter(
                Q(sigla__icontains=q)
                | Q(nome__icontains=q)
                | Q(codice_istat__icontains=q)
                | Q(regione__nome__icontains=q)
            )
        if regione:
            qs = qs.filter(regione_id=regione)
        return qs.order_by("nome")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["regione"] = (self.request.GET.get("regione") or "").strip()
        context["has_filters"] = bool(context["q"] or context["regione"])
        context["totale"] = Provincia.objects.count()
        context["regioni"] = Regione.objects.order_by("nome")
        return context


class ProvinciaDetailView(LoginRequiredMixin, DetailView):
    model = Provincia
    template_name = "geografia/provincia_detail.html"
    context_object_name = "provincia"
    pk_url_kwarg = "sigla"

    def get_queryset(self):
        return Provincia.objects.select_related("regione")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["citta"] = self.object.citta.order_by("nome")
        return context


class CittaListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Citta
    template_name = "geografia/citta_list.html"
    context_object_name = "citta_list"
    paginate_by = 50

    def get_queryset(self):
        qs = Citta.objects.select_related("provincia", "provincia__regione")
        q = (self.request.GET.get("q") or "").strip()
        provincia = (self.request.GET.get("provincia") or "").strip().upper()
        regione = (self.request.GET.get("regione") or "").strip()
        if q:
            qs = qs.filter(
                Q(nome__icontains=q)
                | Q(codice_istat__icontains=q)
                | Q(cap__icontains=q)
                | Q(codice_catastale__icontains=q)
                | Q(provincia__nome__icontains=q)
                | Q(provincia__sigla__icontains=q)
            )
        if provincia:
            qs = qs.filter(provincia_id=provincia)
        if regione:
            qs = qs.filter(provincia__regione_id=regione)
        return qs.order_by("nome", "codice_istat")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["provincia"] = (self.request.GET.get("provincia") or "").strip().upper()
        context["regione"] = (self.request.GET.get("regione") or "").strip()
        context["has_filters"] = bool(
            context["q"] or context["provincia"] or context["regione"]
        )
        context["totale"] = Citta.objects.count()
        context["regioni"] = Regione.objects.order_by("nome")
        context["province"] = Provincia.objects.select_related("regione").order_by("nome")
        return context


class CittaDetailView(LoginRequiredMixin, DetailView):
    model = Citta
    template_name = "geografia/citta_detail.html"
    context_object_name = "citta"
    pk_url_kwarg = "codice_istat"

    def get_queryset(self):
        return Citta.objects.select_related("provincia", "provincia__regione")
