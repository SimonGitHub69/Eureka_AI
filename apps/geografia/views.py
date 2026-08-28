from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.pagination import PerPageListMixin
from apps.core.export_list import ExportListMixin
from apps.core.print_list import PrintListView
from apps.core.sorting import SortableListMixin
from apps.geografia.forms import CittaForm, ProvinciaForm, RegioneForm
from apps.geografia.models import Citta, Provincia, Regione


class RegioneListView(LoginRequiredMixin, SortableListMixin, PerPageListMixin, ListView):
    model = Regione
    template_name = "geografia/regione_list.html"
    context_object_name = "regioni"
    sortable_fields = ("nome", "codice")
    default_sort = "nome"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_queryset(self):
        qs = Regione.objects.annotate(
            n_province=Count("province", distinct=True),
            n_citta=Count("province__citta", distinct=True),
        )
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(codice__icontains=q) | Q(nome__icontains=q))
        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["has_filters"] = bool(context["q"])
        context["totale"] = Regione.objects.count()
        return context


class RegionePrintListView(PrintListView):
    print_title = "Regioni"
    print_subtitle = "Anagrafica ISTAT Italia"
    sortable_fields = ("nome", "codice")
    default_sort = "nome"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice ISTAT"},
        {"field": "nome", "label": "Nome"},
    )

    def get_print_queryset(self):
        qs = Regione.objects.all()
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(codice__icontains=q) | Q(nome__icontains=q))
        return qs


class RegioneExportListView(ExportListMixin, RegionePrintListView):
    export_filename = "regioni"


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


class RegioneCreateView(LoginRequiredMixin, View):
    template_name = "geografia/regione_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": RegioneForm(),
                "is_create": True,
                "page_heading": "Nuova regione",
            },
        )

    def post(self, request):
        form = RegioneForm(request.POST)
        if form.is_valid():
            regione = form.save()
            messages.success(request, f"Regione {regione.codice} creata.")
            return redirect("geografia:regione_detail", codice=regione.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova regione",
            },
        )


class RegioneUpdateView(LoginRequiredMixin, View):
    template_name = "geografia/regione_form.html"

    def get_object(self, codice):
        return get_object_or_404(Regione, pk=codice)

    def get(self, request, codice):
        regione = self.get_object(codice)
        form = RegioneForm(instance=regione, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "regione": regione,
                "is_create": False,
                "page_heading": "Modifica regione",
            },
        )

    def post(self, request, codice):
        regione = self.get_object(codice)
        form = RegioneForm(request.POST, instance=regione, codice_readonly=True)
        if form.is_valid():
            regione = form.save()
            messages.success(request, f"Regione {regione.codice} aggiornata.")
            return redirect("geografia:regione_detail", codice=regione.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "regione": regione,
                "is_create": False,
                "page_heading": "Modifica regione",
            },
        )


class RegioneDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        regione = get_object_or_404(Regione, pk=codice)
        label = regione.codice
        regione.delete()
        messages.success(request, f"Regione {label} eliminata.")
        return redirect("geografia:regioni_list")


class ProvinciaListView(LoginRequiredMixin, SortableListMixin, PerPageListMixin, ListView):
    model = Provincia
    template_name = "geografia/provincia_list.html"
    context_object_name = "province"
    sortable_fields = ("nome", "sigla", "regione__nome", "codice_istat")
    default_sort = "nome"
    default_dir = "asc"
    sort_tiebreaker = "sigla"
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
        return self.apply_sorting(qs)

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


class ProvinciaPrintListView(PrintListView):
    print_title = "Province"
    print_subtitle = "Anagrafica ISTAT Italia"
    sortable_fields = ("nome", "sigla", "regione__nome", "codice_istat")
    default_sort = "nome"
    default_dir = "asc"
    sort_tiebreaker = "sigla"
    print_columns = (
        {"field": "sigla", "label": "Sigla"},
        {"field": "nome", "label": "Nome"},
        {"field": "regione__nome", "label": "Regione"},
        {"field": "codice_istat", "label": "Codice ISTAT"},
    )

    def get_print_queryset(self):
        qs = Provincia.objects.select_related("regione")
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
        return qs

    def get_filter_summary(self):
        parts = []
        q = (self.request.GET.get("q") or "").strip()
        regione = (self.request.GET.get("regione") or "").strip()
        if q:
            parts.append(f'Ricerca: "{q}"')
        if regione:
            parts.append(f"Regione: {regione}")
        return " · ".join(parts)


class ProvinciaExportListView(ExportListMixin, ProvinciaPrintListView):
    export_filename = "province"


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


class ProvinciaCreateView(LoginRequiredMixin, View):
    template_name = "geografia/provincia_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": ProvinciaForm(),
                "is_create": True,
                "page_heading": "Nuova provincia",
            },
        )

    def post(self, request):
        form = ProvinciaForm(request.POST)
        if form.is_valid():
            provincia = form.save()
            messages.success(request, f"Provincia {provincia.sigla} creata.")
            return redirect("geografia:provincia_detail", sigla=provincia.sigla)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova provincia",
            },
        )


