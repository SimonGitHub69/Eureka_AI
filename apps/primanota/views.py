from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection, transaction
from django.db.models import DateField, Q, TextField
from django.db.models.functions import Cast, Trim, Upper
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

import json

from apps.articoli.lookups import resolve_descrizione
from apps.documenti.castelletto import aliquote_map_for_js

from apps.core.mirror_crud import delete_mirror_row, mirror_row_to_campi, stamp_modifica
from apps.core.navigation import related_back
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.primanota.forms import (
    PrimanotaForm,
    PrimanotaRigaForm,
    delete_primanota,
    riga_formset_for,
    save_primanota_with_righe,
    save_single_riga,
)
from apps.primanota.lookups import (
    annotate_totale_documento,
    attach_causali_contabili,
    attach_line_lookups,
    attach_registri_iva,
    causale_is_autofattura_automatica,
    corrispettivi_extra_from_causale,
    registro_iva_choices,
    resolve_causale_contabile,
    resolve_pagamento,
    resolve_partita_clifor,
    resolve_registro_iva,
)
from apps.primanota.models import Primanota, PrimanotaDettaglio
from apps.primanota.numerazione import (
    esercizio_from_data,
    peek_next_numero_reg,
    resolve_contatore_primanota,
)
from apps.primanota.protocollo import peek_next_protocollo, protocollo_from_causale
from apps.primanota.sync import sync_primanota
from apps.valute.lookups import cambio_info, is_cambio_visible, valute_cambi_catalog

SCADENZE_CAMPI_EXCLUDE = (
    {"ScadenzeIns"}
    | {f"Scad{i}" for i in range(1, 11)}
    | {f"ImpScad{i}" for i in range(1, 11)}
    | {f"Flag_RA{i:02d}" for i in range(1, 11)}
)

IVA_CAMPI_EXCLUDE = {
    "ID",
    "NumeroReg",
    "DataReg",
    "NumeroProt",
    "AlfaProt",
    "Causale",
    "NumeroDoc",
    "DataDoc",
    "Registro",
    "Tipo",
    "CodicePartita",
    "CodicePaga",
    "Valuta",
    "DataValuta",
    "Acconto",
    "FornitoreCEE",
} | SCADENZE_CAMPI_EXCLUDE


def _filter_primanota_queryset(request):
    qs = Primanota.objects.all()
    q = (request.GET.get("q") or "").strip()
    causale = (request.GET.get("causale") or "").strip()
    registro = (request.GET.get("registro") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())

    if q:
        filters = (
            Q(causale__icontains=q)
            | Q(numero_doc__icontains=q)
            | Q(codice_partita__icontains=q)
            | Q(registro__icontains=q)
            | Q(alfa_prot__icontains=q)
            | Q(nr_fatt_anno__icontains=q)
        )
        if q.isdigit():
            n = int(q)
            filters |= Q(numero_reg=n) | Q(numero_prot=n) | Q(id=n)
        qs = qs.filter(filters)
    if causale:
        qs = qs.annotate(
            _causale_n=Upper(Trim("causale"), output_field=TextField())
        ).filter(_causale_n=causale.upper())
    if registro:
        qs = qs.filter(registro__iexact=registro)
    if tipo.isdigit():
        qs = qs.filter(tipo=int(tipo))
    if data_da or data_a:
        qs = qs.annotate(_data_reg_cal=Cast("data_reg", DateField()))
    if data_da:
        qs = qs.filter(_data_reg_cal__gte=data_da)
    if data_a:
        qs = qs.filter(_data_reg_cal__lte=data_a)
    return annotate_totale_documento(qs.order_by("-data_reg", "-numero_reg", "-id"))


def fetch_primanota_row(pk: int) -> list[tuple[str, object]] | None:
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute('SELECT * FROM primanota WHERE "ID" = %s', [pk])
                row = cur.fetchone()
                if row is None:
                    return None
                columns = [col[0] for col in cur.description]
            return list(zip(columns, row))
    except (ProgrammingError, OperationalError):
        return None


