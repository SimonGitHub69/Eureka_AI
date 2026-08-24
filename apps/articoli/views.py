from urllib.parse import unquote

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.db.models.functions import Trim, Upper
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.articoli.forms import ArticoloForm
from apps.articoli.giacenza import (
    attach_giacenze_articoli,
    attach_inventario_articoli,
    giacenza_articolo,
    giacenze_non_nulle,
    inventario_anomalia_counts,
    inventario_categorie_label,
    inventario_discrepanza_pct,
    inventario_discrepanza_soglia,
    inventario_filter_giacenza_non_zero,
    inventario_filter_solo_anomalie,
    inventario_gruppi_per_categoria,
    inventario_periodo_label,
    inventario_preset_urls,
    inventario_active_preset,
    inventario_row_class,
    inventario_row_classes,
    inventario_sort_per_categoria,
    inventario_totali,
    inventario_want_ignora_anomalie,
    inventario_want_rottura,
    inventario_want_solo_anomalie,
    parse_inventario_categorie,
    parse_inventario_periodo,
    prezzo_ultimo_acquisto_articolo,
)
from apps.core.print_list import (
    MirrorPrintListView,
    RawPrintListView,
    build_print_rows,
    format_it_number,
    print_header_cells,
    structured_print_row,
)
from apps.articoli.movimenti_magazzino import MOVIMENTI_ARTICOLO_PRINT_COLUMNS, ultime_date_movimenti
from apps.articoli.movimenti_periodo import (
    movimenti_articolo_for_request,
    movimenti_periodo_context,
    movimenti_print_filter_summary,
)
from apps.articoli.lookups import (
    LOOKUP_TIPI,
    attach_articoli_list_labels,
    linked_labels_for_articolo,
    resolve_articolo,
    resolve_clifor,
    resolve_descrizione,
    search_opzioni,
)
from apps.articoli.models import Articolo
from apps.core.navigation import related_back
from apps.core.mirror_crud import save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.sorting import SortableListMixin


def _distinta_list_root() -> str:
    return reverse("distinte_base:list")


def _distinta_selection_back_url(request) -> str | None:
    raw = unquote((request.GET.get("list_back") or "").strip())
    if raw and "//" not in raw:
        root = _distinta_list_root()
        if raw.startswith(root + "?"):
            return raw

    if (request.GET.get("from") or "").strip().lower() == "distinta":
        legacy = unquote((request.GET.get("distinta_back") or "").strip())
        root = _distinta_list_root()
        if legacy.startswith(root + "?") and "//" not in legacy:
            return legacy
    return None


def _distinta_articolo_back_url(request) -> str | None:
    if (request.GET.get("from") or "").strip().lower() != "distinta":
        return None
    raw = unquote((request.GET.get("distinta_back") or "").strip())
    if raw.startswith("/articoli/") and "//" not in raw:
        return raw
    return None


def _filter_articoli_queryset(request):
    qs = Articolo.objects.all()

    q = (request.GET.get("q") or "").strip()
    campo = (request.GET.get("campo") or "tutto").strip().lower()
    stato = (request.GET.get("stato") or "").strip()

    if q:
        if campo == "codice":
            filters = Q(codice__icontains=q)
        elif campo == "descrizione":
            filters = Q(descrizione__icontains=q)
        else:
            campo = "tutto"
            filters = (
                Q(codice__icontains=q)
                | Q(descrizione__icontains=q)
                | Q(cat_omogenea__icontains=q)
                | Q(cod_gruppo__icontains=q)
                | Q(cod_fornitore__icontains=q)
                | Q(codice_alternativo1__icontains=q)
                | Q(codice_alternativo2__icontains=q)
                | Q(cod_breve_art__icontains=q)
                | Q(cod_magazzino__icontains=q)
                | Q(unita_misura__icontains=q)
            )
        qs = qs.filter(filters)

    if stato == "attivi":
        qs = qs.filter(Q(fl_disattivato=False) | Q(fl_disattivato__isnull=True))
    elif stato == "disattivi":
        qs = qs.filter(fl_disattivato=True)

    return qs.order_by("descrizione", "codice")


