from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

from apps.anagrafiche.codice_fiscale import cf_eligible, check_anagrafica_cf
from apps.anagrafiche.forms import AgenteForm, ClienteForm, FornitoreForm
from apps.anagrafiche.lookups import (
    agente_display,
    condizione_display,
    form_linked_labels,
)
from apps.anagrafiche.models import Agente, Cliente, Fornitore, get_by_codice
from apps.anagrafiche.partitario import (
    PARTITARIO_SORT_FIELDS,
    build_partitario,
    default_periodo,
    sort_partitario_righe,
)
from apps.anagrafiche.vies import check_anagrafica_vat, parse_vat_input, vies_eligible
from apps.anagrafiche.vies_views import _load_vies_payload
from apps.core.mirror_crud import stamp_modifica
from apps.core.navigation import related_back
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.sorting import SortableListMixin, resolve_sort
from apps.destinazioni.models import destinazioni_for_anagrafica


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
    context["totale"] = safe_mirror_count(model.objects)
    return context


def _vies_detail_context(subject, subject_label: str) -> dict:
    return {
        "vies_eligible": vies_eligible(subject.partita_iva, subject.cod_nazione),
        "vies_input": parse_vat_input(subject.partita_iva, subject.cod_nazione),
        "subject_label": subject_label,
    }


def _cf_detail_context(subject) -> dict:
    persona_fisica = getattr(subject, "persona_fisica", None)
    cf_check = check_anagrafica_cf(
        subject.cod_fiscale,
        subject.cod_nazione,
        partita_iva=subject.partita_iva,
        persona_fisica=persona_fisica,
    )
    return {
        "cf_eligible": cf_eligible(subject.cod_fiscale, subject.cod_nazione),
        "cf_check": cf_check,
    }


def _destinazioni_detail_context(codice: str) -> dict:
    from django.db.utils import OperationalError, ProgrammingError

    try:
        destinazioni = list(destinazioni_for_anagrafica(codice))
    except (ProgrammingError, OperationalError):
        destinazioni = []
    return {
        "destinazioni": destinazioni,
        "destinazione_codice": (codice or "").strip(),
    }


def _destinazioni_form_context(*, is_create: bool, instance=None) -> dict:
    """Destinazioni card on create/edit: full list on edit, 'salva prima' on create."""
    if is_create or instance is None:
        return {
            "destinazioni": [],
            "destinazione_codice": "",
            "destinazioni_salva_prima": True,
        }
    ctx = _destinazioni_detail_context(getattr(instance, "codice", "") or "")
    ctx["destinazioni_salva_prima"] = False
    return ctx


def _anagrafica_form_context(form, *, is_create: bool, page_heading: str, **extra) -> dict:
    context = {
        "form": form,
        "is_create": is_create,
        "page_heading": page_heading,
        "labels": form_linked_labels(form),
        "lookup_url": reverse("articoli:lookup_codice"),
    }
    context.update(extra)
    return context


class ClienteListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Cliente
    template_name = "anagrafiche/cliente_list.html"
    context_object_name = "clienti"
    sortable_fields = ("ragione_sociale1", "localita", "partita_iva", "email", "telefono", "codice")
    default_sort = "ragione_sociale1"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_anagrafica_queryset(Cliente, self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _anagrafica_list_context(self, Cliente, context)


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = "anagrafiche/cliente_detail.html"
    context_object_name = "cliente"
    pk_url_kwarg = "codice"

    def get_object(self, queryset=None):
        obj = get_by_codice(Cliente, self.kwargs.get(self.pk_url_kwarg))
        if obj is None:
            raise Http404("Cliente non trovato")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            _vies_detail_context(
                self.object,
                "Cliente",
            )
        )
        context.update(_cf_detail_context(self.object))
        context["cond_paga_display"] = condizione_display(self.object.cond_paga)
        context["agente_display"] = agente_display(self.object.agente)
        context["agente2_display"] = agente_display(self.object.agente2)
        context.update(_destinazioni_detail_context(self.object.codice))
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context


