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
    # Riepilogo 1: registrati nel mese IVA (per data di registrazione)
    riepilogo: list[LibroRegistroIvaRiepilogoVoce] = field(default_factory=list)
    # Registrati nel mese ma competenza già conteggiata nel mese precedente (da non ridetrarre)
    riepilogo_gia_conteggiate: list[LibroRegistroIvaRiepilogoVoce] = field(
        default_factory=list
    )
    # Riepilogo 2: registrati nel mese successivo con competenza nel mese IVA
    riepilogo_competenza: list[LibroRegistroIvaRiepilogoVoce] = field(default_factory=list)
    # Totale complessivo di competenza del mese IVA (R1 − già conteggiate + R2)
    riepilogo_totale_competenza: list[LibroRegistroIvaRiepilogoVoce] = field(
        default_factory=list
    )
    totale_imponibile: float = 0.0
    totale_iva: float = 0.0
    totale_iva_deducibile: float = 0.0
    totale_iva_indeducibile: float = 0.0
    # Somma delle sole righe stampate nel corpo registro (Totali generali)
    totale_imponibile_stampa: float = 0.0
    totale_iva_stampa: float = 0.0
    totale_documento: float = 0.0
    totale_imponibile_gia_conteggiate: float = 0.0
    totale_iva_gia_conteggiate: float = 0.0
    totale_iva_deducibile_gia_conteggiate: float = 0.0
    totale_iva_indeducibile_gia_conteggiate: float = 0.0
    totale_imponibile_competenza: float = 0.0
    totale_iva_competenza: float = 0.0
    totale_iva_deducibile_competenza: float = 0.0
    totale_iva_indeducibile_competenza: float = 0.0
    totale_imponibile_competenza_mese: float = 0.0
    totale_iva_competenza_mese: float = 0.0
    totale_iva_deducibile_competenza_mese: float = 0.0
    totale_iva_indeducibile_competenza_mese: float = 0.0
    documenti_count: int = 0
    mostra_competenza: bool = False
    mostra_riepilogo_competenza: bool = False
    # R2 (mese successivo): non vale per dicembre (niente gennaio anno dopo)
    mostra_riepilogo_2: bool = False
    mostra_riepilogo_gia_conteggiate: bool = False
    mese_iva_label: str = ""
    mese_successivo_label: str = ""
    mese_precedente_label: str = ""
    protocolli_altra_competenza: list[str] = field(default_factory=list)
    protocolli_gia_conteggiate: list[str] = field(default_factory=list)
    max_protocollo: int | None = None

    @property
    def col_count(self) -> int:
        return 11 if self.mostra_competenza else 10

    @property
    def label_colspan(self) -> int:
        """Colonne prima degli importi (Prot…Descr. Iva)."""
        return 7 if self.mostra_competenza else 6

    @property
    def ha_riepilogo_stampa(self) -> bool:
        """True se la stampa include il foglio riepilogo (pagina aggiuntiva)."""
        return bool(self.riepilogo or self.mostra_riepilogo_competenza)

    @property
    def stima_pagine(self) -> int:
        from apps.registri_iva.stampa_stato import stima_num_pagine

        return stima_num_pagine(
            len(self.righe), con_riepilogo=self.ha_riepilogo_stampa
        )


def _is_registro_acquisto(registro: RegistroIva | None) -> bool:
    if registro is None:
        return False
    return (registro.tipo_registro or "").strip().lower().startswith("acquisto")


def _is_registro_corrispettivi(registro: RegistroIva | None) -> bool:
    if registro is None:
        return False
    return (registro.tipo_registro or "").strip().lower().startswith("corrispett")


def _importi_riga_libro(
    riga: PrimanotaDettaglio,
    *,
    iva_inclusa: bool,
    aliquota_cache: dict,
) -> tuple[float, float, float]:
    """
    Restituisce (imponibile, iva, totale_riga).

    Per i corrispettivi l'importo in dare/avere è già IVA inclusa: si scorpora.
    """
    from apps.primanota.iva import scorporo_iva_da_lordo

    raw = float(riga.imponibile or 0)
    if iva_inclusa:
        scorporato = scorporo_iva_da_lordo(
            raw, riga.codice_iva, cache=aliquota_cache
        )
        if scorporato is None:
            return 0.0, 0.0, 0.0
        imp, iva = scorporato
        return imp, iva, raw
    iva = float(riga.importo_iva or 0)
    return raw, iva, raw + iva