def _articoli_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    campo = (view.request.GET.get("campo") or "tutto").strip().lower()
    if campo not in ("tutto", "codice", "descrizione"):
        campo = "tutto"
    context["campo"] = campo
    context["stato"] = (view.request.GET.get("stato") or "").strip()
    context["has_filters"] = bool(context["q"] or context["stato"])
    context["totale"] = safe_mirror_count(Articolo.objects)

    articoli = list(context.get("articoli") or context.get("object_list") or [])
    attach_articoli_list_labels(articoli)
    attach_giacenze_articoli(articoli)
    return context


def _form_linked_labels(form) -> dict[str, str]:
    if form.is_bound:
        data = form.data
        return {
            "magazzino": resolve_descrizione("magazzino", data.get("cod_magazzino")),
            "categoria": resolve_descrizione("categoria", data.get("cat_omogenea")),
            "gruppo": resolve_descrizione("gruppo", data.get("cod_gruppo")),
            "fornitore": resolve_descrizione("fornitore", data.get("cod_fornitore")),
            "iva": resolve_descrizione("iva", data.get("cod_iva")),
            "c_partita_vend": resolve_descrizione("pdc", data.get("c_partita_vend")),
            "c_partita_acq": resolve_descrizione("pdc", data.get("c_partita_acq")),
        }
    instance = getattr(form, "instance", None)
    if instance and getattr(instance, "pk", None):
        return linked_labels_for_articolo(instance)
    return {k: "" for k in ("magazzino", "categoria", "gruppo", "fornitore", "iva", "c_partita_vend", "c_partita_acq")}


class ArticoloListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = Articolo
    template_name = "articoli/articolo_list.html"
    context_object_name = "articoli"
    sortable_fields = ("descrizione", "codice", "cat_omogenea", "unita_misura", "cod_fornitore", "listino1")
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_articoli_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _articoli_list_context(self, context)


class ArticoloPrintListView(MirrorPrintListView):
    print_title = "Articoli"
    print_subtitle = "Elenco articoli"
    filter_queryset = staticmethod(_filter_articoli_queryset)
    sortable_fields = (
        "descrizione",
        "codice",
        "cat_omogenea",
        "unita_misura",
        "cod_fornitore",
        "listino1",
    )
    default_sort = "descrizione"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Articolo"},
        {"field": "cat_omogenea", "label": "Categoria"},
        {"field": "unita_misura", "label": "U.M."},
        {
            "label": "Giacenza",
            "value": lambda a: getattr(a, "giacenza_quantita", 0) or 0,
            "align": "end",
        },
        {"field": "cod_fornitore", "label": "Fornitore"},
        {"field": "listino1", "label": "Listino 1", "align": "end"},
    )

    def get_queryset(self):
        rows = list(super().get_queryset())
        attach_articoli_list_labels(rows)
        attach_giacenze_articoli(rows)
        return rows


def _inventario_cell_classes(
    articolo, n_cols: int, *, soglia: float | None = None
) -> list[str]:
    """Classi sulle colonne prezzo/valore (6–9) in base alle anomalie."""
    classes = [""] * n_cols
    flags = set(inventario_row_classes(articolo, soglia=soglia))
    if "eureka-print-row--prezzo-zero-ultimo" in flags:
        if n_cols > 5:
            classes[5] = "eureka-print-cell--anomalia-zero"
        if n_cols > 6:
            classes[6] = "eureka-print-cell--anomalia-zero"
    if "eureka-print-row--prezzo-zero-medio" in flags:
        if n_cols > 7:
            classes[7] = "eureka-print-cell--anomalia-zero"
        if n_cols > 8:
            classes[8] = "eureka-print-cell--anomalia-zero"
    if "eureka-print-row--prezzo-discrepanza" in flags:
        if n_cols > 5:
            classes[5] = "eureka-print-cell--anomalia-discrepanza"
        if n_cols > 7:
            classes[7] = "eureka-print-cell--anomalia-discrepanza"
    return classes


def _inventario_row_title(
    articolo, *, soglia: float | None = None, pct: int | None = None
) -> str:
    flags = set(inventario_row_classes(articolo, soglia=soglia))
    if pct is None:
        pct = inventario_discrepanza_pct()
    notes: list[str] = []
    if "eureka-print-row--giacenza-negativa" in flags:
        notes.append("giacenza negativa")
    if "eureka-print-row--prezzo-zero-ultimo" in flags:
        notes.append("ultimo prezzo a zero")
    if "eureka-print-row--prezzo-zero-medio" in flags:
        notes.append("prezzo medio a zero")
    if "eureka-print-row--prezzo-discrepanza" in flags:
        notes.append(f"ultimo e medio molto discrepanti (≥{pct}%)")
    return "Anomalia: " + "; ".join(notes) if notes else ""