def load_primanota_righe(id_testa: int) -> tuple[list, bool]:
    """Righe dettaglio; (lista, tabella_mancante). Non lascia la connessione aborted."""
    try:
        with transaction.atomic():
            return (
                list(
                    PrimanotaDettaglio.objects.filter(id_testa=id_testa)
                    .exclude(dummy=True)
                    .order_by("pos", "id")
                ),
                False,
            )
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


class PrimanotaListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = Primanota
    template_name = "primanota/primanota_list.html"
    context_object_name = "registrazioni"
    sortable_fields = (
        "numero_reg",
        "data_reg",
        "causale",
        "numero_doc",
        "registro",
        "tipo",
        "totale_documento_list",
        "id",
    )
    default_sort = "data_reg"
    default_dir = "desc"
    sort_tiebreaker = ("-numero_reg", "-id")
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_primanota_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["causale"] = (self.request.GET.get("causale") or "").strip()
        context["registro"] = (self.request.GET.get("registro") or "").strip()
        context["tipo"] = (self.request.GET.get("tipo") or "").strip()
        context["tipo_choices"] = Primanota.TIPO_CHOICES
        context["data_da"] = (self.request.GET.get("data_da") or "").strip()
        context["data_a"] = (self.request.GET.get("data_a") or "").strip()
        context["has_filters"] = bool(
            context["q"]
            or context["causale"]
            or context["registro"]
            or context["tipo"]
            or context["data_da"]
            or context["data_a"]
        )
        context["totale"] = safe_mirror_count(Primanota)
        context["registri_choices"] = registro_iva_choices(context["registro"])
        attach_causali_contabili(context.get("registrazioni") or [])
        attach_registri_iva(context.get("registrazioni") or [])
        return context


class PrimanotaPrintListView(MirrorPrintListView):
    print_title = "Primanota"
    print_subtitle = "Elenco registrazioni"
    filter_queryset = staticmethod(_filter_primanota_queryset)
    sortable_fields = (
        "numero_reg",
        "data_reg",
        "causale",
        "numero_doc",
        "registro",
        "tipo",
        "totale_documento_list",
        "id",
    )
    default_sort = "data_reg"
    default_dir = "desc"
    sort_tiebreaker = ("-numero_reg", "-id")
    print_columns = (
        {"field": "numero_reg", "label": "N. reg."},
        {"field": "data_reg", "label": "Data", "date": True},
        {"field": "causale", "label": "Causale"},
        {"label": "Tipo", "value": lambda r: r.tipo_label},
        {"field": "numero_doc", "label": "Documento"},
        {"field": "registro", "label": "Registro"},
        {
            "field": "totale_documento_list",
            "label": "Totale",
            "number": True,
            "decimals": 2,
            "align": "end",
        },
    )

    def get_filter_summary(self) -> str:
        return _primanota_print_filter_summary(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        registro = (request.GET.get("registro") or "").strip()
        context.update(
            {
                "print_primanota_filters": True,
                "data_da": (request.GET.get("data_da") or "").strip(),
                "data_a": (request.GET.get("data_a") or "").strip(),
                "tipo": (request.GET.get("tipo") or "").strip(),
                "q": (request.GET.get("q") or "").strip(),
                "causale": (request.GET.get("causale") or "").strip(),
                "registro": registro,
                "tipo_choices": Primanota.TIPO_CHOICES,
                "registri_choices": registro_iva_choices(registro),
            }
        )
        return context


def _primanota_print_filter_summary(request) -> str:
    parts: list[str] = []
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())
    if data_da and data_a:
        parts.append(
            f"Dal {data_da.strftime('%d/%m/%Y')} al {data_a.strftime('%d/%m/%Y')}"
        )
    elif data_da:
        parts.append(f"Da {data_da.strftime('%d/%m/%Y')}")
    elif data_a:
        parts.append(f"Fino al {data_a.strftime('%d/%m/%Y')}")

    tipo = (request.GET.get("tipo") or "").strip()
    if tipo.isdigit():
        label = dict(Primanota.TIPO_CHOICES).get(int(tipo), tipo)
        parts.append(f"Tipo: {label}")

    causale = (request.GET.get("causale") or "").strip()
    if causale:
        parts.append(f"Causale: {causale}")

    registro = (request.GET.get("registro") or "").strip()
    if registro:
        parts.append(f"Registro: {registro}")

    q = (request.GET.get("q") or "").strip()
    if q:
        parts.append(f'Ricerca: "{q}"')

    return " · ".join(parts)