class ClienteViesCheckView(LoginRequiredMixin, View):
    def post(self, request, codice):
        cliente = get_object_or_404(Cliente, pk=codice)
        payload = _load_vies_payload(request)
        partita_iva = payload.get("partita_iva") or cliente.partita_iva
        cod_nazione = payload.get("cod_nazione") or cliente.cod_nazione
        result = check_anagrafica_vat(partita_iva, cod_nazione)
        status = 200 if result.ok or not result.eligible else 503
        return JsonResponse(result.to_dict(), status=status)


class ClienteCreateView(LoginRequiredMixin, View):
    template_name = "anagrafiche/cliente_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                ClienteForm(auto_codice=True),
                is_create=True,
                page_heading="Nuovo cliente",
                **_destinazioni_form_context(is_create=True),
            ),
        )

    def post(self, request):
        form = ClienteForm(request.POST, auto_codice=True)
        if form.is_valid():
            cliente = form.save(commit=False)
            stamp_modifica(cliente)
            cliente.save()
            messages.success(request, f"Cliente {cliente.codice} creato.")
            return redirect("anagrafiche:cliente_detail", codice=cliente.codice)
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                form,
                is_create=True,
                page_heading="Nuovo cliente",
                **_destinazioni_form_context(is_create=True),
            ),
        )


class ClienteUpdateView(LoginRequiredMixin, View):
    template_name = "anagrafiche/cliente_form.html"

    def get_object(self, codice):
        obj = get_by_codice(Cliente, codice)
        if obj is None:
            raise Http404("Cliente non trovato")
        return obj

    def get(self, request, codice):
        cliente = self.get_object(codice)
        form = ClienteForm(instance=cliente, codice_readonly=True)
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                form,
                is_create=False,
                page_heading="Modifica cliente",
                cliente=cliente,
                **_destinazioni_form_context(is_create=False, instance=cliente),
            ),
        )

    def post(self, request, codice):
        cliente = self.get_object(codice)
        form = ClienteForm(request.POST, instance=cliente, codice_readonly=True)
        if form.is_valid():
            cliente = form.save(commit=False)
            stamp_modifica(cliente)
            cliente.save()
            messages.success(request, f"Cliente {cliente.codice} aggiornato.")
            return redirect("anagrafiche:cliente_detail", codice=cliente.codice)
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                form,
                is_create=False,
                page_heading="Modifica cliente",
                cliente=cliente,
                **_destinazioni_form_context(is_create=False, instance=cliente),
            ),
        )


class ClienteDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        cliente = get_object_or_404(Cliente, pk=codice)
        label = cliente.codice
        cliente.delete()
        messages.success(request, f"Cliente {label} eliminato.")
        return redirect("anagrafiche:clienti_list")


class FornitoreListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Fornitore
    template_name = "anagrafiche/fornitore_list.html"
    context_object_name = "fornitori"
    sortable_fields = ("ragione_sociale1", "localita", "partita_iva", "email", "telefono", "codice")
    default_sort = "ragione_sociale1"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_anagrafica_queryset(Fornitore, self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _anagrafica_list_context(self, Fornitore, context)


class FornitoreDetailView(LoginRequiredMixin, DetailView):
    model = Fornitore
    template_name = "anagrafiche/fornitore_detail.html"
    context_object_name = "fornitore"
    pk_url_kwarg = "codice"

    def get_object(self, queryset=None):
        obj = get_by_codice(Fornitore, self.kwargs.get(self.pk_url_kwarg))
        if obj is None:
            raise Http404("Fornitore non trovato")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            _vies_detail_context(
                self.object,
                "Fornitore",
            )
        )
        context.update(_cf_detail_context(self.object))
        context["cond_paga_display"] = condizione_display(self.object.cond_paga)
        context["agente_display"] = agente_display(self.object.agente)
        context.update(_destinazioni_detail_context(self.object.codice))
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context