def parse_includi_reg_successive(params) -> bool:
    """
    Opzione filtro stampa: includere nel corpo del registro le registrazioni
    con data reg. nel mese successivo ma competenza IVA nel mese stampato.
    Non influisce sui riepiloghi (sempre per competenza).
    Default False all'apertura maschera (assente → non include).
    """
    raw = params.get("incl_reg_succ") if params is not None else None
    if raw is None:
        return False
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _percentuale_ind(codice_iva: str, cache: dict[str, float]) -> float:
    key = (codice_iva or "").strip().upper()
    if not key:
        return 0.0
    if key in cache:
        return cache[key]
    pct = 0.0
    try:
        from apps.aliquote.models import Aliquota

        row = (
            Aliquota.objects.filter(codice__iexact=key)
            .only("percentuale_ind")
            .first()
        )
        if row is not None and row.percentuale_ind is not None:
            pct = float(row.percentuale_ind)
    except Exception:
        pct = 0.0
    cache[key] = pct
    return pct


def _split_iva(importo_iva: float, percentuale_ind: float) -> tuple[float, float]:
    """Ripartisce IVA in (deducibile, indeducibile) secondo % indetraibile aliquota."""
    iva = float(importo_iva or 0)
    pct = float(percentuale_ind or 0)
    if iva == 0 or pct <= 0:
        return round(iva, 2), 0.0
    if pct >= 100:
        return 0.0, round(iva, 2)
    inded = round(iva * pct / 100.0, 2)
    ded = round(iva - inded, 2)
    return ded, inded


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


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _date_in_period(
    value, data_da: date | None, data_a: date | None
) -> bool:
    d = _as_date(value)
    if d is None:
        return False
    if data_da and d < data_da:
        return False
    if data_a and d > data_a:
        return False
    return True


def _month_bounds(d: date) -> tuple[date, date]:
    import calendar

    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, 1), date(d.year, d.month, last)


def _next_month_end(mese_start: date) -> date:
    import calendar

    if mese_start.month == 12:
        y, m = mese_start.year + 1, 1
    else:
        y, m = mese_start.year, mese_start.month + 1
    return date(y, m, calendar.monthrange(y, m)[1])


def _mese_label(d: date) -> str:
    return f"{MESE_IT[d.month]} {d.year}"


def _next_mese_label(mese_start: date) -> str:
    if mese_start.month == 12:
        return f"{MESE_IT[1]} {mese_start.year + 1}"
    return f"{MESE_IT[mese_start.month + 1]} {mese_start.year}"


def _prev_mese_label(mese_start: date) -> str:
    if mese_start.month == 1:
        return f"{MESE_IT[12]} {mese_start.year - 1}"
    return f"{MESE_IT[mese_start.month - 1]} {mese_start.year}"


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


def _filter_registrazioni_libro(
    request, registro_code: str, *, estendi_mese_successivo: bool = False
):
    """
    Filtro per data registrazione.
    Se estendi_mese_successivo (acquisti, periodo = un mese calendario): include anche
    le registrazioni del mese successivo con competenza IVA nel mese stampato.
    """
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
    if not (data_da or data_a):
        return qs.order_by("data_reg", "numero_prot", "id")

    qs = qs.annotate(_data_reg_cal=Cast("data_reg", DateField()))

    if (
        estendi_mese_successivo
        and data_da
        and data_a
        and data_da.year == data_a.year
        and data_da.month == data_a.month
    ):
        mese_start, mese_end = _month_bounds(data_da)
        next_end = _next_month_end(mese_start)
        qs = qs.annotate(_data_comp_cal=Cast("data_valuta", DateField())).filter(
            Q(_data_reg_cal__gte=mese_start, _data_reg_cal__lte=mese_end)
            | Q(
                _data_comp_cal__gte=mese_start,
                _data_comp_cal__lte=mese_end,
                _data_reg_cal__gt=mese_end,
                _data_reg_cal__lte=next_end,
            )
        )
    else:
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


