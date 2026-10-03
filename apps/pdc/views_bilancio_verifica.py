"""Stampa Bilancio di Verifica (menu Contabilità · Stampe)."""

from __future__ import annotations

from types import SimpleNamespace

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View

from apps.aziende.configurazione import resolve_print_azienda_context
from apps.core.print_list import print_preview_requested
from apps.pdc.bilancio_verifica import (
    MODALITA_BILANCIO,
    MODALITA_CLIENTI,
    MODALITA_FORNITORI,
    MODALITA_LABELS,
    BilancioVerificaResult,
    build_bilancio_verifica,
    default_periodo,
    modalita_label,
    normalize_modalita,
)
from apps.registri_iva.libro_registro import _resolve_azienda_header


class BilancioVerificaPrintView(LoginRequiredMixin, View):
    """Anteprima/stampa bilancio di verifica / situazione analitica clifor."""

    template_name = "pdc/bilancio_verifica_print.html"

    def get(self, request):
        preview_ready = print_preview_requested(request)
        default_da, default_a = default_periodo()
        data_da = parse_date((request.GET.get("data_da") or "").strip()) or default_da
        data_a = parse_date((request.GET.get("data_a") or "").strip()) or default_a
        if data_da > data_a:
            data_da, data_a = data_a, data_da

        modalita = normalize_modalita(request.GET.get("modalita"))
        titolo = modalita_label(modalita)

        if preview_ready:
            solo_con_movimenti = "solo_movimenti" in request.GET
            mostra_precedenti = "mostra_prec" in request.GET
            escludi_saldo_zero = "escludi_zero" in request.GET
            includi_tutti = "tutti_sottoconti" in request.GET
        else:
            solo_con_movimenti = True
            mostra_precedenti = True
            escludi_saldo_zero = False
            includi_tutti = False

        error = ""
        bilancio = BilancioVerificaResult(data_da=data_da, data_a=data_a)

        if preview_ready:
            try:
                bilancio = build_bilancio_verifica(
                    data_da,
                    data_a,
                    solo_con_movimenti=solo_con_movimenti and not includi_tutti,
                    escludi_saldo_zero=escludi_saldo_zero,
                    includi_tutti_sottoconti=includi_tutti,
                    modalita=modalita,
                )
            except Exception as exc:  # noqa: BLE001 — mirror assente / SQL
                error = f"Impossibile calcolare {titolo.lower()}: {exc}"
                preview_ready = False
            else:
                if not bilancio.righe:
                    error = "Nessuna riga da stampare con i filtri selezionati."
                    preview_ready = False

        periodo_label = f"{data_da.strftime('%d/%m/%Y')} – {data_a.strftime('%d/%m/%Y')}"
        masthead = SimpleNamespace(
            registro_label=titolo,
            anno=data_da.year,
            periodo_label=periodo_label,
            doctype=titolo,
        )
        if modalita == MODALITA_CLIENTI:
            count_label = "clienti"
        elif modalita == MODALITA_FORNITORI:
            count_label = "fornitori"
        else:
            count_label = "conti"

        response = render(
            request,
            self.template_name,
            {
                "print_preview_ready": preview_ready,
                "print_date": timezone.localdate(),
                "data_da": data_da.isoformat(),
                "data_a": data_a.isoformat(),
                "data_da_default": default_da.isoformat(),
                "data_a_default": default_a.isoformat(),
                "periodo_label": periodo_label,
                "modalita": modalita,
                "modalita_choices": MODALITA_LABELS,
                "titolo_stampa": titolo,
                "count_label": count_label,
                "solo_con_movimenti": solo_con_movimenti,
                "escludi_saldo_zero": escludi_saldo_zero,
                "includi_tutti": includi_tutti,
                "mostra_precedenti": mostra_precedenti,
                "bilancio": bilancio,
                "bilancio_masthead": masthead,
                "pagina_da": 1,
                "error": error,
                "azienda_header": _resolve_azienda_header(),
                **resolve_print_azienda_context(branding="liste"),
            },
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response
