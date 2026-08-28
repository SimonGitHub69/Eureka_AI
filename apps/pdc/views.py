from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

from apps.anagrafiche.partitario import (
    PARTITARIO_SORT_FIELDS,
    build_partitario,
    default_periodo,
    sort_partitario_righe,
)
from apps.aziende.configurazione import PDC_NOLEGGIO_DB_COLUMNS, is_azienda_noleggio
from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.navigation import related_back
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin, resolve_sort
from apps.pdc.forms import PianoContiForm
from apps.pdc.gruppo import raggruppamento_label, raggruppamento_map
from apps.pdc.hierarchy import (
    LIVELLO_CONTO,
    LIVELLO_LABELS,
    LIVELLO_MASTRO,
    LIVELLO_SOTTOCONTO,
    pdc_breadcrumb,
    pdc_create_context,
    pdc_hierarchy_context,
    pdc_is_contropartita,
    pdc_level_nav,
    pdc_list_livello,
    pdc_list_regex,
    pdc_list_title,
    pdc_mastro_codice,
)
from apps.pdc.models import PianoConti
from apps.pdc.sync import sync_pdc


def _filter_pdc_queryset(request):
    if request.GET.get("ai") == "1":
        qs = PianoConti.objects.all()
        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(codice__icontains=q)
                | Q(descrizione__icontains=q)
                | Q(tipo__icontains=q)
                | Q(tipo_conto__icontains=q)
                | Q(gruppo__icontains=q)
                | Q(desc_conto__icontains=q)
            )
        return qs.order_by("codice")

    mastro = (request.GET.get("mastro") or "").strip()
    conto = (request.GET.get("conto") or "").strip()
    gruppo = (request.GET.get("gruppo") or "").strip()
    vista = (request.GET.get("vista") or "").strip()

    if gruppo and not mastro and not conto:
        qs = PianoConti.objects.filter(gruppo=gruppo)
    else:
        qs = PianoConti.objects.filter(
            codice__regex=pdc_list_regex(mastro or None, conto or None, vista or None)
        )
        if gruppo:
            qs = qs.filter(gruppo=gruppo)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(tipo__icontains=q)
            | Q(tipo_conto__icontains=q)
            | Q(gruppo__icontains=q)
            | Q(desc_conto__icontains=q)
        )
    return qs.order_by("codice")


def _pdc_list_context(view, context):
    request = view.request
    if request.GET.get("ai") == "1":
        params = request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (request.GET.get("q") or "").strip()
        context["has_filters"] = True
        context["ai_mode"] = True
        context["list_title"] = "Risultati ricerca AI"
        context["list_livello"] = 2
        context["list_livello_label"] = "Tutti i livelli"
        context["mastro"] = ""
        context["conto"] = ""
        context["vista"] = ""
        context["gruppo"] = ""
        context["gruppo_label"] = ""
        context["gruppo_map"] = raggruppamento_map()
        context["breadcrumb"] = []
        context["level_nav"] = []
        context["totale"] = safe_mirror_count(_filter_pdc_queryset(request))
        return context

    mastro = (request.GET.get("mastro") or "").strip()
    conto = (request.GET.get("conto") or "").strip()
    vista = (request.GET.get("vista") or "").strip()

    if conto and not mastro:
        mastro = pdc_mastro_codice(conto)

    params = request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (request.GET.get("q") or "").strip()
    context["has_filters"] = bool(context["q"])
    context["mastro"] = mastro
    context["conto"] = conto
    context["vista"] = vista
    context["gruppo"] = (request.GET.get("gruppo") or "").strip()
    context["gruppo_map"] = raggruppamento_map()
    if context["gruppo"]:
        context["gruppo_label"] = raggruppamento_label(
            context["gruppo"], context["gruppo_map"]
        )
    else:
        context["gruppo_label"] = ""
    context["list_livello"] = pdc_list_livello(mastro or None, conto or None, vista or None)
    if context["gruppo"] and not mastro and not conto:
        context["list_title"] = (
            f"Conti collegati · {context['gruppo_label'] or context['gruppo']}"
        )
        context["list_livello_label"] = "Tutti i livelli"
    else:
        context["list_title"] = pdc_list_title(mastro or None, conto or None, vista or None)
        context["list_livello_label"] = LIVELLO_LABELS[context["list_livello"]]
    context["breadcrumb"] = pdc_breadcrumb(mastro or None, conto or None, vista or None)
    context["level_nav"] = pdc_level_nav(mastro or None, conto or None, vista or None)
    context["totale"] = safe_mirror_count(_filter_pdc_queryset(request))
    return context


def fetch_pdc_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM pdc WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


