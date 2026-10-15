"""Liquidazione periodica IVA (mensile) da registri vendite/acquisti."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db.models import Q
from django.http import QueryDict
from django.utils.dateparse import parse_date

from apps.registri_iva.libro_registro import (
    MESE_IT,
    _is_registro_acquisto,
    _mese_label,
    _month_bounds,
    _resolve_azienda_header,
    build_libro_registro_iva,
)
from apps.registri_iva.models import RegistroIva


@dataclass
class LiquidazioneRegistroVoce:
    codice: str
    label: str
    tipo: str
    imponibile: float = 0.0
    iva: float = 0.0
    iva_deducibile: float = 0.0
    iva_indeducibile: float = 0.0
    documenti: int = 0


@dataclass
class LiquidazionePeriodicaDati:
    periodo_label: str = ""
    anno: int | None = None
    mese: int | None = None
    data_da: date | None = None
    data_a: date | None = None
    vendite: list[LiquidazioneRegistroVoce] = field(default_factory=list)
    acquisti: list[LiquidazioneRegistroVoce] = field(default_factory=list)
    totale_imponibile_vendite: float = 0.0
    totale_iva_debito: float = 0.0
    totale_imponibile_acquisti: float = 0.0
    totale_iva_credito: float = 0.0
    totale_iva_indeducibile_acquisti: float = 0.0
    differenza: float = 0.0
    credito_periodo_precedente: float = 0.0
    saldo: float = 0.0
    iva_da_versare: float = 0.0
    iva_a_credito: float = 0.0
    ready: bool = False
    note: str = ""


def _parse_credito_precedente(raw) -> float:
    if raw in (None, ""):
        return 0.0
    try:
        text = str(raw).strip().replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        return round(float(text), 2)
    except (TypeError, ValueError):
        return 0.0


def _is_registro_vendita(registro: RegistroIva | None) -> bool:
    if registro is None:
        return False
    tipo = (registro.tipo_registro or "").strip().lower()
    return tipo.startswith("vendita") or tipo.startswith("corrispettiv")


def _registri_attivi():
    qs = RegistroIva.objects.filter(
        Q(disattivato=False) | Q(disattivato__isnull=True)
    ).order_by("codice")
    rows = list(qs)
    return rows if rows else list(RegistroIva.objects.order_by("codice"))


def _fake_request(base_request, *, registro: str, data_da: date, data_a: date):
    """Request GET minimale per riusare build_libro_registro_iva."""
    qd = QueryDict(mutable=True)
    qd["registro"] = registro
    qd["data_da"] = data_da.isoformat()
    qd["data_a"] = data_a.isoformat()
    qd["anteprima"] = "1"
    qd["incl_reg_succ"] = "0"

    class _Req:
        pass

    req = _Req()
    req.GET = qd
    req.user = getattr(base_request, "user", None)
    return req


def resolve_periodo_liquidazione(params) -> tuple[date | None, date | None, str]:
    """Risolve periodo da data_da/data_a oppure anno+mese."""
    data_da = parse_date((params.get("data_da") or "").strip())
    data_a = parse_date((params.get("data_a") or "").strip())
    if data_da and data_a:
        if data_da.year == data_a.year and data_da.month == data_a.month:
            start, end = _month_bounds(data_da)
            return start, end, _mese_label(start)
        return (
            data_da,
            data_a,
            f"Dal {data_da.strftime('%d/%m/%Y')} al {data_a.strftime('%d/%m/%Y')}",
        )

    try:
        anno = int((params.get("anno") or "").strip() or 0)
        mese = int((params.get("mese") or "").strip() or 0)
    except (TypeError, ValueError):
        anno = mese = 0
    if anno >= 1900 and 1 <= mese <= 12:
        start, end = _month_bounds(date(anno, mese, 1))
        return start, end, _mese_label(start)
    return None, None, ""


def build_liquidazione_periodica(request) -> LiquidazionePeriodicaDati:
    data_da, data_a, periodo_label = resolve_periodo_liquidazione(request.GET)
    credito_prec = _parse_credito_precedente(request.GET.get("credito_prec"))
    empty = LiquidazionePeriodicaDati(
        periodo_label=periodo_label,
        data_da=data_da,
        data_a=data_a,
        credito_periodo_precedente=credito_prec,
        anno=data_da.year if data_da else None,
        mese=data_da.month if data_da else None,
    )
    if not data_da or not data_a:
        empty.note = "Seleziona anno e mese e genera l'anteprima."
        return empty

    vendite: list[LiquidazioneRegistroVoce] = []
    acquisti: list[LiquidazioneRegistroVoce] = []
    tot_imp_v = tot_iva_v = 0.0
    tot_imp_a = tot_iva_cred = tot_iva_inded_a = 0.0

    for reg in _registri_attivi():
        is_acq = _is_registro_acquisto(reg)
        is_ven = _is_registro_vendita(reg)
        if not (is_acq or is_ven):
            continue

        libro = build_libro_registro_iva(
            _fake_request(request, registro=reg.codice, data_da=data_da, data_a=data_a)
        )
        label = (reg.descrizione or reg.codice or "").strip()
        if is_acq:
            if libro.mostra_riepilogo_competenza:
                iva_cred = float(libro.totale_iva_deducibile_competenza_mese or 0)
                iva_inded = float(libro.totale_iva_indeducibile_competenza_mese or 0)
                imp = float(libro.totale_imponibile_competenza_mese or 0)
            else:
                iva_cred = float(libro.totale_iva_deducibile or libro.totale_iva or 0)
                iva_inded = float(libro.totale_iva_indeducibile or 0)
                imp = float(libro.totale_imponibile or 0)
            voce = LiquidazioneRegistroVoce(
                codice=reg.codice,
                label=label,
                tipo=(reg.tipo_registro or "Acquisto").strip(),
                imponibile=round(imp, 2),
                iva=round(iva_cred + iva_inded, 2),
                iva_deducibile=round(iva_cred, 2),
                iva_indeducibile=round(iva_inded, 2),
                documenti=libro.documenti_count,
            )
            acquisti.append(voce)
            tot_imp_a += voce.imponibile
            tot_iva_cred += voce.iva_deducibile
            tot_iva_inded_a += voce.iva_indeducibile
        else:
            iva = float(libro.totale_iva or 0)
            imp = float(libro.totale_imponibile or 0)
            voce = LiquidazioneRegistroVoce(
                codice=reg.codice,
                label=label,
                tipo=(reg.tipo_registro or "Vendita").strip(),
                imponibile=round(imp, 2),
                iva=round(iva, 2),
                documenti=libro.documenti_count,
            )
            vendite.append(voce)
            tot_imp_v += voce.imponibile
            tot_iva_v += voce.iva

    tot_imp_v = round(tot_imp_v, 2)
    tot_iva_v = round(tot_iva_v, 2)
    tot_imp_a = round(tot_imp_a, 2)
    tot_iva_cred = round(tot_iva_cred, 2)
    tot_iva_inded_a = round(tot_iva_inded_a, 2)
    differenza = round(tot_iva_v - tot_iva_cred, 2)
    saldo = round(differenza - credito_prec, 2)
    iva_da_versare = saldo if saldo > 0 else 0.0
    iva_a_credito = abs(saldo) if saldo < 0 else 0.0

    note_parts = [
        "IVA a debito: registri vendite/corrispettivi (data registrazione).",
        "IVA a credito: registri acquisti per competenza del periodo "
        "(riepilogo 1 − da detrarre + riepilogo 2; a dicembre senza R2).",
    ]
    if data_da.month == 12:
        note_parts.append(
            "Dicembre: nessun contributo da registrazioni di gennaio dell'anno successivo."
        )

    return LiquidazionePeriodicaDati(
        periodo_label=periodo_label,
        anno=data_da.year,
        mese=data_da.month,
        data_da=data_da,
        data_a=data_a,
        vendite=vendite,
        acquisti=acquisti,
        totale_imponibile_vendite=tot_imp_v,
        totale_iva_debito=tot_iva_v,
        totale_imponibile_acquisti=tot_imp_a,
        totale_iva_credito=tot_iva_cred,
        totale_iva_indeducibile_acquisti=tot_iva_inded_a,
        differenza=differenza,
        credito_periodo_precedente=credito_prec,
        saldo=saldo,
        iva_da_versare=round(iva_da_versare, 2),
        iva_a_credito=round(iva_a_credito, 2),
        ready=True,
        note=" ".join(note_parts),
    )


def mese_choices():
    return [(i, MESE_IT[i]) for i in range(1, 13)]


def resolve_azienda_header_liquidazione() -> dict[str, str]:
    return _resolve_azienda_header()
