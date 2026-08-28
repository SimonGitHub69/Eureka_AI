import re
import json
import threading

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

# Display form of numero_documento: "6/FF", "47/A"
_NUMERO_SERIE_RE = re.compile(r"^(\d+)\s*/\s*(.+)$")

from apps.core.mirror_crud import stamp_modifica
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.sorting import SortableListMixin
from apps.core.programma import (
    DOC_MENU_FIELDS,
    get_documenti_menu_flags,
    get_documenti_menu_items,
    get_tipi_documento_abilitati,
    is_documento_menu_enabled,
)
from apps.documenti.mapping import PREVENTIVI_TIPI
from apps.core.sync_incremental import sync_full_from_request
from apps.documenti.bridge import (
    FattureMirrorUnavailable,
    fatture_mirror_available,
    sync_fatture_mirror_to_unified,
)
from apps.documenti.castelletto import (
    aliquote_map_for_js,
    apply_castelletto_to_testa,
    calcola_castelletto_documento,
    calcola_totale_peso,
    format_euro,
    get_aliquota_iva_spese,
)
from apps.documenti.sconto import sconti_map_for_js
from apps.documenti.forms import (
    AliquotaIvaSpeseForm,
    InviaDocumentoMailForm,
    RigaDocumentoFormSet,
    TestaDocumentoForm,
    riga_formset_for,
)
from apps.documenti.layout import colonne_riga_for
from apps.anagrafiche.models import clienti_mirror_available
from apps.documenti.models import (
    RigaDocumento,
    SyncDocumentiLog,
    TestaDocumento,
    TipoDocumento,
    annotate_clifor_ragione_sociale,
)
from apps.documenti.numerazione import (
    allocate_next_numero,
    initial_numerazione,
    serie_default_for,
    next_riga_id_4d,
    next_testa_id_4d,
)
from apps.documenti.scadenze import (
    calcola_scadenze,
    ensure_scadenze,
    load_condizione,
    scadenze_for_documento,
    slots_as_json,
)
from apps.documenti.sync import (
    CANCELLED_MESSAGE,
    FATTURE_TIPI,
    ensure_documenti_tables,
    request_cancel_sync,
    should_cancel_sync,
    sync_documenti,
)

_SYNC_DOCUMENTI_LOCK = threading.Lock()
_SYNC_DOCUMENTI_RUNNING_LOG_ID: int | None = None


def _sync_documenti_log_snapshot(log: SyncDocumentiLog) -> dict:
    running = log.finished_at is None
    status = "running"
    if not running:
        if log.cancel_requested and not log.ok:
            status = "cancelled"
        elif log.ok:
            status = "done"
        else:
            status = "error"
    return {
        "id": log.pk,
        "status": status,
        "running": running,
        "ok": log.ok,
        "cancel_requested": log.cancel_requested,
        "teste_count": log.teste_count,
        "righe_count": log.righe_count,
        "message": log.message,
        "started_at": log.started_at.isoformat() if log.started_at else "",
        "finished_at": log.finished_at.isoformat() if log.finished_at else "",
    }


def _run_sync_documenti_task(
    log_id: int,
    *,
    tipos: list[str],
    from_mirror: bool,
    full: bool = False,
) -> None:
    global _SYNC_DOCUMENTI_RUNNING_LOG_ID

    log = SyncDocumentiLog.objects.get(pk=log_id)
    parts: list[str] = []
    teste_total = 0
    righe_total = 0
    ok = True
    cancelled = False

    try:
        try:
            ensure_documenti_tables()
        except Exception as exc:
            ok = False
            parts.append(f"Impossibile preparare tabelle documenti: {exc}")
            return

        mirror_present = fatture_mirror_available() if from_mirror else False
        # Bridge-only skips ODBC only when the mirror tables actually exist.
        run_odbc = bool(tipos) or not from_mirror or not mirror_present
        if run_odbc:
            result = sync_documenti(
                only=tipos if tipos else None,
                log_id=log_id,
                full=full,
            )
            parts.extend(t.message for t in result.tables if t.message)
            if result.message and result.message not in parts:
                parts.append(result.message)
            teste_total += result.teste_count
            righe_total += result.righe_count
            ok = ok and result.ok
            cancelled = cancelled or result.cancelled

        if from_mirror and not cancelled and not should_cancel_sync(log_id):
            mirror_tipos = [
                t for t in FATTURE_TIPI if is_documento_menu_enabled(t)
            ]
            if tipos:
                mirror_tipos = [t for t in mirror_tipos if t in tipos]
            if not mirror_tipos:
                parts.append(
                    "Bridge mirror fatture: nessun tipo FAT/NCR/NDB selezionato o abilitato."
                )
            else:
                try:
                    n_teste, n_righe = sync_fatture_mirror_to_unified(
                        tipos=mirror_tipos
                    )
                except FattureMirrorUnavailable as exc:
                    # Warning only — ODBC (if any) already ran / will have run.
                    parts.append(str(exc))
                else:
                    parts.append(
                        f"Bridge mirror fatture ({', '.join(mirror_tipos)}): "
                        f"{n_teste} testate, {n_righe} righe."
                    )
                    teste_total += n_teste
                    righe_total += n_righe

        if should_cancel_sync(log_id):
            cancelled = True
            ok = False
            parts.append(CANCELLED_MESSAGE)
    finally:
        log.refresh_from_db()
        log.ok = ok and not cancelled
        log.teste_count = teste_total
        log.righe_count = righe_total
        if cancelled:
            log.message = "\n".join(parts) if parts else CANCELLED_MESSAGE
            log.cancel_requested = True
        else:
            log.message = "\n".join(parts) or "Nessuna operazione eseguita."
        log.finished_at = timezone.now()
        log.save()
        with _SYNC_DOCUMENTI_LOCK:
            if _SYNC_DOCUMENTI_RUNNING_LOG_ID == log_id:
                _SYNC_DOCUMENTI_RUNNING_LOG_ID = None


