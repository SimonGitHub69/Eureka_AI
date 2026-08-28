"""Risoluzione etichette (causale / cliente / fornitore) per i movimenti magazzino."""

from __future__ import annotations

from django.db import transaction
from django.db.models import TextField
from django.db.models.functions import Trim, Upper
from django.db.utils import OperationalError, ProgrammingError


def _norm_code(value: str | None) -> str:
    return (value or "").strip().upper()


def _ragione_sociale(obj) -> str:
    parts = [
        p.strip()
        for p in (
            getattr(obj, "ragione_sociale1", None),
            getattr(obj, "ragione_sociale2", None),
        )
        if isinstance(p, str) and p.strip()
    ]
    if parts:
        return " ".join(parts)
    prop = getattr(obj, "ragione_sociale", None)
    if callable(prop):
        return (prop() or "").strip()
    if isinstance(prop, str):
        return prop.strip()
    return ""


def _mirror_labels_by_codes(model, codes, *, label_fn) -> dict[str, str]:
    keys = sorted({_norm_code(c) for c in codes if _norm_code(c)})
    if not keys:
        return {}
    try:
        with transaction.atomic():
            qs = model.objects.annotate(
                _n=Upper(Trim("codice"), output_field=TextField())
            ).filter(_n__in=keys)
            return {
                _norm_code(row.codice): label
                for row in qs
                if (label := (label_fn(row) or "").strip())
            }
    except (ProgrammingError, OperationalError):
        return {}


def causali_magazzino_by_codes(codes) -> dict[str, str]:
    from apps.causali_magazzino.models import CausaleMagazzino

    return _mirror_labels_by_codes(
        CausaleMagazzino,
        codes,
        label_fn=lambda row: (row.descrizione or "").strip(),
    )


def clienti_ragione_sociale_by_codes(codes) -> dict[str, str]:
    from apps.anagrafiche.models import Cliente

    return _mirror_labels_by_codes(Cliente, codes, label_fn=_ragione_sociale)


def fornitori_ragione_sociale_by_codes(codes) -> dict[str, str]:
    from apps.anagrafiche.models import Fornitore

    return _mirror_labels_by_codes(Fornitore, codes, label_fn=_ragione_sociale)


def attach_movimento_labels(movimenti) -> None:
    """Attacca descrizione causale e ragioni sociali sulla pagina corrente."""
    rows = list(movimenti or [])
    if not rows:
        return

    causali = causali_magazzino_by_codes(getattr(r, "causale", None) for r in rows)
    clienti = clienti_ragione_sociale_by_codes(getattr(r, "cliente", None) for r in rows)
    fornitori = fornitori_ragione_sociale_by_codes(
        getattr(r, "fornitore", None) for r in rows
    )

    for row in rows:
        row.causale_descrizione = causali.get(_norm_code(getattr(row, "causale", None)), "")
        row.cliente_ragione_sociale = clienti.get(
            _norm_code(getattr(row, "cliente", None)), ""
        )
        row.fornitore_ragione_sociale = fornitori.get(
            _norm_code(getattr(row, "fornitore", None)), ""
        )


def format_causale_display(movimento) -> str:
    code = (getattr(movimento, "causale", None) or "").strip()
    if not code:
        return ""
    desc = (getattr(movimento, "causale_descrizione", None) or "").strip()
    return f"{code} - {desc}" if desc else code


def format_anagrafica_display(code: str | None, ragione: str | None) -> str:
    code = (code or "").strip()
    ragione = (ragione or "").strip()
    if ragione and code:
        return f"{ragione} ({code})"
    return ragione or code