def _accumula_riepilogo(
    mappa: dict[str, LibroRegistroIvaRiepilogoVoce],
    *,
    descr: str,
    imp: float,
    iva: float,
    iva_ded: float,
    iva_inded: float,
) -> None:
    key = descr.upper()
    if key not in mappa:
        mappa[key] = LibroRegistroIvaRiepilogoVoce(
            descrizione=descr, imponibile=0.0, iva=0.0
        )
    mappa[key].imponibile += imp
    mappa[key].iva += iva
    mappa[key].iva_deducibile += iva_ded
    mappa[key].iva_indeducibile += iva_inded


def _merge_riepiloghi(
    *mappe: dict[str, LibroRegistroIvaRiepilogoVoce],
) -> list[LibroRegistroIvaRiepilogoVoce]:
    merged: dict[str, LibroRegistroIvaRiepilogoVoce] = {}
    for mappa in mappe:
        for voce in mappa.values():
            _accumula_riepilogo(
                merged,
                descr=voce.descrizione,
                imp=voce.imponibile,
                iva=voce.iva,
                iva_ded=voce.iva_deducibile,
                iva_inded=voce.iva_indeducibile,
            )
    return sorted(merged.values(), key=lambda v: v.descrizione.upper())


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
    label = (
        (registro.descrizione or registro.codice or registro_code).strip()
        if registro
        else registro_code
    )
    mostra_competenza = _is_registro_acquisto(registro)
    iva_inclusa = _is_registro_corrispettivi(registro)
    periodo_mese = bool(
        data_da
        and data_a
        and data_da.year == data_a.year
        and data_da.month == data_a.month
    )
    includi_reg_succ = parse_includi_reg_successive(request.GET)
    # Schema PDF: R1 + (eventuale da detrarre) + R2 per competenza.
    # Dicembre: niente R2 (non si includono registrazioni di gennaio anno successivo).
    # Resta la detrazione delle reg. di dicembre con competenza novembre.
    mostra_riepilogo_competenza = bool(mostra_competenza and periodo_mese)
    mese_start = mese_end = None
    mese_iva_label = ""
    mese_successivo_label = ""
    mese_precedente_label = ""
    mostra_riepilogo_2 = False
    if mostra_riepilogo_competenza and data_da is not None:
        mese_start, mese_end = _month_bounds(data_da)
        mese_iva_label = _mese_label(mese_start)
        mese_precedente_label = _prev_mese_label(mese_start)
        # R2 solo gen–nov: a dicembre non esiste “mese successivo” nello stesso esercizio
        mostra_riepilogo_2 = mese_start.month != 12
        if mostra_riepilogo_2:
            mese_successivo_label = _next_mese_label(mese_start)

    empty = LibroRegistroIvaDati(
        registro=registro,
        registro_label=label,
        periodo_label=periodo,
        anno=anno,
        mostra_competenza=mostra_competenza,
        mostra_riepilogo_competenza=mostra_riepilogo_competenza,
        mostra_riepilogo_2=mostra_riepilogo_2,
        mese_iva_label=mese_iva_label,
        mese_successivo_label=mese_successivo_label,
        mese_precedente_label=mese_precedente_label,
    )
    if not registro_code:
        return empty

    registrazioni = list(
        _filter_registrazioni_libro(
            request,
            registro_code,
            # Estendi a mese successivo solo se R2 è attivo (non a dicembre)
            estendi_mese_successivo=mostra_riepilogo_2,
        )
    )
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
    ind_cache: dict[str, float] = {}
    partita_cache: dict[str, dict] = {}
    output: list[LibroRegistroIvaRiga] = []
    riepilogo_map: dict[str, LibroRegistroIvaRiepilogoVoce] = {}
    riepilogo_gia_map: dict[str, LibroRegistroIvaRiepilogoVoce] = {}
    riepilogo_comp_mese_map: dict[str, LibroRegistroIvaRiepilogoVoce] = {}
    riepilogo_r2_map: dict[str, LibroRegistroIvaRiepilogoVoce] = {}
    tot_imp = tot_iva = tot_doc = 0.0
    tot_iva_ded = tot_iva_inded = 0.0
    tot_imp_gia = tot_iva_gia = 0.0
    tot_iva_ded_gia = tot_iva_inded_gia = 0.0
    tot_imp_comp = tot_iva_comp = 0.0
    tot_iva_ded_comp = tot_iva_inded_comp = 0.0
    tot_imp_r2 = tot_iva_r2 = 0.0
    tot_iva_ded_r2 = tot_iva_inded_r2 = 0.0
    max_protocollo: int | None = None
    protocolli_tardivi: list[str] = []
    protocolli_gia: list[str] = []
    documenti_stampati = 0

    for reg in registrazioni:
        dettagli = righe_by_testa.get(reg.id) or []
        if not dettagli:
            continue

        partita_code = (reg.codice_partita or "").strip()
        if partita_code not in partita_cache:
            partita_cache[partita_code] = resolve_partita_clifor(partita_code)
        ragione = partita_cache[partita_code].get("label") or partita_code

        prot = str(reg.numero_prot or "")
        data_reg_d = _as_date(reg.data_reg)
        data_reg = _fmt_date_short(reg.data_reg)
        data_comp = _fmt_date_short(reg.data_valuta) if mostra_competenza else ""
        numero_doc = (reg.numero_doc or "").strip()
        data_doc = _fmt_date_short(reg.data_doc)
        data_competenza = _as_date(reg.data_valuta) or data_reg_d

        registrato_nel_mese = bool(
            mese_start
            and mese_end
            and data_reg_d
            and mese_start <= data_reg_d <= mese_end
        )
        competenza_nel_mese = bool(
            mese_start
            and mese_end
            and data_competenza
            and mese_start <= data_competenza <= mese_end
        )
        competenza_mese_precedente = bool(
            mostra_riepilogo_competenza
            and mese_start
            and data_competenza
            and data_competenza < mese_start
        )
        # R1: tutte le registrazioni con data reg. nel mese
        in_riepilogo_1 = bool(
            not mostra_riepilogo_competenza or registrato_nel_mese
        )
        # Già conteggiate: in R1 ma competenza già liquidata nel mese precedente
        in_gia_conteggiate = bool(
            mostra_riepilogo_competenza
            and registrato_nel_mese
            and competenza_mese_precedente
        )
        # Competenza del mese corrente (per totale: R1 senza già conteggiate)
        in_competenza_mese = bool(
            mostra_riepilogo_competenza
            and registrato_nel_mese
            and competenza_nel_mese
        )
        registrato_dopo_con_comp = bool(
            mostra_riepilogo_2
            and mese_start
            and mese_end
            and data_reg_d
            and data_reg_d > mese_end
            and competenza_nel_mese
        )
        if registrato_dopo_con_comp and prot and prot not in protocolli_tardivi:
            protocolli_tardivi.append(prot)
        if in_gia_conteggiate and prot and prot not in protocolli_gia:
            protocolli_gia.append(prot)

        # Corpo registro: opzione OFF → non stampare le reg. del mese successivo
        stampa_nel_registro = includi_reg_succ or not registrato_dopo_con_comp
        if stampa_nel_registro:
            documenti_stampati += 1

        if stampa_nel_registro and reg.numero_prot is not None:
            try:
                prot_n = int(reg.numero_prot)
            except (TypeError, ValueError):
                prot_n = None
            if prot_n is not None:
                max_protocollo = (
                    prot_n if max_protocollo is None else max(max_protocollo, prot_n)
                )

        importi_righe = [
            _importi_riga_libro(
                r, iva_inclusa=iva_inclusa, aliquota_cache=aliquota_cache
            )
            for r in dettagli
        ]
        doc_imp = sum(t[0] for t in importi_righe)
        doc_iva = sum(t[1] for t in importi_righe)
        tot_doc_line = sum(t[2] for t in importi_righe)
        if stampa_nel_registro:
            tot_imp += doc_imp
            tot_iva += doc_iva
            tot_doc += tot_doc_line
        last_idx = len(dettagli) - 1

        for idx, riga in enumerate(dettagli):
            imp, iva, _tot_riga = importi_righe[idx]
            descr, pct = _descrizione_iva(riga.codice_iva, aliquota_cache)
            pct_ind = _percentuale_ind(riga.codice_iva, ind_cache)
            iva_ded, iva_inded = _split_iva(iva, pct_ind)

            # R1: registrati nel mese (per data di registrazione)
            if in_riepilogo_1:
                _accumula_riepilogo(
                    riepilogo_map,
                    descr=descr,
                    imp=imp,
                    iva=iva,
                    iva_ded=iva_ded,
                    iva_inded=iva_inded,
                )
                tot_iva_ded += iva_ded
                tot_iva_inded += iva_inded

            # Già conteggiate nel mese precedente (in R1 ma escluse dal totale competenza)
            if in_gia_conteggiate:
                _accumula_riepilogo(
                    riepilogo_gia_map,
                    descr=descr,
                    imp=imp,
                    iva=iva,
                    iva_ded=iva_ded,
                    iva_inded=iva_inded,
                )
                tot_imp_gia += imp
                tot_iva_gia += iva
                tot_iva_ded_gia += iva_ded
                tot_iva_inded_gia += iva_inded

            # Quota R1 con competenza nel mese corrente (per totale competenza)
            if in_competenza_mese:
                _accumula_riepilogo(
                    riepilogo_comp_mese_map,
                    descr=descr,
                    imp=imp,
                    iva=iva,
                    iva_ded=iva_ded,
                    iva_inded=iva_inded,
                )
                tot_imp_comp += imp
                tot_iva_comp += iva
                tot_iva_ded_comp += iva_ded
                tot_iva_inded_comp += iva_inded

            # R2: registrati dopo, competenza nel mese IVA
            if registrato_dopo_con_comp:
                _accumula_riepilogo(
                    riepilogo_r2_map,
                    descr=descr,
                    imp=imp,
                    iva=iva,
                    iva_ded=iva_ded,
                    iva_inded=iva_inded,
                )
                tot_imp_r2 += imp
                tot_iva_r2 += iva
                tot_iva_ded_r2 += iva_ded
                tot_iva_inded_r2 += iva_inded

            if not stampa_nel_registro:
                continue

            cells = [
                LibroRegistroIvaCella(prot if idx == 0 else "", "end", "eureka-print-nowrap"),
                LibroRegistroIvaCella(data_reg if idx == 0 else "", "start", "eureka-print-nowrap"),
            ]
            if mostra_competenza:
                cells.append(
                    LibroRegistroIvaCella(
                        data_comp if idx == 0 else "", "start", "eureka-print-nowrap"
                    )
                )
            cells.extend(
                [
                    LibroRegistroIvaCella(ragione if idx == 0 else "", "start"),
                    LibroRegistroIvaCella(
                        numero_doc if idx == 0 else "", "start", "eureka-print-nowrap"
                    ),
                    LibroRegistroIvaCella(
                        data_doc if idx == 0 else "", "start", "eureka-print-nowrap"
                    ),
                    LibroRegistroIvaCella(descr, "start"),
                    LibroRegistroIvaCella(_fmt_money(imp), "end", "eureka-print-nowrap"),
                    LibroRegistroIvaCella(_fmt_pct(pct), "end", "eureka-print-nowrap"),
                    LibroRegistroIvaCella(_fmt_money(iva), "end", "eureka-print-nowrap"),
                    LibroRegistroIvaCella(
                        _fmt_money(tot_doc_line) if idx == last_idx else "",
                        "end",
                        "eureka-print-nowrap eureka-print-cell--totale-doc"
                        if idx == last_idx
                        else "",
                    ),
                ]
            )
            row_classes = []
            if idx == last_idx:
                row_classes.append("eureka-print-row--doc-end")
            if registrato_dopo_con_comp:
                row_classes.append("eureka-print-row--comp-successiva")
            elif in_gia_conteggiate:
                row_classes.append("eureka-print-row--comp-precedente")
            output.append(
                LibroRegistroIvaRiga(cells=cells, row_class=" ".join(row_classes))
            )

    # Totali corpo registro (tutte le righe stampate) vs R1 (per data reg.)
    tot_imp_stampa = round(tot_imp, 2)
    tot_iva_stampa = round(tot_iva, 2)
    if mostra_riepilogo_competenza:
        tot_imp = sum(v.imponibile for v in riepilogo_map.values())
        tot_iva = sum(v.iva for v in riepilogo_map.values())

    riepilogo = sorted(riepilogo_map.values(), key=lambda v: v.descrizione.upper())
    # Segno negativo: sezione "Da detrarre" (già conteggiate nel mese precedente)
    riepilogo_gia = sorted(
        (
            LibroRegistroIvaRiepilogoVoce(
                descrizione=v.descrizione,
                imponibile=-v.imponibile,
                iva=-v.iva,
                iva_deducibile=-v.iva_deducibile,
                iva_indeducibile=-v.iva_indeducibile,
            )
            for v in riepilogo_gia_map.values()
        ),
        key=lambda v: v.descrizione.upper(),
    )
    riepilogo_r2 = sorted(riepilogo_r2_map.values(), key=lambda v: v.descrizione.upper())
    # Totale competenza = (R1 per data reg. con competenza nel mese) + R2
    riepilogo_tot = _merge_riepiloghi(riepilogo_comp_mese_map, riepilogo_r2_map)
    mostra_gia = bool(mostra_riepilogo_competenza and riepilogo_gia)
    if mostra_riepilogo_competenza:
        tot_imp_mese = round(tot_imp_comp + tot_imp_r2, 2)
        tot_iva_mese = round(tot_iva_comp + tot_iva_r2, 2)
        tot_ded_mese = round(tot_iva_ded_comp + tot_iva_ded_r2, 2)
        tot_inded_mese = round(tot_iva_inded_comp + tot_iva_inded_r2, 2)
    else:
        tot_imp_mese = round(tot_imp, 2)
        tot_iva_mese = round(tot_iva, 2)
        tot_ded_mese = round(tot_iva_ded, 2)
        tot_inded_mese = round(tot_iva_inded, 2)

    return LibroRegistroIvaDati(
        registro=registro,
        registro_label=label,
        periodo_label=periodo,
        anno=anno,
        righe=output,
        riepilogo=riepilogo,
        riepilogo_gia_conteggiate=riepilogo_gia,
        riepilogo_competenza=riepilogo_r2,
        riepilogo_totale_competenza=riepilogo_tot,
        totale_imponibile=round(tot_imp, 2),
        totale_iva=round(tot_iva, 2),
        totale_iva_deducibile=round(tot_iva_ded, 2),
        totale_iva_indeducibile=round(tot_iva_inded, 2),
        totale_imponibile_stampa=tot_imp_stampa,
        totale_iva_stampa=tot_iva_stampa,
        totale_documento=round(tot_doc, 2),
        totale_imponibile_gia_conteggiate=round(-tot_imp_gia, 2),
        totale_iva_gia_conteggiate=round(-tot_iva_gia, 2),
        totale_iva_deducibile_gia_conteggiate=round(-tot_iva_ded_gia, 2),
        totale_iva_indeducibile_gia_conteggiate=round(-tot_iva_inded_gia, 2),
        totale_imponibile_competenza=round(tot_imp_r2, 2),
        totale_iva_competenza=round(tot_iva_r2, 2),
        totale_iva_deducibile_competenza=round(tot_iva_ded_r2, 2),
        totale_iva_indeducibile_competenza=round(tot_iva_inded_r2, 2),
        totale_imponibile_competenza_mese=tot_imp_mese,
        totale_iva_competenza_mese=tot_iva_mese,
        totale_iva_deducibile_competenza_mese=tot_ded_mese,
        totale_iva_indeducibile_competenza_mese=tot_inded_mese,
        documenti_count=documenti_stampati,
        mostra_competenza=mostra_competenza,
        mostra_riepilogo_competenza=mostra_riepilogo_competenza,
        mostra_riepilogo_2=mostra_riepilogo_2,
        mostra_riepilogo_gia_conteggiate=mostra_gia,
        mese_iva_label=mese_iva_label,
        mese_successivo_label=mese_successivo_label,
        mese_precedente_label=mese_precedente_label,
        protocolli_altra_competenza=protocolli_tardivi,
        protocolli_gia_conteggiate=protocolli_gia,
        max_protocollo=max_protocollo,
    )
