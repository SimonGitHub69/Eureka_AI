"""Lookup DestCliFor (destinazioni diverse) per combobox documenti."""

from __future__ import annotations

from django.db.models import Q

from apps.destinazioni.models import DestinazioneDiversa, compact_codice, destinazioni_for_anagrafica


def _norm(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _nazione(obj: DestinazioneDiversa) -> str:
    """CodNazione / DescNazione → campo nazione testata (preferisci descrizione)."""
    desc = _norm(getattr(obj, "desc_nazione", None))
    if desc:
        return desc
    return _norm(getattr(obj, "cod_nazione", None))


def _row_from_obj(obj: DestinazioneDiversa) -> dict:
    codice = _norm(obj.codice_dest) or str(obj.id)
    desc = _norm(obj.ragione_sociale)
    return {
        "found": True,
        "codice": codice,
        "descrizione": desc,
        "codice_dest": _norm(obj.codice_dest),
        "codice_clifor": compact_codice(obj.codice),
        "destinatario": desc,
        "indirizzo": _norm(obj.indirizzo),
        "localita": _norm(obj.citta),
        "cap": _norm(obj.cap),
        "provincia": _norm(obj.provincia),
        "nazione": _nazione(obj),
        "telefono": _norm(obj.telefono),
        "id": obj.id,
    }


def _empty(codice_dest: str | None = None, codice_clifor: str | None = None) -> dict:
    return {
        "found": False,
        "codice": _norm(codice_dest),
        "descrizione": "",
        "codice_dest": _norm(codice_dest),
        "codice_clifor": compact_codice(codice_clifor),
        "destinatario": "",
        "indirizzo": "",
        "localita": "",
        "cap": "",
        "provincia": "",
        "nazione": "",
        "telefono": "",
        "id": None,
    }


def resolve_destinazione(
    codice_dest: str | None,
    *,
    codice_clifor: str | None = None,
) -> dict:
    """Risolve una destinazione per CodiceDest (opz. filtrata sul Cli/For)."""
    code = _norm(codice_dest)
    if not code:
        return _empty(codice_dest, codice_clifor)
    try:
        qs = destinazioni_for_anagrafica(codice_clifor) if compact_codice(codice_clifor) else DestinazioneDiversa.objects.all()
        obj = (
            qs.filter(Q(codice_dest__iexact=code) | Q(codice_dest__iexact=code.upper()))
            .order_by("codice_dest", "id")
            .first()
        )
        if obj is None and code.isdigit():
            obj = qs.filter(id=int(code)).first()
        if obj is None:
            return _empty(codice_dest, codice_clifor)
        return _row_from_obj(obj)
    except Exception:
        return _empty(codice_dest, codice_clifor)


def search_destinazioni(
    codice_clifor: str | None,
    q: str | None = None,
    *,
    limit: int = 40,
) -> list[dict]:
    """Elenco destinazioni del Cli/For (filtro opzionale su codice/ragione sociale)."""
    compact = compact_codice(codice_clifor)
    if not compact:
        return []
    limit = max(1, min(int(limit or 40), 100))
    q = _norm(q)
    try:
        qs = destinazioni_for_anagrafica(codice_clifor)
        if q:
            qs = qs.filter(
                Q(codice_dest__icontains=q)
                | Q(ragione_sociale__icontains=q)
                | Q(citta__icontains=q)
                | Q(indirizzo__icontains=q)
            )
        return [_row_from_obj(o) for o in qs.order_by("codice_dest", "id")[:limit]]
    except Exception:
        return []