def _safe_internal_path(raw: str, *, host: str) -> str | None:
    """Accetta solo path relativi (o URL stesso host) per redirect «next»."""
    raw = (raw or "").strip()
    if not raw:
        return None
    from urllib.parse import urlparse

    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        if parsed.netloc and parsed.netloc != host:
            return None
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
    else:
        path = raw
    if path.startswith("/") and not path.startswith("//"):
        return path
    return None


def _partitario_back_from_request(request) -> tuple[str | None, str]:
    """Se si arriva dal partitario (?next=…/partitario/…), torna lì."""
    raw = (
        (request.POST.get("next") if request.method == "POST" else None)
        or (request.GET.get("next") or "")
    ).strip()
    path = _safe_internal_path(raw, host=request.get_host())
    if not path or "/partitario" not in path.lower():
        return None, ""
    return path, "Torna al partitario"


class PrimanotaDetailView(LoginRequiredMixin, DetailView):
    model = Primanota
    template_name = "primanota/primanota_detail.html"
    context_object_name = "registrazione"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        back_url, back_label = related_back(self.request)
        context["back_url"] = back_url
        context["back_label"] = back_label
        righe, dettaglio_mancante = load_primanota_righe(self.object.id)
        context["righe"] = righe
        context["dettaglio_mancante"] = dettaglio_mancante
        context["totale_dare"] = float(sum(float(r.dare or 0) for r in righe))
        context["totale_avere"] = float(sum(float(r.avere or 0) for r in righe))
        context["sbilancio"] = round(context["totale_dare"] - context["totale_avere"], 2)
        context["causale_contabile"] = resolve_causale_contabile(self.object.causale)
        context["registro_iva"] = resolve_registro_iva(self.object.registro)
        context["is_iva"] = self.object.is_iva
        context["is_generico"] = self.object.is_generico
        context["is_corrispettivi"] = self.object.is_corrispettivi
        context["is_iva_autofattura"] = self.object.is_iva_autofattura
        context["show_fornitore_cee"] = (
            self.object.is_iva_autofattura
            and causale_is_autofattura_automatica(context["causale_contabile"])
        )
        context["is_iva_layout"] = self.object.is_iva or self.object.is_corrispettivi
        attach_line_lookups(righe, iva=context["is_iva_layout"])
        if self.object.is_iva:
            totale_imponibile = float(sum(r.imponibile for r in righe))
            totale_iva = float(sum(float(r.importo_iva or 0) for r in righe))
            context["totale_imponibile"] = totale_imponibile
            context["totale_imponibile_valuta"] = float(sum(r.imponibile_valuta for r in righe))
            context["totale_iva"] = totale_iva
            context["totale_documento"] = totale_imponibile + totale_iva
        elif self.object.is_corrispettivi:
            totale_imponibile = float(sum(r.imponibile for r in righe))
            context["totale_imponibile"] = totale_imponibile
            context["totale_imponibile_valuta"] = float(sum(r.imponibile_valuta for r in righe))
            context["totale_iva"] = float(sum(float(r.importo_iva or 0) for r in righe))
            context["totale_documento"] = totale_imponibile
        context.update(corrispettivi_extra_from_causale(context["causale_contabile"]))
        context["clifor"] = resolve_partita_clifor(self.object.codice_partita)
        context["fornitore"] = resolve_partita_clifor(self.object.fornitore_cee)
        context["pagamento"] = resolve_pagamento(self.object.codice_paga)
        context["cambio_info"] = cambio_info(
            self.object.valuta, alla_data=self.object.data_reg
        )
        context["show_cambio"] = (not self.object.is_generico) and is_cambio_visible(
            self.object.valuta
        )
        row = fetch_primanota_row(self.object.id) or []
        exclude = IVA_CAMPI_EXCLUDE if self.object.is_iva else {
            "ID",
            "NumeroReg",
            "DataReg",
            "NumeroProt",
            "AlfaProt",
            "Causale",
            "NumeroDoc",
            "DataDoc",
            "Registro",
            "Tipo",
            "CodicePartita",
            "CodicePaga",
            "Valuta",
            "DataValuta",
            "Acconto",
            "Scad1",
        }
        if self.object.is_generico:
            exclude = exclude | SCADENZE_CAMPI_EXCLUDE
        context["campi"] = mirror_row_to_campi(row, exclude=exclude)
        return context


