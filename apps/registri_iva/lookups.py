"""Lookup condivisi per RegistriIva."""

from __future__ import annotations

from django.db import transaction
from django.db.models import TextField
from django.db.models.functions import Trim, Upper
from django.db.utils import OperationalError, ProgrammingError

from apps.registri_iva.models import RegistroIva


def _norm_code(codice: str | None) -> str:
    return (codice or "").strip().upper()


def registri_iva_by_codes(codici) -> dict[str, RegistroIva]:
    keys = sorted({_norm_code(c) for c in codici if _norm_code(c)})
    if not keys:
        return {}
    try:
        with transaction.atomic():
            qs = RegistroIva.objects.annotate(
                _n=Upper(Trim("codice"), output_field=TextField())
            ).filter(_n__in=keys)
            return {_norm_code(r.codice): r for r in qs}
    except (ProgrammingError, OperationalError):
        return {}


def resolve_registro_iva(codice: str | None) -> RegistroIva | None:
    return registri_iva_by_codes([codice]).get(_norm_code(codice))


def attach_registri_iva(items, *, code_attr: str, target_attr: str) -> None:
    mapping = registri_iva_by_codes(getattr(item, code_attr, None) for item in items)
    for item in items:
        code = _norm_code(getattr(item, code_attr, None))
        setattr(item, target_attr, mapping.get(code))


def registro_iva_choices(current: str | None = None) -> list[tuple[str, str]]:
    """Opzioni select: codice + descrizione, con eventuale valore corrente assente."""
    choices: list[tuple[str, str]] = [("", "—")]
    seen: set[str] = {""}
    try:
        with transaction.atomic():
            for registro in RegistroIva.objects.order_by("codice"):
                code = (registro.codice or "").strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                label = registro.label
                choices.append((code, f"{code} — {label}" if label else code))
    except (ProgrammingError, OperationalError):
        pass
    current_code = (current or "").strip()
    if current_code and current_code not in seen:
        choices.append((current_code, current_code))
    return choices
