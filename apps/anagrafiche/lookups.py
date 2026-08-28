from __future__ import annotations

from apps.articoli.lookups import resolve_descrizione


def condizione_label(codice: str | None) -> str:
    return resolve_descrizione("condizione", codice)


def condizione_display(codice: str | None) -> str:
    return _code_display(codice, condizione_label(codice))


def agente_label(codice: str | None) -> str:
    return resolve_descrizione("agente", codice)


def agente_display(codice: str | None) -> str:
    return _code_display(codice, agente_label(codice))


def _code_display(codice: str | None, label: str | None) -> str:
    code = (codice or "").strip()
    if not code:
        return ""
    text = (label or "").strip()
    return f"{code} – {text}" if text else code


def _form_value(form, name: str):
    if form.is_bound:
        return form.data.get(name)
    instance = getattr(form, "instance", None)
    if instance:
        return getattr(instance, name, None)
    return None


def form_linked_labels(form) -> dict[str, str]:
    return {
        "cond_paga": condizione_label(_form_value(form, "cond_paga")),
        "agente": agente_label(_form_value(form, "agente")),
        "agente2": agente_label(_form_value(form, "agente2")),
    }