def _inventario_structured_rows(
    articoli,
    columns,
    *,
    soglia: float | None = None,
    pct: int | None = None,
    ignora_anomalie: bool = False,
) -> list[dict]:
    """Righe stampa inventario con evidenziazione anomalie (opzionale)."""
    _, cells_list = build_print_rows(articoli, columns)
    n_cols = len(columns)
    if ignora_anomalie:
        return [
            structured_print_row(cells, columns)
            for cells in cells_list
        ]
    return [
        structured_print_row(
            cells,
            columns,
            row_class=inventario_row_class(art, soglia=soglia),
            cell_classes=_inventario_cell_classes(art, n_cols, soglia=soglia),
            row_title=_inventario_row_title(art, soglia=soglia, pct=pct),
        )
        for art, cells in zip(articoli, cells_list)
    ]


def _filter_inventario_queryset(request, stocks: dict[str, float] | None = None):
    """Articoli gestiti a magazzino con giacenza calcolata diversa da zero."""
    if stocks is None:
        stocks = giacenze_non_nulle()
    if not stocks:
        return Articolo.objects.none()

    qs = (
        Articolo.objects.annotate(_cod_norm=Upper(Trim("codice")))
        .filter(_cod_norm__in=list(stocks))
        .exclude(no_magazzino=True)
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
    cat_da, cat_a = parse_inventario_categorie(request)
    if cat_da or cat_a:
        qs = qs.annotate(_cat_norm=Upper(Trim("cat_omogenea")))
        if cat_da:
            qs = qs.filter(_cat_norm__gte=cat_da.upper())
        if cat_a:
            qs = qs.filter(_cat_norm__lte=cat_a.upper())
    return qs.order_by("descrizione", "codice")


def _inventario_totale_cells(label: str, totals: dict[str, float], n_cols: int) -> list[str]:
    cells = [""] * n_cols
    cells[0] = label
    if n_cols > 4:
        cells[4] = format_it_number(totals["giacenza"], decimals=2)
    if n_cols > 6:
        cells[6] = format_it_number(totals["valore_ultimo"], decimals=2)
    if n_cols > 8:
        cells[8] = format_it_number(totals["valore_medio"], decimals=2)
    return cells


def _inventario_print_columns():
    from apps.core.prezzi import get_prezzo_decimali

    dec = get_prezzo_decimali()
    return (
        {"field": "codice", "label": "Articolo"},
        {"field": "cat_omogenea", "label": "Cat.", "nowrap": True},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "unita_misura", "label": "UM", "nowrap": True},
        {
            "label": "Giacenza",
            "value": lambda a: getattr(a, "giacenza_quantita", 0) or 0,
            "align": "end",
            "decimals": 2,
        },
        {
            "label": "Prezzo ultimo\nacquisto",
            "value": lambda a: getattr(a, "prezzo_ultimo_acquisto", 0) or 0,
            "align": "end",
            "decimals": dec,
        },
        {
            "label": "Valore a\nprezzo ultimo",
            "value": lambda a: getattr(a, "valore_prezzo_ultimo", 0) or 0,
            "align": "end",
            "decimals": 2,
        },
        {
            "label": "Prezzo medio\ndi acquisto",
            "value": lambda a: getattr(a, "prezzo_medio_inventario", 0) or 0,
            "align": "end",
            "decimals": dec,
        },
        {
            "label": "Valore a\nprezzo medio",
            "value": lambda a: getattr(a, "valore_prezzo_medio", 0) or 0,
            "align": "end",
            "decimals": 2,
        },
    )


