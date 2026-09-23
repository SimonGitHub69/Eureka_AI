from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection, transaction
from django.db.models import DateField, Exists, OuterRef, Q
from django.db.models.functions import Cast
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

from apps.articoli.movimenti_magazzino import attach_prezzi_movimento_righe
from apps.core.navigation import related_back
from apps.depositi.lookups import depositi_by_codes
from apps.core.export_list import ExportListMixin, RawExportListMixin
from apps.core.mirror_crud import mirror_row_to_campi
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView, RawPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.movimenti.lookups import (
    attach_movimento_labels,
    format_anagrafica_display,
    format_causale_display,
)
from apps.movimenti.models import MovimentoT, MovimentoTDettaglio
from apps.movimenti.statistiche import (
    STATISTICHE_TIPI,
    articoli_da_set,
    default_causali_selection,
    elabora_statistiche,
    filter_summary,
    is_data_riga,
    list_causali,
    movimenti_count_preview,
    parse_period,
    resolve_articoli_selection,
    resolve_statistica_tipo,
    selected_articoli,
    selected_causali,
    selected_set_ids,
    statistica_tipo_label,
)
from apps.movimenti.sync import sync_movimenti
from apps.set_articoli.models import SetArticoloH


def _movimenti_articolo_filter(q: str) -> Q:
    """Movimenti con almeno una riga dettaglio che matcha codice o descrizione articolo."""
    from apps.articoli.models import Articolo

    text = (q or "").strip()
    if not text:
        return Q()
    dettaglio_codice = MovimentoTDettaglio.objects.filter(
        id_testa=OuterRef("pk"),
        codice_art__icontains=text,
    )
    dettaglio_desc = MovimentoTDettaglio.objects.filter(
        id_testa=OuterRef("pk"),
        codice_art__in=Articolo.objects.filter(descrizione__icontains=text).values(
            "codice"
        ),
    )
    return Q(Exists(dettaglio_codice)) | Q(Exists(dettaglio_desc))


def _filter_movimenti_queryset(request):
    qs = MovimentoT.objects.all()
    q = (request.GET.get("q") or "").strip()
    causale = (request.GET.get("causale") or "").strip()
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())

    if q:
        filters = (
            Q(causale__icontains=q)
            | Q(num_doc__icontains=q)
            | Q(cliente__icontains=q)
            | Q(fornitore__icontains=q)
            | Q(dep_entrata__icontains=q)
            | Q(dep_uscita__icontains=q)
        )
        if q.isdigit():
            n = int(q)
            filters |= Q(num_registraz=n) | Q(id_testa=n)
        filters |= _movimenti_articolo_filter(q)
        qs = qs.filter(filters)
    if causale:
        qs = qs.filter(causale__iexact=causale)
    if data_da or data_a:
        qs = qs.annotate(_data_reg_cal=Cast("data_registraz", DateField()))
    if data_da:
        qs = qs.filter(_data_reg_cal__gte=data_da)
    if data_a:
        qs = qs.filter(_data_reg_cal__lte=data_a)
    return qs.order_by("-data_registraz", "-num_registraz", "-id_testa")


def fetch_movimento_row(pk: int) -> list[tuple[str, object]] | None:
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute('SELECT * FROM movimentit WHERE "ID_Testa" = %s', [pk])
                row = cur.fetchone()
                if row is None:
                    return None
                columns = [col[0] for col in cur.description]
            return list(zip(columns, row))
    except (ProgrammingError, OperationalError):
        return None


def load_movimento_righe(id_testa: int) -> tuple[list, bool]:
    try:
        with transaction.atomic():
            righe = list(
                MovimentoTDettaglio.objects.filter(id_testa=id_testa).order_by(
                    "pos", "id"
                )
            )
            attach_prezzi_movimento_righe(righe)
            return righe, False
    except (ProgrammingError, OperationalError):
        return [], True


