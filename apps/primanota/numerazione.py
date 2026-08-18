"""Progressivi ID / numero registrazione su tabelle mirror Primanota."""

from __future__ import annotations

from datetime import date, datetime

from django.db import connection, transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone


def _next_id(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COALESCE(MAX("ID"), 0) FROM "{table}"')
            return int(cur.fetchone()[0] or 0) + 1
    except (ProgrammingError, OperationalError):
        return 1


def next_primanota_id() -> int:
    return _next_id("primanota")


def next_dettaglio_id() -> int:
    return _next_id("primanota_dettaglio")


def next_numero_reg() -> int:
    """Fallback: MAX(NumeroReg) + 1 se manca un contatore Primanota."""
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT COALESCE(MAX("NumeroReg"), 0) FROM primanota')
            return int(cur.fetchone()[0] or 0) + 1
    except (ProgrammingError, OperationalError):
        return 1


def esercizio_from_data(value) -> int:
    """Anno di esercizio dalla data di registrazione (locale)."""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.year
    if isinstance(value, date):
        return value.year
    return timezone.localdate().year


def resolve_contatore_primanota(data_reg=None):
    """Contatore Tipo=Primanota con esercizio = anno della data registrazione."""
    from apps.documenti.models import ContatoreDocumento

    year = esercizio_from_data(data_reg)
    return (
        ContatoreDocumento.objects.filter(
            tipo_contatore=ContatoreDocumento.TIPO_PRIMANOTA,
            esercizio=year,
        )
        .order_by("codice")
        .first()
    )


def peek_next_numero_reg(data_reg=None) -> int:
    """Prossimo n. registrazione in anteprima (non incrementa il contatore)."""
    c = resolve_contatore_primanota(data_reg)
    if c is not None:
        return int(c.ultimo_numero or 0) + 1
    return next_numero_reg()


def allocate_next_numero_reg(data_reg=None) -> int:
    """Assegna il prossimo n. registrazione dal contatore Primanota dell'esercizio.

    Incrementa ``ultimo_numero`` con ``select_for_update``. Senza contatore
    per quell'anno, fallback a MAX(NumeroReg)+1.
    """
    from apps.documenti.models import ContatoreDocumento

    c = resolve_contatore_primanota(data_reg)
    if c is None:
        return next_numero_reg()

    with transaction.atomic():
        locked = ContatoreDocumento.objects.select_for_update().get(pk=c.pk)
        next_n = int(locked.ultimo_numero or 0) + 1
        locked.ultimo_numero = next_n
        locked.save(update_fields=["ultimo_numero"])
        return next_n