class ArticoloInventarioPrintView(MirrorPrintListView):
    """Stampa allineata a 4D «Valori Articoli»."""

    print_title = "Valori Articoli"
    print_subtitle = "Inventario magazzino"
    print_orientation = "portrait"
    print_table_class = "eureka-print-table--compact"
    sortable_fields = (
        "codice",
        "cat_omogenea",
        "descrizione",
        "unita_misura",
        "prezzo_ult_car",
        "prezzo_medio_acquisto",
    )
    default_sort = "cat_omogenea"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = _inventario_print_columns()

    def get_print_queryset(self):
        self.print_columns = _inventario_print_columns()
        data_da, data_a = parse_inventario_periodo(self.request)
        cat_da, cat_a = parse_inventario_categorie(self.request)
        self._inventario_data_da = data_da
        self._inventario_data_a = data_a
        self._inventario_categoria_da = cat_da
        self._inventario_categoria_a = cat_a
        self._inventario_rottura = inventario_want_rottura(self.request)
        self._inventario_ignora_anomalie = inventario_want_ignora_anomalie(
            self.request
        )
        self._inventario_solo_anomalie = (
            not self._inventario_ignora_anomalie
            and inventario_want_solo_anomalie(self.request)
        )
        # Come 4D: inventario alla data di chiusura (storico fino a data_a).
        self._inventario_stocks = giacenze_non_nulle(data_da=data_da, data_a=data_a)
        return _filter_inventario_queryset(self.request, self._inventario_stocks)

    def get_queryset(self):
        # Assicura periodo/stocks anche se get_print_queryset non è già passato.
        if not hasattr(self, "_inventario_data_a"):
            data_da, data_a = parse_inventario_periodo(self.request)
            self._inventario_data_da = data_da
            self._inventario_data_a = data_a
            self._inventario_categoria_da, self._inventario_categoria_a = (
                parse_inventario_categorie(self.request)
            )
            self._inventario_rottura = inventario_want_rottura(self.request)
            self._inventario_ignora_anomalie = inventario_want_ignora_anomalie(
                self.request
            )
            self._inventario_solo_anomalie = (
                not self._inventario_ignora_anomalie
                and inventario_want_solo_anomalie(self.request)
            )
            self._inventario_stocks = giacenze_non_nulle(data_da=data_da, data_a=data_a)
        pct = inventario_discrepanza_pct()
        soglia = inventario_discrepanza_soglia(pct=pct)
        self._inventario_discrepanza_pct = pct
        self._inventario_discrepanza_soglia = soglia
        rows = list(super().get_queryset())
        attach_inventario_articoli(
            rows,
            getattr(self, "_inventario_stocks", None),
            data_a=getattr(self, "_inventario_data_a", None),
        )
        rows = inventario_filter_giacenza_non_zero(rows)
        if getattr(self, "_inventario_solo_anomalie", False):
            rows = inventario_filter_solo_anomalie(rows, soglia=soglia)
        if getattr(self, "_inventario_rottura", False):
            rows = inventario_sort_per_categoria(rows)
        self._inventario_rows = rows
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_da = getattr(self, "_inventario_data_da", None)
        data_a = getattr(self, "_inventario_data_a", None)
        cat_da = getattr(self, "_inventario_categoria_da", "")
        cat_a = getattr(self, "_inventario_categoria_a", "")
        if data_da is None and data_a is None:
            data_da, data_a = parse_inventario_periodo(self.request)
            self._inventario_data_da = data_da
            self._inventario_data_a = data_a
        if not cat_da and not cat_a:
            cat_da, cat_a = parse_inventario_categorie(self.request)
            self._inventario_categoria_da = cat_da
            self._inventario_categoria_a = cat_a
        rottura = getattr(self, "_inventario_rottura", False) or inventario_want_rottura(
            self.request
        )
        ignora_anomalie = getattr(
            self, "_inventario_ignora_anomalie", False
        ) or inventario_want_ignora_anomalie(self.request)
        solo_anomalie = (
            not ignora_anomalie
            and (
                getattr(self, "_inventario_solo_anomalie", False)
                or inventario_want_solo_anomalie(self.request)
            )
        )
        pct = getattr(self, "_inventario_discrepanza_pct", None)
        soglia = getattr(self, "_inventario_discrepanza_soglia", None)
        if pct is None or soglia is None:
            pct = inventario_discrepanza_pct()
            soglia = inventario_discrepanza_soglia(pct=pct)
            self._inventario_discrepanza_pct = pct
            self._inventario_discrepanza_soglia = soglia

        rows = getattr(self, "_inventario_rows", None)
        if rows is None:
            rows = list(context.get(self.context_object_name) or [])
            attach_inventario_articoli(
                rows,
                getattr(self, "_inventario_stocks", None),
                data_a=data_a,
            )
            rows = inventario_filter_giacenza_non_zero(rows)
            if solo_anomalie:
                rows = inventario_filter_solo_anomalie(rows, soglia=soglia)
            if rottura:
                rows = inventario_sort_per_categoria(rows)
            self._inventario_rows = rows
        columns = self.print_columns
        n_cols = len(columns)
        structured: list[dict] = []

        if rottura:
            for cat, group in inventario_gruppi_per_categoria(rows):
                structured.extend(
                    _inventario_structured_rows(
                        group,
                        columns,
                        soglia=soglia,
                        pct=pct,
                        ignora_anomalie=ignora_anomalie,
                    )
                )
                cat_label = cat or "—"
                sub = inventario_totali(group)
                structured.append(
                    structured_print_row(
                        _inventario_totale_cells(
                            f"TOTALI CATEGORIA {cat_label}",
                            sub,
                            n_cols,
                        ),
                        columns,
                        row_class="eureka-print-row--subtotale",
                    )
                )
        else:
            structured = _inventario_structured_rows(
                rows,
                columns,
                soglia=soglia,
                pct=pct,
                ignora_anomalie=ignora_anomalie,
            )

        totals = inventario_totali(rows)
        structured.append(
            structured_print_row(
                _inventario_totale_cells(
                    "Totale valore di magazzino",
                    totals,
                    n_cols,
                ),
                columns,
                row_class="eureka-print-row--totale",
            )
        )

        if ignora_anomalie:
            anomalies = {
                "giacenza_negativa": 0,
                "prezzo_zero_ultimo": 0,
                "prezzo_zero_medio": 0,
                "prezzo_discrepanza": 0,
            }
            anomalie_total = 0
        else:
            anomalies = inventario_anomalia_counts(rows, soglia=soglia)
            anomalie_total = sum(anomalies.values())
        context.update(
            {
                "print_period_filters": True,
                "print_inventario_options": True,
                "data_da": data_da.isoformat() if data_da else "",
                "data_a": data_a.isoformat() if data_a else "",
                "categoria_da": cat_da,
                "categoria_a": cat_a,
                "q": (self.request.GET.get("q") or "").strip(),
                "rottura": rottura,
                "solo_anomalie": solo_anomalie,
                "ignora_anomalie": ignora_anomalie,
                "inventario_discrepanza_pct": pct,
                "inventario_preset_urls": inventario_preset_urls(self.request),
                "inventario_active_preset": inventario_active_preset(data_da, data_a),
                "print_orientation": self.print_orientation,
                "print_table_class": getattr(self, "print_table_class", ""),
                "print_header_cells": print_header_cells(columns),
                "print_rows": structured,
                "print_rows_structured": True,
                "print_count": len(rows),
                "inventario_anomalie": anomalies,
                "inventario_anomalie_total": anomalie_total,
            }
        )
        return context

    def get_print_subtitle(self) -> str:
        data_da = getattr(self, "_inventario_data_da", None)
        data_a = getattr(self, "_inventario_data_a", None)
        cat_da = getattr(self, "_inventario_categoria_da", "")
        cat_a = getattr(self, "_inventario_categoria_a", "")
        if not cat_da and not cat_a:
            cat_da, cat_a = parse_inventario_categorie(self.request)
        parts = []
        periodo = inventario_periodo_label(data_da, data_a)
        if periodo:
            parts.append(periodo)
        categorie = inventario_categorie_label(cat_da, cat_a)
        if categorie:
            parts.append(categorie)
        if parts:
            return " · ".join(parts)
        return self.print_subtitle

    def get_filter_summary(self) -> str:
        parts = ["Solo articoli con giacenza ≠ 0"]
        data_da = getattr(self, "_inventario_data_da", None)
        data_a = getattr(self, "_inventario_data_a", None)
        cat_da = getattr(self, "_inventario_categoria_da", "")
        cat_a = getattr(self, "_inventario_categoria_a", "")
        if data_da is None and data_a is None:
            data_da, data_a = parse_inventario_periodo(self.request)
        if not cat_da and not cat_a:
            cat_da, cat_a = parse_inventario_categorie(self.request)
        periodo = inventario_periodo_label(data_da, data_a)
        if periodo:
            parts.append(periodo)
        categorie = inventario_categorie_label(cat_da, cat_a)
        if categorie:
            parts.append(categorie)
        if getattr(self, "_inventario_rottura", False) or inventario_want_rottura(
            self.request
        ):
            parts.append("Rottura per categoria")
        if getattr(
            self, "_inventario_ignora_anomalie", False
        ) or inventario_want_ignora_anomalie(self.request):
            parts.append("Ignora anomalie")
        elif getattr(
            self, "_inventario_solo_anomalie", False
        ) or inventario_want_solo_anomalie(self.request):
            parts.append("Solo anomalie")
        extra = super().get_filter_summary()
        if extra:
            parts.append(extra)
        return " · ".join(parts)


