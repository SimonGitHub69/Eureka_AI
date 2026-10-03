"""Stampa Partitario clienti / fornitori / sottoconti PDC."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Literal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View

from apps.anagrafiche.models import Cliente, Fornitore, get_by_codice
from apps.anagrafiche.partitario import Kind, PartitarioResult, build_partitario, default_periodo
from apps.articoli.lookups import resolve_descrizione
from apps.aziende.configurazione import resolve_print_azienda_context
from apps.core.print_list import print_preview_requested
from apps.pdc.hierarchy import pdc_contropartite_qs, pdc_is_contropartita
from apps.pdc.models import PianoConti
from apps.registri_iva.libro_registro import _resolve_azienda_header

LOOKUP_TIPO_BY_KIND = {
    "C": "cliente",
    "F": "fornitore",
    "P": "pdc",
}

KIND_CHOICES: tuple[tuple[str, str], ...] = (
    ("C", "Cliente"),
    ("F", "Fornitore"),
    ("P", "Sottoconto"),
)

KIND_LABELS = dict(KIND_CHOICES)

SaldoOp = Literal["any", "gt", "gte", "lt", "lte", "ne", "eq"]

SALDO_OP_CHOICES: tuple[tuple[str, str], ...] = (
    ("any", "Qualsiasi saldo"),
    ("ne", "Diverso da"),
    ("gt", "Maggiore di"),
    ("gte", "Maggiore o uguale a"),
    ("lt", "Minore di"),
    ("lte", "Minore o uguale a"),
    ("eq", "Uguale a"),
)

SALDO_OP_LABELS = dict(SALDO_OP_CHOICES)

# Limite di sicurezza per stampa massiva (evita timeout).
MAX_PARTITARI_STAMPA = 250


@dataclass
class PartitarioSubjectInfo:
    codice: str
    label: str
    nome: str
    kind: Kind
    kind_label: str
    error: str = ""


@dataclass
class PartitarioPrintBlock:
    subject: PartitarioSubjectInfo
    partitario: PartitarioResult
    movimenti_count: int = 0


@dataclass
class PartitarioPrintBundle:
    blocks: list[PartitarioPrintBlock] = field(default_factory=list)
    truncated: bool = False
    scanned: int = 0
    matched: int = 0


def parse_importo_it(raw: str | None) -> float | None:
    """Accetta 1234,56 / 1.234,56 / 1234.56. Vuoto → None."""
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace(" ", "").replace("€", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def saldo_filter_for_request(saldo_op: str, *, tutti: bool) -> str:
    """Il filtro sul saldo sceglie i soggetti solo in stampa massiva («Tutti»).

    Su un codice singolo il partitario va stampato anche a saldo zero: il default
    «diverso da 0» altrimenti risponde «nessun partitario» per i clienti saldati.
    """
    if not tutti:
        return "any"
    return saldo_op if saldo_op in SALDO_OP_LABELS else "ne"


def saldo_matches(saldo: float, op: str, soglia: float) -> bool:
    if op == "any":
        return True
    if op == "gt":
        return saldo > soglia
    if op == "gte":
        return saldo >= soglia
    if op == "lt":
        return saldo < soglia
    if op == "lte":
        return saldo <= soglia
    if op == "ne":
        return abs(saldo - soglia) > 1e-9
    if op == "eq":
        return abs(saldo - soglia) <= 1e-9
    return True


def list_partitario_candidates(kind: Kind) -> list[PartitarioSubjectInfo]:
    """Elenco soggetti stampabili (tutti i clienti / fornitori / sottoconti)."""
    kind_label = KIND_LABELS[kind]
    out: list[PartitarioSubjectInfo] = []
    if kind == "C":
        for row in Cliente.objects.order_by("codice").only(
            "codice", "ragione_sociale1", "ragione_sociale2"
        ):
            nome = row.ragione_sociale or row.codice
            out.append(
                PartitarioSubjectInfo(
                    codice=row.codice,
                    label=row.codice,
                    nome=nome,
                    kind="C",
                    kind_label=kind_label,
                )
            )
        return out
    if kind == "F":
        for row in Fornitore.objects.order_by("codice").only(
            "codice", "ragione_sociale1", "ragione_sociale2"
        ):
            nome = row.ragione_sociale or row.codice
            out.append(
                PartitarioSubjectInfo(
                    codice=row.codice,
                    label=row.codice,
                    nome=nome,
                    kind="F",
                    kind_label=kind_label,
                )
            )
        return out
    for row in pdc_contropartite_qs().order_by("codice").only("codice", "descrizione"):
        if not pdc_is_contropartita(row.codice):
            continue
        nome = (row.descrizione or row.codice).strip()
        out.append(
            PartitarioSubjectInfo(
                codice=row.codice,
                label=row.codice,
                nome=nome,
                kind="P",
                kind_label=kind_label,
            )
        )
    return out


def resolve_partitario_subject(kind: str, codice: str) -> PartitarioSubjectInfo:
    """Risolve soggetto per stampa; error valorizzato se non valido."""
    kind_norm = (kind or "C").strip().upper()
    if kind_norm not in KIND_LABELS:
        kind_norm = "C"
    codice_norm = (codice or "").strip()
    kind_label = KIND_LABELS[kind_norm]
    if not codice_norm:
        return PartitarioSubjectInfo(
            codice="",
            label="",
            nome="",
            kind=kind_norm,  # type: ignore[arg-type]
            kind_label=kind_label,
            error="Inserisci il codice del soggetto (oppure attiva «Tutti»).",
        )

    if kind_norm == "C":
        subject = get_by_codice(Cliente, codice_norm)
        if subject is None:
            return PartitarioSubjectInfo(
                codice=codice_norm,
                label="",
                nome="",
                kind="C",
                kind_label=kind_label,
                error=f"Cliente «{codice_norm}» non trovato.",
            )
        nome = subject.ragione_sociale or subject.codice
        return PartitarioSubjectInfo(
            codice=subject.codice,
            label=subject.codice,
            nome=nome,
            kind="C",
            kind_label=kind_label,
        )

    if kind_norm == "F":
        subject = get_by_codice(Fornitore, codice_norm)
        if subject is None:
            return PartitarioSubjectInfo(
                codice=codice_norm,
                label="",
                nome="",
                kind="F",
                kind_label=kind_label,
                error=f"Fornitore «{codice_norm}» non trovato.",
            )
        nome = subject.ragione_sociale or subject.codice
        return PartitarioSubjectInfo(
            codice=subject.codice,
            label=subject.codice,
            nome=nome,
            kind="F",
            kind_label=kind_label,
        )

    try:
        conto = PianoConti.objects.get(pk=codice_norm)
    except PianoConti.DoesNotExist:
        return PartitarioSubjectInfo(
            codice=codice_norm,
            label="",
            nome="",
            kind="P",
            kind_label=kind_label,
            error=f"Sottoconto «{codice_norm}» non trovato.",
        )
    if not pdc_is_contropartita(conto.codice):
        return PartitarioSubjectInfo(
            codice=conto.codice,
            label=conto.codice,
            nome=(conto.descrizione or conto.codice),
            kind="P",
            kind_label=kind_label,
            error="Il partitario è disponibile solo per i sottoconti.",
        )
    return PartitarioSubjectInfo(
        codice=conto.codice,
        label=conto.codice,
        nome=(conto.descrizione or conto.codice),
        kind="P",
        kind_label=kind_label,
    )


def build_print_bundle(
    *,
    kind: Kind,
    codice: str,
    tutti: bool,
    data_da,
    data_a,
    saldo_op: str,
    saldo_soglia: float,
) -> tuple[PartitarioPrintBundle, str]:
    """
    Costruisce uno o più partitari filtrati per saldo finale del periodo.
    Ritorna (bundle, error).
    """
    op = saldo_op if saldo_op in SALDO_OP_LABELS else "any"
    bundle = PartitarioPrintBundle()

    if tutti:
        candidates = list_partitario_candidates(kind)
    else:
        subject = resolve_partitario_subject(kind, codice)
        if subject.error:
            return bundle, subject.error
        candidates = [subject]

    for subject in candidates:
        bundle.scanned += 1
        partitario = build_partitario(
            subject.codice,
            kind=subject.kind,
            data_da=data_da,
            data_a=data_a,
        )
        if not saldo_matches(partitario.saldo_finale, op, saldo_soglia):
            continue
        movimenti = sum(
            1 for r in partitario.righe if not r.is_saldo_precedente and not r.is_totale
        )
        # In stampa massiva salta soggetti senza movimenti se il filtro saldo è "any"
        # (evita centinaia di fogli vuoti); con filtro saldo il match è già selettivo.
        if tutti and op == "any" and movimenti == 0 and abs(partitario.saldo_finale) < 1e-9:
            continue
        bundle.matched += 1
        if len(bundle.blocks) >= MAX_PARTITARI_STAMPA:
            bundle.truncated = True
            break
        bundle.blocks.append(
            PartitarioPrintBlock(
                subject=subject,
                partitario=partitario,
                movimenti_count=movimenti,
            )
        )

    if tutti and not bundle.blocks and not bundle.truncated:
        op_label = SALDO_OP_LABELS.get(op, op)
        return bundle, (
            f"Nessun {KIND_LABELS[kind].lower()} con saldo {op_label.lower()} "
            f"{saldo_soglia:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            + " nel periodo."
        )
    return bundle, ""


class PartitarioPrintView(LoginRequiredMixin, View):
    """Stampa partitario (mastrino) clienti / fornitori / sottoconti."""

    template_name = "anagrafiche/partitario_print.html"

    def get(self, request):
        preview_ready = print_preview_requested(request)
        default_da, default_a = default_periodo()
        kind = (request.GET.get("kind") or "C").strip().upper()
        if kind not in KIND_LABELS:
            kind = "C"
        codice = (request.GET.get("codice") or "").strip()
        tutti = (request.GET.get("tutti") or "").strip() in ("1", "true", "on", "yes")
        riepilogo = (request.GET.get("riepilogo") or "").strip() in ("1", "true", "on", "yes")
        saldo_op = (request.GET.get("saldo_op") or "ne").strip().lower()
        if saldo_op not in SALDO_OP_LABELS:
            saldo_op = "ne"
        saldo_soglia_raw = (request.GET.get("saldo_soglia") or "0").strip()
        saldo_soglia = parse_importo_it(saldo_soglia_raw)
        if saldo_soglia is None:
            saldo_soglia = 0.0
            saldo_soglia_raw = "0"

        data_da = parse_date((request.GET.get("data_da") or "").strip()) or default_da
        data_a = parse_date((request.GET.get("data_a") or "").strip()) or default_a
        if data_da > data_a:
            data_da, data_a = data_a, data_da

        error = ""
        bundle = PartitarioPrintBundle()
        subject = resolve_partitario_subject(kind, codice) if codice else PartitarioSubjectInfo(
            codice="",
            label="",
            nome="",
            kind=kind,  # type: ignore[arg-type]
            kind_label=KIND_LABELS[kind],
        )

        if preview_ready:
            if not tutti and not codice:
                error = "Inserisci un codice oppure attiva «Tutti»."
                preview_ready = False
            else:
                bundle, err = build_print_bundle(
                    kind=kind,  # type: ignore[arg-type]
                    codice=codice,
                    tutti=tutti,
                    data_da=data_da,
                    data_a=data_a,
                    saldo_op=saldo_filter_for_request(saldo_op, tutti=tutti),
                    saldo_soglia=saldo_soglia,
                )
                if err:
                    error = err
                    preview_ready = False
                elif not bundle.blocks:
                    error = "Nessun partitario da stampare con i filtri selezionati."
                    preview_ready = False
                else:
                    subject = bundle.blocks[0].subject

        movimenti_count = sum(b.movimenti_count for b in bundle.blocks)
        tot_dare = sum(b.partitario.totale_dare for b in bundle.blocks)
        tot_avere = sum(b.partitario.totale_avere for b in bundle.blocks)
        tot_saldo = sum(b.partitario.saldo_finale for b in bundle.blocks)
        periodo_label = f"{data_da.strftime('%d/%m/%Y')} – {data_a.strftime('%d/%m/%Y')}"
        filtro_saldo_label = ""
        if tutti and saldo_op != "any":
            filtro_saldo_label = (
                f"Saldo {SALDO_OP_LABELS.get(saldo_op, saldo_op).lower()} "
                f"{saldo_soglia:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
        masthead_title = f"Partitario {KIND_LABELS[kind]}"
        if tutti:
            masthead_title += " · Tutti"
        if riepilogo:
            masthead_title += " · Riepilogo saldi"
        partitario_masthead = SimpleNamespace(
            registro_label=masthead_title,
            anno=data_da.year,
            periodo_label=periodo_label,
            doctype="Partitario",
        )
        lookup_tipo = LOOKUP_TIPO_BY_KIND.get(kind, "cliente")
        codice_label = ""
        if codice and not tutti:
            codice_label = (subject.nome if subject and subject.nome else "") or (
                resolve_descrizione(lookup_tipo, codice) or ""
            )
        response = render(
            request,
            self.template_name,
            {
                "print_preview_ready": preview_ready,
                "print_date": timezone.localdate(),
                "kind": kind,
                "kind_choices": KIND_CHOICES,
                "lookup_tipo": lookup_tipo,
                "lookup_url": reverse("articoli:lookup_codice"),
                "codice": codice,
                "codice_label": codice_label,
                "tutti": tutti,
                "riepilogo": riepilogo,
                "saldo_op": saldo_op,
                "saldo_op_choices": SALDO_OP_CHOICES,
                "saldo_soglia": saldo_soglia_raw,
                "filtro_saldo_label": filtro_saldo_label,
                "subject": subject,
                "data_da": data_da.isoformat(),
                "data_a": data_a.isoformat(),
                "data_da_default": default_da.isoformat(),
                "data_a_default": default_a.isoformat(),
                "periodo_label": periodo_label,
                "bundle": bundle,
                "partitario_masthead": partitario_masthead,
                "movimenti_count": movimenti_count,
                "soggetti_count": len(bundle.blocks),
                "riepilogo_tot_dare": tot_dare,
                "riepilogo_tot_avere": tot_avere,
                "riepilogo_tot_saldo": tot_saldo,
                "error": error,
                "pagina_da": 1,
                "max_partitari": MAX_PARTITARI_STAMPA,
                "azienda_header": _resolve_azienda_header(),
                **resolve_print_azienda_context(branding="liste"),
            },
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response
