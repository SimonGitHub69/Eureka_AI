"""Periodo filtro movimenti magazzino sulla scheda articolo."""

from __future__ import annotations

from datetime import date

from django.http import HttpRequest
from django.utils.dateparse import parse_date

from apps.anagrafiche.partitario import default_periodo
from apps.articoli.movimenti_magazzino import MovimentiArticoloResult, movimenti_articolo
from apps.articoli.movimenti_sort import MOVIMENTI_ARTICOLO_SORT_FIELDS, sort_movimenti_righe
from apps.core.sorting import resolve_sort


def parse_movimenti_periodo(request: HttpRequest) -> tuple[date | None, date | None, bool]:
    """
    Restituisce (data_da, data_a, filtro_attivo).

    - ``mov_tutti=1``: nessun filtro date
    - ``mov_data_da`` / ``mov_data_a`` valorizzati: filtro sul periodo
    - altrimenti: nessun filtro (tutti i movimenti)
    """
    if (request.GET.get("mov_tutti") or "").strip() == "1":
        return None, None, False

    raw_da = (request.GET.get("mov_data_da") or "").strip()
    raw_a = (request.GET.get("mov_data_a") or "").strip()
    if not raw_da and not raw_a:
        return None, None, False

    default_da, default_a = default_periodo()
    data_da = parse_date(raw_da) or default_da
    data_a = parse_date(raw_a) or default_a
    if data_da > data_a:
        data_da, data_a = data_a, data_da
    return data_da, data_a, True


def movimenti_articolo_for_request(
    request: HttpRequest, codice: str
) -> MovimentiArticoloResult:
    data_da, data_a, filtro = parse_movimenti_periodo(request)
    result = movimenti_articolo(
        codice,
        data_da=data_da if filtro else None,
        data_a=data_a if filtro else None,
    )
    sort, direction = resolve_sort(
        request,
        allowed=MOVIMENTI_ARTICOLO_SORT_FIELDS,
        default_sort="data_registraz",
        default_dir="asc",
    )
    result.righe = sort_movimenti_righe(result.righe, sort, direction)
    return result


def movimenti_print_filter_summary(
    request: HttpRequest,
    result: MovimentiArticoloResult,
    articolo,
) -> str:
    parts: list[str] = []
    codice = (getattr(articolo, "codice", None) or "").strip()
    if codice:
        parts.append(f"Articolo: {codice}")
    um = (getattr(articolo, "unita_misura", None) or "").strip()
    parts.append(
        f"Esistenza attuale: {int(result.esistenza_attuale):,}".replace(",", ".")
        + (f" {um}" if um else "")
    )
    if (request.GET.get("mov_tutti") or "").strip() == "1" or not result.filtro_attivo:
        parts.append("Periodo: tutti i movimenti")
    elif result.data_da and result.data_a:
        parts.append(
            f"Periodo: {result.data_da.strftime('%d/%m/%Y')} — {result.data_a.strftime('%d/%m/%Y')}"
        )
        if result.giacenza_precedente:
            parts.append(
                f"Giacenza precedente: {int(result.giacenza_precedente):,}".replace(",", ".")
            )
    return " · ".join(parts)


def movimenti_print_query(request: HttpRequest) -> str:
    if (request.GET.get("mov_tutti") or "").strip() == "1":
        params = ["mov_tutti=1"]
    else:
        data_da, data_a, filtro = parse_movimenti_periodo(request)
        params: list[str] = []
        if not filtro:
            params = []
        else:
            if data_da:
                params.append(f"mov_data_da={data_da.isoformat()}")
            if data_a:
                params.append(f"mov_data_a={data_a.isoformat()}")
    sort, direction = resolve_sort(
        request,
        allowed=MOVIMENTI_ARTICOLO_SORT_FIELDS,
        default_sort="data_registraz",
        default_dir="asc",
    )
    if sort:
        params.append(f"sort={sort}")
        params.append(f"dir={direction}")
    return "&".join(params)


def movimenti_periodo_context(request: HttpRequest) -> dict:
    data_da, data_a, filtro_attivo = parse_movimenti_periodo(request)
    default_da, default_a = default_periodo()
    today = default_a
    prev_da = date(today.year - 1, 1, 1)
    prev_a = date(today.year - 1, 12, 31)
    sort, direction = resolve_sort(
        request,
        allowed=MOVIMENTI_ARTICOLO_SORT_FIELDS,
        default_sort="data_registraz",
        default_dir="asc",
    )
    qs = request.GET.copy()
    for key in ("mov_data_da", "mov_data_a", "mov_tutti", "page"):
        qs.pop(key, None)
    return {
        "mov_data_da": data_da.isoformat() if filtro_attivo and data_da else "",
        "mov_data_a": data_a.isoformat() if filtro_attivo and data_a else "",
        "mov_filtro_attivo": filtro_attivo,
        "mov_data_da_default": default_da.isoformat(),
        "mov_data_a_default": default_a.isoformat(),
        "mov_data_da_prev": prev_da.isoformat(),
        "mov_data_a_prev": prev_a.isoformat(),
        "movimenti_query": qs.urlencode(),
        "mov_print_query": movimenti_print_query(request),
        "sort": sort,
        "dir": direction,
    }
