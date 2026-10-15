"""PDF Libro Registro IVA con ReportLab — identico su Mac, Windows e ogni client."""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from django.conf import settings
from django.contrib.staticfiles.finders import find
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from apps.core.print_list import format_it_number
from apps.registri_iva.libro_registro import LibroRegistroIvaDati, LibroRegistroIvaRiga

# Palette fiscale Eureka
BLUE = colors.HexColor("#1e3a8a")
BLUE_SOFT = colors.HexColor("#dbeafe")
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#1e293b")
ROW_ALT = colors.HexColor("#f8fafc")
COMP_SUCC = colors.HexColor("#ecfdf5")
COMP_PREC = colors.HexColor("#fff7ed")

PAGE_W, PAGE_H = A4
MARGIN = 8 * mm


def _register_fonts() -> tuple[str, str]:
    """Preferisce font TTF leggibili; fallback Helvetica."""
    regular, bold = "Helvetica", "Helvetica-Bold"
    candidates = [
        (
            Path(settings.BASE_DIR) / "static" / "eureka" / "fonts" / "DejaVuSans.ttf",
            Path(settings.BASE_DIR) / "static" / "eureka" / "fonts" / "DejaVuSans-Bold.ttf",
            "EurekaSans",
            "EurekaSans-Bold",
        ),
    ]
    # Windows
    windir = Path(settings.BASE_DIR).anchor and Path("C:/Windows/Fonts")
    if windir.is_dir():
        candidates.append(
            (windir / "arial.ttf", windir / "arialbd.ttf", "EurekaArial", "EurekaArial-Bold")
        )
    # macOS
    candidates.append(
        (
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            "EurekaArial",
            "EurekaArial-Bold",
        )
    )
    for reg_path, bold_path, reg_name, bold_name in candidates:
        try:
            if reg_path.is_file() and bold_path.is_file():
                if reg_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(reg_name, str(reg_path)))
                    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                return reg_name, bold_name
        except Exception:
            continue
    return regular, bold


