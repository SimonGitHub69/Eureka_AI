"""Catalogo campi riga documento e layout colonne parametrico."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

CAMPI_RIGA: dict[str, dict[str, str]] = {
    "numero_riga": {
        "label": "#",
        "icon": "ti-hash",
        "larghezza": "4rem",
        "align": "",
    },
    "codice": {
        "label": "Codice",
        "icon": "ti-barcode",
        "larghezza": "8rem",
        "align": "",
    },
    "descrizione": {
        "label": "Descrizione",
        "icon": "ti-align-left",
        "larghezza": "",
        "align": "",
    },
    "quantita": {
        "label": "Qtà",
        "icon": "ti-numbers",
        "larghezza": "6rem",
        "align": "end",
    },
    "unita_misura": {
        "label": "U.M.",
        "icon": "ti-ruler-measure",
        "larghezza": "5rem",
        "align": "",
    },
    "prezzo_unitario": {
        "label": "Prezzo",
        "icon": "ti-currency-euro",
        "larghezza": "7rem",
        "align": "end",
    },
    "sconto": {
        "label": "Sconto",
        "icon": "ti-percentage",
        "larghezza": "5rem",
        "align": "",
    },
    "provvigione": {
        "label": "Provvigione",
        "icon": "ti-percentage",
        "larghezza": "6rem",
        "align": "end",
    },
    "iva": {
        "label": "IVA",
        "icon": "ti-receipt-tax",
        "larghezza": "5rem",
        "align": "",
    },
}

CAMPO_RIGA_CHOICES = tuple((key, spec["label"]) for key, spec in CAMPI_RIGA.items())

DEFAULT_COLONNE_RIGA: tuple[tuple[str, int], ...] = (
    ("numero_riga", 10),
    ("codice", 20),
    ("descrizione", 30),
    ("quantita", 40),
    ("unita_misura", 50),
    ("prezzo_unitario", 60),
    ("sconto", 70),
    ("iva", 80),
)

COLONNE_RIGA_PREVENTIVI: tuple[tuple[str, int], ...] = (
    ("numero_riga", 10),
    ("codice", 20),
    ("descrizione", 30),
    ("quantita", 40),
    ("unita_misura", 50),
    ("prezzo_unitario", 60),
    ("sconto", 70),
    ("provvigione", 75),
    ("iva", 80),
)


def default_colonne_for(tipo=None) -> tuple[tuple[str, int], ...]:
    categoria = (getattr(tipo, "categoria", "") or "").upper()
    if categoria == "PREVENTIVI":
        return COLONNE_RIGA_PREVENTIVI
    return DEFAULT_COLONNE_RIGA


def campo_meta(campo: str) -> dict[str, str]:
    return CAMPI_RIGA.get(campo) or {
        "label": campo,
        "icon": "ti-forms",
        "larghezza": "",
        "align": "",
    }


def campo_label(campo: str) -> str:
    return campo_meta(campo)["label"]


def campo_icon(campo: str) -> str:
    return campo_meta(campo)["icon"]


def campo_larghezza(campo: str) -> str:
    return campo_meta(campo)["larghezza"]


def campo_align_class(campo: str) -> str:
    align = campo_meta(campo).get("align") or ""
    if align == "end":
        return "text-end"
    if align == "center":
        return "text-center"
    return ""


@dataclass(frozen=True)
class ColonnaRigaSpec:
    campo: str
    posizione: int
    etichetta: str = ""
    larghezza: str = ""

    @property
    def etichetta_display(self) -> str:
        return (self.etichetta or "").strip() or campo_label(self.campo)

    @property
    def icon(self) -> str:
        return campo_icon(self.campo)

    @property
    def align_class(self) -> str:
        return campo_align_class(self.campo)

    @property
    def larghezza_css(self) -> str:
        return (self.larghezza or "").strip() or campo_larghezza(self.campo)


def default_colonne_specs(tipo=None) -> list[ColonnaRigaSpec]:
    return [
        ColonnaRigaSpec(campo=campo, posizione=posizione)
        for campo, posizione in default_colonne_for(tipo)
    ]


def colonne_riga_for(tipo) -> Sequence[Any]:
    """Colonne configurate per il tipo, oppure il layout predefinito."""
    from apps.documenti.models import ColonnaRigaDocumento

    if tipo is None or not getattr(tipo, "pk", None):
        return default_colonne_specs(tipo)
    rows = list(
        ColonnaRigaDocumento.objects.filter(tipo_doc=tipo).order_by("posizione", "pk")
    )
    return rows or default_colonne_specs(tipo)


def campi_visibili(colonne: Sequence[Any]) -> list[str]:
    seen: list[str] = []
    for col in colonne:
        campo = getattr(col, "campo", "")
        if campo and campo not in seen:
            seen.append(campo)
    return seen


def seed_colonne_riga_default(tipo, *, force: bool = False) -> int:
    """Crea (o ripristina) le colonne predefinite per un tipo documento."""
    from apps.documenti.models import ColonnaRigaDocumento

    qs = ColonnaRigaDocumento.objects.filter(tipo_doc=tipo)
    if qs.exists() and not force:
        return 0
    if force:
        qs.delete()
    created = [
        ColonnaRigaDocumento(
            tipo_doc=tipo,
            campo=campo,
            posizione=posizione,
            etichetta="",
            larghezza="",
        )
        for campo, posizione in default_colonne_for(tipo)
    ]
    ColonnaRigaDocumento.objects.bulk_create(created)
    return len(created)
