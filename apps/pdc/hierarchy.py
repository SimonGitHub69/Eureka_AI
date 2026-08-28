"""Gerarchia Piano dei Conti: Mastro → Conto → Sottoconto/Contropartita (es. 1, 1.10, 1.10.9).

In 4D il campo ``PDC.Tipo`` distingue i livelli:
- 2 = Mastro (codice senza punti)
- 0 = Conto (un punto)
- 1 = Contropartita / sottoconto (due punti: Mastro.Conto.Sottoconto)
"""

from __future__ import annotations

import re
from typing import Any

from django.db.models import QuerySet
from django.urls import reverse

from apps.pdc.models import PianoConti

LIVELLO_MASTRO = 0
LIVELLO_CONTO = 1
LIVELLO_SOTTOCONTO = 2

# Valori 4D di PDC.Tipo (allineati al livello gerarchico del codice).
PDC_TIPO_CONTO = 0
PDC_TIPO_CONTROPARTITA = 1
PDC_TIPO_MASTRO = 2

LIVELLO_LABELS = {
    LIVELLO_MASTRO: "Mastro",
    LIVELLO_CONTO: "Conto",
    LIVELLO_SOTTOCONTO: "Sottoconto",
}

# Regex codice contropartita: Mastro.Conto.Sottoconto (esattamente due punti).
PDC_CONTROPARTITA_CODICE_REGEX = r"^[^.]+\.[^.]+\.[^.]+$"


def pdc_livello(codice: str) -> int:
    return (codice or "").count(".")


def pdc_is_contropartita(codice: str | None) -> bool:
    """True se il codice ha formato contropartita (sottoconto, livello 2)."""
    return pdc_livello((codice or "").strip()) == LIVELLO_SOTTOCONTO


def pdc_contropartite_qs(qs: QuerySet | None = None) -> QuerySet:
    """Queryset limitato alle sole contropartite (4D Tipo=1)."""
    if qs is None:
        qs = PianoConti.objects.all()
    return qs.filter(tipo=PDC_TIPO_CONTROPARTITA)


def pdc_livello_label(codice: str) -> str:
    level = pdc_livello(codice)
    return LIVELLO_LABELS.get(level, LIVELLO_LABELS[LIVELLO_SOTTOCONTO])


def pdc_mastro_codice(codice: str) -> str:
    return (codice or "").split(".")[0]


def pdc_conto_codice(codice: str) -> str | None:
    parts = (codice or "").split(".")
    if len(parts) < 2:
        return None
    return f"{parts[0]}.{parts[1]}"


def pdc_parent_codice(codice: str) -> str | None:
    codice = (codice or "").strip()
    if "." not in codice:
        return None
    return codice.rsplit(".", 1)[0]


def pdc_descrizione(codice: str) -> str:
    if not codice:
        return ""
    obj = PianoConti.objects.filter(pk=codice).values_list("descrizione", flat=True).first()
    return (obj or "").strip()


def pdc_list_regex(
    mastro: str | None = None,
    conto: str | None = None,
    vista: str | None = None,
) -> str:
    if conto:
        return f"^{re.escape(conto)}\\.[^.]+$"
    if mastro:
        return f"^{re.escape(mastro)}\\.[^.]+$"
    vista_key = (vista or "").strip().lower()
    if vista_key == "conti":
        return r"^[^.]+\.[^.]+$"
    if vista_key in ("sottoconti", "sottoconto"):
        return PDC_CONTROPARTITA_CODICE_REGEX
    return r"^[^.]+$"


def pdc_list_livello(
    mastro: str | None = None,
    conto: str | None = None,
    vista: str | None = None,
) -> int:
    if conto:
        return LIVELLO_SOTTOCONTO
    if mastro:
        return LIVELLO_CONTO
    vista_key = (vista or "").strip().lower()
    if vista_key == "conti":
        return LIVELLO_CONTO
    if vista_key in ("sottoconti", "sottoconto"):
        return LIVELLO_SOTTOCONTO
    return LIVELLO_MASTRO


def pdc_list_title(
    mastro: str | None = None,
    conto: str | None = None,
    vista: str | None = None,
) -> str:
    livello = pdc_list_livello(mastro, conto, vista)
    if livello == LIVELLO_SOTTOCONTO and conto:
        desc = pdc_descrizione(conto)
        return f"Sottoconti di {conto}" + (f" · {desc}" if desc else "")
    if livello == LIVELLO_SOTTOCONTO:
        return "Sottoconti"
    if livello == LIVELLO_CONTO and mastro:
        desc = pdc_descrizione(mastro)
        return f"Conti del mastro {mastro}" + (f" · {desc}" if desc else "")
    if livello == LIVELLO_CONTO:
        return "Conti"
    return "Mastri"


