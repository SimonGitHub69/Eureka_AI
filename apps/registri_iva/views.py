from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView

from apps.aziende.configurazione import resolve_print_azienda_context
from apps.core.export_list import ExportListMixin
from apps.core.mirror_crud import mirror_row_to_campi, save_mirror_form_instance
from apps.core.pagination import PerPageListMixin, SafeMirrorListMixin, safe_mirror_count
from apps.core.print_list import MirrorPrintListView, print_preview_requested
from apps.core.sorting import SortableListMixin
from apps.core.sync_incremental import sync_full_from_request
from apps.primanota.lookups import registro_iva_choices
from apps.registri_iva.forms import RegistroIvaForm, RegistroIvaStampaStatoForm
from apps.registri_iva.liquidazione import (
    LiquidazionePeriodicaDati,
    build_liquidazione_periodica,
    mese_choices,
    resolve_azienda_header_liquidazione,
    resolve_periodo_liquidazione,
)
from apps.registri_iva.libro_registro import (
    LibroRegistroIvaDati,
    _resolve_azienda_header,
    build_libro_registro_iva,
    parse_includi_reg_successive,
)
from apps.registri_iva.models import RegistroIva, RegistroIvaStampaStato
from apps.registri_iva.stampa_stato import (
    LIQUIDAZIONE_STAMPA_CODICE,
    StampaDefinitivaInfo,
    get_stampa_stato,
    parse_int_or_none,
    periodo_sovrappone_definitiva,
    resolve_data_a_default,
    resolve_data_da_default,
    resolve_pagina_da,
    save_stampa_stato,
    stima_num_pagine,
)
from apps.registri_iva.sync import sync_registri_iva


def _filter_registri_iva_queryset(request):
    qs = RegistroIva.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(codice__icontains=q)
            | Q(descrizione__icontains=q)
            | Q(tipo_registro__icontains=q)
        )
    tipo = (request.GET.get("tipo") or "").strip()
    if tipo:
        qs = qs.filter(tipo_registro__iexact=tipo)
    attivo = (request.GET.get("attivo") or "").strip()
    if attivo == "1":
        qs = qs.filter(Q(disattivato=False) | Q(disattivato__isnull=True))
    elif attivo == "0":
        qs = qs.filter(disattivato=True)
    return qs.order_by("codice")


def _registri_iva_print_filter_summary(request) -> str:
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
    if tipo:
        parts.append(f"Tipo: {tipo}")

    attivo = (request.GET.get("attivo") or "").strip()
    if attivo == "1":
        parts.append("Solo attivi")
    elif attivo == "0":
        parts.append("Solo disattivati")

    q = (request.GET.get("q") or "").strip()
    if q:
        parts.append(f'Ricerca: "{q}"')

    return " · ".join(parts)


def _is_registri_iva_elenco_stampa(request) -> bool:
    return (request.GET.get("elenco") or "").strip() == "1"


def _registri_iva_list_context(view, context):
    params = view.request.GET.copy()
    params.pop("page", None)
    params["elenco"] = "1"
    context["filter_query"] = params.urlencode()
    context["q"] = (view.request.GET.get("q") or "").strip()
    context["tipo"] = (view.request.GET.get("tipo") or "").strip()
    context["attivo"] = (view.request.GET.get("attivo") or "").strip()
    context["has_filters"] = bool(context["q"] or context["tipo"] or context["attivo"])
    context["totale"] = safe_mirror_count(RegistroIva.objects)
    return context


def fetch_registro_iva_row(codice: str) -> list[tuple[str, object]] | None:
    with connection.cursor() as cur:
        cur.execute('SELECT * FROM registri_iva WHERE "Codice" = %s', [codice])
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
    return list(zip(columns, row))


class RegistroIvaListView(
    LoginRequiredMixin, SortableListMixin, SafeMirrorListMixin, PerPageListMixin, ListView
):
    model = RegistroIva
    template_name = "registri_iva/registro_list.html"
    context_object_name = "registri"
    sortable_fields = ("codice", "descrizione", "tipo_registro", "disattivato")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    paginate_by = 50

    def get_mirror_queryset(self):
        return _filter_registri_iva_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return _registri_iva_list_context(self, context)