def _form_page_heading(is_create: bool, livello: int, codice: str = "") -> str:
    label = LIVELLO_LABELS.get(livello, "Conto")
    if is_create:
        return f"Nuovo {label.lower()}"
    return f"Modifica {label.lower()} {codice}".strip()


def _form_context(
    request,
    form,
    is_create: bool,
    conto=None,
    livello: int | None = None,
    mastro: str | None = None,
    conto_parent: str | None = None,
):
    if conto and livello is None:
        hierarchy = pdc_hierarchy_context(conto.codice)
        livello = hierarchy["livello"]
        ctx = {
            "form": form,
            "conto": conto,
            "is_create": is_create,
            "livello": livello,
            "livello_label": hierarchy["livello_label"],
            "descrizione_mastro": hierarchy["descrizione_mastro"],
            "descrizione_conto": hierarchy["descrizione_conto"],
            "mastro_codice": hierarchy["mastro_codice"],
            "conto_codice": hierarchy["conto_codice"] or "",
            "codice_prefix": getattr(form, "codice_prefix", ""),
            "breadcrumb": hierarchy["breadcrumb"],
            "page_heading": _form_page_heading(is_create, livello, conto.codice),
            "azienda_noleggio": is_azienda_noleggio(),
        }
    else:
        create_ctx = pdc_create_context(
            livello or LIVELLO_MASTRO,
            mastro=mastro,
            conto=conto_parent,
        )
        ctx = {
            "form": form,
            "conto": conto,
            "is_create": is_create,
            "livello": create_ctx["livello"],
            "livello_label": create_ctx["livello_label"],
            "descrizione_mastro": create_ctx["descrizione_mastro"],
            "descrizione_conto": create_ctx["descrizione_conto"],
            "mastro_codice": create_ctx["mastro_codice"],
            "conto_codice": create_ctx["conto_codice"],
            "codice_prefix": form.codice_prefix if hasattr(form, "codice_prefix") else "",
            "breadcrumb": create_ctx["breadcrumb"],
            "page_heading": _form_page_heading(is_create, create_ctx["livello"]),
            "azienda_noleggio": is_azienda_noleggio(),
        }
    return ctx


class PdcListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = PianoConti
    template_name = "pdc/pdc_list.html"
    context_object_name = "conti"
    sortable_fields = ("codice", "descrizione", "tipo_conto", "gruppo")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_pdc_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _pdc_list_context(self, context)


class PdcPrintListView(MirrorPrintListView):
    print_title = "Piano dei Conti"
    print_subtitle = "Elenco conti"
    filter_queryset = staticmethod(_filter_pdc_queryset)
    sortable_fields = ("codice", "descrizione", "tipo_conto", "gruppo")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "tipo_conto", "label": "Tipo conto"},
        {"field": "gruppo", "label": "Gruppo"},
    )


class PdcDetailView(LoginRequiredMixin, DetailView):
    model = PianoConti
    template_name = "pdc/pdc_detail.html"
    context_object_name = "conto"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hierarchy = pdc_hierarchy_context(self.object.codice)
        row = fetch_pdc_row(self.object.codice) or []
        gruppo_map = raggruppamento_map()
        context.update(hierarchy)
        context["gruppo_map"] = gruppo_map
        context["gruppo_label"] = raggruppamento_label(
            self.object.gruppo, gruppo_map
        )
        context["campi"] = mirror_row_to_campi(row)
        if not is_azienda_noleggio():
            context["campi"] = [
                (name, value)
                for name, value in context["campi"]
                if name not in PDC_NOLEGGIO_DB_COLUMNS
            ]
        context["children_url"] = None
        if self.object.livello == LIVELLO_MASTRO:
            context["children_url"] = f"?mastro={self.object.codice}"
            context["children_label"] = "Conti"
        elif self.object.livello == LIVELLO_CONTO:
            context["children_url"] = (
                f"?mastro={self.object.codice_mastro}&conto={self.object.codice}"
            )
            context["children_label"] = "Sottoconti"
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context