def pdc_level_nav(
    mastro: str | None = None,
    conto: str | None = None,
    vista: str | None = None,
) -> list[dict[str, Any]]:
    """Bottoni Mastri / Conti / Sottoconti — sempre attivi, vista piatta per livello."""
    base = reverse("pdc:list")
    livello = pdc_list_livello(mastro, conto, vista)
    return [
        {
            "label": "Mastri",
            "url": base,
            "active": livello == LIVELLO_MASTRO,
        },
        {
            "label": "Conti",
            "url": f"{base}?vista=conti",
            "active": livello == LIVELLO_CONTO,
        },
        {
            "label": "Sottoconti",
            "url": f"{base}?vista=sottoconti",
            "active": livello == LIVELLO_SOTTOCONTO,
        },
    ]


def pdc_breadcrumb(
    mastro: str | None = None,
    conto: str | None = None,
    vista: str | None = None,
) -> list[dict[str, Any]]:
    base = reverse("pdc:list")
    mastro = (mastro or "").strip()
    conto = (conto or "").strip()

    if mastro or conto:
        items: list[dict[str, Any]] = [
            {
                "label": "Mastri",
                "url": base,
                "active": False,
            }
        ]
        if mastro:
            desc = pdc_descrizione(mastro)
            items.append(
                {
                    "label": f"{mastro} {desc}".strip(),
                    "url": f"{base}?mastro={mastro}",
                    "active": mastro and not conto,
                }
            )
        if conto:
            desc = pdc_descrizione(conto)
            items.append(
                {
                    "label": f"{conto} {desc}".strip(),
                    "url": f"{base}?mastro={mastro}&conto={conto}",
                    "active": True,
                }
            )
        return items

    livello = pdc_list_livello(None, None, vista)
    return [
        {
            "label": "Mastri",
            "url": base,
            "active": livello == LIVELLO_MASTRO,
        },
        {
            "label": "Conti",
            "url": f"{base}?vista=conti",
            "active": livello == LIVELLO_CONTO,
        },
        {
            "label": "Sottoconti",
            "url": f"{base}?vista=sottoconti",
            "active": livello == LIVELLO_SOTTOCONTO,
        },
    ]


def pdc_hierarchy_context(
    codice: str,
) -> dict[str, Any]:
    livello = pdc_livello(codice)
    mastro_codice = pdc_mastro_codice(codice)
    conto_codice = pdc_conto_codice(codice)
    parent_codice = pdc_parent_codice(codice)

    descrizione_mastro = ""
    descrizione_conto = ""
    if livello >= LIVELLO_CONTO:
        descrizione_mastro = pdc_descrizione(mastro_codice)
    if livello == LIVELLO_SOTTOCONTO and conto_codice:
        descrizione_conto = pdc_descrizione(conto_codice)

    return {
        "livello": livello,
        "livello_label": pdc_livello_label(codice),
        "mastro_codice": mastro_codice,
        "conto_codice": conto_codice,
        "parent_codice": parent_codice,
        "descrizione_mastro": descrizione_mastro,
        "descrizione_conto": descrizione_conto,
        "breadcrumb": pdc_breadcrumb(
            mastro=mastro_codice if livello >= LIVELLO_CONTO else None,
            conto=conto_codice if livello == LIVELLO_SOTTOCONTO else None,
        ),
    }


def pdc_create_context(livello: int, mastro: str | None = None, conto: str | None = None) -> dict[str, Any]:
    livello = max(LIVELLO_MASTRO, min(LIVELLO_SOTTOCONTO, livello))
    parent_prefix = ""
    descrizione_mastro = ""
    descrizione_conto = ""

    if livello == LIVELLO_CONTO and mastro:
        parent_prefix = mastro.strip()
        descrizione_mastro = pdc_descrizione(parent_prefix)
    elif livello == LIVELLO_SOTTOCONTO and conto:
        parent_prefix = conto.strip()
        mastro = pdc_mastro_codice(conto)
        descrizione_mastro = pdc_descrizione(mastro)
        descrizione_conto = pdc_descrizione(conto)

    return {
        "livello": livello,
        "livello_label": LIVELLO_LABELS[livello],
        "parent_prefix": parent_prefix,
        "mastro_codice": mastro or "",
        "conto_codice": conto or "",
        "descrizione_mastro": descrizione_mastro,
        "descrizione_conto": descrizione_conto,
        "breadcrumb": pdc_breadcrumb(
            mastro=mastro if livello >= LIVELLO_CONTO else None,
            conto=conto if livello == LIVELLO_SOTTOCONTO else None,
        ),
    }
