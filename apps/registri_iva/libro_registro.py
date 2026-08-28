"""Costruzione dati per stampa Libro Registro IVA (layout 4D)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from django.db.models import DateField, Q
from django.db.models.functions import Cast
from django.utils.dateparse import parse_date

from apps.aziende.configurazione import resolve_azienda_dati
from apps.aziende.models import Azienda
from apps.core.print_list import format_it_number
from apps.documenti.castelletto import resolve_aliquota
from apps.primanota.lookups import resolve_partita_clifor
from apps.primanota.models import Primanota, PrimanotaDettaglio
from apps.registri_iva.models import RegistroIva

MESE_IT = (
    "",
    "Gennaio",
    "Febbraio",
    "Marzo",
    "Aprile",
    "Maggio",
    "Giugno",
    "Luglio",
    "Agosto",
    "Settembre",
    "Ottobre",
    "Novembre",
    "Dicembre",
)


@dataclass
class LibroRegistroIvaCella:
    text: str = ""
    align: str = "start"
    cell_class: str = ""
    colspan: int = 1


@dataclass
class LibroRegistroIvaRiga:
    cells: list[LibroRegistroIvaCella] = field(default_factory=list)
    row_class: str = ""


@dataclass
class LibroRegistroIvaRiepilogoVoce:
    descrizione: str
    imponibile: float
    iva: float
    iva_deducibile: float = 0.0
    iva_indeducibile: float = 0.0


@dataclass
class LibroRegistroIvaDati:
    registro: RegistroIva | None
    registro_label: str
    periodo_label: str
    anno: int | None
    righe: list[LibroRegistroIvaRiga] = field(default_factory=list)
    riepilogo: list[LibroRegistroIvaRiepilogoVoce] = field(default_factory=list)
    totale_imponibile: float = 0.0
    totale_iva: float = 0.0
    totale_documento: float = 0.0
    documenti_count: int = 0


def _fmt_date_short(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%y")
    return str(value)


def _fmt_money(value) -> str:
    if value in (None, ""):
        return ""
    return format_it_number(value, decimals=2)


def _fmt_pct(value) -> str:
    if value in (None, ""):
        return ""
    try:
        number = Decimal(str(value))
    except Exception:
        return str(value)
    if number == number.to_integral_value():
        return str(int(number))
    return format_it_number(number, decimals=2).replace(".", "").replace(",", ".")


def _periodo_label(data_da: date | None, data_a: date | None) -> str:
    if data_da and data_a and data_da.year == data_a.year and data_da.month == data_a.month:
        return f"{MESE_IT[data_da.month]} {data_da.year}"
    if data_da and data_a:
        return f"Dal {data_da.strftime('%d/%m/%Y')} al {data_a.strftime('%d/%m/%Y')}"
    if data_da:
        return f"Da {data_da.strftime('%d/%m/%Y')}"
    if data_a:
        return f"Fino al {data_a.strftime('%d/%m/%Y')}"
    return ""


def _descrizione_iva(codice_iva: str, cache: dict) -> tuple[str, Decimal]:
    info = resolve_aliquota(codice_iva, cache=cache)
    label = (info.descrizione or "").strip()
    if not label:
        pct = info.percentuale
        if pct is not None and pct > 0:
            label = f"IVA {pct:g}%"
        else:
            label = (codice_iva or "").strip() or "—"
    return label, info.percentuale or Decimal("0")


def _filter_registrazioni_libro(request, registro_code: str):
    qs = Primanota.objects.filter(
        registro__iexact=registro_code,
        tipo__in=(
            Primanota.TIPO_IVA,
            Primanota.TIPO_CORRISPETTIVI,
            Primanota.TIPO_IVA_AUTOFATTURA,
        ),
    )
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())
    if data_da or data_a:
        qs = qs.annotate(_data_reg_cal=Cast("data_reg", DateField()))
    if data_da:
        qs = qs.filter(_data_reg_cal__gte=data_da)
    if data_a:
        qs = qs.filter(_data_reg_cal__lte=data_a)
    return qs.order_by("data_reg", "numero_prot", "id")


def _resolve_azienda_header() -> dict[str, str]:
    dati = resolve_azienda_dati()
    azienda = None
    if dati:
        azienda = Azienda.objects.filter(pk=dati.azienda_id).first()
    if azienda is None:
        aziende = list(Azienda.objects.order_by("id")[:1])
        azienda = aziende[0] if aziende else None
    if azienda is None:
        return {
            "ragione_sociale": "",
            "indirizzo": "",
            "codice_fiscale": "",
            "partita_iva": "",
        }
    locality = " ".join(
        p
        for p in (
            (azienda.cap or "").strip(),
            (azienda.localita or "").strip(),
            (f"({azienda.provincia})" if (azienda.provincia or "").strip() else ""),
        )
        if p
    )
    indirizzo = (azienda.indirizzo or "").strip()
    if locality:
        indirizzo = f"{indirizzo} - {locality}" if indirizzo else locality
    return {
        "ragione_sociale": (azienda.ragione_sociale or "").strip(),
        "indirizzo": indirizzo,
        "codice_fiscale": (azienda.codice_fiscale or "").strip(),
        "partita_iva": (azienda.partita_iva or "").strip(),
    }


def build_libro_registro_iva(request) -> LibroRegistroIvaDati:
    registro_code = (request.GET.get("registro") or "").strip()
    registro = (
        RegistroIva.objects.filter(codice__iexact=registro_code).first()
        if registro_code
        else None
    )
    data_da = parse_date((request.GET.get("data_da") or "").strip())
    data_a = parse_date((request.GET.get("data_a") or "").strip())
    periodo = _periodo_label(data_da, data_a)
    anno = data_a.year if data_a else (data_da.year if data_da else None)
    label = (registro.descrizione or registro.codice or registro_code).strip() if registro else registro_code

    empty = LibroRegistroIvaDati(
        registro=registro,
        registro_label=label,
        periodo_label=periodo,
        anno=anno,
    )
    if not registro_code:
        return empty

    registrazioni = list(_filter_registrazioni_libro(request, registro_code))
    if not registrazioni:
        return empty

    ids = [r.id for r in registrazioni]
    righe_by_testa: dict[int, list[PrimanotaDettaglio]] = defaultdict(list)
    for riga in (
        PrimanotaDettaglio.objects.filter(id_testa__in=ids)
        .exclude(dummy=True)
        .order_by("id_testa", "pos", "id")
    ):
        if (riga.codice_iva or "").strip():
            righe_by_testa[int(riga.id_testa)].append(riga)

    aliquota_cache: dict = {}
    partita_cache: dict[str, dict] = {}
    output: list[LibroRegistroIvaRiga] = []
    riepilogo_map: dict[str, LibroRegistroIvaRiepilogoVoce] = {}
    tot_imp = tot_iva = tot_doc = 0.0

    for reg in registrazioni:
        dettagli = righe_by_testa.get(reg.id) or []
        if not dettagli:
            continue

        partita_code = (reg.codice_partita or "").strip()
        if partita_code not in partita_cache:
            partita_cache[partita_code] = resolve_partita_clifor(partita_code)
        ragione = partita_cache[partita_code].get("label") or partita_code

        prot = str(reg.numero_prot or "")
        data_reg = _fmt_date_short(reg.data_reg)
        numero_doc = (reg.numero_doc or "").strip()
        data_doc = _fmt_date_short(reg.data_doc)

        doc_imp = doc_iva = 0.0
        for idx, riga in enumerate(dettagli):
            imp = float(riga.imponibile or 0)
            iva = float(riga.importo_iva or 0)
            doc_imp += imp
            doc_iva += iva
            descr, pct = _descrizione_iva(riga.codice_iva, aliquota_cache)
            key = descr.upper()
            if key not in riepilogo_map:
                riepilogo_map[key] = LibroRegistroIvaRiepilogoVoce(
                    descrizione=descr, imponibile=0.0, iva=0.0
                )
            riepilogo_map[key].imponibile += imp
            riepilogo_map[key].iva += iva

            cells = [
                LibroRegistroIvaCella(prot if idx == 0 else "", "end", "eureka-print-nowrap"),
                LibroRegistroIvaCella(data_reg if idx == 0 else "", "start", "eureka-print-nowrap"),
                LibroRegistroIvaCella(ragione if idx == 0 else "", "start"),
                LibroRegistroIvaCella(numero_doc if idx == 0 else "", "start"),
                LibroRegistroIvaCella(data_doc if idx == 0 else "", "start", "eureka-print-nowrap"),
                LibroRegistroIvaCella(descr, "start"),
                LibroRegistroIvaCella(_fmt_money(imp), "end", "eureka-print-nowrap"),
                LibroRegistroIvaCella(_fmt_pct(pct), "end", "eureka-print-nowrap"),
                LibroRegistroIvaCella(_fmt_money(iva), "end", "eureka-print-nowrap"),
                LibroRegistroIvaCella("", "end"),
            ]
            output.append(LibroRegistroIvaRiga(cells=cells))

        tot_doc_line = doc_imp + doc_iva
        tot_imp += doc_imp
        tot_iva += doc_iva
        tot_doc += tot_doc_line
        output.append(
            LibroRegistroIvaRiga(
                cells=[
                    LibroRegistroIvaCella("", "start"),
                    LibroRegistroIvaCella("", "start"),
                    LibroRegistroIvaCella("", "start"),
                    LibroRegistroIvaCella("", "start"),
                    LibroRegistroIvaCella("", "start"),
                    LibroRegistroIvaCella("", "start"),
                    LibroRegistroIvaCella("", "end"),
                    LibroRegistroIvaCella("", "end"),
                    LibroRegistroIvaCella("", "end"),
                    LibroRegistroIvaCella(_fmt_money(tot_doc_line), "end", "eureka-print-nowrap eureka-print-cell--totale-doc"),
                ],
                row_class="eureka-print-row--totale-doc",
            )
        )
        output.append(
            LibroRegistroIvaRiga(
                cells=[LibroRegistroIvaCella("", colspan=10)],
                row_class="eureka-print-row--separator",
            )
        )

    riepilogo = sorted(riepilogo_map.values(), key=lambda v: v.descrizione.upper())
    documenti_rendered = sum(1 for reg in registrazioni if righe_by_testa.get(reg.id))
    return LibroRegistroIvaDati(
        registro=registro,
        registro_label=label,
        periodo_label=periodo,
        anno=anno,
        righe=output,
        riepilogo=riepilogo,
        totale_imponibile=tot_imp,
        totale_iva=tot_iva,
        totale_documento=tot_doc,
        documenti_count=documenti_rendered,
    )
