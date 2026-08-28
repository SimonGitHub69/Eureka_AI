from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.pagination import PerPageListMixin
from apps.core.sorting import SortableListMixin
from apps.documenti.forms import (
    ColonnaRigaFormSet,
    ContatoreDocumentoForm,
    TipoDocumentoForm,
)
from apps.documenti.layout import seed_colonne_riga_default
from apps.documenti.models import ContatoreDocumento, TipoDocumento


def _filter_parametri_queryset(request):
    qs = TipoDocumento.objects.all()
    q = (request.GET.get("q") or "").strip()
    categoria = (request.GET.get("categoria") or "").strip()
    clifor = (request.GET.get("clifor") or "").strip().upper()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(label__icontains=q)
            | Q(descrizione__icontains=q)
        )
    if categoria:
        qs = qs.filter(categoria=categoria)
    if clifor:
        qs = qs.filter(clifor_tipo=clifor)
    return qs


def _parametri_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["categoria"] = (view.request.GET.get("categoria") or "").strip()
    context["clifor"] = (view.request.GET.get("clifor") or "").strip().upper()
    context["has_filters"] = bool(context["q"] or context["categoria"] or context["clifor"])
    context["categorie"] = TipoDocumento.CATEGORIA_CHOICES
    context["clifor_choices"] = TipoDocumento.CLIFOR_CHOICES
    context["totale"] = TipoDocumento.objects.count()
    return context


class ParametriDocumentoListView(
    LoginRequiredMixin, SortableListMixin, PerPageListMixin, ListView
):
    model = TipoDocumento
    template_name = "documenti/parametri_list.html"
    context_object_name = "parametri"
    sortable_fields = (
        "codice",
        "label",
        "categoria",
        "clifor_tipo",
        "scadenze",
        "contatore",
        "serie",
        "ordine",
        "attivo",
    )
    default_sort = "ordine"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_queryset(self):
        return self.apply_sorting(
            _filter_parametri_queryset(self.request).select_related("contatore")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _parametri_list_context(self, context)


class ParametriDocumentoDetailView(LoginRequiredMixin, DetailView):
    model = TipoDocumento
    template_name = "documenti/parametri_detail.html"
    context_object_name = "parametro"
    pk_url_kwarg = "codice"

    def get_queryset(self):
        return super().get_queryset().select_related("contatore")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["colonne_formset"] = ColonnaRigaFormSet(instance=self.object)
        return context


class ParametriDocumentoColonneView(LoginRequiredMixin, View):
    def get_object(self, codice):
        return get_object_or_404(TipoDocumento, pk=codice)

    def post(self, request, codice):
        parametro = self.get_object(codice)
        if request.POST.get("ripristina_default"):
            seed_colonne_riga_default(parametro, force=True)
            messages.success(request, f"Colonne riga di {parametro.codice} ripristinate.")
            return redirect("documenti:parametri_detail", codice=parametro.codice)

        formset = ColonnaRigaFormSet(request.POST, instance=parametro)
        if formset.is_valid():
            formset.save()
            messages.success(request, f"Colonne riga di {parametro.codice} aggiornate.")
            return redirect("documenti:parametri_detail", codice=parametro.codice)
        return render(
            request,
            "documenti/parametri_detail.html",
            {
                "parametro": parametro,
                "colonne_formset": formset,
            },
        )


class ParametriDocumentoCreateView(LoginRequiredMixin, View):
    template_name = "documenti/parametri_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": TipoDocumentoForm(),
                "is_create": True,
                "page_heading": "Nuovo parametro documento",
            },
        )

    def post(self, request):
        form = TipoDocumentoForm(request.POST)
        if form.is_valid():
            parametro = form.save()
            messages.success(request, f"Parametro documento {parametro.codice} creato.")
            return redirect("documenti:parametri_detail", codice=parametro.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo parametro documento",
            },
        )


class ParametriDocumentoUpdateView(LoginRequiredMixin, View):
    template_name = "documenti/parametri_form.html"

    def get_object(self, codice):
        return get_object_or_404(TipoDocumento, pk=codice)

    def get(self, request, codice):
        parametro = self.get_object(codice)
        form = TipoDocumentoForm(instance=parametro, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "parametro": parametro,
                "is_create": False,
                "page_heading": "Modifica parametro documento",
            },
        )

    def post(self, request, codice):
        parametro = self.get_object(codice)
        form = TipoDocumentoForm(request.POST, instance=parametro, codice_readonly=True)
        if form.is_valid():
            parametro = form.save()
            messages.success(request, f"Parametro documento {parametro.codice} aggiornato.")
            return redirect("documenti:parametri_detail", codice=parametro.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "parametro": parametro,
                "is_create": False,
                "page_heading": "Modifica parametro documento",
            },
        )


class ParametriDocumentoDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        parametro = get_object_or_404(TipoDocumento, pk=codice)
        label = parametro.codice
        try:
            parametro.delete()
        except ProtectedError:
            messages.error(
                request,
                f"Impossibile eliminare {label}: esistono documenti collegati.",
            )
            return redirect("documenti:parametri_detail", codice=label)
        messages.success(request, f"Parametro documento {label} eliminato.")
        return redirect("documenti:parametri_list")