def _righe_queryset(pk: int):
    return (
        PrimanotaDettaglio.objects.filter(id_testa=pk)
        .exclude(dummy=True)
        .order_by("pos", "id")
    )


def _lookup_context() -> dict:
    return {
        "lookup_url": reverse("articoli:lookup_codice"),
        "aliquote_map_json": json.dumps(aliquote_map_for_js(), ensure_ascii=False),
    }


def _valute_cambi_json() -> dict:
    try:
        return valute_cambi_catalog()
    except Exception:
        return {}


def _tipo_is_iva(tipo) -> bool:
    try:
        return int(tipo) in (Primanota.TIPO_IVA, Primanota.TIPO_IVA_AUTOFATTURA)
    except (TypeError, ValueError):
        return False


def _tipo_is_corrispettivi(tipo) -> bool:
    try:
        return int(tipo) == Primanota.TIPO_CORRISPETTIVI
    except (TypeError, ValueError):
        return False


def _tipo_is_iva_autofattura(tipo) -> bool:
    try:
        return int(tipo) == Primanota.TIPO_IVA_AUTOFATTURA
    except (TypeError, ValueError):
        return False


def _tipo_is_iva_layout(tipo) -> bool:
    return _tipo_is_iva(tipo) or _tipo_is_corrispettivi(tipo)


def _tipo_is_generico(tipo) -> bool:
    try:
        return int(tipo) == Primanota.TIPO_GENERICO
    except (TypeError, ValueError):
        return False


def _parse_amount(raw) -> float:
    if raw in (None, ""):
        return 0.0
    if isinstance(raw, bool):
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(" ", "")
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _bound_amount(form, name: str) -> float:
    try:
        raw = form[name].value()
    except Exception:
        raw = None
    if raw in (None, ""):
        raw = (getattr(form, "initial", None) or {}).get(name)
    return _parse_amount(raw)


def _form_deleted(form) -> bool:
    cleaned = getattr(form, "cleaned_data", None)
    if isinstance(cleaned, dict) and cleaned.get("DELETE"):
        return True
    try:
        return bool(form["DELETE"].value())
    except Exception:
        return False


def _formset_totals(formset) -> dict[str, float]:
    tot_imp = tot_imp_val = tot_iva = tot_dare = tot_avere = 0.0
    filled = 0
    for form in getattr(formset, "forms", None) or []:
        if _form_deleted(form):
            continue
        imp = _bound_amount(form, "imponibile")
        imp_val = _bound_amount(form, "imp_val") or imp
        iva = _bound_amount(form, "importo_iva")
        dare = _bound_amount(form, "dare")
        avere = _bound_amount(form, "avere")
        tot_imp += imp
        tot_imp_val += imp_val
        tot_iva += iva
        tot_dare += dare
        tot_avere += avere
        inst = getattr(form, "instance", None)
        if (
            imp
            or imp_val
            or iva
            or dare
            or avere
            or (inst is not None and getattr(inst, "pk", None))
        ):
            filled += 1
    return {
        "totale_imponibile": tot_imp,
        "totale_imponibile_valuta": tot_imp_val,
        "totale_iva": tot_iva,
        "totale_documento": tot_imp + tot_iva,
        "totale_dare": tot_dare,
        "totale_avere": tot_avere,
        "sbilancio": round(tot_dare - tot_avere, 2),
        "righe_filled": filled,
    }


