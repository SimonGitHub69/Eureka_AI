"""Collegamento PDC.Gruppo → Raggruppamento.Codice."""

from __future__ import annotations

from django import forms

from apps.raggruppamento_conti.models import RaggruppamentoConto


def raggruppamento_map() -> dict[str, str]:
    try:
        return {
            codice: (desc or "").strip()
            for codice, desc in RaggruppamentoConto.objects.values_list(
                "codice", "descrizione"
            )
        }
    except Exception:
        return {}


def raggruppamento_choices() -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = [("", "---------")]
    try:
        for codice, descrizione in RaggruppamentoConto.objects.order_by("codice").values_list(
            "codice", "descrizione"
        ):
            desc = (descrizione or "").strip()
            label = f"{codice} – {desc}" if desc else codice
            choices.append((codice, label))
    except Exception:
        pass
    return choices


def raggruppamento_label(codice: str | None, cache: dict[str, str] | None = None) -> str:
    code = (codice or "").strip()
    if not code:
        return ""
    mapping = cache or raggruppamento_map()
    desc = (mapping.get(code) or "").strip()
    return f"{code} – {desc}" if desc else code


def gruppo_choice_field(**kwargs) -> forms.ChoiceField:
    return forms.ChoiceField(
        choices=raggruppamento_choices(),
        required=False,
        label="Gruppo",
        widget=forms.Select(attrs={"class": "form-select"}),
        **kwargs,
    )
