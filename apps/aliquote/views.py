from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.aliquote.forms import AliquotaForm
from apps.aliquote.models import Aliquota
from apps.aliquote.sync import sync_aliquote
from apps.core.mirror_crud import mirror_row_to_campi, stamp_modifica
from apps.core.navigation import related_back
from apps.core.sync_incremental import sync_full_from_request
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.export_list import ExportListMixin
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin


def _registrazione_back_from_request(request) -> tuple[str | None, str]:
    return related_back(request)


def _filter_aliquote_queryset(request):
    qs = Aliquota.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(natura_cod_ese_edi__icontains=q)
            | Q(des_ese_edi__icontains=q)
            | Q(tipo_esigibilita__icontains=q)
        )
    return qs.order_by("codice")


def _aliquote_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["totale"] = safe_mirror_count(Aliquota.objects)
    return context


def fetch_aliquota_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM aliquote WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class AliquotaListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Aliquota
    template_name = "aliquote/aliquota_list.html"
    context_object_name = "aliquote"
    sortable_fields = (
        "codice",
        "descrizione",
        "percentuale",
        "natura_cod_ese_edi",
        "tipo_esigibilita",
        "fl_reverse_charge",
    )
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_aliquote_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _aliquote_list_context(self, context)


class AliquotaPrintListView(MirrorPrintListView):
    print_title = "Aliquote IVA"
    print_subtitle = "Elenco aliquote IVA"
    filter_queryset = staticmethod(_filter_aliquote_queryset)
    sortable_fields = ("codice", "descrizione", "percentuale", "natura_cod_ese_edi", "tipo_esigibilita", "fl_reverse_charge")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "percentuale", "label": "% IVA", "percent": True},
        {"field": "natura_cod_ese_edi", "label": "Natura SDI"},
        {"field": "tipo_esigibilita", "label": "Esigibilità"},
        {"field": "fl_reverse_charge", "label": "Reverse charge", "bool": True},
    )


class AliquotaExportListView(ExportListMixin, AliquotaPrintListView):
    export_filename = "aliquote"


class AliquotaDetailView(LoginRequiredMixin, DetailView):
    model = Aliquota
    template_name = "aliquote/aliquota_detail.html"
    context_object_name = "aliquota"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_aliquota_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        back_url, back_label = _registrazione_back_from_request(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context

class AliquotaCreateView(LoginRequiredMixin, View):
    template_name = "aliquote/aliquota_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": AliquotaForm(),
                "is_create": True,
                "page_heading": "Nuova aliquota",
            },
        )

    def post(self, request):
        form = AliquotaForm(request.POST)
        if form.is_valid():
            aliquota = form.save(commit=False)
            stamp_modifica(aliquota)
            aliquota.save()
            messages.success(request, f"Aliquota {aliquota.codice} creata.")
            return redirect("aliquote:detail", codice=aliquota.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": "Nuova aliquota",
            },
        )


class AliquotaUpdateView(LoginRequiredMixin, View):
    template_name = "aliquote/aliquota_form.html"

    def get_object(self, codice):
        return get_object_or_404(Aliquota, pk=codice)

    def _ctx(self, request, form, *, aliquota, is_create: bool):
        back_url, back_label = _registrazione_back_from_request(request)
        return {
            "form": form,
            "aliquota": aliquota,
            "is_create": is_create,
            "page_heading": "Nuova aliquota" if is_create else "Modifica aliquota",
            "back_url": back_url,
            "back_label": back_label,
        }

    def get(self, request, codice):
        aliquota = self.get_object(codice)
        form = AliquotaForm(instance=aliquota, codice_readonly=True)
        return render(
            request,
            self.template_name,
            self._ctx(request, form, aliquota=aliquota, is_create=False),
        )

    def post(self, request, codice):
        aliquota = self.get_object(codice)
        form = AliquotaForm(request.POST, instance=aliquota, codice_readonly=True)
        if form.is_valid():
            aliquota = form.save(commit=False)
            stamp_modifica(aliquota)
            aliquota.save()
            messages.success(request, f"Aliquota {aliquota.codice} aggiornata.")
            from django.urls import reverse
            from urllib.parse import urlencode

            detail = reverse("aliquote:detail", kwargs={"codice": aliquota.codice})
            back_url, _ = _registrazione_back_from_request(request)
            if back_url:
                return redirect(f"{detail}?{urlencode({'next': back_url})}")
            return redirect(detail)
        return render(
            request,
            self.template_name,
            self._ctx(request, form, aliquota=aliquota, is_create=False),
        )


class AliquotaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        aliquota = get_object_or_404(Aliquota, pk=codice)
        label = aliquota.codice
        aliquota.delete()
        messages.success(request, f"Aliquota {label} eliminata.")
        return redirect("aliquote:list")


def _unique_aliquota_codice(base: str) -> str:
    raw = (base or "COPIA").strip() or "COPIA"
    candidate = f"{raw}_C"
    if not Aliquota.objects.filter(pk=candidate).exists():
        return candidate
    n = 2
    while n < 1000:
        candidate = f"{raw}_{n}"
        if not Aliquota.objects.filter(pk=candidate).exists():
            return candidate
        n += 1
    return f"{raw}_{n}"


class AliquotaDuplicateView(LoginRequiredMixin, View):
    template_name = "aliquote/aliquota_form.html"

    def post(self, request, codice):
        src = get_object_or_404(Aliquota, pk=codice)
        initial = {
            name: getattr(src, name)
            for name in AliquotaForm.Meta.fields
            if name != "codice"
        }
        initial["codice"] = _unique_aliquota_codice(src.codice)
        form = AliquotaForm(initial=initial)
        messages.info(
            request,
            f"Copia di {src.codice}: verifica il nuovo codice e salva.",
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "is_create": True,
                "page_heading": f"Duplica aliquota ({src.codice})",
            },
        )


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncAliquoteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "aliquote/sync_aliquote.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "aliquote_count": _pg_table_count("aliquote"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_aliquote(full=sync_full_from_request(request))
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
