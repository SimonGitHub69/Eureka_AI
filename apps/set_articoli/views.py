from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.articoli.lookups import descrizione_articolo, descrizione_fornitore
from apps.core.export_list import ExportListMixin
from apps.core.mirror_crud import stamp_modifica
from apps.core.navigation import redirect_with_back, related_back
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.set_articoli.forms import SetArticoloDForm, SetArticoloHForm
from apps.set_articoli.models import SetArticoloD, SetArticoloH
from apps.set_articoli.sync import sync_set_articoli


def _next_header_id() -> int:
    current = SetArticoloH.objects.aggregate(m=Max("id"), n=Max("numero_set"))
    return max(int(current["m"] or 0), int(current["n"] or 0)) + 1


def _next_riga_id() -> int:
    current = SetArticoloD.objects.aggregate(m=Max("id"))["m"] or 0
    return int(current) + 1


def _next_pos(testa: SetArticoloH) -> int:
    current = testa.righe.aggregate(m=Max("pos"))["m"] or 0
    return int(current) + 10


def _filter_set_queryset(request):
    qs = SetArticoloH.objects.annotate(n_righe=Count("righe", distinct=True))
    q = (request.GET.get("q") or "").strip()
    stato = (request.GET.get("stato") or "").strip()
    fornitore = (request.GET.get("fornitore") or "").strip()

    if q:
        filters = (
            Q(nome_set__icontains=q)
            | Q(fornitore__icontains=q)
            | Q(note__icontains=q)
            | Q(righe__cod_art__icontains=q)
            | Q(righe__desc_art__icontains=q)
        )
        if q.isdigit():
            filters |= Q(numero_set=int(q)) | Q(id=int(q))
        qs = qs.filter(filters).distinct()
    if fornitore:
        qs = qs.filter(fornitore__iexact=fornitore)
    if stato == "attivi":
        qs = qs.filter(Q(disattivato=False) | Q(disattivato__isnull=True))
    elif stato == "disattivi":
        qs = qs.filter(disattivato=True)

    return qs.order_by("numero_set", "nome_set", "id")


def _set_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["stato"] = (view.request.GET.get("stato") or "").strip()
    context["fornitore"] = (view.request.GET.get("fornitore") or "").strip()
    context["has_filters"] = bool(
        context["q"] or context["stato"] or context["fornitore"]
    )
    context["totale"] = safe_mirror_count(SetArticoloH.objects)
    return context


def _header_form_context(form, *, is_create: bool, set_h=None, labels=None, request=None):
    ctx = {
        "form": form,
        "set_h": set_h,
        "is_create": is_create,
        "page_heading": "Nuovo set articoli" if is_create else "Modifica set articoli",
        "lookup_url": reverse("articoli:lookup_codice"),
        "labels": labels or {},
        "list_url": reverse("set_articoli:list"),
    }
    if request is not None:
        back_url, back_label = related_back(request)
        ctx["back_url"] = back_url
        ctx["back_label"] = back_label
        ctx["exit_url"] = back_url or ctx["list_url"]
    else:
        ctx["exit_url"] = ctx["list_url"]
    return ctx


def _riga_form_context(form, *, set_h, riga=None, is_create: bool, labels=None):
    return {
        "form": form,
        "set_h": set_h,
        "riga": riga,
        "is_create": is_create,
        "page_heading": "Nuova riga set" if is_create else "Modifica riga set",
        "lookup_url": reverse("articoli:lookup_codice"),
        "labels": labels or {},
    }


class SetArticoloListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = SetArticoloH
    template_name = "set_articoli/set_list.html"
    context_object_name = "set_list"
    sortable_fields = ("numero_set", "nome_set", "data_set", "fornitore", "n_righe")
    default_sort = "numero_set"
    default_dir = "asc"
    sort_tiebreaker = "id"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_set_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _set_list_context(self, context)


class SetArticoloPrintListView(MirrorPrintListView):
    print_title = "Set articoli"
    print_subtitle = "Elenco set articoli"
    filter_queryset = staticmethod(_filter_set_queryset)
    sortable_fields = ("numero_set", "nome_set", "data_set", "fornitore", "n_righe")
    default_sort = "numero_set"
    default_dir = "asc"
    sort_tiebreaker = "id"
    print_columns = (
        {"field": "numero_set", "label": "N."},
        {"field": "nome_set", "label": "Nome"},
        {"field": "data_set", "label": "Data"},
        {"field": "fornitore", "label": "Fornitore"},
        {"field": "n_righe", "label": "Righe", "align": "end"},
    )


class SetArticoloExportListView(ExportListMixin, SetArticoloPrintListView):
    export_filename = "set_articoli"


class SetArticoloDetailView(LoginRequiredMixin, DetailView):
    model = SetArticoloH
    template_name = "set_articoli/set_detail.html"
    context_object_name = "set_h"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["righe"] = list(self.object.righe.order_by("pos", "id"))
        context["list_url"] = reverse("set_articoli:list")
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        context["exit_url"] = back_url or context["list_url"]
        context["fornitore_descrizione"] = descrizione_fornitore(self.object.fornitore)
        if self.object.fornitore:
            context["fornitore_url"] = reverse(
                "anagrafiche:fornitore_detail",
                kwargs={"codice": self.object.fornitore},
            )
        else:
            context["fornitore_url"] = ""
        return context