def _formset_visible_count(formset) -> int:
    n = 0
    for form in getattr(formset, "forms", None) or []:
        if _form_deleted(form):
            continue
        n += 1
    return n


def _pagamento_label(form) -> str:
    if form.is_bound:
        code = form.data.get("codice_paga")
    elif getattr(form.instance, "pk", None):
        code = form.instance.codice_paga
    else:
        code = form.initial.get("codice_paga")
    return resolve_descrizione("condizione", code)


def _partita_info(form) -> dict:
    if form.is_bound:
        code = form.data.get("codice_partita")
    elif getattr(form.instance, "pk", None):
        code = form.instance.codice_partita
    else:
        code = form.initial.get("codice_partita")
    return resolve_partita_clifor(code)


def _fornitore_info(form) -> dict:
    if form.is_bound:
        code = form.data.get("fornitore_cee")
    elif getattr(form.instance, "pk", None):
        code = getattr(form.instance, "fornitore_cee", None)
    else:
        initial = getattr(form, "initial", None) or {}
        code = initial.get("fornitore_cee") if isinstance(initial, dict) else None
    if not isinstance(code, str):
        code = ""
    return resolve_partita_clifor(code)


def _form_tipo(form, registrazione=None, *, is_create: bool = False):
    tipo = None
    if not is_create and registrazione is not None and getattr(
        registrazione, "tipo", None
    ) not in (None, ""):
        tipo = registrazione.tipo
    elif form.is_bound:
        tipo = form.data.get("tipo")
    if tipo in (None, "") and registrazione is not None:
        tipo = registrazione.tipo
    if tipo in (None, ""):
        tipo = form.initial.get("tipo", Primanota.TIPO_IVA)
    return tipo


def _form_causale(form, registrazione=None):
    if form.is_bound:
        code = form.data.get("causale")
    elif registrazione is not None:
        code = registrazione.causale
    elif getattr(form.instance, "pk", None):
        code = getattr(form.instance, "causale", None)
    else:
        initial = getattr(form, "initial", None) or {}
        code = initial.get("causale") if isinstance(initial, dict) else None
    if not isinstance(code, str):
        code = ""
    return resolve_causale_contabile(code)


def _form_valuta_code(form, registrazione=None) -> str:
    code = None
    if form.is_bound:
        code = form.data.get("valuta") if hasattr(form, "data") else None
    elif registrazione is not None:
        code = getattr(registrazione, "valuta", None)
    if code in (None, ""):
        instance = getattr(form, "instance", None)
        if instance is not None:
            code = getattr(instance, "valuta", None)
    if code in (None, ""):
        initial = getattr(form, "initial", None) or {}
        if isinstance(initial, dict):
            code = initial.get("valuta")
    if not isinstance(code, str):
        return ""
    return code.strip()