class PdcCreateView(LoginRequiredMixin, View):
    template_name = "pdc/pdc_form.html"

    def get_livello_params(self, request):
        livello_raw = (
            request.GET.get("livello")
            or request.POST.get("livello")
            or "mastro"
        ).strip().lower()
        livello_map = {
            "mastro": LIVELLO_MASTRO,
            "conto": LIVELLO_CONTO,
            "sottoconto": LIVELLO_SOTTOCONTO,
        }
        livello = livello_map.get(livello_raw, LIVELLO_MASTRO)
        mastro = (
            request.GET.get("mastro") or request.POST.get("mastro") or ""
        ).strip()
        conto = (request.GET.get("conto") or request.POST.get("conto") or "").strip()
        if livello == LIVELLO_CONTO and not mastro:
            livello = LIVELLO_MASTRO
        if livello == LIVELLO_SOTTOCONTO and not conto:
            livello = LIVELLO_CONTO if mastro else LIVELLO_MASTRO
        parent_prefix = ""
        if livello == LIVELLO_CONTO:
            parent_prefix = mastro
        elif livello == LIVELLO_SOTTOCONTO:
            parent_prefix = conto
        return livello, mastro, conto, parent_prefix

    def get(self, request):
        livello, mastro, conto, parent_prefix = self.get_livello_params(request)
        return render(
            request,
            self.template_name,
            _form_context(
                request,
                PianoContiForm(
                    livello=livello,
                    parent_prefix=parent_prefix,
                    azienda_noleggio=is_azienda_noleggio(),
                ),
                is_create=True,
                livello=livello,
                mastro=mastro,
                conto_parent=conto,
            ),
        )

    def post(self, request):
        livello, mastro, conto, parent_prefix = self.get_livello_params(request)
        form = PianoContiForm(
            request.POST,
            livello=livello,
            parent_prefix=parent_prefix,
            azienda_noleggio=is_azienda_noleggio(),
        )
        if form.is_valid():
            conto_obj = save_mirror_form_instance(form)
            messages.success(
                request,
                f"{LIVELLO_LABELS[livello]} {conto_obj.codice} creato.",
            )
            return redirect("pdc:detail", codice=conto_obj.codice)
        if form.errors.get("codice") or form.errors.get("codice_suffix"):
            messages.error(
                request,
                "Codice non valido o già esistente: verifica il campo codice.",
            )
        return render(
            request,
            self.template_name,
            _form_context(
                request,
                form,
                is_create=True,
                livello=livello,
                mastro=mastro,
                conto_parent=conto,
            ),
        )


class PdcUpdateView(LoginRequiredMixin, View):
    template_name = "pdc/pdc_form.html"

    def get_object(self, codice):
        return get_object_or_404(PianoConti, pk=codice)

    def get(self, request, codice):
        conto = self.get_object(codice)
        form = PianoContiForm(
            instance=conto,
            codice_readonly=True,
            livello=conto.livello,
            azienda_noleggio=is_azienda_noleggio(),
        )
        return render(
            request,
            self.template_name,
            _form_context(request, form, is_create=False, conto=conto),
        )

    def post(self, request, codice):
        conto = self.get_object(codice)
        form = PianoContiForm(
            request.POST,
            instance=conto,
            codice_readonly=True,
            livello=conto.livello,
            azienda_noleggio=is_azienda_noleggio(),
        )
        if form.is_valid():
            conto = save_mirror_form_instance(form)
            messages.success(request, f"{conto.livello_label} {conto.codice} aggiornato.")
            return redirect("pdc:detail", codice=conto.codice)
        return render(
            request,
            self.template_name,
            _form_context(request, form, is_create=False, conto=conto),
        )


class PdcDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        conto = get_object_or_404(PianoConti, pk=codice)
        label = f"{conto.livello_label} {conto.codice}"
        mastro = (request.POST.get("mastro") or "").strip()
        conto_parent = (request.POST.get("conto") or "").strip()
        conto.delete()
        messages.success(request, f"{label} eliminato.")
        if conto_parent:
            return redirect(
                reverse("pdc:list")
                + f"?mastro={mastro}&conto={conto_parent}"
            )
        if mastro:
            return redirect(reverse("pdc:list") + f"?mastro={mastro}")
        return redirect("pdc:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class PdcPartitarioView(LoginRequiredMixin, View):
    """Partitario (mastrino) sul sottoconto PDC — stesse regole di clienti/fornitori."""

    def get(self, request, codice):
        conto = get_object_or_404(PianoConti, pk=codice)
        if not pdc_is_contropartita(conto.codice):
            raise Http404("Il partitario è disponibile solo per i sottoconti.")

        default_da, default_a = default_periodo()
        data_da = parse_date((request.GET.get("data_da") or "").strip()) or default_da
        data_a = parse_date((request.GET.get("data_a") or "").strip()) or default_a
        if data_da > data_a:
            data_da, data_a = data_a, data_da

        result = build_partitario(
            conto.codice,
            kind="P",
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
        movimenti = [
            r for r in result.righe if not r.is_saldo_precedente and not r.is_totale
        ]
        return render(
            request,
            "anagrafiche/partitario.html",
            {
                "conto": conto,
                "subject": conto,
                "subject_label": "Sottoconto",
                "subject_detail_label": "Dettaglio",
                "kind": "P",
                "detail_url_name": "pdc:detail",
                "list_url_name": "pdc:list",
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


class SyncPdcView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "pdc/sync_pdc.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "pdc_count": _pg_table_count("pdc"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_pdc()
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