class SetArticoloCreateView(LoginRequiredMixin, View):
    template_name = "set_articoli/set_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            _header_form_context(SetArticoloHForm(), is_create=True, request=request),
        )

    def post(self, request):
        form = SetArticoloHForm(request.POST)
        if form.is_valid():
            set_h = form.save(commit=False)
            set_h.id = _next_header_id()
            if not set_h.numero_set:
                set_h.numero_set = set_h.id
            if set_h.disattivato is None:
                set_h.disattivato = False
            if set_h.controllo_doc is None:
                set_h.controllo_doc = False
            stamp_modifica(set_h)
            set_h.save(force_insert=True)
            messages.success(request, f"Set articoli {set_h.numero_set} creato.")
            return redirect_with_back(
                request,
                reverse("set_articoli:detail", kwargs={"pk": set_h.id}),
            )
        return render(
            request,
            self.template_name,
            _header_form_context(form, is_create=True, request=request),
        )


class SetArticoloUpdateView(LoginRequiredMixin, View):
    template_name = "set_articoli/set_form.html"

    def get_object(self, pk):
        return get_object_or_404(SetArticoloH, pk=pk)

    def get(self, request, pk):
        set_h = self.get_object(pk)
        form = SetArticoloHForm(instance=set_h)
        labels = {"fornitore": descrizione_fornitore(set_h.fornitore)}
        return render(
            request,
            self.template_name,
            _header_form_context(
                form, is_create=False, set_h=set_h, labels=labels, request=request
            ),
        )

    def post(self, request, pk):
        set_h = self.get_object(pk)
        form = SetArticoloHForm(request.POST, instance=set_h)
        if form.is_valid():
            set_h = form.save(commit=False)
            stamp_modifica(set_h)
            set_h.save()
            messages.success(request, f"Set articoli {set_h.numero_set} aggiornato.")
            return redirect_with_back(
                request,
                reverse("set_articoli:detail", kwargs={"pk": set_h.id}),
            )
        labels = {
            "fornitore": descrizione_fornitore(form.data.get("fornitore") or set_h.fornitore)
        }
        return render(
            request,
            self.template_name,
            _header_form_context(
                form, is_create=False, set_h=set_h, labels=labels, request=request
            ),
        )


class SetArticoloDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        set_h = get_object_or_404(SetArticoloH, pk=pk)
        label = set_h.numero_set or set_h.id
        SetArticoloD.objects.filter(testa_id=set_h.id).delete()
        set_h.delete()
        messages.success(request, f"Set articoli {label} eliminato.")
        return redirect_with_back(
            request,
            reverse("set_articoli:list"),
            preserve_on_fallback=False,
        )

class SetArticoloRigaCreateView(LoginRequiredMixin, View):
    template_name = "set_articoli/riga_form.html"

    def get(self, request, pk):
        set_h = get_object_or_404(SetArticoloH, pk=pk)
        form = SetArticoloDForm(initial={"pos": _next_pos(set_h)}, testa=set_h)
        return render(
            request,
            self.template_name,
            _riga_form_context(form, set_h=set_h, is_create=True),
        )

    def post(self, request, pk):
        set_h = get_object_or_404(SetArticoloH, pk=pk)
        form = SetArticoloDForm(request.POST, testa=set_h)
        if form.is_valid():
            riga = form.save(commit=False)
            riga.id = _next_riga_id()
            riga.testa = set_h
            if riga.pos is None:
                riga.pos = _next_pos(set_h)
            stamp_modifica(riga)
            riga.save(force_insert=True)
            messages.success(request, f"Riga {riga.cod_art} aggiunta.")
            return redirect("set_articoli:detail", pk=set_h.id)
        labels = {"cod_art": descrizione_articolo(form.data.get("cod_art"))}
        return render(
            request,
            self.template_name,
            _riga_form_context(form, set_h=set_h, is_create=True, labels=labels),
        )


class SetArticoloRigaUpdateView(LoginRequiredMixin, View):
    template_name = "set_articoli/riga_form.html"

    def _get(self, pk, riga_id):
        set_h = get_object_or_404(SetArticoloH, pk=pk)
        riga = get_object_or_404(SetArticoloD, pk=riga_id, testa=set_h)
        return set_h, riga

    def get(self, request, pk, riga_id):
        set_h, riga = self._get(pk, riga_id)
        form = SetArticoloDForm(instance=riga, testa=set_h)
        labels = {"cod_art": descrizione_articolo(riga.cod_art)}
        return render(
            request,
            self.template_name,
            _riga_form_context(
                form, set_h=set_h, riga=riga, is_create=False, labels=labels
            ),
        )

    def post(self, request, pk, riga_id):
        set_h, riga = self._get(pk, riga_id)
        form = SetArticoloDForm(request.POST, instance=riga, testa=set_h)
        if form.is_valid():
            riga = form.save(commit=False)
            stamp_modifica(riga)
            riga.save()
            messages.success(request, f"Riga {riga.cod_art} aggiornata.")
            return redirect("set_articoli:detail", pk=set_h.id)
        labels = {"cod_art": descrizione_articolo(form.data.get("cod_art") or riga.cod_art)}
        return render(
            request,
            self.template_name,
            _riga_form_context(
                form, set_h=set_h, riga=riga, is_create=False, labels=labels
            ),
        )


class SetArticoloRigaDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, riga_id):
        set_h = get_object_or_404(SetArticoloH, pk=pk)
        riga = get_object_or_404(SetArticoloD, pk=riga_id, testa=set_h)
        label = riga.cod_art or riga.id
        riga.delete()
        messages.success(request, f"Riga {label} eliminata.")
        return redirect("set_articoli:detail", pk=set_h.id)


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncSetArticoliView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "set_articoli/sync_set_articoli.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "set_h_count": _pg_table_count("set_articoli_h"),
            "set_d_count": _pg_table_count("set_articoli_d"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_set_articoli()
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