def list_tipo_codes_for(tipo_doc: str) -> tuple[str, ...]:
    """Tipi visibili in elenco/filtro: il tipo richiesto più varianti serie nascoste.

    Es. Preventivi (PRV) include PRF (FF) e PRT (T). Fatture/NCR/NDB restano
    elenchi distinti perché hanno ciascuno una voce di menu.
    """
    codice = (tipo_doc or "").upper()
    if not codice:
        return ()
    codes = [codice]
    tipo = TipoDocumento.objects.filter(codice=codice).only("source_table_4d").first()
    source = ((tipo.source_table_4d if tipo else "") or "").strip()
    if not source:
        if codice in PREVENTIVI_TIPI:
            return tuple(PREVENTIVI_TIPI)
        return (codice,)
    siblings = TipoDocumento.objects.filter(
        attivo=True,
        source_table_4d__iexact=source,
    ).values_list("codice", flat=True)
    for sib in siblings:
        if sib not in codes and sib not in DOC_MENU_FIELDS:
            codes.append(sib)
    return tuple(codes)


def _filter_documenti_queryset(
    request, tipo_doc: str | None = None, *, clifor_tipo: str | None = None
):
    qs = TestaDocumento.objects.select_related("tipo_doc")
    if tipo_doc:
        codes = list_tipo_codes_for(tipo_doc)
        if len(codes) == 1:
            qs = qs.filter(tipo_doc_id=codes[0])
        else:
            qs = qs.filter(tipo_doc_id__in=codes)

    q = (request.GET.get("q") or "").strip()
    serie = (request.GET.get("serie") or request.GET.get("alfa") or "").strip()
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())

    if q:
        filters = (
            Q(codice_clifor__icontains=q)
            | Q(codice_agente__icontains=q)
            | Q(destinatario__icontains=q)
            | Q(alfa__icontains=q)
            | Q(file_name__icontains=q)
        )
        if q.isdigit():
            filters |= Q(numero=int(q)) | Q(id_4d=int(q))
        # Users type the displayed ref "6/FF" (numero/alfa), which is not isdigit
        # and does not match alfa alone.
        m = _NUMERO_SERIE_RE.match(q)
        if m:
            serie_q = m.group(2).strip()
            if serie_q:
                filters |= Q(numero=int(m.group(1)), alfa__icontains=serie_q)
        qs = qs.filter(filters)

    if serie:
        qs = qs.filter(alfa__iexact=serie)

    if data_da:
        qs = qs.filter(data_documento__date__gte=data_da)
    if data_a:
        qs = qs.filter(data_documento__date__lte=data_a)

    return annotate_clifor_ragione_sociale(
        qs.order_by("-data_documento", "-numero", "alfa", "-id_4d"),
        clifor_tipo=clifor_tipo,
    )


def _resolve_tipo_doc(tipo_doc: str) -> TipoDocumento:
    codice = (tipo_doc or "").upper()
    if not is_documento_menu_enabled(codice):
        raise PermissionDenied
    return get_object_or_404(
        TipoDocumento.objects.select_related("contatore"),
        codice=codice,
        attivo=True,
    )


def _is_preventivo(tipo: TipoDocumento) -> bool:
    if (getattr(tipo, "categoria", "") or "") == TipoDocumento.CATEGORIA_PREVENTIVI:
        return True
    return (getattr(tipo, "codice", "") or "").upper() in PREVENTIVI_TIPI


def _clifor_label(tipo: TipoDocumento) -> str:
    return "Fornitore" if tipo.clifor_tipo == "F" else "Cliente"


def _testa_form_kwargs(tipo: TipoDocumento, *, is_create: bool = False) -> dict:
    return {
        "clifor_label": _clifor_label(tipo),
        "scadenze_obbligatorie": tipo.scadenze_obbligatorie,
        "tipo": tipo,
        "is_create": is_create,
    }


def _clifor_lookup_tipo(tipo: TipoDocumento) -> str:
    return "fornitore" if tipo.clifor_tipo == "F" else "cliente"


def _clifor_mirror_available(tipo: TipoDocumento) -> bool:
    if tipo.clifor_tipo == "F":
        from apps.anagrafiche.models import fornitori_mirror_available

        return fornitori_mirror_available()
    return clienti_mirror_available()


def _anagrafica_panel(tipo: TipoDocumento, codice: str | None) -> dict:
    """Sede anagrafica (Destinatario 4D): non è il luogo di destinazione del documento."""
    empty = {
        "destinatario": "",
        "indirizzo": "",
        "localita": "",
        "cap": "",
        "provincia": "",
        "nazione": "",
        "telefono": "",
    }
    code = (codice or "").strip()
    if not code or not _clifor_mirror_available(tipo):
        return empty
    from apps.articoli.lookups import resolve_clifor

    info = resolve_clifor(_clifor_lookup_tipo(tipo), code)
    return {
        "destinatario": (info.get("destinatario") or info.get("descrizione") or "").strip(),
        "indirizzo": (info.get("indirizzo") or "").strip(),
        "localita": (info.get("localita") or "").strip(),
        "cap": (info.get("cap") or "").strip(),
        "provincia": (info.get("provincia") or "").strip(),
        "nazione": (info.get("nazione") or "").strip(),
        "telefono": (info.get("telefono") or "").strip(),
    }


