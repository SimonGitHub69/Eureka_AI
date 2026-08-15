"""
Castelletto IVA: riepilogo merce / sconto / netto / IVA per aliquota.

Percentuale IVA: decodificata da apps.aliquote.models.Aliquota
(tabella 4D AliquoteIva → DB ``aliquote``, campo ``percentuale`` / property
``aliquota_sdi``). Il codice riga (``iva``) è solo la chiave di lookup su
``Aliquota.codice`` — non si inventa la % dal solo testo del codice se la
riga esiste in anagrafica.

Label «Tipo Aliquota Iva»: ``Aliquota.descrizione`` (es. codice ``VA22``);
se vuota, il codice stesso. Le righe SPESE aggiungono il suffisso « SPESE».

Per ogni riga documento:
  merce (imponibile lordo) = quantità × prezzo_unitario
  sconto importo           = merce × (1 − Π(1 − pᵢ/100))
    (campo riga ``sconto``: % singola o composta a cascata, es. ``10+5``
     → fattore 0,9×0,95 = 0,855 → sconto = merce × 0,145; standard ERP/4D IT)
  netto (imponibile)       = merce − sconto
  IVA                      = netto × Aliquota.percentuale / 100

Aggregato per aliquota (+ riga SPESE da spese testata; aliquota da
Parametri contabili se configurata, altrimenti prima riga merce):
  Tot. Merce / Sconto / Netto / IVA / Imponibile+IVA ; Totale Doc = Σ Netto + Σ IVA

Campi persistiti su TestaDocumento: imponibile (= Σ Netto), totale (= Totale Documento).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, Sequence

TWOPLACES = Decimal("0.01")
THREEPLACES = Decimal("0.001")

# Fallback se anagrafica aliquote assente (stessi codici tipici di fatturapa)
_IVA_FALLBACK: dict[str, Decimal] = {
    "22": Decimal("22"),
    "22A": Decimal("22"),
    "22RC": Decimal("22"),
    "22SP": Decimal("22"),
    "22PM": Decimal("22"),
    "22PP": Decimal("22"),
    "22XX": Decimal("22"),
    "21": Decimal("21"),
    "20": Decimal("20"),
    "15": Decimal("15"),
    "26": Decimal("26"),
    "10": Decimal("10"),
    "5": Decimal("5"),
    "4": Decimal("4"),
    "0": Decimal("0"),
}


def _txt(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _money(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    try:
        raw = str(value).strip().replace(",", ".")
        return Decimal(raw).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _prezzo_unitario(value: Any) -> Decimal:
    """Prezzo unitario riga: 3 decimali (imponibile/totale restano a 2)."""
    if value in (None, ""):
        return Decimal("0.000")
    try:
        raw = str(value).strip().replace(",", ".")
        return Decimal(raw).quantize(THREEPLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.000")


def _qty(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        raw = str(value).strip().replace(",", ".")
        return Decimal(raw)
    except Exception:
        return Decimal("0")


def parse_sconto_parts(raw: Any) -> list[Decimal]:
    """Estrae tutte le % dal testo riga (separatori ``+`` / ``-`` / spazi / ``%``).

    Es. ``10``, ``10%``, ``10+5``, ``10-5`` → [10], [10], [10, 5], [10, 5].
    """
    text = _txt(raw).replace(",", ".")
    if not text:
        return []
    parts: list[Decimal] = []
    for m in re.finditer(r"\d+(?:\.\d+)?", text):
        try:
            parts.append(Decimal(m.group(0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP))
        except Exception:
            continue
    return parts


def sconto_residuo_factor(parts: Sequence[Decimal]) -> Decimal:
    """Fattore residuo dopo sconti a cascata: Π(1 − p/100)."""
    factor = Decimal("1")
    for p in parts:
        if p <= 0:
            continue
        factor *= Decimal("1") - (p / Decimal("100"))
    return factor


def parse_sconto_percent(raw: Any) -> Decimal:
    """% sconto equivalente (cascata ERP IT).

    Es. ``10`` → 10; ``10+5`` → 14,50 (= 100 × (1 − 0,9 × 0,95)).
    """
    parts = parse_sconto_parts(raw)
    if not parts:
        return Decimal("0")
    factor = sconto_residuo_factor(parts)
    equiv = (Decimal("1") - factor) * Decimal("100")
    return equiv.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_pct(pct: Decimal) -> str:
    q = pct.quantize(TWOPLACES, rounding=ROUND_HALF_UP).normalize()
    text = format(q, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def format_euro(value: Decimal | float | int | None) -> str:
    """Formato italiano 1.234,56."""
    amount = _money(value)
    formatted = f"{amount:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass(frozen=True)
class AliquotaInfo:
    codice: str
    percentuale: Decimal
    descrizione: str = ""

    @property
    def label(self) -> str:
        """Tipo Aliquota Iva: Aliquota.descrizione, altrimenti il codice."""
        desc = _txt(self.descrizione)
        if desc:
            return desc
        return _txt(self.codice) or f"IVA {format_pct(self.percentuale)}%"

    @property
    def label_spese(self) -> str:
        base = self.label
        if re.search(r"\bSPESE\b", base, re.IGNORECASE):
            return base
        return f"{base} SPESE"


@dataclass
class CastellettoRiga:
    codice_iva: str
    percentuale: Decimal
    label: str
    is_spese: bool
    merce: Decimal = Decimal("0.00")
    sconto: Decimal = Decimal("0.00")
    netto: Decimal = Decimal("0.00")
    iva: Decimal = Decimal("0.00")

    @property
    def imponibile_iva(self) -> Decimal:
        """Imponibile (netto) + IVA della riga."""
        return (self.netto + self.iva).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    def finalize(self) -> None:
        self.merce = self.merce.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        self.sconto = self.sconto.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        self.netto = (self.merce - self.sconto).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        self.iva = (self.netto * self.percentuale / Decimal("100")).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "codice_iva": self.codice_iva,
            "percentuale": float(self.percentuale),
            "label": self.label,
            "is_spese": self.is_spese,
            "merce": float(self.merce),
            "sconto": float(self.sconto),
            "netto": float(self.netto),
            "iva": float(self.iva),
            "imponibile_iva": float(self.imponibile_iva),
            "merce_fmt": format_euro(self.merce),
            "sconto_fmt": format_euro(self.sconto),
            "netto_fmt": format_euro(self.netto),
            "iva_fmt": format_euro(self.iva),
            "imponibile_iva_fmt": format_euro(self.imponibile_iva),
        }


@dataclass
class CastellettoResult:
    righe: list[CastellettoRiga] = field(default_factory=list)
    totale_merce: Decimal = Decimal("0.00")
    totale_sconto: Decimal = Decimal("0.00")
    totale_netto: Decimal = Decimal("0.00")
    totale_iva: Decimal = Decimal("0.00")
    totale_documento: Decimal = Decimal("0.00")
    totale_peso: Decimal | None = None
    totale_quantita: Decimal = Decimal("0.00")

    def as_dict(self) -> dict[str, Any]:
        return {
            "righe": [r.as_dict() for r in self.righe],
            "totale_merce": float(self.totale_merce),
            "totale_sconto": float(self.totale_sconto),
            "totale_netto": float(self.totale_netto),
            "totale_iva": float(self.totale_iva),
            "totale_documento": float(self.totale_documento),
            "totale_peso": (
                float(self.totale_peso) if self.totale_peso is not None else None
            ),
            "totale_quantita": float(self.totale_quantita),
            "totale_merce_fmt": format_euro(self.totale_merce),
            "totale_sconto_fmt": format_euro(self.totale_sconto),
            "totale_netto_fmt": format_euro(self.totale_netto),
            "totale_iva_fmt": format_euro(self.totale_iva),
            "totale_documento_fmt": format_euro(self.totale_documento),
            "totale_peso_fmt": (
                format_euro(self.totale_peso) if self.totale_peso is not None else ""
            ),
            "totale_quantita_fmt": format_euro(self.totale_quantita),
        }


def _info_from_aliquota_row(row: Any, *, fallback_codice: str = "") -> AliquotaInfo:
    """Costruisce AliquotaInfo da un record AliquoteIva (campo Percentuale)."""
    return AliquotaInfo(
        codice=_txt(getattr(row, "codice", None)) or fallback_codice,
        percentuale=row.aliquota_sdi,  # normalizza Aliquota.percentuale
        descrizione=_txt(getattr(row, "descrizione", None)),
    )


def resolve_aliquota(codice: str | None, cache: dict[str, AliquotaInfo] | None = None) -> AliquotaInfo:
    """
    Decodifica la % IVA dal codice riga.

    Ordine: cache → tabella ``aliquote`` (Aliquota.percentuale / aliquota_sdi)
    → fallback noti / parsing numerico del codice (solo se anagrafica assente).
    """
    code = _txt(codice) or "22"
    key = code.upper()
    if cache is not None and key in cache:
        return cache[key]

    info: AliquotaInfo | None = None
    try:
        from apps.aliquote.models import Aliquota

        row = (
            Aliquota.objects.filter(codice__iexact=code)
            .only("codice", "percentuale", "descrizione")
            .first()
        )
        if row is not None:
            info = _info_from_aliquota_row(row, fallback_codice=code)
    except Exception:
        info = None

    if info is None:
        if key in _IVA_FALLBACK:
            pct = _IVA_FALLBACK[key]
        else:
            m = re.match(r"^(\d{1,2}(?:[.,]\d+)?)", key)
            if m:
                pct = Decimal(m.group(1).replace(",", ".")).quantize(
                    TWOPLACES, rounding=ROUND_HALF_UP
                )
            else:
                pct = Decimal("0")
        info = AliquotaInfo(codice=code, percentuale=pct)

    if cache is not None:
        cache[key] = info
    return info


def _line_amounts(
    *,
    quantita: Any,
    prezzo_unitario: Any,
    sconto: Any,
) -> tuple[Decimal, Decimal, Decimal]:
    """Ritorna (merce, sconto_importo, netto) per una riga documento."""
    from apps.documenti.sconto import resolve_sconto_percentuale

    qty = _qty(quantita)
    prezzo = _prezzo_unitario(prezzo_unitario)
    if qty == 0 and prezzo == 0:
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    if qty == 0:
        qty = Decimal("1")
    merce = (qty * prezzo).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    # Codice tabella Sconti (es. 50A) → formula % (50+10); non modifica la riga.
    parts = parse_sconto_parts(resolve_sconto_percentuale(sconto))
    sconto_imp = Decimal("0.00")
    if parts:
        factor = sconto_residuo_factor(parts)
        sconto_imp = (merce * (Decimal("1") - factor)).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )
    netto = (merce - sconto_imp).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return merce, sconto_imp, netto


def _spese_total(spese: Mapping[str, Any] | None) -> Decimal:
    if not spese:
        return Decimal("0.00")
    keys = (
        "spese_imballo",
        "spese_trasporto",
        "spese_incasso",
        "spese_varie",
        "spese_bolli",
        "spese_e15",
    )
    total = Decimal("0.00")
    for key in keys:
        total += _money(spese.get(key))
    return total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calcola_castelletto(
    righe: Iterable[Any],
    *,
    spese: Mapping[str, Any] | None = None,
    include_spese_zero_row: bool = True,
    peso_by_codice: Mapping[str, float | Decimal] | None = None,
    aliquote_cache: dict[str, AliquotaInfo] | None = None,
    aliquota_iva_spese: str | None = None,
    header_sconto: str | None = None,
) -> CastellettoResult:
    """
    Calcola il castelletto da oggetti riga (model o dict-like) e spese testata.

    Ogni riga deve esporre quantita, prezzo_unitario, sconto, iva (attr o key).
    ``iva`` = codice Aliquota (AliquoteIva.Codice); la % viene da Aliquota.percentuale.

    ``aliquote_cache``: mappa opzionale codice.upper() → AliquotaInfo (test / preload).
    ``aliquota_iva_spese``: codice aliquota per la riga SPESE (Parametri contabili);
    se vuoto, si usa l'aliquota della prima riga merce.
    ``header_sconto``: formula/% testata (da tabella Sconti); in cascata con lo
    sconto riga se entrambi valorizzati (non viene scritta sulle righe).
    """
    from apps.documenti.sconto import effective_sconto_formula

    cache: dict[str, AliquotaInfo] = dict(aliquote_cache or {})
    groups: dict[tuple[str, bool], CastellettoRiga] = {}
    order: list[tuple[str, bool]] = []
    default_iva_code = "22"
    first_iva_seen = False
    peso_totale = Decimal("0.00")
    peso_any = False
    quantita_totale = Decimal("0.00")

    def _get(obj: Any, name: str) -> Any:
        if isinstance(obj, Mapping):
            return obj.get(name)
        return getattr(obj, name, None)

    for riga in righe:
        codice_iva = _txt(_get(riga, "iva")) or "22"
        if not first_iva_seen:
            default_iva_code = codice_iva
            first_iva_seen = True

        # merce = qta × prezzo_unitario; sconto% (Sconti / testata) → netto imponibile
        merce, sconto_imp, _netto = _line_amounts(
            quantita=_get(riga, "quantita"),
            prezzo_unitario=_get(riga, "prezzo_unitario"),
            sconto=effective_sconto_formula(
                _get(riga, "sconto"),
                header_sconto=header_sconto,
            ),
        )
        if merce == 0 and sconto_imp == 0 and not _txt(_get(riga, "codice")) and not _txt(
            _get(riga, "descrizione")
        ):
            # Riga vuota
            continue

        quantita_totale += _qty(_get(riga, "quantita"))

        aliq = resolve_aliquota(codice_iva, cache)
        key = (aliq.codice.upper(), False)
        if key not in groups:
            groups[key] = CastellettoRiga(
                codice_iva=aliq.codice,
                percentuale=aliq.percentuale,
                label=aliq.label,
                is_spese=False,
            )
            order.append(key)
        groups[key].merce += merce
        groups[key].sconto += sconto_imp

        if peso_by_codice is not None:
            codice_art = _txt(_get(riga, "codice"))
            if codice_art:
                w = peso_by_codice.get(codice_art) or peso_by_codice.get(codice_art.upper())
                if w is not None:
                    qty = _qty(_get(riga, "quantita"))
                    if qty == 0:
                        qty = Decimal("1")
                    peso_totale += qty * Decimal(str(w))
                    peso_any = True

    spese_tot = _spese_total(spese)
    if spese_tot > 0 or (include_spese_zero_row and order):
        spese_iva_code = _txt(aliquota_iva_spese) or default_iva_code
        aliq = resolve_aliquota(spese_iva_code, cache)
        key = (aliq.codice.upper(), True)
        if key not in groups:
            groups[key] = CastellettoRiga(
                codice_iva=aliq.codice,
                percentuale=aliq.percentuale,
                label=aliq.label_spese,
                is_spese=True,
            )
            # SPESE subito dopo il gruppo merce stessa aliquota, altrimenti in coda
            merce_key = (aliq.codice.upper(), False)
            if merce_key in order:
                idx = order.index(merce_key) + 1
                order.insert(idx, key)
            else:
                order.append(key)
        groups[key].merce += spese_tot

    result_rows: list[CastellettoRiga] = []
    totale_merce = Decimal("0.00")
    totale_sconto = Decimal("0.00")
    totale_netto = Decimal("0.00")
    totale_iva = Decimal("0.00")

    for key in order:
        row = groups[key]
        row.finalize()
        result_rows.append(row)
        totale_merce += row.merce
        totale_sconto += row.sconto
        totale_netto += row.netto
        totale_iva += row.iva

    totale_merce = totale_merce.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    totale_sconto = totale_sconto.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    totale_netto = totale_netto.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    totale_iva = totale_iva.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    totale_documento = (totale_netto + totale_iva).quantize(
        TWOPLACES, rounding=ROUND_HALF_UP
    )

    return CastellettoResult(
        righe=result_rows,
        totale_merce=totale_merce,
        totale_sconto=totale_sconto,
        totale_netto=totale_netto,
        totale_iva=totale_iva,
        totale_documento=totale_documento,
        totale_peso=(
            peso_totale.quantize(TWOPLACES, rounding=ROUND_HALF_UP) if peso_any else None
        ),
        totale_quantita=quantita_totale.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
    )


def get_aliquota_iva_spese() -> str:
    """Codice aliquota IVA spese da Parametri contabili (vuoto = fallback prima riga)."""
    try:
        from apps.core.models import ParametriContabili

        return ParametriContabili.get_solo().aliquota_iva_spese_codice()
    except Exception:
        return ""


def calcola_castelletto_documento(documento: Any, *, with_peso: bool = False) -> CastellettoResult:
    """Calcola dal model TestaDocumento (+ related righe)."""
    from apps.documenti.sconto import header_sconto_from_documento

    righe = list(documento.righe.all().order_by("numero_riga", "id_4d"))
    if getattr(documento, "add_spese", False):
        spese = {
            "spese_imballo": getattr(documento, "spese_imballo", None),
            "spese_trasporto": getattr(documento, "spese_trasporto", None),
            "spese_incasso": getattr(documento, "spese_incasso", None),
            "spese_varie": getattr(documento, "spese_varie", None),
            "spese_bolli": getattr(documento, "spese_bolli", None),
            "spese_e15": getattr(documento, "spese_e15", None),
        }
    else:
        spese = None
    peso_map = None
    if with_peso:
        peso_map = _peso_map_for_codici(
            [_txt(getattr(r, "codice", None)) for r in righe if _txt(getattr(r, "codice", None))]
        )
    return calcola_castelletto(
        righe,
        spese=spese,
        peso_by_codice=peso_map,
        aliquota_iva_spese=get_aliquota_iva_spese(),
        header_sconto=header_sconto_from_documento(documento),
    )


def apply_castelletto_to_testa(documento: Any, result: CastellettoResult | None = None) -> CastellettoResult:
    """Aggiorna imponibile/totale sulla testata (in memoria; caller fa save)."""
    if result is None:
        result = calcola_castelletto_documento(documento)
    documento.imponibile = float(result.totale_netto)
    documento.totale = float(result.totale_documento)
    return result


def _peso_map_for_codici(codici: Sequence[str]) -> dict[str, float]:
    codes = [c for c in {_txt(c) for c in codici} if c]
    if not codes:
        return {}
    try:
        from apps.articoli.models import Articolo

        qs = Articolo.objects.filter(codice__in=codes).only("codice", "peso_netto")
        out: dict[str, float] = {}
        for art in qs:
            if art.peso_netto is not None:
                out[_txt(art.codice)] = float(art.peso_netto)
        return out
    except Exception:
        return {}


def calcola_totale_peso(righe: Iterable[Any]) -> Decimal:
    """Σ (qta × peso_netto articolo) per codice riga."""
    rows = list(righe)
    codes = []
    for r in rows:
        if isinstance(r, Mapping):
            c = _txt(r.get("codice"))
        else:
            c = _txt(getattr(r, "codice", None))
        if c:
            codes.append(c)
    peso_map = _peso_map_for_codici(codes)
    result = calcola_castelletto(rows, spese=None, include_spese_zero_row=False, peso_by_codice=peso_map)
    return result.totale_peso if result.totale_peso is not None else Decimal("0.00")


def aliquote_map_for_js() -> dict[str, dict[str, Any]]:
    """
    Mappa codice → {pct, descrizione, label} per il ricalcolo live in form.

    Preferisce ``Aliquota.percentuale`` / ``descrizione`` (AliquoteIva); i fallback
    noti riempiono solo i codici assenti in anagrafica così server e JS restano
    allineati. ``label`` = descrizione o codice (stesso criterio del castelletto).
    """
    out: dict[str, dict[str, Any]] = {}

    def _put(info: AliquotaInfo) -> None:
        payload = {
            "pct": float(info.percentuale),
            "descrizione": _txt(info.descrizione),
            "label": info.label,
        }
        out[info.codice] = payload
        out[info.codice.upper()] = payload

    try:
        from apps.aliquote.models import Aliquota

        for row in Aliquota.objects.all().only("codice", "percentuale", "descrizione"):
            _put(_info_from_aliquota_row(row))
    except Exception:
        pass

    for code, pct in _IVA_FALLBACK.items():
        if code not in out and code.upper() not in out:
            _put(AliquotaInfo(codice=code, percentuale=pct))
    return out