class RegistroIvaElencoPrintView(MirrorPrintListView):
    print_title = "Registri IVA"
    print_subtitle = "Elenco registri IVA"
    filter_queryset = staticmethod(_filter_registri_iva_queryset)
    sortable_fields = ("codice", "descrizione", "tipo_registro", "disattivato")
    default_sort = "codice"
    default_dir = "asc"
    sort_tiebreaker = "codice"
    print_columns = (
        {"field": "codice", "label": "Codice"},
        {"field": "descrizione", "label": "Descrizione"},
        {"field": "tipo_registro", "label": "Tipo"},
        {"field": "registro_cee", "label": "CEE", "bool": True},
        {"field": "disattivato", "label": "Disattivato", "bool": True},
    )

    def get_filter_summary(self) -> str:
        return _registri_iva_print_filter_summary(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        context.update(
            {
                "print_registri_iva_filters": True,
                "data_da": (request.GET.get("data_da") or "").strip(),
                "data_a": (request.GET.get("data_a") or "").strip(),
                "q": (request.GET.get("q") or "").strip(),
                "tipo": (request.GET.get("tipo") or "").strip(),
                "attivo": (request.GET.get("attivo") or "").strip(),
            }
        )
        return context


class RegistroIvaLibroPrintView(LoginRequiredMixin, View):
    """Stampa libro registro IVA (layout 4D: protocollo, righe IVA, riepilogo)."""

    template_name = "registri_iva/libro_registro_print.html"

    def get(self, request):
        preview_ready = print_preview_requested(request)
        registro = (request.GET.get("registro") or "").strip()
        stato = get_stampa_stato(registro)
        data_da = resolve_data_da_default(request.GET, stato)
        data_a = resolve_data_a_default(request.GET, stato, data_da=data_da)
        pagina_da = resolve_pagina_da(request.GET, stato)
        includi_reg_succ = parse_includi_reg_successive(request.GET)
        # Rebuild GET con date proposte (da stato definitiva) per il builder libro
        if preview_ready:
            mutable = request.GET.copy()
            if data_da and not (request.GET.get("data_da") or "").strip():
                mutable["data_da"] = data_da
            if data_a and not (request.GET.get("data_a") or "").strip():
                mutable["data_a"] = data_a
            request.GET = mutable
        libro = build_libro_registro_iva(request) if preview_ready else LibroRegistroIvaDati(
            registro=None,
            registro_label=registro,
            periodo_label="",
            anno=None,
        )
        data_da_d = parse_date(data_da) if data_da else None
        data_a_d = parse_date(data_a) if data_a else None
        azienda_header = _resolve_azienda_header()
        print_ctx = resolve_print_azienda_context(branding="liste")
        # Conteggio fogli = PDF reale (movimenti + fogli riepilogo effettivamente prodotti).
        stima = 1
        ultima_prevista = pagina_da
        pagina_riepilogo = None
        if preview_ready:
            from apps.registri_iva.pdf_libro import conteggio_pagine_libro

            try:
                pdf_info = conteggio_pagine_libro(
                    libro=libro,
                    azienda_header=azienda_header,
                    logo_url=print_ctx.get("print_azienda_logo_url") or "",
                    pagina_da=pagina_da,
                )
                stima = pdf_info.num_pages
                ultima_prevista = pdf_info.ultima_pagina
                pagina_riepilogo = pdf_info.pagina_riepilogo
            except Exception:
                # Fallback: stima righe + 1 foglio riepilogo se presente
                ha_riepilogo = bool(getattr(libro, "ha_riepilogo_stampa", False))
                stima = stima_num_pagine(
                    len(libro.righe),
                    pagina_da=pagina_da,
                    con_riepilogo=ha_riepilogo,
                )
                ultima_prevista = pagina_da + stima - 1
                pagina_riepilogo = ultima_prevista if ha_riepilogo else None
        response = render(
            request,
            self.template_name,
            {
                "print_preview_ready": preview_ready,
                "print_date": timezone.localdate(),
                "mostra_data_stampa": False,
                "registro": registro,
                "data_da": data_da,
                "data_a": data_a,
                "pagina_da": pagina_da,
                "pagina_counter_reset": max(0, pagina_da - 1),
                "stima_pagine": stima,
                "pagina_riepilogo": pagina_riepilogo,
                "ultima_pagina_prevista": ultima_prevista,
                "stampa_stato": stato,
                "stampa_sovrappone": periodo_sovrappone_definitiva(data_da_d, data_a_d, stato),
                "conferma_url": reverse("registri_iva:conferma_definitiva"),
                "registri_choices": registro_iva_choices(registro),
                "includi_reg_succ": includi_reg_succ,
                "libro": libro,
                "azienda_header": azienda_header,
                **print_ctx,
            },
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response


@login_required
def stampa_stato_suggerimenti(request):
    """JSON: date/pagina proposte per ristampa (giorno dopo definitiva → fine mese)."""
    registro = (request.GET.get("registro") or "").strip()
    if not registro:
        return JsonResponse({"ok": False, "error": "Registro obbligatorio"}, status=400)
    stato = get_stampa_stato(registro)
    data_da = stato.data_da_suggerita
    data_a = stato.data_a_suggerita
    return JsonResponse(
        {
            "ok": True,
            "registro": stato.registro_codice or registro,
            "data_da": data_da.isoformat() if data_da else "",
            "data_a": data_a.isoformat() if data_a else "",
            "pagina_da": stato.pagina_da_suggerita,
            "data_finale": stato.data_finale.isoformat() if stato.data_finale else None,
            "ultimo_protocollo": stato.ultimo_protocollo,
            "ultima_pagina": int(stato.ultima_pagina or 0),
        }
    )


@login_required
@require_POST
def conferma_stampa_definitiva(request):
    """Salva stato dopo stampa definitiva (data finale, protocollo, pagina)."""
    registro = (request.POST.get("registro") or "").strip()
    if not registro:
        return JsonResponse({"ok": False, "error": "Registro obbligatorio"}, status=400)
    data_finale = parse_date((request.POST.get("data_finale") or "").strip())
    if data_finale is None:
        return JsonResponse(
            {"ok": False, "error": "Data finale obbligatoria"}, status=400
        )
    ultimo_protocollo = parse_int_or_none(request.POST.get("ultimo_protocollo"))
    # Liquidazione non gestisce il protocollo: conserva quello del registro collegato
    if ultimo_protocollo is None and (
        (request.POST.get("sync_periodo_liquidazione") or "").strip() == "1"
    ):
        ultimo_protocollo = get_stampa_stato(registro).ultimo_protocollo
    ultima_pagina = parse_int_or_none(request.POST.get("ultima_pagina"))
    if ultima_pagina is None or ultima_pagina < 0:
        return JsonResponse(
            {"ok": False, "error": "Ultima pagina non valida"}, status=400
        )
    obj = save_stampa_stato(
        registro_codice=registro,
        data_finale=data_finale,
        ultimo_protocollo=ultimo_protocollo,
        ultima_pagina=ultima_pagina,
    )
    # Periodo liquidazione (mese successivo in ristampa) separato dalla numerazione pagine
    if (request.POST.get("sync_periodo_liquidazione") or "").strip() == "1":
        save_stampa_stato(
            registro_codice=LIQUIDAZIONE_STAMPA_CODICE,
            data_finale=data_finale,
            ultimo_protocollo=None,
            ultima_pagina=ultima_pagina,
        )
    return JsonResponse(
        {
            "ok": True,
            "registro": obj.registro_codice,
            "data_finale": obj.data_finale.isoformat() if obj.data_finale else None,
            "ultimo_protocollo": obj.ultimo_protocollo,
            "ultima_pagina": obj.ultima_pagina,
        }
    )


def registro_iva_print_dispatch(request):
    if _is_registri_iva_elenco_stampa(request):
        return RegistroIvaElencoPrintView.as_view()(request)
    return RegistroIvaLibroPrintView.as_view()(request)


@login_required
@require_GET
def registro_iva_libro_pdf(request):
    """PDF libro Registro IVA generato sul server (Chrome/Edge, senza header Safari)."""
    from apps.registri_iva.pdf_libro import (
        pdf_filename_for_libro,
        render_libro_pdf_result,
    )

    if not print_preview_requested(request):
        return JsonResponse(
            {"ok": False, "error": "Genera prima l'anteprima (anteprima=1)."},
            status=400,
        )
    try:
        pdf_info = render_libro_pdf_result(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)

    filename = pdf_filename_for_libro(
        (request.GET.get("registro") or "").strip(),
        (request.GET.get("data_da") or "").strip(),
        (request.GET.get("data_a") or "").strip(),
    )
    response = HttpResponse(pdf_info.data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    # Fogli reali prodotti (movimenti + riepilogo): usati dalla definitiva.
    response["X-Eureka-Pdf-Pages"] = str(pdf_info.num_pages)
    response["X-Eureka-Pdf-Pagina-Da"] = str(pdf_info.pagina_da)
    response["X-Eureka-Pdf-Ultima-Pagina"] = str(pdf_info.ultima_pagina)
    if pdf_info.pagina_riepilogo is not None:
        response["X-Eureka-Pdf-Pagina-Riepilogo"] = str(pdf_info.pagina_riepilogo)
    return response


@login_required
@require_GET
def registro_iva_libro_pdf_stima(request):
    """JSON: fogli reali del PDF (stesso layout della stampa) per la definitiva."""
    from apps.registri_iva.pdf_libro import render_libro_pdf_result

    if not print_preview_requested(request):
        return JsonResponse(
            {"ok": False, "error": "Genera prima l'anteprima (anteprima=1)."},
            status=400,
        )
    try:
        pdf_info = render_libro_pdf_result(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)

    return JsonResponse(
        {
            "ok": True,
            "pagine": pdf_info.num_pages,
            "pagine_movimenti": pdf_info.pagine_movimenti,
            "pagina_da": pdf_info.pagina_da,
            "ultima_pagina": pdf_info.ultima_pagina,
            "pagina_riepilogo": pdf_info.pagina_riepilogo,
        }
    )


class LiquidazionePeriodicaIvaPrintView(LoginRequiredMixin, View):
    """Stampa Liquidazione Periodica IVA (mensile) con bozza/definitiva.

    La numerazione pagine è collegata a un registro IVA reale (es. acquisti):
    in definitiva aggiorna ``ultima_pagina`` su quel registro.
    Il periodo (mese successivo) resta tracciato su ``LIQUIDAZIONE``.
    """

    template_name = "registri_iva/liquidazione_periodica_print.html"

    def get(self, request):
        preview_ready = print_preview_requested(request)
        today = timezone.localdate()
        stato_periodo = get_stampa_stato(LIQUIDAZIONE_STAMPA_CODICE)
        registro = (request.GET.get("registro") or "").strip()
        if not registro:
            registro = _default_registro_liquidazione()
        stato_pagine = get_stampa_stato(registro) if registro else StampaDefinitivaInfo(
            registro_codice=""
        )

        anno_raw = (request.GET.get("anno") or "").strip()
        mese_raw = (request.GET.get("mese") or "").strip()
        try:
            anno = int(anno_raw) if anno_raw else today.year
        except ValueError:
            anno = today.year
        try:
            mese = int(mese_raw) if mese_raw else today.month
        except ValueError:
            mese = today.month

        # Dopo una definitiva liquidazione: proponi il mese successivo
        if not anno_raw and not mese_raw and stato_periodo.data_finale is not None:
            from datetime import timedelta as _td

            nxt = stato_periodo.data_finale + _td(days=1)
            anno, mese = nxt.year, nxt.month

        credito_prec = (request.GET.get("credito_prec") or "").strip()
        # Pagine dal registro collegato (non dal codice sintetico LIQUIDAZIONE)
        pagina_da = resolve_pagina_da(request.GET, stato_pagine)

        mutable = request.GET.copy()
        mutable["anno"] = str(anno)
        mutable["mese"] = str(mese)
        if registro:
            mutable["registro"] = registro
        if not mutable.get("data_da") or not mutable.get("data_a"):
            from datetime import date as date_cls

            from apps.registri_iva.libro_registro import _month_bounds

            start, end = _month_bounds(date_cls(anno, mese, 1))
            mutable["data_da"] = start.isoformat()
            mutable["data_a"] = end.isoformat()
        request.GET = mutable

        liq = (
            build_liquidazione_periodica(request)
            if preview_ready
            else LiquidazionePeriodicaDati(
                anno=anno,
                mese=mese,
                periodo_label="",
                credito_periodo_precedente=0.0,
            )
        )
        reg_label = ""
        if registro:
            for code, label in registro_iva_choices(registro):
                if code == registro:
                    reg_label = label
                    break
        libro_masthead = LibroRegistroIvaDati(
            registro=None,
            registro_label="Liquidazione Periodica IVA"
            + (f" · {reg_label}" if reg_label else ""),
            periodo_label=liq.periodo_label or "",
            anno=liq.anno or anno,
        )
        data_da, data_a, _ = resolve_periodo_liquidazione(request.GET)
        data_da_d = data_da
        data_a_d = data_a
        stima = 1 if preview_ready else 1
        if preview_ready and (liq.vendite or liq.acquisti):
            stima = max(1, stima_num_pagine(8, pagina_da=pagina_da))
            if stima > 2:
                stima = 2
        response = render(
            request,
            self.template_name,
            {
                "print_preview_ready": preview_ready,
                "print_date": today,
                "mostra_data_stampa": False,
                "anno": anno,
                "mese": mese,
                "mese_choices": mese_choices(),
                "credito_prec": credito_prec,
                "registro": registro,
                "registri_choices": registro_iva_choices(registro),
                "data_da": data_da.isoformat() if data_da else "",
                "data_a": data_a.isoformat() if data_a else "",
                "pagina_da": pagina_da,
                "pagina_counter_reset": max(0, pagina_da - 1),
                "stima_pagine": stima,
                "ultima_pagina_prevista": pagina_da + stima - 1,
                "stampa_stato": stato_periodo,
                "stampa_stato_registro": stato_pagine,
                "stampa_sovrappone": periodo_sovrappone_definitiva(
                    data_da_d, data_a_d, stato_periodo
                ),
                "conferma_url": reverse("registri_iva:conferma_definitiva"),
                "liquidazione_codice": registro or LIQUIDAZIONE_STAMPA_CODICE,
                "libro": libro_masthead,
                "liq": liq,
                "azienda_header": resolve_azienda_header_liquidazione(),
                **resolve_print_azienda_context(branding="liste"),
            },
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response


def _default_registro_liquidazione() -> str:
    """Preferisce un registro Acquisti attivo; altrimenti il primo disponibile."""
    try:
        qs = RegistroIva.objects.filter(
            Q(disattivato=False) | Q(disattivato__isnull=True)
        ).order_by("codice")
        acquisti = qs.filter(tipo_registro__icontains="acquist").first()
        if acquisti is not None:
            return (acquisti.codice or "").strip()
        first = qs.first()
        return (first.codice or "").strip() if first else ""
    except Exception:
        return ""

class RegistroIvaExportListView(ExportListMixin, RegistroIvaElencoPrintView):
    export_filename = "registri_iva"


class RegistroIvaDetailView(LoginRequiredMixin, DetailView):
    model = RegistroIva
    template_name = "registri_iva/registro_detail.html"
    context_object_name = "registro"
    pk_url_kwarg = "codice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row = fetch_registro_iva_row(self.object.codice) or []
        context["campi"] = mirror_row_to_campi(row)
        context["stampa_stato"] = get_stampa_stato(self.object.codice)
        return context


class RegistroIvaCreateView(LoginRequiredMixin, View):
    template_name = "registri_iva/registro_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": RegistroIvaForm(),
                "stampa_form": None,
                "is_create": True,
                "page_heading": "Nuovo registro IVA",
            },
        )

    def post(self, request):
        form = RegistroIvaForm(request.POST)
        if form.is_valid():
            registro = save_mirror_form_instance(form)
            messages.success(request, f"Registro IVA {registro.codice} creato.")
            return redirect("registri_iva:detail", codice=registro.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "stampa_form": None,
                "is_create": True,
                "page_heading": "Nuovo registro IVA",
            },
        )


class RegistroIvaUpdateView(LoginRequiredMixin, View):
    template_name = "registri_iva/registro_form.html"

    def get_object(self, codice):
        return get_object_or_404(RegistroIva, pk=codice)

    def _stampa_instance(self, codice: str) -> RegistroIvaStampaStato:
        obj = RegistroIvaStampaStato.objects.filter(registro_codice__iexact=codice).first()
        if obj is None:
            return RegistroIvaStampaStato(registro_codice=codice, ultima_pagina=0)
        return obj

    def get(self, request, codice):
        registro = self.get_object(codice)
        form = RegistroIvaForm(instance=registro, codice_readonly=True)
        stampa_form = RegistroIvaStampaStatoForm(instance=self._stampa_instance(codice))
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "stampa_form": stampa_form,
                "registro": registro,
                "is_create": False,
                "page_heading": "Modifica registro IVA",
            },
        )

    def post(self, request, codice):
        registro = self.get_object(codice)
        form = RegistroIvaForm(request.POST, instance=registro, codice_readonly=True)
        stampa_inst = self._stampa_instance(codice)
        stampa_form = RegistroIvaStampaStatoForm(request.POST, instance=stampa_inst)
        if form.is_valid() and stampa_form.is_valid():
            registro = save_mirror_form_instance(form)
            stato = stampa_form.save(commit=False)
            stato.registro_codice = registro.codice
            stato.save()
            messages.success(request, f"Registro IVA {registro.codice} aggiornato.")
            return redirect("registri_iva:detail", codice=registro.codice)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "stampa_form": stampa_form,
                "registro": registro,
                "is_create": False,
                "page_heading": "Modifica registro IVA",
            },
        )


class RegistroIvaDeleteView(LoginRequiredMixin, View):
    def post(self, request, codice):
        registro = get_object_or_404(RegistroIva, pk=codice)
        label = registro.codice
        registro.delete()
        messages.success(request, f"Registro IVA {label} eliminato.")
        return redirect("registri_iva:list")


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


class SyncRegistriIvaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "registri_iva/sync_registri_iva.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self, last_message: str = ""):
        return {
            "registri_count": _pg_table_count("registri_iva"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_registri_iva(full=sync_full_from_request(request))
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
