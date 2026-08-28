"""Collegamenti Condizioni di pagamento → banche."""

from __future__ import annotations

from django.db.utils import OperationalError, ProgrammingError


def _norm_code(codice: str | None) -> str:
    return (codice or "").strip()


def attach_banca_condizione(condizione) -> None:
    from apps.banche.models import Banca

    code = _norm_code(getattr(condizione, "codice_banca", None))
    if not code:
        setattr(condizione, "banca_collegata", None)
        return
    try:
        setattr(condizione, "banca_collegata", Banca.objects.filter(codice=code).first())
    except (ProgrammingError, OperationalError):
        setattr(condizione, "banca_collegata", None)


def build_scadenze_riepilogo(condizione) -> str:
    chunks: list[str] = []
    if condizione.numero_rate is not None:
        n = condizione.numero_rate
        chunks.append(f"{n} {'rata' if n == 1 else 'rate'}")
    if condizione.prima_rata is not None:
        chunks.append(f"prima scadenza a {condizione.prima_rata} gg")
    if condizione.intervallo is not None:
        chunks.append(f"poi ogni {condizione.intervallo} gg")
    if condizione.fine_mese:
        chunks.append("fine mese")
    elif condizione.giorno_fisso:
        chunks.append(f"giorno fisso del mese: {condizione.giorno_fisso}")
    return " · ".join(chunks)


def has_esclusioni(condizione) -> bool:
    return any(
        getattr(condizione, name) not in (None, "", 0)
        for name in (
            "mese_esclusione",
            "mese_esclusione2",
            "gg_mese_esclus",
            "gg_mese_esclus2",
        )
    )