class ArticoloDetailView(LoginRequiredMixin, DetailView):
    model = Articolo
    template_name = "articoli/articolo_detail.html"
    context_object_name = "articolo"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        art = self.object
        context["articolo_flags"] = [
            ("Chiede descriz. in DDT", art.descr_express),
            ("Gestione lotti", art.gest_lotti),
            ("Articolo con kit", art.kit),
            ("Non movimenta mag.", art.no_magazzino),
            ("Confezionato", art.confezionato),
            ("Articolo TAG", art.articolo_tag),
            ("Patentino", art.richiesta_patentino),
            ("Giacenza", art.giacenza),
            ("Disponibile", art.disponibile),
        ]
        context["labels"] = linked_labels_for_articolo(art)
        context["fornitore_ragione_sociale"] = context["labels"]["fornitore"]
        context["movimenti_magazzino"] = movimenti_articolo_for_request(
            self.request, art.codice
        )
        context["giacenza_quantita"] = giacenza_articolo(art.codice)
        context["prezzo_ultimo_acquisto"] = prezzo_ultimo_acquisto_articolo(art)
        data_ult_car, data_ult_scar = ultime_date_movimenti(art.codice)
        context["data_ult_carico"] = data_ult_car
        context["data_ult_scarico"] = data_ult_scar
        context.update(movimenti_periodo_context(self.request))
        try:
            from apps.distinte_base.models import DistintaBase

            context["distinta_righe"] = list(
                DistintaBase.objects.filter(codice_db=self.object.codice).order_by(
                    "fase", "codice_art", "id"
                )[:200]
            )
            context["distinta_count"] = DistintaBase.objects.filter(
                codice_db=self.object.codice
            ).count()
        except Exception:
            context["distinta_righe"] = []
            context["distinta_count"] = 0
        context["distinta_selection_back_url"] = _distinta_selection_back_url(self.request)
        context["distinta_articolo_back_url"] = _distinta_articolo_back_url(self.request)
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        return context