def _anagrafica_panel_from_form(form: TestaDocumentoForm, tipo: TipoDocumento) -> dict:
    if form.is_bound:
        codice = form.data.get("codice_clifor")
    else:
        instance = getattr(form, "instance", None)
        codice = getattr(instance, "codice_clifor", None) if instance else None
    return _anagrafica_panel(tipo, codice)


def _clifor_linked_label(form: TestaDocumentoForm, tipo: TipoDocumento) -> str:
    from apps.articoli.lookups import resolve_descrizione

    lookup_tipo = _clifor_lookup_tipo(tipo)
    if form.is_bound:
        return resolve_descrizione(lookup_tipo, form.data.get("codice_clifor"))
    instance = getattr(form, "instance", None)
    if instance and getattr(instance, "pk", None):
        return resolve_descrizione(
            lookup_tipo, getattr(instance, "codice_clifor", None)
        )
    return ""


def _pagamento_label(form: TestaDocumentoForm) -> str:
    from apps.articoli.lookups import resolve_descrizione

    if form.is_bound:
        return resolve_descrizione("condizione", form.data.get("cod_pagamento"))
    instance = getattr(form, "instance", None)
    if instance:
        return resolve_descrizione("condizione", getattr(instance, "cod_pagamento", None))
    return ""


def _agente_label(form: TestaDocumentoForm) -> str:
    from apps.articoli.lookups import resolve_descrizione

    if form.is_bound:
        return resolve_descrizione("agente", form.data.get("codice_agente"))
    instance = getattr(form, "instance", None)
    if instance:
        return resolve_descrizione("agente", getattr(instance, "codice_agente", None))
    return ""


def _porto_label(form: TestaDocumentoForm) -> str:
    from apps.articoli.lookups import resolve_descrizione

    if form.is_bound:
        return resolve_descrizione("porto", form.data.get("porto"))
    instance = getattr(form, "instance", None)
    if instance:
        return resolve_descrizione("porto", getattr(instance, "porto", None))
    return ""


def _cau_trasp_label(form: TestaDocumentoForm) -> str:
    from apps.articoli.lookups import resolve_descrizione

    if form.is_bound:
        return resolve_descrizione("causale_trasp", form.data.get("cod_cau_trasp"))
    instance = getattr(form, "instance", None)
    if instance:
        return resolve_descrizione(
            "causale_trasp", getattr(instance, "cod_cau_trasp", None)
        )
    return ""


def _banca_label(form: TestaDocumentoForm) -> str:
    from apps.articoli.lookups import resolve_descrizione

    if form.is_bound:
        return resolve_descrizione("banca", form.data.get("cod_banca"))
    instance = getattr(form, "instance", None)
    if instance:
        return resolve_descrizione("banca", getattr(instance, "cod_banca", None))
    return ""


def _sconto_label(form: TestaDocumentoForm) -> str:
    from apps.articoli.lookups import resolve_descrizione

    if form.is_bound:
        return resolve_descrizione("sconto", form.data.get("codice_sconto"))
    instance = getattr(form, "instance", None)
    if instance:
        return resolve_descrizione("sconto", getattr(instance, "codice_sconto", None))
    return ""


def _form_pagamento_display(form: TestaDocumentoForm) -> str:
    from apps.anagrafiche.lookups import condizione_display

    if form.is_bound:
        return condizione_display(form.data.get("cod_pagamento"))
    instance = getattr(form, "instance", None)
    if instance:
        return condizione_display(getattr(instance, "cod_pagamento", None))
    return ""


def _clifor_url(tipo: TipoDocumento, codice: str | None) -> str:
    """URL scheda Cliente/Fornitore se il codice è risolvibile nel mirror."""
    code = (codice or "").strip()
    if not code or not _clifor_mirror_available(tipo):
        return ""
    from apps.articoli.lookups import resolve_clifor

    info = resolve_clifor(_clifor_lookup_tipo(tipo), code)
    if not info.get("found"):
        return ""
    resolved = (info.get("codice") or code).strip()
    if tipo.clifor_tipo == "F":
        return reverse("anagrafiche:fornitore_detail", kwargs={"codice": resolved})
    return reverse("anagrafiche:cliente_detail", kwargs={"codice": resolved})


def _clifor_url_from_form(form: TestaDocumentoForm, tipo: TipoDocumento) -> str:
    if form.is_bound:
        codice = form.data.get("codice_clifor")
    else:
        instance = getattr(form, "instance", None)
        codice = getattr(instance, "codice_clifor", None) if instance else None
    return _clifor_url(tipo, codice)


def _documento_form_context(
    *,
    tipo: TipoDocumento,
    form: TestaDocumentoForm,
    formset: RigaDocumentoFormSet,
    is_create: bool,
    documento: TestaDocumento | None = None,
    castelletto=None,
):
    label = tipo.label
    clifor_linked = _clifor_mirror_available(tipo)

    return {
        "tipo": tipo,
        "form": form,
        "formset": formset,
        "documento": documento,
        "is_create": is_create,
        "page_heading": f"Nuovo {label}" if is_create else f"Modifica {label}",
        "clifor_label": _clifor_label(tipo),
        "clifor_linked": clifor_linked,
        "clifor_lookup_tipo": _clifor_lookup_tipo(tipo),
        "clifor_linked_label": (
            _clifor_linked_label(form, tipo) if clifor_linked else ""
        ),
        "clifor_url": _clifor_url_from_form(form, tipo) if clifor_linked else "",
        "anagrafica": _anagrafica_panel_from_form(form, tipo),
        "pagamento_label": _pagamento_label(form),
        "agente_label": _agente_label(form),
        "porto_label": _porto_label(form),
        "cau_trasp_label": _cau_trasp_label(form),
        "banca_label": _banca_label(form),
        "sconto_label": _sconto_label(form),
        "lookup_url": reverse("articoli:lookup_codice"),
        "castelletto": castelletto,
        "aliquote_map_json": json.dumps(aliquote_map_for_js(), ensure_ascii=False),
        "sconti_map_json": json.dumps(sconti_map_for_js(), ensure_ascii=False),
        "aliquota_iva_spese_json": json.dumps(
            get_aliquota_iva_spese(), ensure_ascii=False
        ),
        "calc_peso_url": reverse("documenti:calc_peso"),
        "calc_scadenze_url": reverse("documenti:calc_scadenze"),
        "colonne_riga": colonne_riga_for(tipo),
        "pagamento_display": _form_pagamento_display(form),
    }


