import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.anagrafiche.models import Cliente
from apps.core.export import export_table, normalize_export_fmt
from apps.core.pagination import (
    PER_PAGE_OPTIONS,
    filter_query_from_request,
    resolve_per_page,
)
from apps.core.pagination import PerPageListMixin
from apps.fatture import analisi as analisi_fatturato
from apps.fatture.models import (
    Fattura,
    FatturaDettaglio,
    SyncFattureLog,
    annotate_cliente_ragione_sociale,
)
from apps.fatture.sync import sync_fatture


class FatturaListView(LoginRequiredMixin, PerPageListMixin, ListView):
    model = Fattura
    template_name = "fatture/fattura_list.html"
    context_object_name = "fatture"
    paginate_by = 50

    def get_queryset(self):
        qs = Fattura.objects.all()

        q = (self.request.GET.get("q") or "").strip()
        alfa = (self.request.GET.get("alfa") or "").strip()
        data_da = parse_date((self.request.GET.get("data_da") or "").strip())
        data_a = parse_date((self.request.GET.get("data_a") or "").strip())
        note_credito = (self.request.GET.get("nc") or "").strip().lower()
        if note_credito not in analisi_fatturato.NOTE_CREDITO_MODES:
            note_credito = ""

        if q:
            filters = (
                Q(cliente__icontains=q)
                | Q(destinatario__icontains=q)
                | Q(alfa__icontains=q)
            )
            if q.isdigit():
                filters |= Q(numero_fatt=int(q)) | Q(id_testa=int(q))
            cliente_codes = Cliente.objects.filter(
                Q(ragione_sociale1__icontains=q) | Q(ragione_sociale2__icontains=q)
            ).values("codice")
            filters |= Q(cliente__in=cliente_codes)
            qs = qs.filter(filters)

        if alfa:
            qs = qs.filter(alfa__iexact=alfa)

        iso = (self.request.GET.get("iso") or "").strip().upper()
        if iso:
            qs = analisi_fatturato.filtro_iso_nazione(qs, iso)

        qs = analisi_fatturato.filtro_periodo(qs, data_da, data_a)
        qs = analisi_fatturato.filtro_note_credito(qs, note_credito)

        return annotate_cliente_ragione_sociale(
            qs.order_by("-data_fattura", "-numero_fatt", "-id_testa")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        context["q"] = (self.request.GET.get("q") or "").strip()
        context["alfa"] = (self.request.GET.get("alfa") or "").strip()
        context["iso"] = (self.request.GET.get("iso") or "").strip().upper()
        context["data_da"] = (self.request.GET.get("data_da") or "").strip()
        context["data_a"] = (self.request.GET.get("data_a") or "").strip()
        context["note_credito"] = (self.request.GET.get("nc") or "").strip().lower()
        if context["note_credito"] not in analisi_fatturato.NOTE_CREDITO_MODES:
            context["note_credito"] = ""
        context["note_credito_modes"] = analisi_fatturato.NOTE_CREDITO_MODES
        context["has_filters"] = bool(
            context["q"]
            or context["alfa"]
            or context["iso"]
            or context["data_da"]
            or context["data_a"]
            or context["note_credito"]
        )
        try:
            context["totale_fatture"] = Fattura.objects.count()
        except Exception:
            context["totale_fatture"] = 0
        return context


class FatturaDetailView(LoginRequiredMixin, DetailView):
    model = Fattura
    template_name = "fatture/fattura_detail.html"
    context_object_name = "fattura"
    pk_url_kwarg = "id_testa"

    def get_queryset(self):
        return annotate_cliente_ragione_sociale(Fattura.objects.all())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["righe"] = FatturaDettaglio.objects.filter(
            id_testa=self.object.id_testa
        ).order_by("numero_riga", "id")
        return context


class SyncFattureView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "fatture/sync_fatture.html"
    permission_required = "core.access_parametri_4d"
    raise_exception = True

    def get_context(self):
        last_log = SyncFattureLog.objects.first()
        fatture_count = 0
        dettaglio_count = 0
        try:
            fatture_count = Fattura.objects.count()
            dettaglio_count = FatturaDettaglio.objects.count()
        except Exception:
            pass
        return {
            "last_log": last_log,
            "fatture_count": fatture_count,
            "dettaglio_count": dettaglio_count,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        log = SyncFattureLog.objects.create(
            started_by=request.user,
            message="Sync in corso...",
        )
        result = sync_fatture()
        counts = {t.target: t.rows for t in result.tables}
        log.ok = result.ok
        log.fatture_count = counts.get("fatture", 0)
        log.dettaglio_count = counts.get("fatture_dettaglio", 0)
        log.message = "\n".join(t.message for t in result.tables) or result.message
        log.finished_at = timezone.now()
        log.save()

        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)

        return redirect("fatture:sync")


class AnalisiFatturatoView(LoginRequiredMixin, TemplateView):
    template_name = "fatture/analisi_fatturato.html"

    def get(self, request, *args, **kwargs):
        export = (request.GET.get("export") or "").strip().lower()
        if export in {"periodo", "persi", "nuovi", "entrambi"}:
            fmt = normalize_export_fmt(request.GET.get("fmt"))
            return self._export_table(export, fmt)
        return super().get(request, *args, **kwargs)

    def _parse_params(self):
        get = self.request.GET
        alfa = (get.get("alfa") or "").strip()
        iso = analisi_fatturato.iso_canonico(get.get("iso"))
        note_credito = (get.get("nc") or "").strip().lower()
        if note_credito not in analisi_fatturato.NOTE_CREDITO_MODES:
            note_credito = ""
        metrica = (get.get("metrica") or "imponibile").strip()
        if metrica not in analisi_fatturato.METRICHE:
            metrica = "imponibile"
        metrica_field, metrica_label = analisi_fatturato.METRICHE[metrica]

        preset = (get.get("preset") or "").strip()
        oggi = date.today()

        if preset.startswith("anno:"):
            try:
                anno = int(preset.split(":", 1)[1])
                rif_da, rif_a = analisi_fatturato.periodi_anno(anno)
                con_da, con_a = analisi_fatturato.periodi_anno(anno - 1)
            except ValueError:
                rif_da, rif_a, con_da, con_a = analisi_fatturato.default_periodi(oggi)
        elif preset == "ytd":
            rif_da = date(oggi.year, 1, 1)
            rif_a = oggi
            con_da = date(oggi.year - 1, 1, 1)
            try:
                con_a = date(oggi.year - 1, oggi.month, oggi.day)
            except ValueError:
                con_a = date(oggi.year - 1, oggi.month, 28)
        else:
            rif_da = parse_date((get.get("rif_da") or "").strip())
            rif_a = parse_date((get.get("rif_a") or "").strip())
            con_da = parse_date((get.get("con_da") or "").strip())
            con_a = parse_date((get.get("con_a") or "").strip())
            if not all((rif_da, rif_a, con_da, con_a)):
                rif_da, rif_a, con_da, con_a = analisi_fatturato.default_periodi(oggi)

        fat_op = (get.get("fat_op") or "").strip().lower()
        if fat_op not in analisi_fatturato.FATTURATO_OPS:
            fat_op = ""
        fat_val = analisi_fatturato.parse_importo(get.get("fat_val"))
        fat_val2 = analisi_fatturato.parse_importo(get.get("fat_val2"))
        if fat_op and fat_op != "between" and fat_val is None:
            fat_op = ""
        if fat_op == "between" and (fat_val is None or fat_val2 is None):
            fat_op = ""

        return {
            "alfa": alfa,
            "iso": iso,
            "note_credito": note_credito,
            "metrica": metrica,
            "metrica_field": metrica_field,
            "metrica_label": metrica_label,
            "rif_da": rif_da,
            "rif_a": rif_a,
            "con_da": con_da,
            "con_a": con_a,
            "preset": preset,
            "fat_op": fat_op,
            "fat_val": fat_val,
            "fat_val2": fat_val2,
            "fat_val_str": (get.get("fat_val") or "").strip(),
            "fat_val2_str": (get.get("fat_val2") or "").strip(),
        }

    def _build_dataset(self, params):
        base = analisi_fatturato.base_queryset(
            alfa=params["alfa"],
            iso=params["iso"],
            note_credito=params["note_credito"],
        )
        field = params["metrica_field"]
        qs_rif = analisi_fatturato.filtro_periodo(base, params["rif_da"], params["rif_a"])
        qs_con = analisi_fatturato.filtro_periodo(base, params["con_da"], params["con_a"])

        kpi_rif = analisi_fatturato.kpi_periodo(qs_rif, field)
        kpi_con = analisi_fatturato.kpi_periodo(qs_con, field)

        map_rif = analisi_fatturato.clienti_fatturati(qs_rif, field)
        map_con = analisi_fatturato.clienti_fatturati(qs_con, field)
        confronto = analisi_fatturato.confronto_clienti(map_rif, map_con)

        mensile_rif = analisi_fatturato.serie_mensile(qs_rif, field)
        mensile_con = analisi_fatturato.serie_mensile(qs_con, field)
        per_mese_rif = analisi_fatturato.serie_mensile_per_mese(qs_rif, field)
        per_mese_con = analisi_fatturato.serie_mensile_per_mese(qs_con, field)
        yoy_labels = [analisi_fatturato.MESI_IT[m] for m in range(1, 13)]
        yoy_rif = [per_mese_rif.get(m, 0.0) for m in range(1, 13)]
        yoy_con = [per_mese_con.get(m, 0.0) for m in range(1, 13)]

        annuale = analisi_fatturato.andamento_annuale(base, field)
        anni = [row["anno"] for row in annuale]
        anni_preset = [
            {"anno": a, "label": f"{a} vs {a - 1}", "preset": f"anno:{a}"}
            for a in anni[-6:]
        ]
        anni_preset.reverse()

        return {
            "kpi_rif": kpi_rif,
            "kpi_con": kpi_con,
            "delta_fatturato": analisi_fatturato.delta_pct(
                kpi_rif.fatturato, kpi_con.fatturato
            ),
            "delta_spese": analisi_fatturato.delta_pct(kpi_rif.spese, kpi_con.spese),
            "delta_lordo": analisi_fatturato.delta_pct(kpi_rif.lordo, kpi_con.lordo),
            "delta_clienti": analisi_fatturato.delta_pct(
                float(kpi_rif.n_clienti), float(kpi_con.n_clienti)
            ),
            "delta_fatture": analisi_fatturato.delta_pct(
                float(kpi_rif.n_fatture), float(kpi_con.n_fatture)
            ),
            "clienti_periodo": confronto["periodo"],
            "clienti_persi": confronto["persi"],
            "clienti_nuovi": confronto["nuovi"],
            "clienti_entrambi": confronto["entrambi"],
            "n_periodo": len(confronto["periodo"]),
            "n_persi": len(confronto["persi"]),
            "n_nuovi": len(confronto["nuovi"]),
            "n_entrambi": len(confronto["entrambi"]),
            "mensile_rif": mensile_rif,
            "mensile_con": mensile_con,
            "annuale": annuale,
            "anni_disponibili": anni,
            "anni_preset": anni_preset,
            "chart_annuale": json.dumps(
                {
                    "labels": [str(r["anno"]) for r in annuale],
                    "fatturato": [round(r["fatturato"], 2) for r in annuale],
                    "clienti": [r["n_clienti"] for r in annuale],
                }
            ),
            "chart_yoy": json.dumps(
                {
                    "labels": yoy_labels,
                    "rif": [round(v, 2) for v in yoy_rif],
                    "con": [round(v, 2) for v in yoy_con],
                }
            ),
            "chart_mensile_rif": json.dumps(
                {
                    "labels": [r["label"] for r in mensile_rif],
                    "fatturato": [round(r["fatturato"], 2) for r in mensile_rif],
                }
            ),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self._parse_params()
        data = self._build_dataset(params)
        tab = (self.request.GET.get("tab") or "periodo").strip()
        if tab not in {"periodo", "persi", "nuovi", "entrambi"}:
            tab = "periodo"

        lists = {
            "periodo": data["clienti_periodo"],
            "persi": data["clienti_persi"],
            "nuovi": data["clienti_nuovi"],
            "entrambi": data["clienti_entrambi"],
        }

        # Filtro fatturato sulle liste clienti (non sui KPI monetari)
        for key, field in (
            ("periodo", "fatturato"),
            ("persi", "fatturato"),
            ("nuovi", "fatturato"),
            ("entrambi", "fatturato_rif"),
        ):
            lists[key] = analisi_fatturato.filtro_clienti_per_fatturato(
                lists[key],
                op=params["fat_op"],
                val=params["fat_val"],
                val2=params["fat_val2"],
                field=field,
            )

        if tab == "entrambi":
            allowed = analisi_fatturato.SORT_FIELDS_ENTRAMBI
            default_sort = "delta"
            default_dir = "desc"
        else:
            allowed = analisi_fatturato.SORT_FIELDS_PERSI_NUOVI
            default_sort = "fatturato"
            default_dir = "desc"

        sort = (self.request.GET.get("sort") or default_sort).strip()
        direction = (self.request.GET.get("dir") or default_dir).strip().lower()
        if sort not in allowed:
            sort = default_sort
        if direction not in {"asc", "desc"}:
            direction = default_dir

        sorted_rows = analisi_fatturato.sort_clienti_rows(
            lists[tab],
            sort=sort,
            direction=direction,
            allowed=allowed,
            default_sort=default_sort,
            default_dir=default_dir,
        )

        per_page = resolve_per_page(self.request)
        paginator = Paginator(sorted_rows, per_page)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        fat_qs = ""
        if params["fat_op"] and params["fat_val"] is not None:
            from urllib.parse import quote

            fat_qs = f"&fat_op={params['fat_op']}&fat_val={quote(params['fat_val_str'])}"
            if params["fat_op"] == "between" and params["fat_val2"] is not None:
                fat_qs += f"&fat_val2={quote(params['fat_val2_str'])}"

        context.update(params)
        context.update(data)
        # Contatori card/tab allineati al filtro fatturato
        context["clienti_periodo"] = lists["periodo"]
        context["clienti_persi"] = lists["persi"]
        context["clienti_nuovi"] = lists["nuovi"]
        context["clienti_entrambi"] = lists["entrambi"]
        context["n_periodo"] = len(lists["periodo"])
        context["n_persi"] = len(lists["persi"])
        context["n_nuovi"] = len(lists["nuovi"])
        context["n_entrambi"] = len(lists["entrambi"])
        context["tab"] = tab
        context["sort"] = sort
        context["dir"] = direction
        context["clienti_page"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages() or page_obj.paginator.count > 0
        context["per_page"] = per_page
        context["per_page_options"] = PER_PAGE_OPTIONS
        context["filter_query"] = filter_query_from_request(self.request)
        context["rif_da_str"] = params["rif_da"].isoformat()
        context["rif_a_str"] = params["rif_a"].isoformat()
        context["con_da_str"] = params["con_da"].isoformat()
        context["con_a_str"] = params["con_a"].isoformat()
        context["note_credito_modes"] = analisi_fatturato.NOTE_CREDITO_MODES
        context["fatturato_ops"] = analisi_fatturato.FATTURATO_OPS
        context["nc_qs"] = (
            f"&nc={params['note_credito']}" if params["note_credito"] else ""
        )
        context["iso_qs"] = f"&iso={params['iso']}" if params["iso"] else ""
        context["fat_qs"] = fat_qs
        return context

    def _export_table(self, kind: str, fmt: str = "csv"):
        params = self._parse_params()
        data = self._build_dataset(params)
        rows_src = {
            "periodo": data["clienti_periodo"],
            "persi": data["clienti_persi"],
            "nuovi": data["clienti_nuovi"],
            "entrambi": data["clienti_entrambi"],
        }[kind]
        field = "fatturato_rif" if kind == "entrambi" else "fatturato"
        rows_src = analisi_fatturato.filtro_clienti_per_fatturato(
            rows_src,
            op=params["fat_op"],
            val=params["fat_val"],
            val2=params["fat_val2"],
            field=field,
        )

        if kind == "periodo":
            filename = f"clienti_periodo_{params['rif_da']}_{params['rif_a']}"
        else:
            filename = (
                f"clienti_{kind}_{params['rif_da']}_{params['rif_a']}"
                f"_vs_{params['con_da']}_{params['con_a']}"
            )

        if kind == "entrambi":
            headers = [
                "Codice",
                "Ragione sociale",
                "Fatturato riferimento",
                "Fatturato confronto",
                "Delta",
                "N. fatture rif.",
                "N. fatture con.",
            ]
            rows = [
                [
                    r["codice"],
                    r.get("ragione_sociale") or "",
                    round(float(r["fatturato_rif"]), 2),
                    round(float(r["fatturato_con"]), 2),
                    round(float(r["delta"]), 2),
                    r["n_fatture_rif"],
                    r["n_fatture_con"],
                ]
                for r in rows_src
            ]
        else:
            periodo_label = {
                "periodo": "riferimento",
                "persi": "confronto",
                "nuovi": "riferimento",
            }.get(kind, "periodo")
            headers = [
                "Codice",
                "Ragione sociale",
                f"Fatturato {periodo_label}",
                "N. fatture",
                "Ultima fattura",
            ]
            rows = []
            for r in rows_src:
                ultima = r.get("ultima")
                rows.append(
                    [
                        r["codice"],
                        r.get("ragione_sociale") or "",
                        round(float(r["fatturato"]), 2),
                        r["n_fatture"],
                        ultima.strftime("%d/%m/%Y") if ultima else "",
                    ]
                )

        return export_table(
            filename=filename,
            headers=headers,
            rows=rows,
            fmt=fmt,
            sheet_title=kind[:31],
        )

class FatturatoRegioniView(LoginRequiredMixin, TemplateView):
    """Geografia fatturato: Italia per regione, mondo per ISO, errori ISO mancante."""

    template_name = "fatture/fatturato_regioni.html"
    AMBITI = ("italia", "mondo", "errori")

    def get(self, request, *args, **kwargs):
        export = (request.GET.get("export") or "").strip().lower()
        if export in {"csv", "xlsx"}:
            return self._export_table(normalize_export_fmt(export))
        if export in {"periodo", "persi", "nuovi", "entrambi"}:
            return self._export_clienti(
                export, normalize_export_fmt(request.GET.get("fmt") or "csv")
            )
        return super().get(request, *args, **kwargs)

    def _parse_params(self):
        get = self.request.GET
        alfa = (get.get("alfa") or "").strip()
        iso = analisi_fatturato.iso_canonico(get.get("iso"))
        cliente_q = (get.get("cliente") or "").strip()
        note_credito = (get.get("nc") or "").strip().lower()
        if note_credito not in analisi_fatturato.NOTE_CREDITO_MODES:
            note_credito = ""
        metrica = (get.get("metrica") or "imponibile").strip()
        if metrica not in analisi_fatturato.METRICHE:
            metrica = "imponibile"
        metrica_field, metrica_label = analisi_fatturato.METRICHE[metrica]

        ambito = (get.get("ambito") or "italia").strip().lower()
        if ambito not in self.AMBITI:
            ambito = "italia"

        regione = (get.get("regione") or "").strip()
        if regione:
            regione = regione.zfill(2) if regione.isdigit() else regione

        provincia = (get.get("provincia") or "").strip().upper()
        if provincia and len(provincia) > 4:
            provincia = ""

        nazione = analisi_fatturato.iso_canonico(get.get("nazione"))

        fat_op = (get.get("fat_op") or "").strip().lower()
        if fat_op not in analisi_fatturato.FATTURATO_OPS:
            fat_op = ""
        fat_val = analisi_fatturato.parse_importo(get.get("fat_val"))
        fat_val2 = analisi_fatturato.parse_importo(get.get("fat_val2"))
        if fat_op and fat_op != "between" and fat_val is None:
            fat_op = ""
        if fat_op == "between" and (fat_val is None or fat_val2 is None):
            fat_op = ""

        preset = (get.get("preset") or "").strip()
        oggi = date.today()

        if preset.startswith("anno:"):
            try:
                anno = int(preset.split(":", 1)[1])
                rif_da, rif_a = analisi_fatturato.periodi_anno(anno)
                con_da, con_a = analisi_fatturato.periodi_anno(anno - 1)
            except ValueError:
                rif_da, rif_a, con_da, con_a = analisi_fatturato.default_periodi(oggi)
                preset = ""
        elif preset == "ytd":
            rif_da = date(oggi.year, 1, 1)
            rif_a = oggi
            con_da = date(oggi.year - 1, 1, 1)
            try:
                con_a = date(oggi.year - 1, oggi.month, oggi.day)
            except ValueError:
                con_a = date(oggi.year - 1, oggi.month, 28)
        else:
            rif_da = parse_date(
                (get.get("rif_da") or get.get("data_da") or "").strip()
            )
            rif_a = parse_date(
                (get.get("rif_a") or get.get("data_a") or "").strip()
            )
            con_da = parse_date((get.get("con_da") or "").strip())
            con_a = parse_date((get.get("con_a") or "").strip())
            if not all((rif_da, rif_a, con_da, con_a)):
                rif_da, rif_a, con_da, con_a = analisi_fatturato.default_periodi(oggi)
                preset = "ytd" if oggi.month >= 7 else f"anno:{oggi.year - 1}"

        return {
            "alfa": alfa,
            "iso": iso,
            "cliente_q": cliente_q,
            "note_credito": note_credito,
            "metrica": metrica,
            "metrica_field": metrica_field,
            "metrica_label": metrica_label,
            "rif_da": rif_da,
            "rif_a": rif_a,
            "con_da": con_da,
            "con_a": con_a,
            # alias per template/export legacy
            "data_da": rif_da,
            "data_a": rif_a,
            "preset": preset,
            "ambito": ambito,
            "regione": regione,
            "provincia": provincia,
            "nazione": nazione,
            "fat_op": fat_op,
            "fat_val": fat_val,
            "fat_val2": fat_val2,
            "fat_val_str": (get.get("fat_val") or "").strip(),
            "fat_val2_str": (get.get("fat_val2") or "").strip(),
        }

    def _dataset(self, params):
        cliente, clienti_suggeriti = analisi_fatturato.risolvi_cliente(
            params["cliente_q"]
        )
        base = analisi_fatturato.base_queryset(
            alfa=params["alfa"],
            iso=params["iso"],
            note_credito=params["note_credito"],
            cliente=cliente.codice if cliente else "",
            escludi_fittizi=not bool(cliente),
        )
        field = params["metrica_field"]
        qs_rif = analisi_fatturato.filtro_periodo(
            base, params["rif_da"], params["rif_a"]
        )
        qs_con = analisi_fatturato.filtro_periodo(
            base, params["con_da"], params["con_a"]
        )

        # Cartina e aggregazioni geo sul periodo di riferimento
        geo_it = analisi_fatturato.fatturato_per_regione(qs_rif, field)
        geo_province = analisi_fatturato.fatturato_per_provincia(qs_rif, field)
        geo_mondo = analisi_fatturato.fatturato_per_nazione(
            qs_rif, field, solo_estero=False
        )
        geo_estero = analisi_fatturato.fatturato_per_nazione(
            qs_rif, field, solo_estero=True
        )
        errori_iso = analisi_fatturato.fatturato_clienti_iso_mancante(qs_rif, field)

        map_rif = analisi_fatturato.clienti_fatturati(qs_rif, field)
        map_con = analisi_fatturato.clienti_fatturati(qs_con, field)
        confronto = analisi_fatturato.confronto_clienti(map_rif, map_con)

        cliente_geo = None
        annuale_cliente = []
        kpi_cliente_periodo = None
        if cliente:
            cliente_geo = analisi_fatturato.info_geo_cliente(cliente)
            annuale_cliente = analisi_fatturato.andamento_annuale(base, field)
            kpi_cliente_periodo = analisi_fatturato.kpi_periodo(qs_rif, field)

        return {
            "cliente": cliente,
            "clienti_suggeriti": clienti_suggeriti,
            "cliente_geo": cliente_geo,
            "annuale_cliente": annuale_cliente,
            "kpi_cliente_periodo": kpi_cliente_periodo,
            "geo_it": geo_it,
            "geo_province": geo_province,
            "geo_mondo": geo_mondo,
            "geo_estero": geo_estero,
            "errori_iso": errori_iso,
            "clienti_periodo": confronto["periodo"],
            "clienti_persi": confronto["persi"],
            "clienti_nuovi": confronto["nuovi"],
            "clienti_entrambi": confronto["entrambi"],
            "kpi_rif": analisi_fatturato.kpi_periodo(qs_rif, field),
            "kpi_con": analisi_fatturato.kpi_periodo(qs_con, field),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self._parse_params()
        data = self._dataset(params)
        geo_it = data["geo_it"]
        geo_mondo = data["geo_mondo"]
        geo_estero = data["geo_estero"]
        errori_iso = data["errori_iso"]
        cliente = data["cliente"]

        anni = [
            row["anno"]
            for row in analisi_fatturato.andamento_annuale(
                analisi_fatturato.base_queryset(
                    alfa=params["alfa"],
                    iso=params["iso"],
                    note_credito=params["note_credito"],
                ),
                params["metrica_field"],
            )
        ]
        anni_preset = [
            {"anno": a, "label": f"{a} vs {a - 1}", "preset": f"anno:{a}"}
            for a in anni[-6:]
        ]
        anni_preset.reverse()

        from urllib.parse import quote

        nc_qs = f"&nc={params['note_credito']}" if params["note_credito"] else ""
        iso_qs = f"&iso={params['iso']}" if params["iso"] else ""
        cliente_qs = (
            f"&cliente={cliente.codice}"
            if cliente
            else (f"&cliente={params['cliente_q']}" if params["cliente_q"] else "")
        )
        ambito_qs = f"&ambito={params['ambito']}"
        fat_qs = ""
        if params["fat_op"] and params["fat_val"] is not None:
            fat_qs = f"&fat_op={params['fat_op']}&fat_val={quote(params['fat_val_str'])}"
            if params["fat_op"] == "between" and params["fat_val2"] is not None:
                fat_qs += f"&fat_val2={quote(params['fat_val2_str'])}"

        # Liste clienti + filtro fatturato (prima del filtro provincia → JSON per drill JS)
        lists_all = {
            "periodo": data["clienti_periodo"],
            "persi": data["clienti_persi"],
            "nuovi": data["clienti_nuovi"],
            "entrambi": data["clienti_entrambi"],
        }
        for key, field in (
            ("periodo", "fatturato"),
            ("persi", "fatturato"),
            ("nuovi", "fatturato"),
            ("entrambi", "fatturato_rif"),
        ):
            lists_all[key] = analisi_fatturato.filtro_clienti_per_fatturato(
                lists_all[key],
                op=params["fat_op"],
                val=params["fat_val"],
                val2=params["fat_val2"],
                field=field,
            )

        codice_to_prov = analisi_fatturato.mappa_cliente_provincia_it()
        codice_to_iso = analisi_fatturato.mappa_cliente_nazione()
        liste_json = analisi_fatturato.serialize_liste_clienti(lists_all)
        # Solo i clienti presenti nelle liste (non tutta l'anagrafica)
        codici_liste: set[str] = set()
        for rows in lists_all.values():
            for row in rows:
                cod = row.get("codice")
                if cod:
                    codici_liste.add(str(cod))
        cliente_sigla = {
            codice: codice_to_prov[codice]["sigla"]
            for codice in codici_liste
            if codice in codice_to_prov
        }
        cliente_iso = {
            codice: codice_to_iso[codice]
            for codice in codici_liste
            if codice_to_iso.get(codice)
        }

        geo_province = data["geo_province"]
        regione_sel = params["regione"]
        provincia_sel = (params["provincia"] or "").strip().upper()
        province_meta = {p["sigla"]: p for p in geo_province["province"]}
        if provincia_sel and provincia_sel not in province_meta:
            provincia_sel = ""
        if provincia_sel and not regione_sel:
            regione_sel = province_meta[provincia_sel].get("regione_codice") or ""
        if regione_sel and regione_sel not in geo_province["by_regione"]:
            regione_sel = ""
            provincia_sel = ""

        nazione_sel = (params.get("nazione") or "").strip().upper()
        nazioni_validi = {r["codice"] for r in data["geo_mondo"]["nazioni"]}
        if nazione_sel and nazione_sel not in nazioni_validi:
            nazione_sel = ""

        lists = {k: list(v) for k, v in lists_all.items()}
        if provincia_sel:
            for key in lists:
                lists[key] = analisi_fatturato.filtro_clienti_per_provincia(
                    lists[key], provincia_sel, codice_to_prov
                )
        elif nazione_sel:
            for key in lists:
                lists[key] = analisi_fatturato.filtro_clienti_per_nazione(
                    lists[key], nazione_sel, codice_to_iso
                )

        tab = (self.request.GET.get("tab") or "periodo").strip()
        if tab not in {"periodo", "persi", "nuovi", "entrambi"}:
            tab = "periodo"
        if tab == "entrambi":
            allowed = analisi_fatturato.SORT_FIELDS_ENTRAMBI
            default_sort = "delta"
            default_dir = "desc"
        else:
            allowed = analisi_fatturato.SORT_FIELDS_PERSI_NUOVI
            default_sort = "fatturato"
            default_dir = "desc"
        sort = (self.request.GET.get("sort") or default_sort).strip()
        direction = (self.request.GET.get("dir") or default_dir).strip().lower()
        if sort not in allowed:
            sort = default_sort
        if direction not in {"asc", "desc"}:
            direction = default_dir
        sorted_rows = analisi_fatturato.sort_clienti_rows(
            lists[tab],
            sort=sort,
            direction=direction,
            allowed=allowed,
            default_sort=default_sort,
            default_dir=default_dir,
        )
        per_page = resolve_per_page(self.request)
        paginator = Paginator(sorted_rows, per_page)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        if params["ambito"] == "mondo":
            map_json = geo_mondo["map_data"]
            max_pct = max(
                (r["percentuale"] for r in geo_mondo["nazioni"]), default=0.0
            )
        else:
            map_json = geo_it["map_data"]
            max_pct = max(
                (r["percentuale"] for r in geo_it["regioni"]), default=0.0
            )

        regioni_nome = {r["codice"]: r["nome"] for r in geo_it["regioni"]}
        province_nome = {p["sigla"]: p["nome"] for p in geo_province["province"]}
        nazioni_nome = {r["codice"]: r["nome"] for r in geo_mondo["nazioni"]}
        drill_payload = {
            "regioni": [
                {
                    "codice": r["codice"],
                    "nome": r["nome"],
                    "fatturato": round(float(r["fatturato"]), 2),
                    "percentuale": round(float(r["percentuale"]), 2),
                    "n_fatture": r["n_fatture"],
                    "n_clienti": r["n_clienti"],
                }
                for r in geo_it["regioni"]
            ],
            "province_by_regione": {
                cod: [
                    {
                        "sigla": p["sigla"],
                        "nome": p["nome"],
                        "fatturato": round(float(p["fatturato"]), 2),
                        "percentuale": round(float(p["percentuale"]), 2),
                        "n_fatture": p["n_fatture"],
                        "n_clienti": p["n_clienti"],
                    }
                    for p in rows
                ]
                for cod, rows in geo_province["by_regione"].items()
            },
            "regioni_nome": regioni_nome,
            "province_nome": province_nome,
            "nazioni": [
                {
                    "codice": r["codice"],
                    "nome": r["nome"],
                    "fatturato": round(float(r["fatturato"]), 2),
                    "percentuale": round(float(r["percentuale"]), 2),
                    "n_fatture": r["n_fatture"],
                    "n_clienti": r["n_clienti"],
                }
                for r in geo_mondo["nazioni"]
            ],
            "nazioni_nome": nazioni_nome,
        }

        period_qs = (
            f"&rif_da={params['rif_da'].isoformat()}"
            f"&rif_a={params['rif_a'].isoformat()}"
            f"&con_da={params['con_da'].isoformat()}"
            f"&con_a={params['con_a'].isoformat()}"
        )

        context.update(
            {
                **params,
                "regione": regione_sel,
                "provincia": provincia_sel,
                "provincia_nome": province_nome.get(provincia_sel, ""),
                "nazione": nazione_sel,
                "nazione_nome": nazioni_nome.get(nazione_sel, ""),
                "nazioni_totale": {
                    "fatturato": float(geo_mondo["totale"] or 0),
                    "n_clienti": int(geo_mondo["n_clienti"] or 0),
                },
                "rif_da_str": params["rif_da"].isoformat(),
                "rif_a_str": params["rif_a"].isoformat(),
                "con_da_str": params["con_da"].isoformat(),
                "con_a_str": params["con_a"].isoformat(),
                "data_da_str": params["rif_da"].isoformat(),
                "data_a_str": params["rif_a"].isoformat(),
                "note_credito_modes": analisi_fatturato.NOTE_CREDITO_MODES,
                "fatturato_ops": analisi_fatturato.FATTURATO_OPS,
                "anni_preset": anni_preset,
                "nc_qs": nc_qs,
                "iso_qs": iso_qs,
                "fat_qs": fat_qs,
                "cliente_qs": cliente_qs,
                "ambito_qs": ambito_qs,
                "period_qs": period_qs,
                "cliente": cliente,
                "clienti_suggeriti": data["clienti_suggeriti"],
                "cliente_geo": data["cliente_geo"],
                "kpi_cliente_periodo": data["kpi_cliente_periodo"],
                "kpi_rif": data["kpi_rif"],
                "kpi_con": data["kpi_con"],
                "delta_fatturato": analisi_fatturato.delta_pct(
                    data["kpi_rif"].fatturato, data["kpi_con"].fatturato
                ),
                "delta_importo": float(data["kpi_rif"].fatturato)
                - float(data["kpi_con"].fatturato),
                "annuale_cliente": data["annuale_cliente"],
                "chart_cliente_annuale": json.dumps(
                    {
                        "labels": [str(r["anno"]) for r in data["annuale_cliente"]],
                        "fatturato": [
                            round(r["fatturato"], 2) for r in data["annuale_cliente"]
                        ],
                        "n_fatture": [
                            r["n_fatture"] for r in data["annuale_cliente"]
                        ],
                    }
                ),
                "regioni": geo_it["regioni"],
                "province_regione": (
                    geo_province["by_regione"].get(regione_sel, [])
                    if regione_sel
                    else []
                ),
                "province_regione_totale": {
                    "fatturato": sum(
                        float(p["fatturato"])
                        for p in geo_province["by_regione"].get(regione_sel, [])
                    ),
                    "n_clienti": sum(
                        int(p["n_clienti"] or 0)
                        for p in geo_province["by_regione"].get(regione_sel, [])
                    ),
                }
                if regione_sel
                else {"fatturato": 0.0, "n_clienti": 0},
                "regioni_totale": {
                    "fatturato": float(geo_it["totale_mappato"] or 0),
                    "n_clienti": int(geo_it["n_clienti_mappati"] or 0),
                },
                "regione_nome": regioni_nome.get(regione_sel, ""),
                "totale_mappato": geo_it["totale_mappato"],
                "totale_non_mappato": geo_it["totale_non_mappato"],
                "totale_italia": geo_it["totale_italia"],
                "n_clienti_mappati": geo_it["n_clienti_mappati"],
                "n_clienti_non_mappati": geo_it["n_clienti_non_mappati"],
                "n_fatture_mappate": geo_it["n_fatture_mappate"],
                "nazioni": geo_mondo["nazioni"],
                "nazioni_estero": geo_estero["nazioni"],
                "totale_mondo": geo_mondo["totale"],
                "totale_estero": geo_estero["totale"],
                "totale_it_iso": float(geo_mondo["totale"]) - float(geo_estero["totale"]),
                "n_clienti_mondo": geo_mondo["n_clienti"],
                "n_nazioni": geo_mondo["n_nazioni"],
                "n_nazioni_estero": geo_estero["n_nazioni"],
                "errori_iso": errori_iso["clienti"],
                "n_errori_iso": errori_iso["n_clienti"],
                "totale_errori_iso": errori_iso["totale"],
                "n_fatture_errori_iso": errori_iso["n_fatture"],
                "map_json": json.dumps(map_json),
                "drill_json": json.dumps(drill_payload),
                "liste_json": json.dumps(liste_json),
                "cliente_sigla_json": json.dumps(cliente_sigla),
                "cliente_iso_json": json.dumps(cliente_iso),
                "max_percentuale_js": json.dumps(round(float(max_pct), 6)),
                "map_mode": "world" if params["ambito"] == "mondo" else "italy",
                "tab": tab,
                "sort": sort,
                "dir": direction,
                "clienti_page": page_obj.object_list,
                "page_obj": page_obj,
                "is_paginated": page_obj.has_other_pages() or page_obj.paginator.count > 0,
                "per_page": per_page,
                "per_page_options": PER_PAGE_OPTIONS,
                "filter_query": filter_query_from_request(self.request),
                "n_periodo": len(lists["periodo"]),
                "n_persi": len(lists["persi"]),
                "n_nuovi": len(lists["nuovi"]),
                "n_entrambi": len(lists["entrambi"]),
                "italia_url": (
                    f"{self.request.path}?rif_da={params['rif_da'].isoformat()}"
                    f"&rif_a={params['rif_a'].isoformat()}"
                    f"&con_da={params['con_da'].isoformat()}"
                    f"&con_a={params['con_a'].isoformat()}"
                    f"&metrica={params['metrica']}"
                    f"{nc_qs}{iso_qs}{fat_qs}{cliente_qs}"
                    f"{('&alfa=' + params['alfa']) if params['alfa'] else ''}"
                    f"{('&preset=' + params['preset']) if params['preset'] else ''}"
                    f"&ambito=italia"
                ),
            }
        )
        return context

    def _export_table(self, fmt: str = "csv"):
        params = self._parse_params()
        data = self._dataset(params)
        cliente = data["cliente"]
        suffix = f"-{cliente.codice}" if cliente else ""
        ambito = params["ambito"]

        if ambito == "errori":
            filename = (
                f"fatturato-iso-mancante{suffix}-"
                f'{params["rif_da"]}-{params["rif_a"]}'
            )
            headers = [
                "Codice",
                "Ragione sociale",
                "Errore",
                "Fatturato",
                "N. fatture",
                "Ultima fattura",
            ]
            rows = []
            for r in data["errori_iso"]["clienti"]:
                ultima = r.get("ultima")
                rows.append(
                    [
                        r["codice"],
                        r.get("ragione_sociale") or "",
                        r.get("errore") or "",
                        round(float(r["fatturato"]), 2),
                        r["n_fatture"],
                        ultima.strftime("%d/%m/%Y") if ultima else "",
                    ]
                )
            sheet = "Errori ISO"
        elif ambito == "mondo":
            filename = (
                f"fatturato-mondo-iso{suffix}-"
                f'{params["rif_da"]}-{params["rif_a"]}'
            )
            headers = [
                "ISO",
                "Nazione",
                "Fatturato",
                "% sul totale",
                "N. fatture",
                "N. clienti",
            ]
            rows = [
                [
                    r["codice"],
                    r["nome"],
                    round(float(r["fatturato"]), 2),
                    round(float(r["percentuale"]), 2),
                    r["n_fatture"],
                    r["n_clienti"],
                ]
                for r in data["geo_mondo"]["nazioni"]
            ]
            sheet = "Mondo ISO"
        else:
            filename = (
                f"fatturato-regioni{suffix}-"
                f'{params["rif_da"]}-{params["rif_a"]}'
            )
            headers = [
                "Codice ISTAT",
                "Regione",
                "Fatturato",
                "% sul totale mappato",
                "N. fatture",
                "N. clienti",
            ]
            rows = [
                [
                    r["codice"],
                    r["nome"],
                    round(float(r["fatturato"]), 2),
                    round(float(r["percentuale"]), 2),
                    r["n_fatture"],
                    r["n_clienti"],
                ]
                for r in data["geo_it"]["regioni"]
            ]
            sheet = "Regioni"

        return export_table(
            filename=filename,
            headers=headers,
            rows=rows,
            fmt=fmt,
            sheet_title=sheet,
        )

    def _export_clienti(self, kind: str, fmt: str = "csv"):
        params = self._parse_params()
        data = self._dataset(params)
        rows_src = {
            "periodo": data["clienti_periodo"],
            "persi": data["clienti_persi"],
            "nuovi": data["clienti_nuovi"],
            "entrambi": data["clienti_entrambi"],
        }[kind]
        field = "fatturato_rif" if kind == "entrambi" else "fatturato"
        rows_src = analisi_fatturato.filtro_clienti_per_fatturato(
            rows_src,
            op=params["fat_op"],
            val=params["fat_val"],
            val2=params["fat_val2"],
            field=field,
        )
        provincia = (params.get("provincia") or "").strip().upper()
        nazione = (params.get("nazione") or "").strip().upper()
        if provincia:
            rows_src = analisi_fatturato.filtro_clienti_per_provincia(
                rows_src, provincia
            )
        elif nazione:
            rows_src = analisi_fatturato.filtro_clienti_per_nazione(
                rows_src, nazione
            )
        filename = (
            f"geo-clienti_{kind}_{params['rif_da']}_{params['rif_a']}"
            f"_vs_{params['con_da']}_{params['con_a']}"
        )
        if kind == "entrambi":
            headers = [
                "Codice",
                "Ragione sociale",
                "Località",
                "Provincia",
                "Fatturato riferimento",
                "Fatturato confronto",
                "Delta",
                "N. fatture rif.",
                "N. fatture con.",
            ]
            rows = [
                [
                    r["codice"],
                    r.get("ragione_sociale") or "",
                    r.get("localita") or "",
                    r.get("provincia") or "",
                    round(float(r["fatturato_rif"]), 2),
                    round(float(r["fatturato_con"]), 2),
                    round(float(r["delta"]), 2),
                    r["n_fatture_rif"],
                    r["n_fatture_con"],
                ]
                for r in rows_src
            ]
        else:
            periodo_label = {
                "periodo": "riferimento",
                "persi": "confronto",
                "nuovi": "riferimento",
            }.get(kind, "periodo")
            headers = [
                "Codice",
                "Ragione sociale",
                "Località",
                "Provincia",
                f"Fatturato {periodo_label}",
                "N. fatture",
                "Ultima fattura",
            ]
            rows = []
            for r in rows_src:
                ultima = r.get("ultima")
                rows.append(
                    [
                        r["codice"],
                        r.get("ragione_sociale") or "",
                        r.get("localita") or "",
                        r.get("provincia") or "",
                        round(float(r["fatturato"]), 2),
                        r["n_fatture"],
                        ultima.strftime("%d/%m/%Y") if ultima else "",
                    ]
                )
        return export_table(
            filename=filename,
            headers=headers,
            rows=rows,
            fmt=fmt,
            sheet_title=kind[:31],
        )


TOP_N_OPTIONS = (10, 25, 50, 100, 0)  # 0 = tutti
CHART_MAX_WHEN_ALL = 100  # con "tutti", il grafico si limita per leggibilità


class ClassificaClientiView(LoginRequiredMixin, TemplateView):
    """Classifica dei clienti migliori per fatturato nel periodo."""

    template_name = "fatture/classifica_clienti.html"

    def get(self, request, *args, **kwargs):
        if (request.GET.get("export") or "").strip().lower() in {"csv", "xlsx"}:
            return self._export_table(
                normalize_export_fmt(request.GET.get("export"))
            )
        return super().get(request, *args, **kwargs)

    def _parse_params(self):
        get = self.request.GET
        alfa = (get.get("alfa") or "").strip()
        iso = analisi_fatturato.iso_canonico(get.get("iso"))
        note_credito = (get.get("nc") or "").strip().lower()
        if note_credito not in analisi_fatturato.NOTE_CREDITO_MODES:
            note_credito = ""
        metrica = (get.get("metrica") or "imponibile").strip()
        if metrica not in analisi_fatturato.METRICHE:
            metrica = "imponibile"
        metrica_field, metrica_label = analisi_fatturato.METRICHE[metrica]

        # Un'unica selezione Top per grafico + lista (accetta anche ?chart= legacy)
        raw_top = (get.get("top") or get.get("chart") or "50").strip()
        try:
            top_n = int(raw_top)
        except ValueError:
            top_n = 50
        if top_n not in TOP_N_OPTIONS:
            # es. vecchio chart=20 → allinea al più vicino
            if top_n > 0:
                top_n = min(TOP_N_OPTIONS[:-1], key=lambda x: abs(x - top_n))
            else:
                top_n = 50

        preset = (get.get("preset") or "").strip()
        oggi = date.today()

        if preset.startswith("anno:"):
            try:
                anno = int(preset.split(":", 1)[1])
                data_da, data_a = analisi_fatturato.periodi_anno(anno)
            except ValueError:
                data_da, data_a, _, _ = analisi_fatturato.default_periodi(oggi)
                preset = ""
        elif preset == "ytd":
            data_da = date(oggi.year, 1, 1)
            data_a = oggi
        else:
            data_da = parse_date((get.get("data_da") or "").strip())
            data_a = parse_date((get.get("data_a") or "").strip())
            if not data_da or not data_a:
                data_da, data_a, _, _ = analisi_fatturato.default_periodi(oggi)
                preset = "ytd" if oggi.month >= 7 else f"anno:{oggi.year - 1}"
                if preset == "ytd":
                    data_da = date(oggi.year, 1, 1)
                    data_a = oggi
                else:
                    data_da, data_a = analisi_fatturato.periodi_anno(oggi.year - 1)

        return {
            "alfa": alfa,
            "iso": iso,
            "note_credito": note_credito,
            "metrica": metrica,
            "metrica_field": metrica_field,
            "metrica_label": metrica_label,
            "data_da": data_da,
            "data_a": data_a,
            "preset": preset,
            "top_n": top_n,
        }

    def _build(self, params):
        base = analisi_fatturato.base_queryset(
            alfa=params["alfa"],
            iso=params["iso"],
            note_credito=params["note_credito"],
        )
        qs = analisi_fatturato.filtro_periodo(
            base, params["data_da"], params["data_a"]
        )
        top = params["top_n"] or None
        ranking = analisi_fatturato.classifica_clienti(
            qs, params["metrica_field"], top_n=top
        )
        kpi = analisi_fatturato.kpi_periodo(qs, params["metrica_field"])
        return ranking, kpi, base

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self._parse_params()
        ranking, kpi, base = self._build(params)

        anni = [
            row["anno"]
            for row in analisi_fatturato.andamento_annuale(
                base, params["metrica_field"]
            )
        ]
        anni_preset = [
            {"anno": a, "label": str(a), "preset": f"anno:{a}"} for a in anni[-6:]
        ]
        anni_preset.reverse()

        # Stessa selezione per lista e grafico
        chart_rows = ranking["classifica"]
        if not params["top_n"]:
            chart_rows = ranking["classifica_completa"][:CHART_MAX_WHEN_ALL]

        nc_qs = f"&nc={params['note_credito']}" if params["note_credito"] else ""
        iso_qs = f"&iso={params['iso']}" if params["iso"] else ""
        top_qs = f"&top={params['top_n']}"

        context.update(
            {
                **params,
                "data_da_str": params["data_da"].isoformat(),
                "data_a_str": params["data_a"].isoformat(),
                "note_credito_modes": analisi_fatturato.NOTE_CREDITO_MODES,
                "top_n_options": TOP_N_OPTIONS,
                "anni_preset": anni_preset,
                "nc_qs": nc_qs,
                "iso_qs": iso_qs,
                "top_qs": top_qs,
                "kpi": kpi,
                "classifica": ranking["classifica"],
                "n_in_lista": len(ranking["classifica"]),
                "n_clienti": ranking["n_clienti"],
                "totale": ranking["totale"],
                "top1_fatturato": ranking["top1_fatturato"],
                "top1_percentuale": ranking["top1_percentuale"],
                "top10_fatturato": ranking["top10_fatturato"],
                "top10_percentuale": ranking["top10_percentuale"],
                "top20_percentuale": ranking["top20_percentuale"],
                "chart_n": len(chart_rows),
                "chart_json": json.dumps(
                    {
                        "labels": [
                            (r.get("ragione_sociale") or r["codice"])[:42]
                            for r in chart_rows
                        ],
                        "codici": [r["codice"] for r in chart_rows],
                        "fatturato": [round(r["fatturato"], 2) for r in chart_rows],
                        "percentuale": [
                            round(r["percentuale"], 2) for r in chart_rows
                        ],
                    }
                ),
            }
        )
        return context

    def _export_table(self, fmt: str = "csv"):
        params = self._parse_params()
        ranking, _, _ = self._build(params)
        rows_src = ranking["classifica"]
        label = f"top{params['top_n']}" if params["top_n"] else "tutti"
        filename = (
            f"classifica-clienti-{label}-"
            f'{params["data_da"]}-{params["data_a"]}'
        )
        headers = [
            "Posizione",
            "Codice",
            "Ragione sociale",
            "Fatturato",
            "% sul totale",
            "% cumulata",
            "N. fatture",
            "Ultima fattura",
        ]
        rows = []
        for r in rows_src:
            ultima = r.get("ultima")
            rows.append(
                [
                    r["posizione"],
                    r["codice"],
                    r.get("ragione_sociale") or "",
                    round(float(r["fatturato"]), 2),
                    round(float(r["percentuale"]), 2),
                    round(float(r["percentuale_cumulata"]), 2),
                    r["n_fatture"],
                    ultima.strftime("%d/%m/%Y") if ultima else "",
                ]
            )
        return export_table(
            filename=filename,
            headers=headers,
            rows=rows,
            fmt=fmt,
            sheet_title="Classifica",
        )