class ArticoloCreateView(LoginRequiredMixin, View):
    template_name = "articoli/articolo_form.html"

    def _context(self, form, *, is_create=True):
        return {
            "form": form,
            "is_create": is_create,
            "page_heading": "Nuovo articolo" if is_create else "Modifica articolo",
            "labels": _form_linked_labels(form),
            "lookup_url": reverse("articoli:lookup_codice"),
            "articolo": None if is_create else form.instance,
        }

    def get(self, request):
        return render(request, self.template_name, self._context(ArticoloForm()))

    def post(self, request):
        form = ArticoloForm(request.POST)
        if form.is_valid():
            articolo = save_mirror_form_instance(form)
            messages.success(request, f"Articolo {articolo.codice} creato.")
            return redirect("articoli:detail", codice=articolo.codice)
        return render(request, self.template_name, self._context(form))


class ArticoloUpdateView(LoginRequiredMixin, View):
    template_name = "articoli/articolo_form.html"

    def get_object(self, codice):
        return get_object_or_404(Articolo, pk=codice)

    def _context(self, form, articolo):
        return {
            "form": form,
            "articolo": articolo,
            "is_create": False,
            "page_heading": "Modifica articolo",
            "labels": _form_linked_labels(form),
            "lookup_url": reverse("articoli:lookup_codice"),
        }

    def get(self, request, codice):
        articolo = self.get_object(codice)
        form = ArticoloForm(instance=articolo, codice_readonly=True)
        return render(request, self.template_name, self._context(form, articolo))

    def post(self, request, codice):
        articolo = self.get_object(codice)
        form = ArticoloForm(request.POST, instance=articolo, codice_readonly=True)
        if form.is_valid():
            articolo = save_mirror_form_instance(form)
            messages.success(request, f"Articolo {articolo.codice} aggiornato.")
            return redirect("articoli:detail", codice=articolo.codice)
        return render(request, self.template_name, self._context(form, articolo))


class ArticoloDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        articolo = get_object_or_404(Articolo, pk=codice)
        label = articolo.codice
        articolo.delete()
        messages.success(request, f"Articolo {label} eliminato.")
        return redirect("articoli:list")


