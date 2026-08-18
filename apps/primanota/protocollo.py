"""Protocollo IVA dal registro collegato alla causale."""

from __future__ import annotations

from datetime import date, datetime, time

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from apps.registri_iva.lookups import resolve_registro_iva
from apps.registri_iva.models import RegistroIva


def protocol_counter_fields(registro) -> tuple[str, str]:
    """Progressivo e data ultimo protocollo in base al tipo registro.

    Acquisto → UPA; Vendita / Corrispettivi → UPS.
    """
    tipo = (getattr(registro, "tipo_registro", None) or "").strip().lower()
    if tipo.startswith("vendit") or tipo.startswith("corrispett"):
        return ("ups", "data_ups")
    return ("upa", "data_upa")


def peek_next_protocollo(registro_code: str | None) -> int | None:
    """Prossimo protocollo in anteprima (non incrementa il registro)."""
    registro = resolve_registro_iva(registro_code)
    if registro is None:
        return None
    field, _ = protocol_counter_fields(registro)
    return int(getattr(registro, field) or 0) + 1


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return timezone.now()


def allocate_next_protocollo(registro_code: str | None, data_reg=None) -> int | None:
    """Assegna il prossimo protocollo e incrementa UPA/UPS sul registro."""
    registro = resolve_registro_iva(registro_code)
    if registro is None:
        return None
    try:
        with transaction.atomic():
            locked = RegistroIva.objects.select_for_update().get(pk=registro.pk)
            field, date_field = protocol_counter_fields(locked)
            next_n = int(getattr(locked, field) or 0) + 1
            setattr(locked, field, next_n)
            setattr(locked, date_field, _as_datetime(data_reg))
            locked.save(update_fields=[field, date_field])
            return next_n
    except (ProgrammingError, OperationalError, RegistroIva.DoesNotExist):
        return peek_next_protocollo(registro_code)


def registro_from_causale(causale) -> str:
    return (getattr(causale, "registro_iva", None) or "").strip() if causale else ""


def protocollo_from_causale(causale) -> dict:
    """Registro e prossimo protocollo da una causale (anteprima, non riserva)."""
    registro_code = registro_from_causale(causale)
    if not registro_code:
        return {
            "registro": None,
            "registro_label": None,
            "numero_prot": None,
            "tipo_registro": None,
        }
    registro = resolve_registro_iva(registro_code)
    label = registro_code
    tipo = None
    if registro is not None:
        desc = (registro.label or "").strip()
        code = (registro.codice or registro_code).strip()
        label = f"{code} — {desc}" if desc else code
        tipo = (registro.tipo_registro or "").strip() or None
    return {
        "registro": registro_code,
        "registro_label": label,
        "numero_prot": peek_next_protocollo(registro_code),
        "tipo_registro": tipo,
    }