def _logo_image(url: str) -> Image | None:
    """Logo da data-URI, file:// o path media/static → Image ReportLab."""
    raw = (url or "").strip()
    if not raw:
        return None
    try:
        if raw.startswith("data:"):
            # data:image/png;base64,....
            m = re.match(
                r"^data:(image/[^;]+);base64,(.+)$",
                raw,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not m:
                return None
            blob = base64.b64decode(m.group(2))
            if not blob:
                return None
            # ReportLab 5: Image vuole path o file-like, non ImageReader.
            img = Image(io.BytesIO(blob))
        else:
            path: Path | None = None
            if raw.startswith("file:"):
                parsed = urlparse(raw)
                path = Path(url2pathname(unquote(parsed.path)))
                if not path.exists() and parsed.path.startswith("/") and len(parsed.path) > 2:
                    path = Path(url2pathname(unquote(parsed.path.lstrip("/"))))
            else:
                media_url = settings.MEDIA_URL or "/media/"
                if raw.startswith(media_url):
                    rel = raw[len(media_url) :].lstrip("/")
                    path = Path(settings.MEDIA_ROOT) / rel
                else:
                    static_url = settings.STATIC_URL or "/static/"
                    if raw.startswith(static_url):
                        rel = raw[len(static_url) :].lstrip("/")
                        found = find(rel)
                        path = Path(found) if found else None
                    else:
                        cand = Path(raw)
                        path = cand if cand.is_file() else None
            if not path or not path.is_file():
                return None
            img = Image(str(path))

        # Max 26×14 mm come in stampa HTML
        max_w, max_h = 26 * mm, 14 * mm
        iw = float(getattr(img, "imageWidth", 0) or 0)
        ih = float(getattr(img, "imageHeight", 0) or 0)
        if iw <= 0 or ih <= 0:
            img.drawWidth = max_w
            img.drawHeight = max_h * 0.7
        else:
            scale = min(max_w / iw, max_h / ih)
            img.drawWidth = iw * scale
            img.drawHeight = ih * scale
        return img
    except Exception:
        return None


def _styles(font: str, font_bold: str) -> dict[str, ParagraphStyle]:
    return {
        "company": ParagraphStyle(
            "libCompany",
            fontName=font_bold,
            fontSize=8,
            leading=10,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        "meta": ParagraphStyle(
            "libMeta",
            fontName=font,
            fontSize=6.5,
            leading=8,
            textColor=MUTED,
            alignment=TA_LEFT,
        ),
        "badge": ParagraphStyle(
            "libBadge",
            fontName=font_bold,
            fontSize=7,
            leading=9,
            textColor=BLUE,
            alignment=TA_LEFT,
        ),
        "doctype": ParagraphStyle(
            "libDoctype",
            fontName=font_bold,
            fontSize=8,
            leading=10,
            textColor=BLUE,
            alignment=TA_RIGHT,
        ),
        "page": ParagraphStyle(
            "libPage",
            fontName=font_bold,
            fontSize=9,
            leading=11,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
        "th": ParagraphStyle(
            "libTh",
            fontName=font_bold,
            fontSize=6,
            leading=7.5,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "th_end": ParagraphStyle(
            "libThEnd",
            fontName=font_bold,
            fontSize=6,
            leading=7.5,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
        "td": ParagraphStyle(
            "libTd",
            fontName=font,
            fontSize=6.5,
            leading=8,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        "td_end": ParagraphStyle(
            "libTdEnd",
            fontName=font,
            fontSize=6.5,
            leading=8,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
        "td_small": ParagraphStyle(
            "libTdSmall",
            fontName=font,
            fontSize=6,
            leading=7.5,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        "title": ParagraphStyle(
            "libTitle",
            fontName=font_bold,
            fontSize=10,
            leading=13,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "note": ParagraphStyle(
            "libNote",
            fontName=font,
            fontSize=7,
            leading=9,
            textColor=MUTED,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "empty": ParagraphStyle(
            "libEmpty",
            fontName=font,
            fontSize=8,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _money(value: float) -> str:
    return format_it_number(value, decimals=2)


def _col_headers(acquisto: bool) -> list[str]:
    if acquisto:
        return [
            "Prot.",
            "Data",
            "Competenza",
            "Rag. Sociale",
            "N.Doc.",
            "del",
            "Descr. Iva",
            "Impon.",
            "%",
            "Imp. Iva",
            "Tot. Doc.",
        ]
    return [
        "Prot.",
        "Data",
        "Rag. Sociale",
        "N.Doc.",
        "del",
        "Descr. Iva",
        "Impon.",
        "%",
        "Imp. Iva",
        "Tot. Doc.",
    ]


def _col_widths(acquisto: bool, usable: float) -> list[float]:
    # Somma pesi → ridistribuisce sulla larghezza utile A4
    if acquisto:
        weights = [7, 9, 9, 22, 9, 8, 14, 9, 5, 9, 9]
    else:
        weights = [7, 9, 24, 9, 8, 15, 9, 5, 9, 10]
    total = float(sum(weights))
    return [usable * (w / total) for w in weights]


def _masthead_table(
    *,
    styles: dict,
    font_bold: str,
    azienda: dict,
    libro: LibroRegistroIvaDati,
    pagina: int,
    logo_url: str,
    usable: float,
) -> Table:
    logo_cell: object = _logo_image(logo_url) or ""
    if not logo_cell:
        initials = (azienda.get("initials") or "")[:3]
        if initials:
            logo_cell = Paragraph(_esc(initials), styles["badge"])

    company = azienda.get("ragione_sociale") or ""
    addr = azienda.get("indirizzo") or ""
    fiscal_bits = []
    if azienda.get("codice_fiscale"):
        fiscal_bits.append(f"C.F. {azienda['codice_fiscale']}")
    if azienda.get("partita_iva"):
        fiscal_bits.append(f"P.IVA {azienda['partita_iva']}")
    chips = []
    if libro.registro_label:
        chips.append(f"<b>{_esc(libro.registro_label)}</b>")
    if libro.anno:
        chips.append(f"Anno {libro.anno}")
    if libro.periodo_label:
        chips.append(_esc(libro.periodo_label))
    body_left = [
        Paragraph(_esc(company), styles["company"]),
        Paragraph(" · ".join(chips), styles["badge"]) if chips else Spacer(1, 1),
    ]
    if addr:
        body_left.append(Paragraph(_esc(addr), styles["meta"]))
    if fiscal_bits:
        body_left.append(Paragraph(_esc("  ".join(fiscal_bits)), styles["meta"]))

    meta = [
        Paragraph("REGISTRO IVA", styles["doctype"]),
        Paragraph(f"Pag. {pagina}", styles["page"]),
    ]
    data = [[logo_cell, body_left, meta]]
    table = Table(data, colWidths=[28 * mm, usable - 28 * mm - 32 * mm, 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, BLUE),
            ]
        )
    )
    return table


def _header_row(acquisto: bool, styles: dict) -> list:
    headers = _col_headers(acquisto)
    out = []
    for i, h in enumerate(headers):
        # ultime 4 colonne importi a destra
        end = i >= len(headers) - 4
        out.append(Paragraph(_esc(h), styles["th_end"] if end else styles["th"]))
    return out


def _data_row(riga: LibroRegistroIvaRiga, styles: dict, acquisto: bool) -> list:
    cells = list(riga.cells or [])
    # Normalizza lunghezza
    n = 11 if acquisto else 10
    while len(cells) < n:
        cells.append(type(cells[0])() if cells else None)
    out = []
    for i, cell in enumerate(cells[:n]):
        text = _esc(getattr(cell, "text", "") or "")
        align_end = (getattr(cell, "align", "") == "end") or (i >= n - 4)
        # Ragione sociale / descrizione un filo più piccoli se lunghi
        if not align_end and len(text) > 42:
            style = styles["td_small"]
        else:
            style = styles["td_end"] if align_end else styles["td"]
        out.append(Paragraph(text, style))
    return out


def _row_bg(riga: LibroRegistroIvaRiga, index: int) -> colors.Color | None:
    cls = riga.row_class or ""
    if "comp-successiva" in cls:
        return COMP_SUCC
    if "comp-precedente" in cls:
        return COMP_PREC
    if index % 2 == 1:
        return ROW_ALT
    return None


def _build_grid(
    *,
    header: list,
    rows: list[list],
    widths: list[float],
    row_objs: Sequence[LibroRegistroIvaRiga] | None = None,
    footer: list | None = None,
) -> Table:
    data = [header] + rows
    if footer:
        data.append(footer)
    table = Table(data, colWidths=widths, repeatRows=0)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("BOX", (0, 0), (-1, -1), 0.7, INK),
    ]
    if row_objs:
        for i, riga in enumerate(row_objs):
            bg = _row_bg(riga, i)
            if bg is not None:
                style_cmds.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))
    if footer:
        last = len(data) - 1
        style_cmds.extend(
            [
                ("BACKGROUND", (0, last), (-1, last), BLUE_SOFT),
                ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
                ("TOPPADDING", (0, last), (-1, last), 2.5),
                ("BOTTOMPADDING", (0, last), (-1, last), 2.5),
            ]
        )
    table.setStyle(TableStyle(style_cmds))
    return table


def _riepilogo_table(
    *,
    styles: dict,
    font_bold: str,
    voci: list,
    totale_label: str,
    tot_imp: float,
    tot_iva_ded: float,
    tot_iva_inded: float,
    usable: float,
) -> Table:
    widths = [usable * 0.46, usable * 0.18, usable * 0.18, usable * 0.18]
    header = [
        Paragraph("Descrizione", styles["th"]),
        Paragraph("Impon.", styles["th_end"]),
        Paragraph("Iva Ded.", styles["th_end"]),
        Paragraph("Iva Inded.", styles["th_end"]),
    ]
    rows = []
    for v in voci:
        rows.append(
            [
                Paragraph(_esc(v.descrizione), styles["td"]),
                Paragraph(_money(v.imponibile), styles["td_end"]),
                Paragraph(_money(getattr(v, "iva_deducibile", 0.0) or v.iva), styles["td_end"]),
                Paragraph(_money(getattr(v, "iva_indeducibile", 0.0) or 0.0), styles["td_end"]),
            ]
        )
    footer = [
        Paragraph(f"<b>{_esc(totale_label)}</b>", styles["td"]),
        Paragraph(f"<b>{_money(tot_imp)}</b>", styles["td_end"]),
        Paragraph(f"<b>{_money(tot_iva_ded)}</b>", styles["td_end"]),
        Paragraph(f"<b>{_money(tot_iva_inded)}</b>", styles["td_end"]),
    ]
    return _build_grid(header=header, rows=rows, widths=widths, footer=footer)


def _flow_height(flowables: list, width: float) -> float:
    """Altezza reale di una lista di flowable (wrap con canvas fittizio)."""
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus.flowables import _listWrapOn

    canv = Canvas(io.BytesIO(), pagesize=A4)
    _w, h = _listWrapOn(flowables, width, canv)
    return float(h)


def _totals_footer_row(libro: LibroRegistroIvaDati, styles: dict, acquisto: bool) -> list:
    label_span = libro.label_colspan
    footer_cells: list = [""] * (11 if acquisto else 10)
    footer_cells[label_span - 1] = Paragraph("<b>Totali generali</b>", styles["td_end"])
    footer_cells[label_span] = Paragraph(
        f"<b>{_money(libro.totale_imponibile_stampa)}</b>", styles["td_end"]
    )
    footer_cells[label_span + 1] = ""
    footer_cells[label_span + 2] = Paragraph(
        f"<b>{_money(libro.totale_iva_stampa)}</b>", styles["td_end"]
    )
    footer_cells[label_span + 3] = Paragraph(
        f"<b>{_money(libro.totale_documento)}</b>", styles["td_end"]
    )
    return footer_cells


def _page_flowables(
    *,
    styles: dict,
    font_bold: str,
    azienda: dict,
    libro: LibroRegistroIvaDati,
    pagina: int,
    logo_url: str,
    usable: float,
    header: list,
    widths: list[float],
    acquisto: bool,
    chunk_rows: list[LibroRegistroIvaRiga],
    with_totals: bool,
) -> list:
    masthead = _masthead_table(
        styles=styles,
        font_bold=font_bold,
        azienda=azienda,
        libro=libro,
        pagina=pagina,
        logo_url=logo_url,
        usable=usable,
    )
    body_rows = [_data_row(r, styles, acquisto) for r in chunk_rows]
    footer = None
    rows_for_bg = chunk_rows
    if with_totals:
        footer = _totals_footer_row(libro, styles, acquisto)
        if not body_rows:
            n_cols = 11 if acquisto else 10
            empty = [""] * n_cols
            empty[0] = Paragraph("Nessuna registrazione nel periodo", styles["empty"])
            body_rows = [empty]
            rows_for_bg = []
    grid = _build_grid(
        header=header,
        rows=body_rows,
        widths=widths,
        row_objs=rows_for_bg,
        footer=footer,
    )
    # Impedisce a ReportLab di spezzare la tabella a metà (pagine fantasma).
    grid.allowSplitting = 0
    return [masthead, Spacer(1, 2.2 * mm), grid]


@dataclass(frozen=True)
class LibroPdfResult:
    """PDF generato + conteggio fogli reali (movimenti e riepilogo)."""

    data: bytes
    num_pages: int
    pagina_da: int
    ultima_pagina: int
    pagina_riepilogo: int | None
    pagine_movimenti: int


def build_libro_pdf(
    *,
    libro: LibroRegistroIvaDati,
    azienda_header: dict,
    logo_url: str = "",
    pagina_da: int = 1,
) -> LibroPdfResult:
    """Genera il PDF e conta i fogli effettivamente prodotti (incluso riepilogo)."""
    font, font_bold = _register_fonts()
    styles = _styles(font, font_bold)
    buffer = io.BytesIO()
    usable = PAGE_W - 2 * MARGIN
    frame_h = PAGE_H - 2 * MARGIN
    # Frame senza padding interno: altrimenti misura ≠ area utile (pagine fantasma).
    frame = Frame(
        MARGIN,
        MARGIN,
        usable,
        frame_h,
        leftPadding=0,
        bottomPadding=0,
        rightPadding=0,
        topPadding=0,
        id="normal",
    )
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Registro IVA — {libro.registro_label}",
        author="Eureka AI",
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])
    acquisto = bool(libro.mostra_competenza)
    widths = _col_widths(acquisto, usable)
    azienda = {
        "ragione_sociale": azienda_header.get("ragione_sociale") or "",
        "indirizzo": azienda_header.get("indirizzo") or "",
        "codice_fiscale": azienda_header.get("codice_fiscale") or "",
        "partita_iva": azienda_header.get("partita_iva") or "",
        "initials": "".join(
            p[0] for p in (azienda_header.get("ragione_sociale") or "E").split()[:3]
        ).upper(),
    }

    righe = list(libro.righe or [])
    pagina_da = max(1, int(pagina_da or 1))
    header = _header_row(acquisto, styles)

    def flow_for(pagina: int, chunk: list[LibroRegistroIvaRiga], with_totals: bool) -> list:
        return _page_flowables(
            styles=styles,
            font_bold=font_bold,
            azienda=azienda,
            libro=libro,
            pagina=pagina,
            logo_url=logo_url,
            usable=usable,
            header=header,
            widths=widths,
            acquisto=acquisto,
            chunk_rows=chunk,
            with_totals=with_totals,
        )

    # Cuscinetto anti-overflow (Paragraph multilinea / arrotondamenti Table).
    FIT_SLACK = 28  # punti (~10mm)

    def max_rows_fitting(start: int, *, with_totals: bool, pagina: int) -> int:
        """Quante righe da ``start`` entrano in un foglio senza overflow."""
        remaining = len(righe) - start
        if remaining <= 0:
            return 0
        lo, hi = 1, remaining
        best = 1
        limit = frame_h - FIT_SLACK
        while lo <= hi:
            mid = (lo + hi) // 2
            chunk = righe[start : start + mid]
            h = _flow_height(flow_for(pagina, chunk, with_totals), usable)
            if h <= limit:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        # Verifica finale + peel (righe con wrap alto)
        while best > 1:
            h = _flow_height(
                flow_for(pagina, righe[start : start + best], with_totals), usable
            )
            if h <= limit:
                break
            best -= 1
        return max(1, best)

    # Chunk pagine misurati (niente spezzatura ReportLab → niente fogli fantasma)
    chunks: list[tuple[int, list[LibroRegistroIvaRiga], bool]] = []
    i = 0
    page_num = pagina_da
    if not righe:
        chunks.append((page_num, [], True))
    else:
        while i < len(righe):
            remaining = len(righe) - i
            n_tot = max_rows_fitting(i, with_totals=True, pagina=page_num)
            if n_tot >= remaining:
                chunks.append((page_num, righe[i:], True))
                break
            n = max_rows_fitting(i, with_totals=False, pagina=page_num)
            # Non consumare tutte le righe senza totali: lascia coda per foglio finale.
            if n >= remaining and remaining > 1:
                n = remaining - 1
            n = max(1, min(n, remaining))
            chunks.append((page_num, righe[i : i + n], False))
            i += n
            page_num += 1
        if chunks and not chunks[-1][2] and i >= len(righe):
            n, c, _ = chunks[-1]
            chunks[-1] = (n, c, True)

    pagine_movimenti = max(1, len(chunks))
    story: list = []
    for idx, (pagina, chunk_rows, is_last) in enumerate(chunks):
        if idx:
            story.append(PageBreak())
        # Niente KeepTogether: con allowSplitting=0 sulla griglia e chunk misurato
        # il foglio non si spezza; KeepTogether in RL5 a volte gonfia l'altezza.
        story.extend(flow_for(pagina, chunk_rows, is_last))

    # Riepiloghi (possono occupare più di un foglio fisico se le tabelle sono lunghe)
    has_riepilogo = bool(libro.riepilogo or libro.mostra_riepilogo_competenza)
    pagina_riepilogo: int | None = None
    if has_riepilogo:
        last_data_page = chunks[-1][0] if chunks else pagina_da
        pagina_riepilogo = last_data_page + 1
        story.append(PageBreak())
        story.append(
            _masthead_table(
                styles=styles,
                font_bold=font_bold,
                azienda=azienda,
                libro=libro,
                pagina=pagina_riepilogo,
                logo_url=logo_url,
                usable=usable,
            )
        )
        story.append(Spacer(1, 3 * mm))

        if libro.mostra_riepilogo_competenza:
            story.append(
                Paragraph(
                    f"Riepilogo 1 — Registrazioni effettuate nel mese di {_esc(libro.mese_iva_label)}",
                    styles["title"],
                )
            )
            story.append(Paragraph(_esc(libro.registro_label), styles["badge"]))
            story.append(
                Paragraph(
                    "Movimenti materialmente registrati nel mese (per data di registrazione).",
                    styles["note"],
                )
            )
        else:
            title = "Riepilogo"
            if libro.periodo_label:
                title += f" : {_esc(libro.periodo_label)}"
            story.append(Paragraph(title, styles["title"]))
            story.append(Paragraph(_esc(libro.registro_label), styles["badge"]))
            story.append(Spacer(1, 1 * mm))

        story.append(
            _riepilogo_table(
                styles=styles,
                font_bold=font_bold,
                voci=libro.riepilogo,
                totale_label="TOTALE",
                tot_imp=libro.totale_imponibile,
                tot_iva_ded=libro.totale_iva_deducibile or libro.totale_iva,
                tot_iva_inded=libro.totale_iva_indeducibile,
                usable=usable,
            )
        )

        if libro.mostra_riepilogo_gia_conteggiate and libro.riepilogo_gia_conteggiate:
            story.append(Spacer(1, 4 * mm))
            story.append(
                Paragraph(
                    f"Da detrarre — già conteggiate in {_esc(libro.mese_precedente_label)}",
                    styles["title"],
                )
            )
            story.append(
                _riepilogo_table(
                    styles=styles,
                    font_bold=font_bold,
                    voci=libro.riepilogo_gia_conteggiate,
                    totale_label="TOTALE DA DETRARRE",
                    tot_imp=libro.totale_imponibile_gia_conteggiate,
                    tot_iva_ded=libro.totale_iva_deducibile_gia_conteggiate,
                    tot_iva_inded=libro.totale_iva_indeducibile_gia_conteggiate,
                    usable=usable,
                )
            )

        if libro.mostra_riepilogo_2 and libro.riepilogo_competenza:
            story.append(Spacer(1, 4 * mm))
            story.append(
                Paragraph(
                    f"Riepilogo 2 — Registrati in {_esc(libro.mese_successivo_label)} "
                    f"con competenza {_esc(libro.mese_iva_label)}",
                    styles["title"],
                )
            )
            story.append(
                _riepilogo_table(
                    styles=styles,
                    font_bold=font_bold,
                    voci=libro.riepilogo_competenza,
                    totale_label="TOTALE",
                    tot_imp=libro.totale_imponibile_competenza,
                    tot_iva_ded=libro.totale_iva_deducibile_competenza,
                    tot_iva_inded=libro.totale_iva_indeducibile_competenza,
                    usable=usable,
                )
            )

        if libro.mostra_riepilogo_competenza and libro.riepilogo_totale_competenza:
            story.append(Spacer(1, 4 * mm))
            story.append(
                Paragraph(
                    f"Totale competenza {_esc(libro.mese_iva_label)}",
                    styles["title"],
                )
            )
            story.append(
                _riepilogo_table(
                    styles=styles,
                    font_bold=font_bold,
                    voci=libro.riepilogo_totale_competenza,
                    totale_label="TOTALE COMPETENZA",
                    tot_imp=libro.totale_imponibile_competenza_mese,
                    tot_iva_ded=libro.totale_iva_deducibile_competenza_mese,
                    tot_iva_inded=libro.totale_iva_indeducibile_competenza_mese,
                    usable=usable,
                )
            )

    doc.build(story)
    num_pages = max(1, int(getattr(doc, "page", 0) or 0))
    if num_pages < 1:
        num_pages = 1
    ultima_pagina = pagina_da + num_pages - 1
    return LibroPdfResult(
        data=buffer.getvalue(),
        num_pages=num_pages,
        pagina_da=pagina_da,
        ultima_pagina=ultima_pagina,
        pagina_riepilogo=pagina_riepilogo,
        pagine_movimenti=pagine_movimenti,
    )


def build_libro_pdf_bytes(
    *,
    libro: LibroRegistroIvaDati,
    azienda_header: dict,
    logo_url: str = "",
    pagina_da: int = 1,
) -> bytes:
    """Genera il PDF binario del libro registro."""
    return build_libro_pdf(
        libro=libro,
        azienda_header=azienda_header,
        logo_url=logo_url,
        pagina_da=pagina_da,
    ).data