def _primanota_form_context(form, formset, *, is_create: bool, registrazione=None, request=None):
    totals = _formset_totals(formset)
    partita = _partita_info(form)
    fornitore = _fornitore_info(form)
    tipo = _form_tipo(form, registrazione, is_create=is_create)
    causale = _form_causale(form, registrazione)
    back_url, back_label = (None, "")
    if request is not None:
        back_url, back_label = _partitario_back_from_request(request)
    ctx = {
        "form": form,
        "formset": formset,
        "is_create": is_create,
        "registrazione": registrazione,
        "page_heading": "Nuova registrazione" if is_create else "Modifica registrazione",
        "scadenza_slots": form.scadenza_slots(),
        "scadenze_editable": form.scadenze_editable(),
        "righe_count": _formset_visible_count(formset),
        "is_iva": _tipo_is_iva(tipo),
        "is_generico": _tipo_is_generico(tipo),
        "is_corrispettivi": _tipo_is_corrispettivi(tipo),
        "is_iva_autofattura": _tipo_is_iva_autofattura(tipo),
        "show_fornitore_cee": _tipo_is_iva_autofattura(tipo)
        and causale_is_autofattura_automatica(causale),
        "show_cambio": (not _tipo_is_generico(tipo))
        and is_cambio_visible(_form_valuta_code(form, registrazione)),
        "is_iva_layout": _tipo_is_iva_layout(tipo),
        "pagamento_label": _pagamento_label(form),
        "partita_label": partita.get("label") or "",
        "partita_url": partita.get("url") or "",
        "fornitore_label": fornitore.get("label") or "",
        "fornitore_url": fornitore.get("url") or "",
        "totale_imponibile": totals["totale_imponibile"],
        "totale_imponibile_valuta": totals["totale_imponibile_valuta"],
        "totale_iva": totals["totale_iva"],
        "totale_documento": totals["totale_documento"],
        "totale_dare": totals["totale_dare"],
        "totale_avere": totals["totale_avere"],
        "sbilancio": totals["sbilancio"],
        "calc_scadenze_url": reverse("documenti:calc_scadenze"),
        "causali_catalog_json": json.dumps(
            form.causali_catalog if isinstance(getattr(form, "causali_catalog", None), list) else [],
            ensure_ascii=False,
        ),
        "valute_cambi_json": json.dumps(_valute_cambi_json(), ensure_ascii=False),
        "back_url": back_url,
        "back_label": back_label,
        **_lookup_context(),
    }
    if ctx["is_corrispettivi"]:
        ctx["totale_documento"] = ctx["totale_imponibile"]
    if registrazione:
        righe = list(_righe_queryset(registrazione.pk))
        if ctx["righe_count"] == 0 and righe:
            ctx["righe_count"] = len(righe)
        formset_empty = not (
            totals["totale_imponibile"]
            or totals["totale_iva"]
            or totals["totale_dare"]
            or totals["totale_avere"]
        )
        if formset_empty and righe:
            if ctx["is_iva_layout"]:
                tot_imp = float(sum(r.imponibile for r in righe))
                tot_iva = float(sum(float(r.importo_iva or 0) for r in righe))
                ctx["totale_imponibile"] = tot_imp
                ctx["totale_imponibile_valuta"] = float(sum(r.imponibile_valuta for r in righe))
                ctx["totale_iva"] = tot_iva
                ctx["totale_documento"] = tot_imp if ctx["is_corrispettivi"] else tot_imp + tot_iva
            else:
                ctx["totale_dare"] = float(sum(float(r.dare or 0) for r in righe))
                ctx["totale_avere"] = float(sum(float(r.avere or 0) for r in righe))
            ctx["sbilancio"] = round(
                float(ctx["totale_dare"] or 0) - float(ctx["totale_avere"] or 0), 2
            )
        ctx["causale_contabile"] = resolve_causale_contabile(registrazione.causale)
        ctx["registro_iva_obj"] = resolve_registro_iva(registrazione.registro)
        ctx.update(corrispettivi_extra_from_causale(ctx["causale_contabile"]))
    else:
        causale_code = None
        try:
            raw = form["causale"].value()
            causale_code = raw if isinstance(raw, str) else None
        except Exception:
            causale_code = None
        if not causale_code:
            initial = getattr(form, "initial", None) or {}
            raw = initial.get("causale") if isinstance(initial, dict) else None
            causale_code = raw if isinstance(raw, str) else None
        ctx.update(
            corrispettivi_extra_from_causale(
                resolve_causale_contabile(causale_code) if causale_code else None
            )
        )
    return ctx


def _apply_numero_reg_preview(form: PrimanotaForm, *, is_create: bool) -> None:
    if not is_create:
        return
    form.fields["numero_reg"].widget.attrs["readonly"] = True


class PrimanotaProssimoNumeroView(LoginRequiredMixin, View):
    """JSON: prossimo n. registrazione per la data (anteprima, non riserva)."""

    def get(self, request):
        data_reg = parse_date((request.GET.get("data_reg") or "").strip()) or timezone.localdate()
        contatore = resolve_contatore_primanota(data_reg)
        return JsonResponse(
            {
                "numero_reg": peek_next_numero_reg(data_reg),
                "esercizio": esercizio_from_data(data_reg),
                "contatore": contatore.codice if contatore else None,
            }
        )


