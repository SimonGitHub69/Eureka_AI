from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mirror_crud import (
    apply_control_widgets,
    mirror_row_to_campi,
    save_mirror_form_instance,
    stamp_modifica,
)
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.documenti.models import Porto


class PortoForm(forms.ModelForm):
    class Meta:
        model = Porto
        fields = ["descrizione", "cod_incoterm"]
        labels = {
            "descrizione": "Descrizione",
            "cod_incoterm": "Incoterm",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descrizione"].required = True
        self.fields["cod_incoterm"].required = False
        apply_control_widgets(self)


def _filter_porto_queryset(request):
    qs = Porto.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        filters = Q(descrizione__icontains=q) | Q(cod_incoterm__icontains=q)
        if q.isdigit():
            filters |= Q(id=int(q))
        qs = qs.filter(filters)
    return qs.order_by("descrizione", "id")


def _porto_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Porto.objects)
    return context


def fetch_porto_row(pk: int) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM tab_porto WHERE "ID" = %s', [pk])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


def next_porto_id() -> int:
    last = Porto.objects.aggregate(Max("id"))["id__max"] or 0
    return int(last) + 1


class PortoListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = Porto
    template_name = "documenti/porto_list.html"
    context_object_name = "porti"
    sortable_fields = ("descrizione", "cod_incoterm", "id")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "id"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_porto_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _porto_list_context(self, context)


class PortoPrintListView(MirrorPrintListView):
    print_title = "Porto"
    print_subtitle = "Elenco porti"
    filter_queryset = staticmethod(_filter_porto_queryset)
    sortable_fields = ("descrizione", "cod_incoterm", "id")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "id"
    print_columns = (
        {"field": "id", "label": "ID"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "cod_incoterm", "label": "Incoterm"},
    )


class PortoExportListView(ExportListMixin, PortoPrintListView):
    export_filename = "porto"


class PortoDetailView(LoginRequiredMixin, DetailView):
    model = Porto
    template_name = "documenti/porto_detail.html"
    context_object_name = "porto"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_porto_row(self.object.pk) or []
        context["campi"] = mirror_row_to_campi(row)
        return context


class PortoCreateView(LoginRequiredMixin, View):
    template_name = "documenti/porto_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": PortoForm(),
                "is_create": True,
                "page_heading": "Nuovo porto",
            },
        )

    def post(self, request):
        form = PortoForm(request.POST)
        if form.is_valid():
            porto = form.save(commit=False)
            porto.id = next_porto_id()
            stamp_modifica(porto)
            porto.save()
            messages.success(request, f"Porto {porto.descrizione} creato.")
            return redirect("documenti:porto_detail", pk=porto.pk)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuovo porto",
            },
        )


class PortoUpdateView(LoginRequiredMixin, View):
    template_name = "documenti/porto_form.html"

    def get_object(self, pk):
        return get_object_or_404(Porto, pk=pk)

    def get(self, request, pk):
        porto = self.get_object(pk)
        return render(
            request,
            self.template_name,
            {
                "form": PortoForm(instance=porto),
                "porto": porto,
                "is_create": False,
                "page_heading": "Modifica porto",
            },
        )

    def post(self, request, pk):
        porto = self.get_object(pk)
        form = PortoForm(request.POST, instance=porto)
        if form.is_valid():
            porto = save_mirror_form_instance(form)
            messages.success(request, f"Porto {porto.descrizione} aggiornato.")
            return redirect("documenti:porto_detail", pk=porto.pk)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "porto": porto,
                "is_create": False,
                "page_heading": "Modifica porto",
            },
        )


class PortoDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        porto = get_object_or_404(Porto, pk=pk)
        label = porto.descrizione or str(porto.pk)
        porto.delete()
        messages.success(request, f"Porto {label} eliminato.")
        return redirect("documenti:porto_list")