def _filter_contatori_queryset(request):
    qs = ContatoreDocumento.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(label__icontains=q))
    tipo = (request.GET.get("tipo") or "").strip().upper()
    if tipo in dict(ContatoreDocumento.TIPO_CHOICES):
        qs = qs.filter(tipo_contatore=tipo)
    return qs


class ContatoriDocumentoListView(
    LoginRequiredMixin, SortableListMixin, PerPageListMixin, ListView
):
    model = ContatoreDocumento
    template_name = "documenti/contatore_list.html"
    context_object_name = "contatori"
    sortable_fields = (
        "codice",
        "label",
        "tipo_contatore",
        "esercizio",
        "ultimo_numero",
        "serie_default",
    )
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_queryset(self):
        return self.apply_sorting(_filter_contatori_queryset(self.request))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["tipo"] = (self.request.GET.get("tipo") or "").strip().upper()
        context["tipo_choices"] = ContatoreDocumento.TIPO_CHOICES
        context["has_filters"] = bool(context["q"] or context["tipo"])
        context["totale"] = ContatoreDocumento.objects.count()
        return context


class ContatoriDocumentoDetailView(LoginRequiredMixin, DetailView):
    model = ContatoreDocumento
    template_name = "documenti/contatore_detail.html"
    context_object_name = "contatore"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Q

        context["tipi_collegati"] = list(
            TipoDocumento.objects.filter(
                Q(contatore=self.object) | Q(contatori=self.object)
            )
            .distinct()
            .order_by("ordine", "codice")
        )
        return context


class ContatoriDocumentoCreateView(LoginRequiredMixin, View):
    template_name = "documenti/contatore_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": ContatoreDocumentoForm(),
                "is_create": True,
                "page_heading": "Nuovo contatore",
            },
        )

    def post(self, request):
        form = ContatoreDocumentoForm(request.POST)
        if form.is_valid():
            contatore = form.save()
            messages.success(request, f"Contatore {contatore.codice} creato.")
            return redirect("documenti:contatori_detail", pk=contatore.pk)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo contatore",
            },
        )


class ContatoriDocumentoUpdateView(LoginRequiredMixin, View):
    template_name = "documenti/contatore_form.html"

    def get_object(self, pk):
        return get_object_or_404(ContatoreDocumento, pk=pk)

    def get(self, request, pk):
        contatore = self.get_object(pk)
        form = ContatoreDocumentoForm(instance=contatore, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "contatore": contatore,
                "is_create": False,
                "page_heading": "Modifica contatore",
            },
        )

    def post(self, request, pk):
        contatore = self.get_object(pk)
        form = ContatoreDocumentoForm(
            request.POST, instance=contatore, codice_readonly=True
        )
        if form.is_valid():
            contatore = form.save()
            messages.success(request, f"Contatore {contatore.codice} aggiornato.")
            return redirect("documenti:contatori_detail", pk=contatore.pk)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "contatore": contatore,
                "is_create": False,
                "page_heading": "Modifica contatore",
            },
        )


def _next_esercizio_libero(src: ContatoreDocumento) -> int:
    year = int(src.esercizio or 0) + 1
    while ContatoreDocumento.objects.filter(
        codice=src.codice,
        tipo_contatore=src.tipo_contatore,
        esercizio=year,
    ).exists():
        year += 1
    return year


class ContatoriDocumentoDuplicateView(LoginRequiredMixin, View):
    template_name = "documenti/contatore_form.html"

    def post(self, request, pk):
        src = get_object_or_404(ContatoreDocumento, pk=pk)
        if "codice" in request.POST:
            form = ContatoreDocumentoForm(request.POST)
            if form.is_valid():
                contatore = form.save()
                messages.success(request, f"Contatore {contatore.codice} creato.")
                return redirect("documenti:contatori_detail", pk=contatore.pk)
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "is_create": True,
                    "page_heading": f"Duplica contatore ({src.codice} · {src.esercizio})",
                },
            )
        initial = {
            "codice": src.codice,
            "label": src.label,
            "tipo_contatore": src.tipo_contatore,
            "esercizio": _next_esercizio_libero(src),
            "ultimo_numero": 0,
            "serie_default": src.serie_default,
        }
        form = ContatoreDocumentoForm(initial=initial)
        messages.info(
            request,
            f"Copia di {src.codice} · {src.esercizio}: verifica esercizio e salva.",
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": f"Duplica contatore ({src.codice} · {src.esercizio})",
            },
        )


class ContatoriDocumentoDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        contatore = get_object_or_404(ContatoreDocumento, pk=pk)
        label = f"{contatore.codice} · {contatore.esercizio}"
        if (
            contatore.tipi_documento.exists()
            or contatore.tipi_documento_multi.exists()
        ):
            messages.error(
                request,
                f"Impossibile eliminare {label}: è associato a uno o più tipi documento.",
            )
            return redirect("documenti:contatori_detail", pk=contatore.pk)
        try:
            contatore.delete()
        except ProtectedError:
            messages.error(
                request,
                f"Impossibile eliminare {label}: è associato a uno o più tipi documento.",
            )
            return redirect("documenti:contatori_detail", pk=contatore.pk)
        messages.success(request, f"Contatore {label} eliminato.")
        return redirect("documenti:contatori_list")
