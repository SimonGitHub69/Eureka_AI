"""PDF libro Registro IVA — ReportLab nativo (identico su ogni piattaforma)."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.dateparse import parse_date

from apps.aziende.configurazione import resolve_print_azienda_context
from apps.core.print_list import print_preview_requested
from apps.registri_iva.libro_registro import (
    LibroRegistroIvaDati,
    _resolve_azienda_header,
    build_libro_registro_iva,
    parse_includi_reg_successive,
)
from apps.registri_iva.pdf_libro_reportlab import LibroPdfResult, build_libro_pdf
from apps.registri_iva.stampa_stato import (
    RIGHE_PER_PAGINA_STIMA,
    get_stampa_stato,
    resolve_data_a_default,
    resolve_data_da_default,
    resolve_pagina_da,
)


def _normalize_date_param(raw: str) -> str:
    """Accetta ISO o gg/mm/aaaa e restituisce ISO (o stringa vuota)."""
    text = (raw or "").strip()
    if not text:
        return ""
    if parse_date(text):
        return text
    parts = text.replace(".", "/").replace("-", "/").split("/")
    if len(parts) == 3 and all(parts):
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000
            from datetime import date as _date

            return _date(y, m, d).isoformat()
        except (TypeError, ValueError):
            return text
    return text

# Stima UI (toolbar / definitiva); il PDF vero calcola le pagine da solo.
RIGHE_PER_PAGINA_PDF = max(48, int(RIGHE_PER_PAGINA_STIMA) - 2)
RIGHE_ULTIMA_PAGINA_PDF = max(40, RIGHE_PER_PAGINA_PDF - 4)


@dataclass(frozen=True)
class LibroPaginaPdf:
    numero: int
    righe: list
    is_last: bool


def chunk_righe_libro(righe: list, *, pagina_da: int = 1) -> list[LibroPaginaPdf]:
    """Spezza le righe per stima pagine (toolbar); il PDF ReportLab ricalcola."""
    rows = list(righe or [])
    da = max(1, int(pagina_da or 1))
    if not rows:
        return [LibroPaginaPdf(numero=da, righe=[], is_last=True)]

    pages: list[LibroPaginaPdf] = []
    i = 0
    page_num = da
    while i < len(rows):
        remaining = len(rows) - i
        if remaining <= RIGHE_ULTIMA_PAGINA_PDF:
            pages.append(LibroPaginaPdf(numero=page_num, righe=rows[i:], is_last=True))
            break
        chunk = rows[i : i + RIGHE_PER_PAGINA_PDF]
        pages.append(LibroPaginaPdf(numero=page_num, righe=chunk, is_last=False))
        i += len(chunk)
        page_num += 1
    if pages and not pages[-1].is_last:
        last = pages[-1]
        pages[-1] = LibroPaginaPdf(numero=last.numero, righe=last.righe, is_last=True)
    return pages


def _prepare_libro(request) -> tuple[LibroRegistroIvaDati, dict, str, int, str, str]:
    if not print_preview_requested(request):
        raise ValueError("Anteprima non richiesta: impostare anteprima=1.")

    registro = (request.GET.get("registro") or "").strip()
    stato = get_stampa_stato(registro)
    # Normalizza subito le date (il widget a schermo è gg/mm/aaaa).
    mutable = request.GET.copy()
    if "data_da" in mutable:
        mutable["data_da"] = _normalize_date_param(mutable.get("data_da") or "")
    if "data_a" in mutable:
        mutable["data_a"] = _normalize_date_param(mutable.get("data_a") or "")
    request.GET = mutable

    data_da = resolve_data_da_default(request.GET, stato)
    data_a = resolve_data_a_default(request.GET, stato, data_da=data_da)
    pagina_da = resolve_pagina_da(request.GET, stato)
    # includi_reg_succ è letto da build_libro_registro_iva via request.GET
    _ = parse_includi_reg_successive(request.GET)

    mutable = request.GET.copy()
    data_da = _normalize_date_param(data_da)
    data_a = _normalize_date_param(data_a)
    if data_da:
        mutable["data_da"] = data_da
    if data_a:
        mutable["data_a"] = data_a
    request.GET = mutable

    libro = build_libro_registro_iva(request)
    if not isinstance(libro, LibroRegistroIvaDati):
        raise ValueError("Dati libro non disponibili.")

    azienda = _resolve_azienda_header()
    print_ctx = resolve_print_azienda_context(branding="liste")
    logo = print_ctx.get("print_azienda_logo_url") or ""
    return libro, azienda, logo, pagina_da, data_da or "", data_a or ""


def render_libro_pdf_result(request) -> LibroPdfResult:
    """PDF nativo ReportLab + conteggio fogli reali (movimenti + riepilogo)."""
    libro, azienda, logo, pagina_da, _da, _a = _prepare_libro(request)
    result = build_libro_pdf(
        libro=libro,
        azienda_header=azienda,
        logo_url=logo,
        pagina_da=pagina_da,
    )
    if not result.data.startswith(b"%PDF"):
        raise RuntimeError("Il file generato non è un PDF valido.")
    return result


def render_libro_pdf(request) -> bytes:
    """PDF nativo ReportLab — nessun browser, nessuna differenza Mac/Windows."""
    return render_libro_pdf_result(request).data


def conteggio_pagine_libro(
    *,
    libro: LibroRegistroIvaDati,
    azienda_header: dict | None = None,
    logo_url: str = "",
    pagina_da: int = 1,
) -> LibroPdfResult:
    """Conta i fogli stampati reali generando lo stesso PDF della stampa definitiva."""
    return build_libro_pdf(
        libro=libro,
        azienda_header=azienda_header or {},
        logo_url=logo_url or "",
        pagina_da=pagina_da,
    )


def stima_pagine_pdf(request) -> int:
    """Numero fogli reali del PDF (movimenti + riepilogo, anche multi-foglio)."""
    return render_libro_pdf_result(request).num_pages


def pdf_filename_for_libro(registro: str, data_da: str, data_a: str) -> str:
    bits = ["Registro_IVA"]
    if registro:
        bits.append("".join(ch for ch in registro if ch.isalnum() or ch in "._-") or "reg")
    if data_da:
        bits.append(str(data_da).replace("-", ""))
    if data_a:
        bits.append(str(data_a).replace("-", ""))
    return "_".join(bits) + ".pdf"