class FornitoreViesCheckView(LoginRequiredMixin, View):
    def post(self, request, codice):
        fornitore = get_object_or_404(Fornitore, pk=codice)
        payload = _load_vies_payload(request)
        partita_iva = payload.get("partita_iva") or fornitore.partita_iva
        cod_nazione = payload.get("cod_nazione") or fornitore.cod_nazione
        result = check_anagrafica_vat(partita_iva, cod_nazione)
        status = 200 if result.ok or not result.eligible else 503
        return JsonResponse(result.to_dict(), status=status)


class FornitoreCreateView(LoginRequiredMixin, View):
    template_name = "anagrafiche/fornitore_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                FornitoreForm(auto_codice=True),
                is_create=True,
                page_heading="Nuovo fornitore",
                **_destinazioni_form_context(is_create=True),
            ),
        )

    def post(self, request):
        form = FornitoreForm(request.POST, auto_codice=True)
        if form.is_valid():
            fornitore = form.save(commit=False)
            stamp_modifica(fornitore)
            fornitore.save()
            messages.success(request, f"Fornitore {fornitore.codice} creato.")
            return redirect("anagrafiche:fornitore_detail", codice=fornitore.codice)
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                form,
                is_create=True,
                page_heading="Nuovo fornitore",
                **_destinazioni_form_context(is_create=True),
            ),
        )


class FornitoreUpdateView(LoginRequiredMixin, View):
    template_name = "anagrafiche/fornitore_form.html"

    def get_object(self, codice):
        obj = get_by_codice(Fornitore, codice)
        if obj is None:
            raise Http404("Fornitore non trovato")
        return obj

    def get(self, request, codice):
        fornitore = self.get_object(codice)
        form = FornitoreForm(instance=fornitore, codice_readonly=True)
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                form,
                is_create=False,
                page_heading="Modifica fornitore",
                fornitore=fornitore,
                **_destinazioni_form_context(is_create=False, instance=fornitore),
            ),
        )

    def post(self, request, codice):
        fornitore = self.get_object(codice)
        form = FornitoreForm(request.POST, instance=fornitore, codice_readonly=True)
        if form.is_valid():
            fornitore = form.save(commit=False)
            stamp_modifica(fornitore)
            fornitore.save()
            messages.success(request, f"Fornitore {fornitore.codice} aggiornato.")
            return redirect("anagrafiche:fornitore_detail", codice=fornitore.codice)
        return render(
            request,
            self.template_name,
            _anagrafica_form_context(
                form,
                is_create=False,
                page_heading="Modifica fornitore",
                fornitore=fornitore,
                **_destinazioni_form_context(is_create=False, instance=fornitore),
            ),
        )


class FornitoreDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        fornitore = get_object_or_404(Fornitore, pk=codice)
        label = fornitore.codice
        fornitore.delete()
        messages.success(request, f"Fornitore {label} eliminato.")
        return redirect("anagrafiche:fornitori_list")


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
    context["totale"] = safe_mirror_count(Agente.objects)
    return context


class AgenteListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Agente
    template_name = "anagrafiche/agente_list.html"
    context_object_name = "agenti"
    sortable_fields = ("ragione_sociale", "email", "provvigione", "listino", "codice")
    default_sort = "ragione_sociale"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_agente_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _agente_list_context(self, context)


class AgenteDetailView(LoginRequiredMixin, DetailView):
    model = Agente
    template_name = "anagrafiche/agente_detail.html"
    context_object_name = "agente"
    pk_url_kwarg = "codice"


