"""Collegamenti Primanota → causali, registri IVA, anagrafiche, PDC, aliquote, condizioni."""

from __future__ import annotations

from django.db import transaction
from django.db.models import TextField
from django.db.models.functions import Trim, Upper
from django.db.utils import OperationalError, ProgrammingError
from django.urls import reverse

from apps.causali_contabili.models import CausaleContabile
from apps.registri_iva.lookups import (
    attach_registri_iva as _attach_registri_iva,
    registro_iva_choices,
    registri_iva_by_codes,
    resolve_registro_iva,
)


def _norm_code(codice: str | None) -> str:
    return (codice or "").strip().upper()


def _mirror_by_codes(model, codici) -> dict:
    keys = sorted({_norm_code(c) for c in codici if _norm_code(c)})
    if not keys:
        return {}
    try:
        with transaction.atomic():
            qs = model.objects.annotate(
                _n=Upper(Trim("codice"), output_field=TextField())
            ).filter(_n__in=keys)
            return {_norm_code(c.codice): c for c in qs}
    except (ProgrammingError, OperationalError):
        return {}


def causali_contabili_by_codes(codici) -> dict[str, CausaleContabile]:
    return _mirror_by_codes(CausaleContabile, codici)


def resolve_causale_contabile(codice: str | None) -> CausaleContabile | None:
    mapping = causali_contabili_by_codes([codice])
    return mapping.get(_norm_code(codice))


def attach_causali_contabili(registrazioni) -> None:
    mapping = causali_contabili_by_codes(r.causale for r in registrazioni)
    for row in registrazioni:
        row.causale_contabile = mapping.get(_norm_code(row.causale))


def _causale_has_registro_iva(causale) -> bool:
    return bool((getattr(causale, "registro_iva", None) or "").strip())


def causali_contabili_catalog() -> list[dict]:
    """Elenco causali per select/JS: code, label, has_registro."""
    items: list[dict] = []
    seen: set[str] = set()
    try:
        with transaction.atomic():
            qs = CausaleContabile.objects.order_by("codice")
            for causale in qs:
                code = (causale.codice or "").strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                label = causale.label
                items.append(
                    {
                        "code": code,
                        "label": f"{code} — {label}" if label else code,
                        "has_registro": _causale_has_registro_iva(causale),
                    }
                )
    except (ProgrammingError, OperationalError):
        pass
    return items


def causali_contabili_choices(
    current: str | None = None,
    *,
    senza_registro_iva: bool = False,
    con_registro_iva: bool = False,
    catalog: list[dict] | None = None,
) -> list[tuple[str, str]]:
    """Opzioni select: codice + descrizione, con eventuale valore corrente assente."""
    choices: list[tuple[str, str]] = [("", "—")]
    seen: set[str] = {""}
    for item in catalog if catalog is not None else causali_contabili_catalog():
        code = item["code"]
        if not code or code in seen:
            continue
        if senza_registro_iva and item.get("has_registro"):
            continue
        if con_registro_iva and not item.get("has_registro"):
            continue
        seen.add(code)
        choices.append((code, item["label"]))
    current_code = (current or "").strip()
    if current_code and current_code not in seen:
        choices.append((current_code, current_code))
    return choices


def attach_registri_iva(registrazioni) -> None:
    _attach_registri_iva(registrazioni, code_attr="registro", target_attr="registro_iva")


def resolve_partita_clifor(codice: str | None) -> dict:
    """Cliente/fornitore da CodicePartita (C… / F…)."""
    from apps.anagrafiche.models import Cliente, Fornitore, get_by_codice
    from apps.destinazioni.models import tipo_clifor

    code = (codice or "").strip()
    result = {"codice": code, "tipo": "Cliente / Fornitore", "label": "", "url": ""}
    if not code:
        return result
    kind = tipo_clifor(code)
    try:
        if kind == "F":
            obj = get_by_codice(Fornitore, code)
            result["tipo"] = "Fornitore"
            name = "anagrafiche:fornitore_detail"
        else:
            obj = get_by_codice(Cliente, code)
            if obj is None and kind != "C":
                obj = get_by_codice(Fornitore, code)
                if obj is not None:
                    result["tipo"] = "Fornitore"
                    name = "anagrafiche:fornitore_detail"
                else:
                    name = "anagrafiche:cliente_detail"
            else:
                result["tipo"] = "Cliente"
                name = "anagrafiche:cliente_detail"
        if obj is None:
            return result
        result["label"] = (getattr(obj, "ragione_sociale", None) or "").strip()
        result["url"] = reverse(name, kwargs={"codice": obj.codice})
        result["codice"] = (obj.codice or code).strip()
        return result
    except Exception:
        return result


def resolve_pagamento(codice: str | None) -> dict:
    from apps.articoli.lookups import descrizione_condizione
    from apps.condizioni.models import Condizione

    code = (codice or "").strip()
    result = {
        "codice": code,
        "label": descrizione_condizione(code) if code else "",
        "url": "",
    }
    obj = _mirror_by_codes(Condizione, [code]).get(_norm_code(code))
    if obj is not None:
        result["url"] = reverse("condizioni:detail", kwargs={"codice": obj.codice})
    return result


def attach_line_lookups(righe, *, iva: bool = False) -> None:
    """Decodifica conti PDC (e aliquote IVA sulle righe tipo 2)."""
    from apps.pdc.models import PianoConti

    codes: list[str] = []
    for riga in righe:
        codes.extend((riga.conto_partita, riga.conto_dare, riga.conto_avere))
    pdc_map = _mirror_by_codes(PianoConti, codes)
    iva_map: dict = {}
    if iva:
        from apps.aliquote.models import Aliquota

        iva_map = _mirror_by_codes(Aliquota, (r.codice_iva for r in righe))
    for riga in righe:
        pdc = pdc_map.get(_norm_code(riga.conto_partita))
        pdc_dare = pdc_map.get(_norm_code(riga.conto_dare))
        pdc_avere = pdc_map.get(_norm_code(riga.conto_avere))
        aliquota = iva_map.get(_norm_code(riga.codice_iva))
        riga.pdc = pdc
        riga.pdc_dare = pdc_dare
        riga.pdc_avere = pdc_avere
        riga.aliquota = aliquota
        riga.pdc_url = (
            reverse("pdc:detail", kwargs={"codice": pdc.codice}) if pdc else ""
        )
        riga.pdc_dare_url = (
            reverse("pdc:detail", kwargs={"codice": pdc_dare.codice}) if pdc_dare else ""
        )
        riga.pdc_avere_url = (
            reverse("pdc:detail", kwargs={"codice": pdc_avere.codice})
            if pdc_avere
            else ""
        )
        if not pdc_dare:
            dare_info = resolve_partita_clifor(riga.conto_dare)
            if dare_info.get("label"):
                riga.pdc_dare = type("Lookup", (), {"label": dare_info["label"]})()
                riga.pdc_dare_url = dare_info.get("url") or ""
        if not pdc_avere:
            avere_info = resolve_partita_clifor(riga.conto_avere)
            if avere_info.get("label"):
                riga.pdc_avere = type("Lookup", (), {"label": avere_info["label"]})()
                riga.pdc_avere_url = avere_info.get("url") or ""
        riga.iva_url = (
            reverse("aliquote:detail", kwargs={"codice": aliquota.codice})
            if aliquota
            else ""
        )


def attach_iva_line_links(righe) -> None:
    attach_line_lookups(righe, iva=True)
