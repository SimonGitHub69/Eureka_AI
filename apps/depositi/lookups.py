"""Lookup codici deposito presenti in anagrafica."""

from __future__ import annotations

from django.db import transaction
from django.db.models import TextField
from django.db.models.functions import Trim, Upper
from django.db.utils import OperationalError, ProgrammingError


def _norm_code(value: str | None) -> str:
    return (value or "").strip().upper()


def depositi_by_codes(codes) -> dict[str, str]:
    """Mappa codice normalizzato → codice anagrafica (per URL)."""
    from apps.depositi.models import Deposito

    keys = sorted({_norm_code(c) for c in codes if _norm_code(c)})
    if not keys:
        return {}
    try:
        with transaction.atomic():
            qs = Deposito.objects.annotate(
                _n=Upper(Trim("codice"), output_field=TextField())
            ).filter(_n__in=keys)
            return {_norm_code(row.codice): (row.codice or "").strip() for row in qs}
    except (ProgrammingError, OperationalError):
        return {}
