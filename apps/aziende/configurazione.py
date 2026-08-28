"""Configurazione locale Eureka per azienda (AziendaDati)."""

from __future__ import annotations

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.aziende.models import Azienda, AziendaDati

PDC_NOLEGGIO_DB_COLUMNS = frozenset(
    {"Nomenclatura", "Bene_Servizio", "TipoNoleggio"}
)


def resolve_azienda_dati(azienda_id: int | None = None) -> AziendaDati | None:
    if azienda_id is not None:
        return (
            AziendaDati.objects.filter(is_active=True, azienda_id=azienda_id)
            .order_by("-updated_at")
            .first()
        )

    # Se esiste una sola azienda mirror, collega i dati locali a quella.
    # Dopo "Azzera tabelle" la relazione "aziende" può non esistere: non far crashare.
    try:
        with transaction.atomic():
            aziende = Azienda.objects.order_by("id")
            if aziende.count() == 1:
                return AziendaDati.objects.filter(
                    is_active=True, azienda_id=aziende.first().id
                ).first()
    except (ProgrammingError, OperationalError):
        pass

    return (
        AziendaDati.objects.filter(is_active=True)
        .order_by("azienda_id")
        .first()
    )


def _initials_from_ragione_sociale(name: str) -> str:
    words = [w for w in (name or "").split() if w]
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    if words:
        return words[0][:2].upper()
    return ""


def resolve_print_azienda_context(*, branding: str = "liste") -> dict[str, str]:
    """Logo e ragione sociale per intestazione stampa.

    ``branding``:
    - ``liste``: logo generale (elenchi)
    - ``documenti``: logo stampe documenti, con fallback al logo generale
    """
    ragione_sociale = ""
    logo_url = ""

    dati = resolve_azienda_dati()
    azienda = None

    try:
        if dati:
            azienda = Azienda.objects.filter(pk=dati.azienda_id).first()
            if branding == "documenti" and dati.logo_documenti:
                logo_url = dati.logo_documenti.url
            elif dati.logo:
                logo_url = dati.logo.url
        else:
            aziende = list(Azienda.objects.order_by("id")[:2])
            if len(aziende) == 1:
                azienda = aziende[0]
    except (ProgrammingError, OperationalError):
        azienda = None

    if azienda:
        ragione_sociale = (azienda.ragione_sociale or "").strip() or f"Azienda {azienda.id}"

    return {
        "print_azienda_ragione_sociale": ragione_sociale,
        "print_azienda_logo_url": logo_url,
        "print_azienda_initials": _initials_from_ragione_sociale(ragione_sociale),
    }


def is_azienda_noleggio(azienda_id: int | None = None) -> bool:
    """True se l'azienda (o almeno una) è configurata come noleggio.

    Resiliente se la tabella mirror ``aziende`` manca (es. dopo azzeramento).
    """
    try:
        if azienda_id is not None:
            dati = resolve_azienda_dati(azienda_id)
            return bool(dati and dati.azienda_noleggio)
        if AziendaDati.objects.filter(is_active=True, azienda_noleggio=True).exists():
            return True
        dati = resolve_azienda_dati()
        return bool(dati and dati.azienda_noleggio)
    except (ProgrammingError, OperationalError):
        return False