class CodiceLookupView(LoginRequiredMixin, View):
    """Lookup descrizione o elenco opzioni per combobox codici collegati."""

    def get(self, request):
        tipo = (request.GET.get("tipo") or "").strip().lower()
        if tipo not in LOOKUP_TIPI:
            return JsonResponse({"tipo": tipo, "results": [], "descrizione": ""}, status=400)

        # Modalità lista/ricerca: ?tipo=...&q=...  oppure ?tipo=...&list=1
        wants_list = "q" in request.GET or (request.GET.get("list") or "").strip() in (
            "1",
            "true",
            "yes",
        )
        if wants_list:
            q = (request.GET.get("q") or "").strip()
            try:
                limit = int(request.GET.get("limit") or 40)
            except (TypeError, ValueError):
                limit = 40
            codice_clifor = (request.GET.get("codice_clifor") or "").strip()
            return JsonResponse(
                {
                    "tipo": tipo,
                    "q": q,
                    "codice_clifor": codice_clifor,
                    "results": search_opzioni(
                        tipo, q, limit=limit, codice_clifor=codice_clifor
                    ),
                }
            )

        codice = (request.GET.get("codice") or "").strip()
        if tipo == "articolo":
            info = resolve_articolo(codice)
            return JsonResponse(
                {
                    "tipo": tipo,
                    "codice": info.get("codice") or codice,
                    "found": bool(info.get("found")),
                    "descrizione": info.get("descrizione") or "",
                    "iva": info.get("iva") or "",
                    "unita_misura": info.get("unita_misura") or "",
                    "prezzo_unitario": info.get("prezzo_unitario"),
                }
            )
        if tipo in ("cliente", "fornitore", "clifor"):
            info = resolve_clifor(tipo, codice)
            payload = {"tipo": tipo, **info}
            payload["codice"] = info.get("codice") or codice
            payload["descrizione"] = info.get("descrizione") or ""
            return JsonResponse(payload)
        if tipo == "destinazione":
            from apps.destinazioni.lookups import resolve_destinazione

            codice_clifor = (request.GET.get("codice_clifor") or "").strip()
            info = resolve_destinazione(codice, codice_clifor=codice_clifor)
            payload = {"tipo": tipo, **info}
            payload["codice"] = info.get("codice") or codice
            payload["descrizione"] = info.get("descrizione") or ""
            return JsonResponse(payload)
        return JsonResponse(
            {
                "tipo": tipo,
                "codice": codice,
                "descrizione": resolve_descrizione(tipo, codice),
            }
        )


class ArticoloMovimentiPrintView(RawPrintListView):
    print_title = "Movimenti di magazzino"
    print_columns = MOVIMENTI_ARTICOLO_PRINT_COLUMNS
    print_orientation = "landscape"

    def dispatch(self, request, codice, *args, **kwargs):
        self.codice = codice
        return super().dispatch(request, *args, **kwargs)

    def get_object_list(self, request):
        self.movimenti_result = movimenti_articolo_for_request(request, self.codice)
        return self.movimenti_result.righe

    def get_filter_summary(self, request) -> str:
        return movimenti_print_filter_summary(
            request, self.movimenti_result, self.articolo
        )

    def get(self, request):
        from django.shortcuts import render
        from django.utils import timezone

        from apps.aziende.configurazione import resolve_print_azienda_context
        from apps.core.print_list import build_print_rows, print_header_cells, structured_print_row

        self.articolo = get_object_or_404(Articolo, pk=self.codice)
        object_list = self.get_object_list(request)
        headers, rows = build_print_rows(object_list, self.print_columns)
        columns = self.print_columns
        structured_rows = [
            structured_print_row(
                cells,
                columns,
                row_class="eureka-print-row--totale" if obj.is_totale else "",
            )
            for obj, cells in zip(object_list, rows)
        ]
        desc = (self.articolo.descrizione or "").strip()
        subtitle = self.codice + (f" — {desc}" if desc else "")
        return render(
            request,
            self.template_name,
            {
                "print_title": self.print_title,
                "print_subtitle": subtitle,
                "print_headers": headers,
                "print_header_cells": print_header_cells(columns),
                "print_rows": structured_rows,
                "print_rows_structured": True,
                "print_count": len(structured_rows),
                "print_date": timezone.localdate(),
                "print_filter_summary": self.get_filter_summary(request),
                "print_orientation": self.print_orientation,
                **resolve_print_azienda_context(branding=self.print_branding),
            },
        )