def _pg_table_count(table: str) -> int:
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                return cur.fetchone()[0]
    except (ProgrammingError, OperationalError):
        return 0


def _movimenti_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["causale"] = (view.request.GET.get("causale") or "").strip()
    context["data_da"] = (view.request.GET.get("data_da") or "").strip()
    context["data_a"] = (view.request.GET.get("data_a") or "").strip()
    context["has_filters"] = bool(
        context["q"] or context["causale"] or context["data_da"] or context["data_a"]
    )
    context["totale"] = safe_mirror_count(MovimentoT)
    return context


class MovimentoListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = MovimentoT
    template_name = "movimenti/movimento_list.html"
    context_object_name = "movimenti"
    sortable_fields = (
        "num_registraz",
        "data_registraz",
        "causale",
        "num_doc",
        "cliente",
        "fornitore",
        "id_testa",
    )
    default_sort = "data_registraz"
    default_dir = "desc"
    sort_tiebreaker = ("-num_registraz", "-id_testa")
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_movimenti_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attach_movimento_labels(context.get("movimenti") or [])
        return _movimenti_list_context(self, context)


class MovimentoPrintListView(MirrorPrintListView):
    print_title = "Movimenti magazzino"
    print_subtitle = "Elenco movimenti"
    filter_queryset = staticmethod(_filter_movimenti_queryset)
    sortable_fields = (
        "num_registraz",
        "data_registraz",
        "causale",
        "num_doc",
        "cliente",
        "fornitore",
        "id_testa",
    )
    default_sort = "data_registraz"
    default_dir = "desc"
    sort_tiebreaker = ("-num_registraz", "-id_testa")
    print_columns = (
        {"field": "num_registraz", "label": "N. reg."},
        {"field": "data_registraz", "label": "Data", "date": True},
        {"label": "Causale", "value": format_causale_display},
        {"field": "num_doc", "label": "Documento"},
        {
            "label": "Cliente",
            "value": lambda m: format_anagrafica_display(
                m.cliente, getattr(m, "cliente_ragione_sociale", "")
            ),
        },
        {
            "label": "Fornitore",
            "value": lambda m: format_anagrafica_display(
                m.fornitore, getattr(m, "fornitore_ragione_sociale", "")
            ),
        },
        {"field": "dep_entrata", "label": "Dep. entrata"},
        {"field": "dep_uscita", "label": "Dep. uscita"},
    )

    def get_queryset(self):
        if not self.print_preview_ready():
            return []
        rows = list(super().get_queryset())
        attach_movimento_labels(rows)
        return rows


class MovimentoExportListView(ExportListMixin, MovimentoPrintListView):
    export_filename = "movimenti"


class MovimentoDetailView(LoginRequiredMixin, DetailView):
    model = MovimentoT
    template_name = "movimenti/movimento_detail.html"
    context_object_name = "movimento"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attach_movimento_labels([self.object])
        row = fetch_movimento_row(self.object.pk) or []
        context["campi"] = mirror_row_to_campi(row)
        righe, dettaglio_mancante = load_movimento_righe(self.object.pk)
        context["righe"] = righe
        context["dettaglio_mancante"] = dettaglio_mancante
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        depositi = depositi_by_codes([self.object.dep_entrata, self.object.dep_uscita])
        context["dep_entrata_deposito"] = depositi.get((self.object.dep_entrata or "").strip().upper(), "")
        context["dep_uscita_deposito"] = depositi.get((self.object.dep_uscita or "").strip().upper(), "")
        return context



class SyncMovimentiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "movimenti/sync_movimenti.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "movimentit_count": _pg_table_count("movimentit"),
            "dettaglio_count": _pg_table_count("movimentit_dettaglio"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_movimenti(full=sync_full_from_request(request))
        message = "\n".join(t.message for t in result.tables) or result.message
        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)
        return render(request, self.template_name, self.get_context(message))