class AgenteCreateView(LoginRequiredMixin, View):
    template_name = "anagrafiche/agente_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": AgenteForm(auto_codice=True),
                "is_create": True,
                "page_heading": "Nuovo agente",
            },
        )

    def post(self, request):
        form = AgenteForm(request.POST, auto_codice=True)
        if form.is_valid():
            agente = form.save(commit=False)
            stamp_modifica(agente)
            agente.save()
            messages.success(request, f"Agente {agente.codice} creato.")
            return redirect("anagrafiche:agente_detail", codice=agente.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo agente",
            },
        )


class AgenteUpdateView(LoginRequiredMixin, View):
    template_name = "anagrafiche/agente_form.html"

    def get_object(self, codice):
        return get_object_or_404(Agente, pk=codice)

    def get(self, request, codice):
        agente = self.get_object(codice)
        form = AgenteForm(instance=agente, codice_readonly=True)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "agente": agente,
                "is_create": False,
                "page_heading": "Modifica agente",
            },
        )

    def post(self, request, codice):
        agente = self.get_object(codice)
        form = AgenteForm(request.POST, instance=agente, codice_readonly=True)
        if form.is_valid():
            agente = form.save(commit=False)
            stamp_modifica(agente)
            agente.save()
            messages.success(request, f"Agente {agente.codice} aggiornato.")
            return redirect("anagrafiche:agente_detail", codice=agente.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "agente": agente,
                "is_create": False,
                "page_heading": "Modifica agente",
            },
        )


class AgenteDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        agente = get_object_or_404(Agente, pk=codice)
        label = agente.codice
        agente.delete()
        messages.success(request, f"Agente {label} eliminato.")
        return redirect("anagrafiche:agenti_list")


class _PartitarioBaseView(LoginRequiredMixin, View):
    """Maschera partitario (mastrino) su cliente o fornitore."""

    kind = "C"  # C | F
    model = Cliente
    detail_url_name = "anagrafiche:cliente_detail"
    list_url_name = "anagrafiche:clienti_list"
    subject_context_name = "cliente"
    subject_label = "Cliente"

    def get(self, request, codice):
        subject = get_by_codice(self.model, codice)
        if subject is None:
            raise Http404(f"{self.subject_label} non trovato")

        default_da, default_a = default_periodo()
        data_da = parse_date((request.GET.get("data_da") or "").strip()) or default_da
        data_a = parse_date((request.GET.get("data_a") or "").strip()) or default_a
        if data_da > data_a:
            data_da, data_a = data_a, data_da

        result = build_partitario(
            subject.codice,
            kind=self.kind,
            data_da=data_da,
            data_a=data_a,
        )
        sort, direction = resolve_sort(
            request,
            allowed=PARTITARIO_SORT_FIELDS,
            default_sort="data_reg",
            default_dir="asc",
        )
        result.righe = sort_partitario_righe(
            result.righe, sort=sort, direction=direction
        )
        movimenti = [r for r in result.righe if not r.is_saldo_precedente and not r.is_totale]
        return render(
            request,
            "anagrafiche/partitario.html",
            {
                self.subject_context_name: subject,
                "subject": subject,
                "subject_label": self.subject_label,
                "kind": self.kind,
                "detail_url_name": self.detail_url_name,
                "list_url_name": self.list_url_name,
                "partitario": result,
                "movimenti_count": len(movimenti),
                "data_da": data_da.isoformat(),
                "data_a": data_a.isoformat(),
                "data_da_default": default_da.isoformat(),
                "data_a_default": default_a.isoformat(),
                "sort": sort,
                "dir": direction,
            },
        )


class ClientePartitarioView(_PartitarioBaseView):
    kind = "C"
    model = Cliente
    detail_url_name = "anagrafiche:cliente_detail"
    list_url_name = "anagrafiche:clienti_list"
    subject_context_name = "cliente"
    subject_label = "Cliente"


class FornitorePartitarioView(_PartitarioBaseView):
    kind = "F"
    model = Fornitore
    detail_url_name = "anagrafiche:fornitore_detail"
    list_url_name = "anagrafiche:fornitori_list"
    subject_context_name = "fornitore"
    subject_label = "Fornitore"