def _castelletto_from_formset(form, formset):
    """Anteprima castelletto da form/formset (anche non salvati)."""
    from apps.documenti.castelletto import calcola_castelletto
    from apps.documenti.sconto import header_sconto_from_documento
    from types import SimpleNamespace

    righe = []
    for f in formset.forms:
        if not hasattr(f, "cleaned_data") or not f.cleaned_data:
            # Unbound GET: usa initial/instance
            data = {}
            if f.is_bound:
                continue
            inst = f.instance
            for name in (
                "codice",
                "descrizione",
                "quantita",
                "prezzo_unitario",
                "sconto",
                "iva",
            ):
                val = getattr(inst, name, None)
                if val in (None, "") and getattr(f, "initial", None):
                    val = f.initial.get(name)
                data[name] = val
            if not any(data.get(n) not in (None, "") for n in data):
                continue
            righe.append(data)
            continue
        if f.cleaned_data.get("DELETE"):
            continue
        cd = f.cleaned_data
        if not any(
            cd.get(n) not in (None, "")
            for n in (
                "codice",
                "descrizione",
                "quantita",
                "prezzo_unitario",
                "sconto",
                "iva",
            )
        ):
            continue
        righe.append(cd)

    # GET senza cleaned_data: leggi instance dal formset
    if not form.is_bound and not righe and getattr(formset, "instance", None):
        inst = formset.instance
        if getattr(inst, "pk", None):
            return calcola_castelletto_documento(inst, with_peso=True)

    spese = {}
    if form.is_bound and hasattr(form, "cleaned_data") and form.cleaned_data:
        for name in (
            "spese_imballo",
            "spese_trasporto",
            "spese_incasso",
            "spese_varie",
            "spese_bolli",
        ):
            spese[name] = form.cleaned_data.get(name)
    elif getattr(form, "instance", None) and form.instance.pk:
        for name in (
            "spese_imballo",
            "spese_trasporto",
            "spese_incasso",
            "spese_varie",
            "spese_bolli",
            "spese_e15",
        ):
            spese[name] = getattr(form.instance, name, None)

    header_sconto = ""
    if form.is_bound and hasattr(form, "cleaned_data") and form.cleaned_data:
        header_sconto = header_sconto_from_documento(
            SimpleNamespace(
                sconto=form.cleaned_data.get("sconto"),
                codice_sconto=form.cleaned_data.get("codice_sconto"),
            )
        )
    elif getattr(form, "instance", None):
        header_sconto = header_sconto_from_documento(form.instance)

    return calcola_castelletto(
        righe,
        spese=spese,
        aliquota_iva_spese=get_aliquota_iva_spese(),
        header_sconto=header_sconto,
    )


def _apply_castelletto_after_save(documento: TestaDocumento) -> None:
    apply_castelletto_to_testa(documento)
    documento.save(update_fields=["imponibile", "totale"])


def _riga_has_content(obj: RigaDocumento) -> bool:
    return any(
        getattr(obj, name) not in (None, "")
        for name in (
            "codice",
            "descrizione",
            "quantita",
            "prezzo_unitario",
            "iva",
            "sconto",
            "unita_misura",
            "provvigione",
        )
    )


def _save_righe_formset(documento: TestaDocumento, formset: RigaDocumentoFormSet) -> None:
    formset.save(commit=False)
    for obj in formset.deleted_objects:
        obj.delete()

    # Keeper in ordine formset (non-DELETE). Rinumera sempre 10, 20, 30…
    # così l'ordine resta pulito anche senza JS; le DELETE non vengono toccate.
    keepers = []
    for form in formset.forms:
        if not hasattr(form, "cleaned_data") or not form.cleaned_data:
            continue
        if form.cleaned_data.get("DELETE"):
            continue
        obj = form.instance
        if not obj.pk and not _riga_has_content(obj):
            continue
        keepers.append(obj)

    next_id = next_riga_id_4d(documento)
    next_num = 10
    for obj in keepers:
        obj.testa = documento
        if obj.__dict__.get("id_4d") in (None, ""):
            obj.id_4d = next_id
            next_id += 1
        obj.numero_riga = next_num
        next_num += 10
        stamp_modifica(obj)
        obj.save()


class DocumentoIndexView(LoginRequiredMixin, ListView):
    """Elenco tipi documento attivi con link alle rispettive liste."""

    model = TipoDocumento
    template_name = "documenti/documento_index.html"
    context_object_name = "tipi"

    def get_queryset(self):
        allowed = [item["codice"] for item in get_documenti_menu_items()]
        return TipoDocumento.objects.filter(codice__in=allowed)