STATISTICHE_PRINT_COLUMNS = (
    {"field": "codice", "label": "Codice", "nowrap": True},
    {"field": "descrizione", "label": "Descrizione"},
    {"field": "quantita", "label": "Quantità", "align": "end", "decimals": 2},
    {"field": "valore_un", "label": "Val. Un.", "align": "end", "decimals": 3},
    {"field": "valore", "label": "Valore", "align": "end", "decimals": 2},
    {"field": "incidenza", "label": "% Incid.", "align": "end", "decimals": 2},
)


def _statistiche_params(request):
    get = request.GET
    data_da, data_a = parse_period(get)
    causali = selected_causali(get)
    if not causali and not (get.get("elabora") or get.get("anteprima")):
        causali = default_causali_selection()
    articolo_da = (get.get("articolo_da") or "").strip()
    articolo_a = (get.get("articolo_a") or "").strip()
    titolo = (get.get("titolo") or "Statistiche di Vendita").strip()
    tipo = resolve_statistica_tipo(get.get("tipo"))["key"]
    set_ids = selected_set_ids(get)
    articoli = selected_articoli(get)
    usa_set = (get.get("usa_set") or "").strip() in ("1", "true", "on", "yes")
    art_edit = (get.get("art_edit") or "").strip() in ("1", "true", "on", "yes")
    if not usa_set:
        set_ids = []
        articoli = []
    elif not art_edit and not articoli and set_ids:
        # Prima selezione set: espandi automaticamente le righe.
        articoli = [row["codice"] for row in articoli_da_set(set_ids)]
    anno = (get.get("anno") or "").strip()
    return {
        "data_da": data_da,
        "data_a": data_a,
        "causali": causali,
        "articolo_da": articolo_da,
        "articolo_a": articolo_a,
        "titolo": titolo or "Statistiche di Vendita",
        "tipo": tipo,
        "set_ids": set_ids,
        "articoli": articoli,
        "usa_set": usa_set,
        "art_edit": art_edit or bool(articoli),
        "anno": anno,
    }


def _set_labels(set_ids: list[int]) -> str:
    if not set_ids:
        return ""
    objs = {
        o.id: o
        for o in SetArticoloH.objects.filter(pk__in=set_ids).only(
            "id", "numero_set", "nome_set"
        )
    }
    labels = []
    for sid in set_ids:
        obj = objs.get(sid)
        labels.append(str(obj) if obj else f"#{sid}")
    return ", ".join(labels)


class StatisticheMagazzinoArticoliSetView(LoginRequiredMixin, View):
    """JSON: articoli (unione) dei set selezionati."""

    def get(self, request):
        set_ids = selected_set_ids(request.GET)
        rows = articoli_da_set(set_ids)
        return JsonResponse({"set_ids": set_ids, "count": len(rows), "articoli": rows})