class PrimanotaDaCausaleView(LoginRequiredMixin, View):
    """JSON: registro IVA e protocollo dalla causale (anteprima, non riserva)."""

    def get(self, request):
        code = (request.GET.get("causale") or "").strip()
        causale = resolve_causale_contabile(code) if code else None
        payload = protocollo_from_causale(causale)
        payload.update(corrispettivi_extra_from_causale(causale))
        return JsonResponse(payload)


class PrimanotaCreateView(LoginRequiredMixin, View):
    template_name = "primanota/primanota_form.html"

    def get(self, request):
        today = timezone.localdate()
        initial = {
            "tipo": Primanota.TIPO_IVA,
            "valuta": "Euro",
            "data_reg": today,
            "data_valuta": today,
            "numero_reg": peek_next_numero_reg(today),
        }
        causale = (request.GET.get("causale") or "").strip()
        if causale:
            initial["causale"] = causale
            obj = resolve_causale_contabile(causale)
            registro = (getattr(obj, "registro_iva", None) or "").strip()
            if registro:
                initial["registro"] = registro
                prot = peek_next_protocollo(registro)
                if prot is not None:
                    initial["numero_prot"] = prot
        form = PrimanotaForm(initial=initial, is_create=True)
        _apply_numero_reg_preview(form, is_create=True)
        formset = riga_formset_for(is_iva=True)
        return render(
            request,
            self.template_name,
            _primanota_form_context(form, formset, is_create=True),
        )

    def post(self, request):
        form = PrimanotaForm(request.POST, is_create=True)
        _apply_numero_reg_preview(form, is_create=True)
        formset = riga_formset_for(
            request.POST, is_iva=_tipo_is_iva_layout(request.POST.get("tipo"))
        )
        if form.is_valid() and formset.is_valid():
            registrazione = save_primanota_with_righe(form, formset)
            messages.success(
                request, f"Registrazione {registrazione.numero_registrazione} creata."
            )
            return redirect("primanota:detail", pk=registrazione.pk)
        return render(
            request,
            self.template_name,
            _primanota_form_context(form, formset, is_create=True),
        )


class PrimanotaUpdateView(LoginRequiredMixin, View):
    template_name = "primanota/primanota_form.html"

    def get_object(self, pk):
        return get_object_or_404(Primanota, pk=pk)

    def get(self, request, pk):
        registrazione = self.get_object(pk)
        form = PrimanotaForm(instance=registrazione)
        formset = riga_formset_for(
            queryset=_righe_queryset(pk), is_iva=_tipo_is_iva_layout(registrazione.tipo)
        )
        return render(
            request,
            self.template_name,
            _primanota_form_context(
                form,
                formset,
                is_create=False,
                registrazione=registrazione,
                request=request,
            ),
        )

    def post(self, request, pk):
        registrazione = self.get_object(pk)
        form = PrimanotaForm(request.POST, instance=registrazione)
        formset = riga_formset_for(
            request.POST,
            queryset=_righe_queryset(pk),
            is_iva=_tipo_is_iva_layout(registrazione.tipo),
        )
        if form.is_valid() and formset.is_valid():
            registrazione = save_primanota_with_righe(form, formset)
            messages.success(
                request,
                f"Registrazione {registrazione.numero_registrazione} aggiornata.",
            )
            detail = reverse("primanota:detail", kwargs={"pk": registrazione.pk})
            back_url, _ = _partitario_back_from_request(request)
            if back_url:
                from urllib.parse import urlencode

                return redirect(f"{detail}?{urlencode({'next': back_url})}")
            return redirect(detail)
        return render(
            request,
            self.template_name,
            _primanota_form_context(
                form,
                formset,
                is_create=False,
                registrazione=registrazione,
                request=request,
            ),
        )


class PrimanotaDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        registrazione = get_object_or_404(Primanota, pk=pk)
        label = registrazione.numero_registrazione
        delete_primanota(registrazione)
        messages.success(request, f"Registrazione {label} eliminata.")
        return redirect("primanota:list")


def _get_registrazione(pk: int) -> Primanota:
    return get_object_or_404(Primanota, pk=pk)


def _get_riga(pk: int, riga_pk: int) -> tuple[Primanota, PrimanotaDettaglio]:
    registrazione = _get_registrazione(pk)
    riga = get_object_or_404(
        PrimanotaDettaglio, pk=riga_pk, id_testa=registrazione.id
    )
    return registrazione, riga


def _riga_form_context(
    form,
    *,
    registrazione: Primanota,
    riga=None,
    is_create: bool,
):
    pos_label = ""
    if riga and riga.pos is not None:
        pos_label = str(riga.pos)
    return {
        "form": form,
        "registrazione": registrazione,
        "riga": riga,
        "is_create": is_create,
        "is_iva": registrazione.is_iva,
        "show_cambio": (not registrazione.is_generico)
        and is_cambio_visible(registrazione.valuta),
        "page_heading": "Nuovo movimento" if is_create else "Modifica movimento",
        "riga_pos_label": pos_label,
        "labels": form.linked_labels(),
        **_lookup_context(),
    }


class PrimanotaRigaCreateView(LoginRequiredMixin, View):
    template_name = "primanota/riga_form.html"

    def get(self, request, pk):
        registrazione = _get_registrazione(pk)
        form = PrimanotaRigaForm(strict=True, is_iva=registrazione.is_iva)
        return render(
            request,
            self.template_name,
            _riga_form_context(form, registrazione=registrazione, is_create=True),
        )

    def post(self, request, pk):
        registrazione = _get_registrazione(pk)
        form = PrimanotaRigaForm(
            request.POST, strict=True, is_iva=registrazione.is_iva
        )
        if form.is_valid():
            save_single_riga(registrazione, form)
            messages.success(request, "Movimento aggiunto.")
            return redirect("primanota:edit", pk=registrazione.pk)
        return render(
            request,
            self.template_name,
            _riga_form_context(form, registrazione=registrazione, is_create=True),
        )


class PrimanotaRigaUpdateView(LoginRequiredMixin, View):
    template_name = "primanota/riga_form.html"

    def get(self, request, pk, riga_pk):
        registrazione, riga = _get_riga(pk, riga_pk)
        form = PrimanotaRigaForm(
            instance=riga, strict=True, is_iva=registrazione.is_iva
        )
        return render(
            request,
            self.template_name,
            _riga_form_context(
                form, registrazione=registrazione, riga=riga, is_create=False
            ),
        )

    def post(self, request, pk, riga_pk):
        registrazione, riga = _get_riga(pk, riga_pk)
        form = PrimanotaRigaForm(
            request.POST,
            instance=riga,
            strict=True,
            is_iva=registrazione.is_iva,
        )
        if form.is_valid():
            save_single_riga(registrazione, form)
            messages.success(request, "Movimento aggiornato.")
            return redirect("primanota:edit", pk=registrazione.pk)
        return render(
            request,
            self.template_name,
            _riga_form_context(
                form, registrazione=registrazione, riga=riga, is_create=False
            ),
        )


class PrimanotaRigaDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, riga_pk):
        registrazione, riga = _get_riga(pk, riga_pk)
        label = riga.pos if riga.pos is not None else riga_pk
        delete_mirror_row(PrimanotaDettaglio, riga.pk)
        stamp_modifica(registrazione)
        registrazione.save()
        messages.success(request, f"Movimento pos. {label} eliminato.")
        return redirect("primanota:edit", pk=registrazione.pk)


class SyncPrimanotaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "primanota/sync_primanota.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "primanota_count": _pg_table_count("primanota"),
            "dettaglio_count": _pg_table_count("primanota_dettaglio"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_primanota(full=sync_full_from_request(request))
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