class DocumentoListView(LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView):
    model = TestaDocumento
    template_name = "documenti/documento_list.html"
    context_object_name = "documenti"
    sortable_fields = (
        "numero",
        "data_documento",
        "cliente_ragione_sociale1",
        "codice_clifor",
        "codice_agente",
        "destinatario",
        "imponibile",
        "totale",
        "id_4d",
    )
    default_sort = "data_documento"
    default_dir = "desc"
    sort_tiebreaker = ("-numero", "alfa", "-id_4d")
    sort_fallbacks = {"cliente_ragione_sociale1": "codice_clifor"}
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        self.tipo_doc = kwargs.get("tipo_doc", "").upper()
        self.tipo = _resolve_tipo_doc(self.tipo_doc)
        self._clienti_available = _clifor_mirror_available(self.tipo)
        return super().dispatch(request, *args, **kwargs)

    def get_sortable_fields(self):
        available = getattr(self, "_clienti_available", None)
        if available is None:
            available = _clifor_mirror_available(self.tipo)
            self._clienti_available = available
        fields = self.sortable_fields
        if not available:
            return tuple(f for f in fields if f != "cliente_ragione_sociale1")
        return fields

    def get_mirror_queryset(self):
        # Annotation prima di SortableListMixin.apply_sorting (order_by)
        return _filter_documenti_queryset(
            self.request,
            self.tipo_doc,
            clifor_tipo=self.tipo.clifor_tipo,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["tipo"] = self.tipo
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["serie"] = (
            self.request.GET.get("serie") or self.request.GET.get("alfa") or ""
        ).strip()
        context["data_da"] = (self.request.GET.get("data_da") or "").strip()
        context["data_a"] = (self.request.GET.get("data_a") or "").strip()
        context["has_filters"] = bool(
            context["q"]
            or context["serie"]
            or context["data_da"]
            or context["data_a"]
        )
        if getattr(self, "_clienti_available", None) is None:
            self._clienti_available = _clifor_mirror_available(self.tipo)
        context["sort_cliente_ragione_sociale"] = self._clienti_available
        context["totale"] = safe_mirror_count(
            TestaDocumento.objects.filter(tipo_doc_id__in=list_tipo_codes_for(self.tipo_doc))
        )
        return context


class DocumentoDetailView(LoginRequiredMixin, DetailView):
    model = TestaDocumento
    template_name = "documenti/documento_detail.html"
    context_object_name = "documento"
    pk_url_kwarg = "pk"

    def dispatch(self, request, *args, **kwargs):
        self.tipo_doc = kwargs.get("tipo_doc", "").upper()
        self.tipo = _resolve_tipo_doc(self.tipo_doc)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return annotate_clifor_ragione_sociale(
            TestaDocumento.objects.select_related("tipo_doc").filter(
                tipo_doc_id=self.tipo_doc
            ),
            clifor_tipo=self.tipo.clifor_tipo,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tipo"] = self.tipo
        context["righe"] = RigaDocumento.objects.filter(testa=self.object).order_by(
            "numero_riga", "id_4d"
        )
        context["castelletto"] = calcola_castelletto_documento(
            self.object, with_peso=True
        )
        context["colonne_riga"] = colonne_riga_for(self.tipo)
        from apps.anagrafiche.lookups import condizione_display
        from apps.articoli.lookups import resolve_clifor, resolve_descrizione

        codice_pag = (self.object.cod_pagamento or "").strip()
        if not codice_pag and (self.object.codice_clifor or "").strip():
            lookup = "fornitore" if self.object.clifor_tipo == "F" else "cliente"
            codice_pag = (
                resolve_clifor(lookup, self.object.codice_clifor).get("cond_paga") or ""
            ).strip()
        context["pagamento_display"] = condizione_display(codice_pag)
        context["agente_label"] = resolve_descrizione("agente", self.object.codice_agente)
        context["porto_label"] = resolve_descrizione("porto", self.object.porto)
        context["cau_trasp_label"] = resolve_descrizione(
            "causale_trasp", self.object.cod_cau_trasp
        )
        context["banca_label"] = resolve_descrizione("banca", self.object.cod_banca)
        context["sconto_label"] = resolve_descrizione("sconto", self.object.codice_sconto)
        context["scadenze"] = scadenze_for_documento(
            self.object, codice_pagamento=codice_pag
        )
        context["anagrafica"] = _anagrafica_panel(
            self.tipo, self.object.codice_clifor
        )
        context["clifor_label"] = _clifor_label(self.tipo)
        context["clifor_lookup_tipo"] = _clifor_lookup_tipo(self.tipo)
        context["clifor_url"] = _clifor_url(self.tipo, self.object.codice_clifor)
        return context


class DocumentoPrintView(LoginRequiredMixin, View):
    """Stampa HTML del documento (layout preventivo) con logo stampe documenti."""

    template_name = "documenti/documento_print.html"

    def get(self, request, tipo_doc, pk):
        tipo = _resolve_tipo_doc(tipo_doc)
        documento = get_object_or_404(
            TestaDocumento.objects.select_related("tipo_doc"),
            pk=pk,
            tipo_doc_id=tipo.codice,
        )
        from apps.documenti.print_documento import build_documento_print_context

        ctx = build_documento_print_context(
            documento,
            autoprint=(request.GET.get("autoprint") or "").strip()
            in {"1", "true", "yes"},
        )
        return render(request, self.template_name, ctx)


class DocumentoInviaMailView(LoginRequiredMixin, View):
    """Invio del documento via SMTP (Parametri mail)."""

    template_name = "documenti/documento_invia_mail.html"

    def dispatch(self, request, *args, **kwargs):
        self.tipo_doc = kwargs.get("tipo_doc", "").upper()
        self.tipo = _resolve_tipo_doc(self.tipo_doc)
        return super().dispatch(request, *args, **kwargs)

    def _documento(self, pk):
        return get_object_or_404(
            annotate_clifor_ragione_sociale(
                TestaDocumento.objects.select_related("tipo_doc").filter(
                    tipo_doc_id=self.tipo.codice
                ),
                clifor_tipo=self.tipo.clifor_tipo,
            ),
            pk=pk,
        )

    def _next_url(self, request, documento):
        nxt = (request.POST.get("next") or request.GET.get("next") or "").strip()
        if nxt.startswith("/") and not nxt.startswith("//"):
            return nxt
        return reverse(
            "documenti:list",
            kwargs={"tipo_doc": documento.tipo_doc_id},
        )

    def _mail_status(self):
        from apps.core.mail import get_parametri_mail, normalize_smtp_host

        cfg = get_parametri_mail()
        host, _port = normalize_smtp_host(cfg.server_smtp)
        return {
            "attiva": bool(cfg.attiva),
            "smtp_ok": bool(host and (cfg.mittente or "").strip()),
        }

    def _form(self, documento, data=None):
        from apps.documenti.mail_documento import (
            default_mail_body,
            default_mail_subject,
            resolve_documento_email,
        )

        initial = {
            "destinatario": resolve_documento_email(documento),
            "oggetto": default_mail_subject(documento),
            "messaggio": default_mail_body(documento),
        }
        return InviaDocumentoMailForm(data, initial=initial)

    def _context(self, request, documento, form):
        from apps.documenti.mail_documento import documento_mail_title

        return {
            "tipo": self.tipo,
            "documento": documento,
            "form": form,
            "mail_title": documento_mail_title(documento),
            "next_url": self._next_url(request, documento),
            "mail_status": self._mail_status(),
            "list_url": reverse(
                "documenti:list", kwargs={"tipo_doc": documento.tipo_doc_id}
            ),
        }

    def get(self, request, tipo_doc, pk):
        documento = self._documento(pk)
        return render(
            request,
            self.template_name,
            self._context(request, documento, self._form(documento)),
        )

    def post(self, request, tipo_doc, pk):
        from apps.core.mail import describe_mail_error, parse_address_list, send_mail_automatica
        from apps.documenti.mail_documento import parse_destinatari

        documento = self._documento(pk)
        form = self._form(documento, request.POST)
        if not form.is_valid():
            return render(
                request, self.template_name, self._context(request, documento, form)
            )
        to = parse_destinatari(form.cleaned_data["destinatario"])
        cc = parse_address_list(form.cleaned_data.get("cc"))
        try:
            from apps.documenti.pdf_documento import pdf_filename_for, render_documento_pdf

            pdf_bytes = render_documento_pdf(documento)
            send_mail_automatica(
                subject=form.cleaned_data["oggetto"],
                body=form.cleaned_data["messaggio"],
                to=to,
                cc=cc,
                attachments=[
                    (pdf_filename_for(documento), pdf_bytes, "application/pdf"),
                ],
            )
        except RuntimeError as exc:
            messages.error(request, str(exc))
            return render(
                request, self.template_name, self._context(request, documento, form)
            )
        except Exception as exc:
            messages.error(
                request,
                describe_mail_error(exc, host=""),
            )
            return render(
                request, self.template_name, self._context(request, documento, form)
            )
        dest = ", ".join(to)
        messages.success(request, f"Documento inviato per email a {dest}.")
        return redirect(self._next_url(request, documento))


class DocumentoCreateView(LoginRequiredMixin, View):
    template_name = "documenti/documento_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.tipo_doc = kwargs.get("tipo_doc", "").upper()
        self.tipo = _resolve_tipo_doc(self.tipo_doc)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, tipo_doc):
        form = TestaDocumentoForm(
            initial={
                **initial_numerazione(self.tipo),
                "data_documento": timezone.localtime(),
            },
            **_testa_form_kwargs(self.tipo, is_create=True),
        )
        formset = riga_formset_for(self.tipo)
        castelletto = _castelletto_from_formset(form, formset)
        return render(
            request,
            self.template_name,
            _documento_form_context(
                tipo=self.tipo,
                form=form,
                formset=formset,
                is_create=True,
                castelletto=castelletto,
            ),
        )

    def post(self, request, tipo_doc):
        form = TestaDocumentoForm(
            request.POST, **_testa_form_kwargs(self.tipo, is_create=True)
        )
        formset = riga_formset_for(self.tipo, request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                documento = form.save(commit=False)
                documento.tipo_doc = self.tipo
                documento.id_4d = next_testa_id_4d(self.tipo.codice)
                documento.source_table_4d = self.tipo.source_table_4d or ""
                documento.clifor_tipo = self.tipo.clifor_tipo or ""
                contatore = form.cleaned_data.get("contatore_scelto")
                if contatore is not None:
                    documento.alfa = serie_default_for(self.tipo, contatore)
                elif not (documento.alfa or "").strip():
                    default_serie = serie_default_for(self.tipo)
                    if default_serie:
                        documento.alfa = default_serie
                # Sempre alloca al salvataggio: l'anteprima GET non riserva il numero
                # (due utenti possono vedere lo stesso N; select_for_update serializza).
                documento.numero = allocate_next_numero(
                    self.tipo,
                    documento.alfa or "",
                    contatore=contatore,
                )
                if not documento.data_documento:
                    documento.data_documento = timezone.localtime()
                ensure_scadenze(documento)
                stamp_modifica(documento)
                documento.save()
                formset.instance = documento
                _save_righe_formset(documento, formset)
                _apply_castelletto_after_save(documento)
            messages.success(
                request,
                f"{self.tipo.label} {documento.numero_documento} creato.",
            )
            return redirect(
                "documenti:detail",
                tipo_doc=self.tipo.codice,
                pk=documento.pk,
            )
        return render(
            request,
            self.template_name,
            _documento_form_context(
                tipo=self.tipo,
                form=form,
                formset=formset,
                is_create=True,
                castelletto=_castelletto_from_formset(form, formset),
            ),
        )


class DocumentoUpdateView(LoginRequiredMixin, View):
    template_name = "documenti/documento_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.tipo_doc = kwargs.get("tipo_doc", "").upper()
        self.tipo = _resolve_tipo_doc(self.tipo_doc)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, pk):
        return get_object_or_404(
            TestaDocumento.objects.select_related("tipo_doc"),
            pk=pk,
            tipo_doc_id=self.tipo_doc,
        )

    def get(self, request, tipo_doc, pk):
        documento = self.get_object(pk)
        form = TestaDocumentoForm(
            instance=documento, **_testa_form_kwargs(self.tipo)
        )
        formset = riga_formset_for(self.tipo, instance=documento)
        return render(
            request,
            self.template_name,
            _documento_form_context(
                tipo=self.tipo,
                form=form,
                formset=formset,
                is_create=False,
                documento=documento,
                castelletto=calcola_castelletto_documento(documento, with_peso=True),
            ),
        )

    def post(self, request, tipo_doc, pk):
        documento = self.get_object(pk)
        form = TestaDocumentoForm(
            request.POST,
            instance=documento,
            **_testa_form_kwargs(self.tipo),
        )
        formset = riga_formset_for(self.tipo, request.POST, instance=documento)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                documento = form.save(commit=False)
                documento.tipo_doc = self.tipo
                if not documento.clifor_tipo:
                    documento.clifor_tipo = self.tipo.clifor_tipo or ""
                ensure_scadenze(documento)
                stamp_modifica(documento)
                documento.save()
                _save_righe_formset(documento, formset)
                _apply_castelletto_after_save(documento)
            messages.success(
                request,
                f"{self.tipo.label} {documento.numero_documento} aggiornato.",
            )
            return redirect(
                "documenti:detail",
                tipo_doc=self.tipo.codice,
                pk=documento.pk,
            )
        return render(
            request,
            self.template_name,
            _documento_form_context(
                tipo=self.tipo,
                form=form,
                formset=formset,
                is_create=False,
                documento=documento,
                castelletto=_castelletto_from_formset(form, formset),
            ),
        )


class CalcScadenzeView(LoginRequiredMixin, View):
    """GET: codice condizione + data documento → N scadenze (numero rate)."""

    def get(self, request):
        codice = (request.GET.get("codice") or "").strip()
        kwargs = {
            "data_documento": request.GET.get("data"),
            "condizione": load_condizione(codice),
            "totale": request.GET.get("totale"),
        }
        raw_max = (request.GET.get("max_n") or "").strip()
        if raw_max:
            try:
                kwargs["max_n"] = int(raw_max)
            except (TypeError, ValueError):
                pass
        slots = calcola_scadenze(**kwargs)
        return JsonResponse({"ok": True, "scadenze": slots_as_json(slots)})


class CalcPesoDocumentoView(LoginRequiredMixin, View):
    """POST JSON: {lines:[{codice, quantita}, ...]} → totale_peso da Articoli.PesoLordo_Manodopera."""

    def post(self, request):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON non valido."}, status=400)
        lines = payload.get("lines") or []
        if not isinstance(lines, list):
            return JsonResponse({"ok": False, "error": "lines deve essere una lista."}, status=400)
        peso = calcola_totale_peso(lines)
        return JsonResponse(
            {
                "ok": True,
                "totale_peso": float(peso),
                "totale_peso_fmt": format_euro(peso),
            }
        )


class DocumentoDeleteView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.tipo_doc = kwargs.get("tipo_doc", "").upper()
        self.tipo = _resolve_tipo_doc(self.tipo_doc)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, tipo_doc, pk):
        documento = get_object_or_404(
            TestaDocumento, pk=pk, tipo_doc_id=self.tipo_doc
        )
        label = documento.numero_documento
        documento.delete()
        messages.success(request, f"{self.tipo.label} {label} eliminato.")
        return redirect("documenti:list", tipo_doc=self.tipo.codice)


class SyncDocumentiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "documenti/sync_documenti.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self):
        last_log = SyncDocumentiLog.objects.first()
        running_log = SyncDocumentiLog.objects.filter(finished_at__isnull=True).first()
        counts = {}
        for tipo in TipoDocumento.objects.filter(attivo=True):
            counts[tipo.codice] = TestaDocumento.objects.filter(
                tipo_doc_id=tipo.codice
            ).count()
        try:
            righe_count = RigaDocumento.objects.count()
        except Exception:
            righe_count = 0
        doc_menu_flags = get_documenti_menu_flags()
        tipi_qs = TipoDocumento.objects.filter(attivo=True)
        return {
            "last_log": last_log,
            "running_log": running_log,
            "counts": counts,
            "righe_count": righe_count,
            "tipi": tipi_qs,
            "doc_menu_flags": doc_menu_flags,
            "tipi_sync_abilitati": get_tipi_documento_abilitati(),
            "tipi_con_flags": [
                {
                    "tipo": tipo,
                    "enabled": doc_menu_flags.get(tipo.codice, True),
                }
                for tipo in tipi_qs
            ],
            "fatture_mirror_available": fatture_mirror_available(),
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        tipos_raw = request.POST.getlist("tipos")
        from_mirror = request.POST.get("from_fatture_mirror") == "on"
        full = sync_full_from_request(request)
        tipos = [
            t.strip().upper()
            for t in tipos_raw
            if t.strip() and is_documento_menu_enabled(t.strip().upper())
        ]

        if not tipos and not from_mirror:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Selezionare almeno una tabella da importare.",
                    },
                    status=400,
                )
            messages.error(request, "Selezionare almeno una tabella da importare.")
            return render(request, self.template_name, self.get_context())

        global _SYNC_DOCUMENTI_RUNNING_LOG_ID
        with _SYNC_DOCUMENTI_LOCK:
            running_log = SyncDocumentiLog.objects.filter(
                finished_at__isnull=True
            ).first()
            if running_log or _SYNC_DOCUMENTI_RUNNING_LOG_ID is not None:
                running_id = (
                    running_log.pk if running_log else _SYNC_DOCUMENTI_RUNNING_LOG_ID
                )
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "ok": False,
                            "error": "Sincronizzazione già in corso.",
                            "log_id": running_id,
                        },
                        status=409,
                    )
                messages.error(request, "Sincronizzazione già in corso.")
                return redirect("documenti:sync")

            log = SyncDocumentiLog.objects.create(
                started_by=request.user,
                message="Sync in corso...",
            )
            _SYNC_DOCUMENTI_RUNNING_LOG_ID = log.pk

        thread = threading.Thread(
            target=_run_sync_documenti_task,
            kwargs={
                "log_id": log.pk,
                "tipos": tipos,
                "from_mirror": from_mirror,
                "full": full,
            },
            daemon=True,
        )
        thread.start()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "log_id": log.pk})

        messages.info(request, "Sincronizzazione avviata in background.")
        return redirect("documenti:sync")


class SyncDocumentiStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get(self, request, log_id, *args, **kwargs):
        log = get_object_or_404(SyncDocumentiLog, pk=log_id)
        return JsonResponse({"ok": True, "log": _sync_documenti_log_snapshot(log)})


def _safe_next_url(request, *, fallback: str) -> str:
    """Redirect interno: query ``next`` o header Referer se stesso host."""
    candidates = [
        (request.POST.get("next") or request.GET.get("next") or "").strip(),
        (request.META.get("HTTP_REFERER") or "").strip(),
    ]
    for raw in candidates:
        if not raw:
            continue
        from urllib.parse import urlparse

        parsed = urlparse(raw)
        if parsed.scheme or parsed.netloc:
            if parsed.netloc and parsed.netloc != request.get_host():
                continue
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            if path.startswith("/") and not path.startswith("//"):
                return path
        elif raw.startswith("/") and not raw.startswith("//"):
            return raw
    return fallback


class DocumentoParametriSpeseView(LoginRequiredMixin, View):
    """Parametri Preventivi: modifica aliquota IVA spese (Parametri contabili)."""

    template_name = "documenti/parametri_spese.html"

    def dispatch(self, request, *args, **kwargs):
        self.tipo = _resolve_tipo_doc(kwargs.get("tipo_doc", ""))
        if not _is_preventivo(self.tipo):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _list_url(self) -> str:
        return reverse("documenti:list", kwargs={"tipo_doc": self.tipo.codice})

    def _context(self, form, *, next_url: str) -> dict:
        from apps.articoli.lookups import resolve_descrizione
        from apps.core.models import ParametriContabili

        code = (
            form.data.get("aliquota_iva_spese")
            if form.is_bound
            else form.instance.aliquota_iva_spese
        )
        return {
            "tipo": self.tipo,
            "form": form,
            "iva_label": resolve_descrizione("iva", code),
            "lookup_url": reverse("articoli:lookup_codice"),
            "next_url": next_url,
            "parametri_contabili_url": reverse("core:parametri_contabili"),
            "list_url": self._list_url(),
            "aliquota_corrente": ParametriContabili.get_solo().aliquota_iva_spese_codice(),
        }

    def get(self, request, *args, **kwargs):
        from apps.core.models import ParametriContabili

        instance = ParametriContabili.get_solo()
        form = AliquotaIvaSpeseForm(instance=instance)
        next_url = _safe_next_url(request, fallback=self._list_url())
        return render(
            request, self.template_name, self._context(form, next_url=next_url)
        )

    def post(self, request, *args, **kwargs):
        from apps.core.models import ParametriContabili

        instance = ParametriContabili.get_solo()
        form = AliquotaIvaSpeseForm(request.POST, instance=instance)
        next_url = _safe_next_url(request, fallback=self._list_url())
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            if not obj.created_by:
                obj.created_by = request.user
            obj.save()
            code = obj.aliquota_iva_spese_codice()
            if code:
                messages.success(
                    request,
                    f"Aliquota IVA spese impostata su «{code}».",
                )
            else:
                messages.success(
                    request,
                    "Aliquota IVA spese azzerata (si userà quella della prima riga merce).",
                )
            return redirect(next_url)
        return render(
            request, self.template_name, self._context(form, next_url=next_url)
        )


class SyncDocumentiCancelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def post(self, request, *args, **kwargs):
        log_id_raw = request.POST.get("log_id")
        if not log_id_raw:
            return JsonResponse(
                {"ok": False, "error": "ID log mancante."},
                status=400,
            )
        try:
            log_id = int(log_id_raw)
        except (TypeError, ValueError):
            return JsonResponse(
                {"ok": False, "error": "ID log non valido."},
                status=400,
            )

        if request_cancel_sync(log_id):
            return JsonResponse({"ok": True, "message": "Interruzione richiesta."})

        return JsonResponse(
            {
                "ok": False,
                "error": "Nessuna sincronizzazione attiva da interrompere.",
            },
            status=404,
        )