class StatisticheMagazzinoView(LoginRequiredMixin, View):
    template_name = "movimenti/statistiche_magazzino.html"

    def get(self, request):
        params = _statistiche_params(request)
        elabora = (request.GET.get("elabora") or "").strip() in ("1", "true", "yes")
        causali_all = list_causali()
        selected = set(params["causali"])
        for c in causali_all:
            c.is_selected = c.codice in selected

        filter_articoli = params["articoli"] if params["usa_set"] else []
        filter_sets = (
            params["set_ids"] if params["usa_set"] and not filter_articoli else []
        )

        righe = []
        tot_qta = 0.0
        tot_val = 0.0
        preview_count = 0
        if elabora and params["causali"]:
            if params["usa_set"] and not filter_articoli and not filter_sets:
                righe = []
            else:
                righe = elabora_statistiche(
                    data_da=params["data_da"],
                    data_a=params["data_a"],
                    causali=params["causali"],
                    articolo_da=params["articolo_da"],
                    articolo_a=params["articolo_a"],
                    set_ids=filter_sets,
                    articoli=filter_articoli or None,
                    tipo=params["tipo"],
                )
            data_rows = [r for r in righe if is_data_riga(r)]
            tot_qta = sum(r.quantita for r in data_rows)
            tot_val = sum(r.valore for r in data_rows)
            preview_count = movimenti_count_preview(
                params["data_da"], params["data_a"], params["causali"]
            )
        elif params["causali"]:
            preview_count = movimenti_count_preview(
                params["data_da"], params["data_a"], params["causali"]
            )

        today = params["data_da"]
        anni = [today.year, today.year - 1]
        selected_sets = set(params["set_ids"])
        sets = list(
            SetArticoloH.objects.filter(Q(disattivato=False) | Q(disattivato__isnull=True))
            .order_by("numero_set", "nome_set")[:500]
        )
        for s in sets:
            s.is_selected = s.id in selected_sets

        articoli_sel = (
            resolve_articoli_selection(params["articoli"]) if params["usa_set"] else []
        )

        summary = filter_summary(
            titolo=params["titolo"],
            data_da=params["data_da"],
            data_a=params["data_a"],
            causali=params["causali"],
            articolo_da=params["articolo_da"],
            articolo_a=params["articolo_a"],
            set_label=_set_labels(params["set_ids"]) if params["usa_set"] else "",
            n_articoli=len(articoli_sel) if params["usa_set"] else 0,
            tipo_label=statistica_tipo_label(params["tipo"]),
        )

        return render(
            request,
            self.template_name,
            {
                **params,
                "data_da_str": params["data_da"].isoformat(),
                "data_a_str": params["data_a"].isoformat(),
                "causali_list": causali_all,
                "sets": sets,
                "articoli_sel": articoli_sel,
                "elabora": elabora,
                "righe": righe,
                "tot_qta": tot_qta,
                "tot_val": tot_val,
                "preview_count": preview_count,
                "anni_preset": anni,
                "filter_summary": summary,
                "n_righe": len([r for r in righe if is_data_riga(r)]),
                "tipi_statistica": STATISTICHE_TIPI,
                "tipo_label": statistica_tipo_label(params["tipo"]),
                "articoli_set_url": reverse("movimenti:statistiche_articoli_set"),
                "lookup_url": reverse("articoli:lookup_codice"),
            },
        )