class ProvinciaUpdateView(LoginRequiredMixin, View):
    template_name = "geografia/provincia_form.html"

    def get_object(self, sigla):
        return get_object_or_404(Provincia, pk=sigla)

    def get(self, request, sigla):
        provincia = self.get_object(sigla)
        form = ProvinciaForm(instance=provincia, sigla_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "provincia": provincia,
                "is_create": False,
                "page_heading": "Modifica provincia",
            },
        )

    def post(self, request, sigla):
        provincia = self.get_object(sigla)
        form = ProvinciaForm(request.POST, instance=provincia, sigla_readonly=True)
        if form.is_valid():
            provincia = form.save()
            messages.success(request, f"Provincia {provincia.sigla} aggiornata.")
            return redirect("geografia:provincia_detail", sigla=provincia.sigla)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "provincia": provincia,
                "is_create": False,
                "page_heading": "Modifica provincia",
            },
        )


class ProvinciaDeleteView(LoginRequiredMixin, View):
    def post(self, request, sigla):
        provincia = get_object_or_404(Provincia, pk=sigla)
        label = provincia.sigla
        provincia.delete()
        messages.success(request, f"Provincia {label} eliminata.")
        return redirect("geografia:province_list")


class CittaListView(LoginRequiredMixin, SortableListMixin, PerPageListMixin, ListView):
    model = Citta
    template_name = "geografia/citta_list.html"
    context_object_name = "citta_list"
    sortable_fields = ("nome", "provincia__nome", "provincia__sigla", "cap", "codice_istat")
    default_sort = "nome"
    default_dir = "asc"
    sort_tiebreaker = "codice_istat"
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
        return self.apply_sorting(qs)

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


class CittaPrintListView(PrintListView):
    print_title = "Città"
    print_subtitle = "Anagrafica ISTAT Italia"
    sortable_fields = ("nome", "provincia__nome", "provincia__sigla", "cap", "codice_istat")
    default_sort = "nome"
    default_dir = "asc"
    sort_tiebreaker = "codice_istat"
    print_columns = (
        {"field": "codice_istat", "label": "Codice ISTAT"},
        {"field": "nome", "label": "Nome"},
        {"field": "provincia__sigla", "label": "Provincia"},
        {"field": "cap", "label": "CAP"},
        {"field": "codice_catastale", "label": "Cod. catastale"},
    )

    def get_print_queryset(self):
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
        return qs

    def get_filter_summary(self):
        parts = []
        q = (self.request.GET.get("q") or "").strip()
        provincia = (self.request.GET.get("provincia") or "").strip().upper()
        regione = (self.request.GET.get("regione") or "").strip()
        if q:
            parts.append(f'Ricerca: "{q}"')
        if provincia:
            parts.append(f"Provincia: {provincia}")
        if regione:
            parts.append(f"Regione: {regione}")
        return " · ".join(parts)


class CittaExportListView(ExportListMixin, CittaPrintListView):
    export_filename = "citta"


class CittaDetailView(LoginRequiredMixin, DetailView):
    model = Citta
    template_name = "geografia/citta_detail.html"
    context_object_name = "citta"
    pk_url_kwarg = "codice_istat"

    def get_queryset(self):
        return Citta.objects.select_related("provincia", "provincia__regione")


class CittaCreateView(LoginRequiredMixin, View):
    template_name = "geografia/citta_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": CittaForm(),
                "is_create": True,
                "page_heading": "Nuova città",
            },
        )

    def post(self, request):
        form = CittaForm(request.POST)
        if form.is_valid():
            citta = form.save()
            messages.success(request, f"Città {citta.codice_istat} creata.")
            return redirect("geografia:citta_detail", codice_istat=citta.codice_istat)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova città",
            },
        )


class CittaUpdateView(LoginRequiredMixin, View):
    template_name = "geografia/citta_form.html"

    def get_object(self, codice_istat):
        return get_object_or_404(Citta, pk=codice_istat)

    def get(self, request, codice_istat):
        citta = self.get_object(codice_istat)
        form = CittaForm(instance=citta, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "citta": citta,
                "is_create": False,
                "page_heading": "Modifica città",
            },
        )

    def post(self, request, codice_istat):
        citta = self.get_object(codice_istat)
        form = CittaForm(request.POST, instance=citta, codice_readonly=True)
        if form.is_valid():
            citta = form.save()
            messages.success(request, f"Città {citta.codice_istat} aggiornata.")
            return redirect("geografia:citta_detail", codice_istat=citta.codice_istat)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "citta": citta,
                "is_create": False,
                "page_heading": "Modifica città",
            },
        )


class CittaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice_istat):
        citta = get_object_or_404(Citta, pk=codice_istat)
        label = citta.codice_istat
        citta.delete()
        messages.success(request, f"Città {label} eliminata.")
        return redirect("geografia:citta_list")
