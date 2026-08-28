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


def corrispettivi_extra_from_causale(causale) -> dict:
    """Campi sola lettura della maschera Corrispettivi: incasso + cassa.

    In 4D la causale di incasso è CausaleCollegAutoF (es. 23), non CDare1.
    CDare1 è la contropartita cliente (es. C4425 CLIENTE CORRISPETTIVI).
    """
    from apps.articoli.lookups import resolve_descrizione

    extra = {
        "incasso_code": "",
        "incasso_label": "",
        "cassa_code": "",
        "cassa_label": "",
    }
    if causale is None:
        return extra
    incasso_raw = getattr(causale, "causale_colleg_auto_f", None)
    incasso = incasso_raw.strip() if isinstance(incasso_raw, str) else ""
    if incasso:
        linked = resolve_causale_contabile(incasso)
        extra["incasso_code"] = incasso
        extra["incasso_label"] = (linked.label if linked else "") or ""
    cassa_raw = getattr(causale, "cassa_corrispettivi", None)
    cassa = cassa_raw.strip() if isinstance(cassa_raw, str) else ""
    if cassa:
        extra["cassa_code"] = cassa
        extra["cassa_label"] = resolve_descrizione("pdc", cassa) or ""
    return extra


def attach_causali_contabili(registrazioni) -> None:
    mapping = causali_contabili_by_codes(r.causale for r in registrazioni)
    for row in registrazioni:
        row.causale_contabile = mapping.get(_norm_code(row.causale))


def tipo_registro_is_corrispettivi(tipo) -> bool:
    text = tipo.strip().lower() if isinstance(tipo, str) else ""
    return text.startswith("corrispett")


def causale_is_registro_corrispettivi(causale) -> bool:
    if causale is None:
        return False
    raw = getattr(causale, "registro_iva", None)
    code = raw.strip() if isinstance(raw, str) else ""
    if not code:
        return False
    registro = resolve_registro_iva(code)
    tipo = getattr(registro, "tipo_registro", None) if registro is not None else None
    return tipo_registro_is_corrispettivi(tipo)


def _flag_on(value) -> bool:
    return value is True or value == 1


def causale_is_autofattura_automatica(causale) -> bool:
    """Causale con flag Autofattura (generazione automatica, con campo Fornitore)."""
    if causale is None:
        return False
    return _flag_on(getattr(causale, "autofattura", False))


def causale_is_iva_autofattura(causale) -> bool:
    """Causale usabile in Primanota tipo Iva con Autofattura."""
    if causale is None:
        return False
    raw = getattr(causale, "registro_iva", None)
    if not (raw.strip() if isinstance(raw, str) else ""):
        return False
    return _flag_on(getattr(causale, "iva_con_autofattura", False)) or causale_is_autofattura_automatica(
        causale
    )


def causali_contabili_catalog() -> list[dict]:
    """Elenco causali per select/JS: code, label, has_registro, tipo_registro."""
    items: list[dict] = []
    seen: set[str] = set()
    try:
        with transaction.atomic():
            causali = list(CausaleContabile.objects.order_by("codice"))
            registri = registri_iva_by_codes(
                getattr(causale, "registro_iva", None) for causale in causali
            )
            for causale in causali:
                code = (causale.codice or "").strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                label = causale.label
                reg_code = (getattr(causale, "registro_iva", None) or "").strip()
                registro = registri.get(_norm_code(reg_code)) if reg_code else None
                tipo_reg = ""
                if registro is not None:
                    tipo_reg = (getattr(registro, "tipo_registro", None) or "").strip()
                items.append(
                    {
                        "code": code,
                        "label": f"{code} — {label}" if label else code,
                        "has_registro": bool(reg_code),
                        "tipo_registro": tipo_reg,
                        "is_autofattura_automatica": _flag_on(
                            getattr(causale, "autofattura", False)
                        ),
                        "is_autofattura": _flag_on(
                            getattr(causale, "iva_con_autofattura", False)
                        )
                        or _flag_on(getattr(causale, "autofattura", False)),
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
    registro_corrispettivi: bool = False,
    iva_autofattura: bool = False,
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
        if registro_corrispettivi:
            if not tipo_registro_is_corrispettivi(item.get("tipo_registro")):
                continue
        elif iva_autofattura:
            if not item.get("has_registro") or not item.get("is_autofattura"):
                continue
        elif con_registro_iva and not item.get("has_registro"):
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
    """Decodifica conti PDC o cliente/fornitore (e aliquote IVA sulle righe tipo 2)."""
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
        aliquota = iva_map.get(_norm_code(riga.codice_iva)) if iva else None
        riga.pdc = pdc
        riga.pdc_dare = pdc_dare
        riga.pdc_avere = pdc_avere
        riga.aliquota = aliquota
        riga.iva_label = (aliquota.label if aliquota else "") or ""
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
        if not pdc:
            partita_info = resolve_partita_clifor(riga.conto_partita)
            if partita_info.get("label"):
                riga.pdc = type("Lookup", (), {"label": partita_info["label"]})()
                riga.pdc_url = partita_info.get("url") or ""
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


def annotate_totale_documento(qs):
    """Totale in elenco Primanota: documento IVA (imponibile+IVA) o TotaleDare se Generico."""
    from django.db.models import (
        Case,
        F,
        FloatField,
        OuterRef,
        Q,
        Subquery,
        Sum,
        Value,
        When,
    )
    from django.db.models.functions import Coalesce

    from apps.primanota.models import Primanota, PrimanotaDettaglio

    line_imp = Case(
        When(
            Q(conto_avere__isnull=False) & ~Q(conto_avere=""),
            then=Coalesce(F("avere"), Value(0.0)),
        ),
        default=Coalesce(F("dare"), Value(0.0)),
        output_field=FloatField(),
    )
    righe = PrimanotaDettaglio.objects.filter(id_testa=OuterRef("pk")).exclude(
        dummy=True
    )
    tot_imp = Subquery(
        righe.annotate(_imp=line_imp)
        .values("id_testa")
        .annotate(_s=Sum("_imp"))
        .values("_s")[:1],
        output_field=FloatField(),
    )
    tot_iva = Subquery(
        righe.values("id_testa").annotate(_s=Sum("importo_iva")).values("_s")[:1],
        output_field=FloatField(),
    )
    tot_dare = Subquery(
        righe.values("id_testa").annotate(_s=Sum("dare")).values("_s")[:1],
        output_field=FloatField(),
    )
    return qs.annotate(
        _tot_imp=Coalesce(tot_imp, Value(0.0)),
        _tot_iva=Coalesce(tot_iva, Value(0.0)),
        _tot_dare=Coalesce(tot_dare, Value(0.0)),
    ).annotate(
        totale_documento_list=Case(
            When(
                tipo__in=(Primanota.TIPO_IVA, Primanota.TIPO_IVA_AUTOFATTURA),
                then=F("_tot_imp") + F("_tot_iva"),
            ),
            When(tipo=Primanota.TIPO_GENERICO, then=F("_tot_dare")),
            default=Value(None),
            output_field=FloatField(),
        )
    )
