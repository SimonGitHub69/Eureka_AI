"""Risoluzione codice tabella Sconti → formula % (es. 50A → 50+10).

Lo sconto testata non viene scritto sulle righe: si usa solo in calcolo
(castelletto) tramite ``effective_sconto_formula``.
"""

from __future__ import annotations

from typing import Any


def resolve_sconto_percentuale(codice_or_formula: str | None) -> str:
    """Se il valore è un codice in Sconti, ritorna Sconti.Sconto; altrimenti il raw."""
    raw = str(codice_or_formula or "").strip()
    if not raw:
        return ""
    try:
        from apps.sconti.models import Sconto

        obj = Sconto.objects.filter(codice__iexact=raw).only("sconto").first()
        if obj is not None:
            val = str(obj.sconto or "").strip()
            if val:
                return val
    except Exception:
        pass
    return raw


def effective_sconto_formula(
    line_sconto: str | None,
    *,
    header_sconto: str | None = None,
) -> str:
    """Formula % effettiva per il castelletto (solo calcolo, non scrive sulle righe).

    Sconto riga e sconto testata (entrambi risolti via tabella Sconti) si
    applicano in **cascata** quando sono entrambi valorizzati e diversi
    (es. riga ``2`` + testata ``3`` → ``2+3``). Se uguali, una sola volta.
    Se uno solo è valorizzato, si usa quello.
    """
    line = resolve_sconto_percentuale(line_sconto)
    header = resolve_sconto_percentuale(header_sconto)
    if line and header and line != header:
        return f"{line}+{header}"
    return line or header or ""


def sconti_map_for_js() -> dict[str, str]:
    """Mappa codice → formula % per il castelletto client-side."""
    out: dict[str, str] = {}
    try:
        from apps.sconti.models import Sconto

        for codice, sconto in Sconto.objects.values_list("codice", "sconto"):
            key = (codice or "").strip()
            if not key:
                continue
            val = (sconto or "").strip() or key
            out[key] = val
    except Exception:
        return out
    return out


def header_sconto_from_documento(documento: Any) -> str:
    """Sconto % testata: campo sconto oppure risoluzione di codice_sconto."""
    direct = str(getattr(documento, "sconto", None) or "").strip()
    if direct:
        return resolve_sconto_percentuale(direct)
    return resolve_sconto_percentuale(getattr(documento, "codice_sconto", None))
