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
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.sorting import SortableListMixin
from apps.primanota.forms import (
    PrimanotaForm,
    PrimanotaRigaForm,
    delete_primanota,
    riga_formset_for,
    save_primanota_with_righe,
    save_single_riga,
)
from apps.primanota.lookups import (
    attach_causali_contabili,
    attach_line_lookups,
    attach_registri_iva,
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
    "ScadenzeIns",
    "Acconto",
} | {f"Scad{i}" for i in range(1, 11)} | {f"ImpScad{i}" for i in range(1, 11)} | {
    f"Flag_RA{i:02d}" for i in range(1, 11)
}


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
    return qs.order_by("-data_reg", "-numero_reg", "-id")


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
        "totale_doc_controllo",
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


class PrimanotaDetailView(LoginRequiredMixin, DetailView):
    model = Primanota
    template_name = "primanota/primanota_detail.html"
    context_object_name = "registrazione"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        righe, dettaglio_mancante = load_primanota_righe(self.object.id)
        context["righe"] = righe
        context["dettaglio_mancante"] = dettaglio_mancante
        context["totale_dare"] = float(sum(float(r.dare or 0) for r in righe))
        context["totale_avere"] = float(sum(float(r.avere or 0) for r in righe))
        context["sbilancio"] = round(context["totale_dare"] - context["totale_avere"], 2)
        context["causale_contabile"] = resolve_causale_contabile(self.object.causale)
        context["registro_iva"] = resolve_registro_iva(self.object.registro)
        context["is_iva"] = self.object.is_iva
        attach_line_lookups(righe, iva=self.object.is_iva)
        if self.object.is_iva:
            totale_imponibile = float(sum(r.imponibile for r in righe))
            totale_iva = float(sum(float(r.importo_iva or 0) for r in righe))
            context["totale_imponibile"] = totale_imponibile
            context["totale_iva"] = totale_iva
            context["totale_documento"] = totale_imponibile + totale_iva
        context["clifor"] = resolve_partita_clifor(self.object.codice_partita)
        context["pagamento"] = resolve_pagamento(self.object.codice_paga)
        row = fetch_primanota_row(self.object.id) or []
        context["campi"] = mirror_row_to_campi(
            row,
            exclude=IVA_CAMPI_EXCLUDE if self.object.is_iva else {
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
            },
        )
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


def _tipo_is_iva(tipo) -> bool:
    try:
        return int(tipo) in (Primanota.TIPO_IVA, Primanota.TIPO_IVA_AUTOFATTURA)
    except (TypeError, ValueError):
        return False


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
    tot_imp = tot_iva = tot_dare = tot_avere = 0.0
    filled = 0
    for form in getattr(formset, "forms", None) or []:
        if _form_deleted(form):
            continue
        imp = _bound_amount(form, "imponibile")
        iva = _bound_amount(form, "importo_iva")
        dare = _bound_amount(form, "dare")
        avere = _bound_amount(form, "avere")
        tot_imp += imp
        tot_iva += iva
        tot_dare += dare
        tot_avere += avere
        inst = getattr(form, "instance", None)
        if (
            imp
            or iva
            or dare
            or avere
            or (inst is not None and getattr(inst, "pk", None))
        ):
            filled += 1
    return {
        "totale_imponibile": tot_imp,
        "totale_iva": tot_iva,
        "totale_documento": tot_imp + tot_iva,
        "totale_dare": tot_dare,
        "totale_avere": tot_avere,
        "sbilancio": round(tot_dare - tot_avere, 2),
        "righe_filled": filled,
    }


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


def _form_tipo(form, registrazione=None):
    tipo = None
    if form.is_bound:
        tipo = form.data.get("tipo")
    if tipo in (None, "") and registrazione is not None:
        tipo = registrazione.tipo
    if tipo in (None, ""):
        tipo = form.initial.get("tipo", Primanota.TIPO_IVA)
    return tipo


def _primanota_form_context(form, formset, *, is_create: bool, registrazione=None):
    totals = _formset_totals(formset)
    partita = _partita_info(form)
    ctx = {
        "form": form,
        "formset": formset,
        "is_create": is_create,
        "registrazione": registrazione,
        "page_heading": "Nuova registrazione" if is_create else "Modifica registrazione",
        "scadenza_slots": form.scadenza_slots(),
        "scadenze_editable": form.scadenze_editable(),
        "righe_count": int(totals["righe_filled"]),
        "is_iva": _tipo_is_iva(_form_tipo(form, registrazione)),
        "is_generico": _tipo_is_generico(_form_tipo(form, registrazione)),
        "pagamento_label": _pagamento_label(form),
        "partita_label": partita.get("label") or "",
        "partita_url": partita.get("url") or "",
        "totale_imponibile": totals["totale_imponibile"],
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
        **_lookup_context(),
    }
    if registrazione:
        righe = list(_righe_queryset(registrazione.pk))
        ctx["righe_count"] = len(righe)
        formset_empty = not (
            totals["totale_imponibile"]
            or totals["totale_iva"]
            or totals["totale_dare"]
            or totals["totale_avere"]
        )
        if formset_empty and righe:
            if ctx["is_iva"]:
                tot_imp = float(sum(r.imponibile for r in righe))
                tot_iva = float(sum(float(r.importo_iva or 0) for r in righe))
                ctx["totale_imponibile"] = tot_imp
                ctx["totale_iva"] = tot_iva
                ctx["totale_documento"] = tot_imp + tot_iva
            else:
                ctx["totale_dare"] = float(sum(float(r.dare or 0) for r in righe))
                ctx["totale_avere"] = float(sum(float(r.avere or 0) for r in righe))
            ctx["sbilancio"] = round(
                float(ctx["totale_dare"] or 0) - float(ctx["totale_avere"] or 0), 2
            )
        ctx["causale_contabile"] = resolve_causale_contabile(registrazione.causale)
        ctx["registro_iva_obj"] = resolve_registro_iva(registrazione.registro)
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
        return JsonResponse(protocollo_from_causale(causale))


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
            request.POST, is_iva=_tipo_is_iva(request.POST.get("tipo"))
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
            queryset=_righe_queryset(pk), is_iva=registrazione.is_iva
        )
        return render(
            request,
            self.template_name,
            _primanota_form_context(
                form, formset, is_create=False, registrazione=registrazione
            ),
        )

    def post(self, request, pk):
        registrazione = self.get_object(pk)
        form = PrimanotaForm(request.POST, instance=registrazione)
        formset = riga_formset_for(
            request.POST,
            queryset=_righe_queryset(pk),
            is_iva=_tipo_is_iva(request.POST.get("tipo") or registrazione.tipo),
        )
        if form.is_valid() and formset.is_valid():
            registrazione = save_primanota_with_righe(form, formset)
            messages.success(
                request,
                f"Registrazione {registrazione.numero_registrazione} aggiornata.",
            )
            return redirect("primanota:detail", pk=registrazione.pk)
        return render(
            request,
            self.template_name,
            _primanota_form_context(
                form, formset, is_create=False, registrazione=registrazione
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
        result = sync_primanota()
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