class StatisticheMagazzinoPrintView(RawPrintListView):
    print_title = "Statistiche di Vendita"
    print_columns = STATISTICHE_PRINT_COLUMNS
    print_orientation = "portrait"
    print_subtitle = "Statistica : Articoli di Magazzino"  # aggiornato in get_object_list

    def get_object_list(self, request):
        params = _statistiche_params(request)
        self._params = params
        self.print_title = params["titolo"] or self.print_title
        self.print_subtitle = "Statistica : " + statistica_tipo_label(params["tipo"])
        filter_articoli = params["articoli"] if params["usa_set"] else []
        filter_sets = (
            params["set_ids"] if params["usa_set"] and not filter_articoli else []
        )
        if params["usa_set"] and not filter_articoli and not filter_sets:
            return []
        return elabora_statistiche(
            data_da=params["data_da"],
            data_a=params["data_a"],
            causali=params["causali"],
            articolo_da=params["articolo_da"],
            articolo_a=params["articolo_a"],
            set_ids=filter_sets,
            articoli=filter_articoli or None,
            tipo=params["tipo"],
        )

    def get_filter_summary(self, request) -> str:
        params = getattr(self, "_params", None) or _statistiche_params(request)
        da = params["data_da"].strftime("%d/%m/%y")
        a = params["data_a"].strftime("%d/%m/%y")
        parts = [f"Periodo dal : {da} al {a}"]
        if params.get("usa_set") and params.get("articoli"):
            parts.append(f"Selezione: {len(params['articoli'])} articoli")
        elif params.get("usa_set") and params.get("set_ids"):
            parts.append("Set: " + _set_labels(params["set_ids"]))
        return " · ".join(parts)

    def get(self, request):
        from django.shortcuts import render

        from apps.core.print_list import (
            format_it_number,
            print_export_request,
            print_header_cells,
            print_preview_requested,
            structured_print_row,
        )
        from apps.aziende.configurazione import resolve_print_azienda_context
        from django.utils import timezone

        preview_ready = print_preview_requested(request) or print_export_request(request)
        if preview_ready:
            object_list = self.get_object_list(request)
        else:
            object_list = []

        columns = self.print_columns
        structured = []
        tot_qta = 0.0
        tot_val = 0.0
        data_count = 0
        for obj in object_list:
            cells = []
            for col in columns:
                from apps.core.print_list import resolve_column_value

                cells.append(resolve_column_value(obj, col))
            kind = getattr(obj, "kind", "row") or "row"
            level = int(getattr(obj, "level", 0) or 0)
            row_class = ""
            if kind == "header":
                row_class = f"eureka-print-row--testata eureka-print-row--level-{level}"
            elif kind == "detail":
                row_class = f"eureka-print-row--dettaglio eureka-print-row--level-{level}"
            structured.append(
                structured_print_row(cells, columns, row_class=row_class)
            )
            if kind != "header":
                data_count += 1
                tot_qta += float(getattr(obj, "quantita", 0) or 0)
                tot_val += float(getattr(obj, "valore", 0) or 0)

        if object_list:
            blank = "—"
            structured.append(
                structured_print_row(
                    [
                        "",
                        "TOTALE",
                        format_it_number(tot_qta, decimals=2),
                        blank,
                        format_it_number(tot_val, decimals=2),
                        blank,
                    ],
                    columns,
                    row_class="eureka-print-row--totale",
                )
            )
            structured.append(
                structured_print_row(
                    [
                        "",
                        "TOTALE PERIODO",
                        blank,
                        blank,
                        format_it_number(tot_val, decimals=2),
                        format_it_number(100, decimals=2),
                    ],
                    columns,
                    row_class="eureka-print-row--totale",
                )
            )

        return render(
            request,
            self.template_name,
            {
                "print_title": self.print_title,
                "print_subtitle": self.print_subtitle,
                "print_headers": [c["label"] for c in columns],
                "print_header_cells": print_header_cells(columns),
                "print_rows": structured,
                "print_rows_structured": True,
                "print_count": data_count,
                "print_date": timezone.localdate(),
                "print_filter_summary": self.get_filter_summary(request)
                if preview_ready
                else "",
                "print_preview_ready": preview_ready,
                "print_filters_gate": True,
                **resolve_print_azienda_context(branding=self.print_branding),
            },
        )

class StatisticheMagazzinoExportView(RawExportListMixin, StatisticheMagazzinoPrintView):
    """Export CSV/XLSX dell'elaborazione (tutte le tipologiche)."""

    export_filename = "statistiche_magazzino"
    export_sheet_title = "Statistiche"
    export_default_fmt = "xlsx"

    def get_export_filename_stem(self) -> str:
        from django.utils import timezone

        params = getattr(self, "_params", None) or _statistiche_params(self.request)
        tipo = (params.get("tipo") or "articoli").strip() or "articoli"
        return f"statistiche_{tipo}_{timezone.localdate():%Y-%m-%d}"

    def get(self, request):
        from apps.core.export import export_table
        from apps.core.print_list import build_print_rows

        object_list = self.get_object_list(request)
        self.export_sheet_title = (self.print_subtitle or "Statistiche")[:31]
        headers, rows = build_print_rows(object_list, self.print_columns)
        return export_table(
            filename=self.get_export_filename_stem(),
            headers=headers,
            rows=rows,
            fmt=self.get_export_fmt(request),
            sheet_title=self.export_sheet_title,
            as_attachment=True,
        )

