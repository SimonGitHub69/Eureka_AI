from __future__ import annotations

import re
from datetime import date, datetime, time

from django import forms
from django.db import transaction
from django.forms import BaseModelFormSet, modelformset_factory
from django.utils import timezone

from apps.core.mirror_crud import SELECT, apply_control_widgets, delete_mirror_row, stamp_modifica
from apps.primanota.lookups import (
    causale_is_autofattura_automatica,
    causale_is_iva_autofattura,
    causale_is_registro_corrispettivi,
    causali_contabili_catalog,
    causali_contabili_choices,
    corrispettivi_extra_from_causale,
    registro_iva_choices,
    resolve_causale_contabile,
)
from apps.primanota.iva import calc_importo_iva
from apps.primanota.models import Primanota, PrimanotaDettaglio
from apps.primanota.scadenze import maybe_apply_scadenze
from apps.primanota.numerazione import (
    allocate_next_numero_reg,
    next_dettaglio_id,
    next_primanota_id,
)
from apps.primanota.protocollo import (
    allocate_next_protocollo,
    peek_next_protocollo,
    registro_from_causale,
)
from apps.valute.lookups import cambio_info, valuta_choices

_DATE = {"type": "date", "class": "form-control"}
_NUM = {"class": "form-control", "inputmode": "decimal", "step": "0.01"}
_NUM_GEN = {
    "class": "form-control text-end",
    "inputmode": "decimal",
    "placeholder": "0,00",
    "lang": "it-IT",
    "data-importo": "1",
    "autocomplete": "off",
}
_IMPORTO_MIGLIAIA = re.compile(r"^\d{1,3}(\.\d{3})+$")


class _RequiredChoiceSelect(forms.Select):
    """Opzione vuota non selezionabile (Django la inserisce se il model è blank)."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        if value in ("", None):
            option["attrs"]["disabled"] = True
            option["attrs"]["hidden"] = True
        return option


def parse_importo(value) -> float | None:
    """Accetta 20696.90, 20696,90 e 20.696,90."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif _IMPORTO_MIGLIAIA.fullmatch(s):
        s = s.replace(".", "")
    return float(s)


def format_importo(value) -> str:
    """20.696,90"""
    number = float(value)
    formatted = f"{number:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


class ImportoNumberInput(forms.TextInput):
    """Importo in stile italiano, con separatore migliaia."""

    def format_value(self, value):
        if value in (None, ""):
            return "0,00"
        try:
            return format_importo(value)
        except (TypeError, ValueError):
            return super().format_value(value)


class ImportoField(forms.FloatField):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", ImportoNumberInput(attrs=_NUM_GEN))
        super().__init__(**kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            parsed = parse_importo(value)
        except (TypeError, ValueError):
            raise forms.ValidationError("Inserire un importo valido.", code="invalid")
        if parsed is None:
            return None
        return parsed


SCAD_DATE_FIELDS = tuple(f"scad{i}" for i in range(1, 11))
DATE_FIELDS = ("data_reg", "data_doc", "data_valuta") + SCAD_DATE_FIELDS
SCAD_IMP_FIELDS = tuple(f"imp_scad{i}" for i in range(1, 11))
SCAD_RA_FIELDS = tuple(f"flag_ra{i:02d}" for i in range(1, 11))
SCADENZE_EDIT_FIELDS = SCAD_DATE_FIELDS + SCAD_IMP_FIELDS + SCAD_RA_FIELDS
BOOL_FIELDS = ("scadenze_ins",) + SCAD_RA_FIELDS


def _tipo_is_generico(tipo) -> bool:
    try:
        return int(tipo) == Primanota.TIPO_GENERICO
    except (TypeError, ValueError):
        return False


def _tipo_is_iva(tipo) -> bool:
    try:
        return int(tipo) in (Primanota.TIPO_IVA, Primanota.TIPO_IVA_AUTOFATTURA)
    except (TypeError, ValueError):
        return False


def _tipo_is_corrispettivi(tipo) -> bool:
    try:
        return int(tipo) == Primanota.TIPO_CORRISPETTIVI
    except (TypeError, ValueError):
        return False


def _tipo_is_iva_autofattura(tipo) -> bool:
    try:
        return int(tipo) == Primanota.TIPO_IVA_AUTOFATTURA
    except (TypeError, ValueError):
        return False


def _tipo_is_iva_layout(tipo) -> bool:
    return _tipo_is_iva(tipo) or _tipo_is_corrispettivi(tipo)


def _upper_clifor_code(value) -> str | None:
    """Codici cliente/fornitore (C7310, F2082) sempre in maiuscolo; PDC invariato."""
    code = (value or "").strip()
    if not code:
        return None
    if code[0].isalpha():
        return code.upper()
    return code


def _form_tipo(form: "PrimanotaForm") -> int | None:
    if form.instance and getattr(form.instance, "pk", None) and getattr(
        form.instance, "tipo", None
    ) not in (None, ""):
        raw = form.instance.tipo
    elif form.is_bound:
        raw = form.data.get("tipo")
    elif form.instance and form.instance.pk:
        raw = form.instance.tipo
    else:
        raw = form.initial.get("tipo")
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _scadenze_ins_active(form: "PrimanotaForm") -> bool:
    if form.is_bound:
        return form.data.get("scadenze_ins") in ("on", "true", "1")
    if getattr(form.instance, "pk", None):
        return bool(form.instance.scadenze_ins)
    return bool(form.initial.get("scadenze_ins"))


def _dt_to_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _alla_data_cambio(form) -> date | None:
    """Data di registrazione: il listino 4D è quello vigente in quella data."""
    if form.is_bound:
        raw = (form.data.get("data_reg") or "").strip()
        if raw:
            try:
                return date.fromisoformat(raw[:10])
            except ValueError:
                pass
    if form.instance is not None:
        found = _dt_to_date(getattr(form.instance, "data_reg", None))
        if found:
            return found
    if getattr(form, "is_create", False):
        return timezone.localdate()
    return None


def _date_to_dt(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        d = _dt_to_date(value)
    elif isinstance(value, date):
        d = value
    else:
        return None
    if d is None:
        return None
    return datetime.combine(d, time.min)


class PrimanotaForm(forms.ModelForm):
    causale = forms.ChoiceField(
        label="Causale",
        required=True,
        choices=[("", "—")],
        widget=forms.Select(attrs=SELECT),
        error_messages={"required": "Campo obbligatorio."},
    )
    registro = forms.ChoiceField(
        label="Registro",
        required=False,
        choices=[("", "—")],
        widget=forms.Select(attrs=SELECT),
    )
    valuta = forms.ChoiceField(
        label="Valuta",
        required=False,
        choices=[("", "—")],
        widget=forms.Select(attrs=SELECT),
    )
    causale_incasso = forms.CharField(
        required=False,
        label="Causale di incasso dei corrispettivi di vendita",
    )
    data_cambio = forms.DateField(
        required=False,
        label="Data cambio",
        disabled=True,
        input_formats=["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"],
        widget=forms.DateInput(attrs=_DATE, format="%Y-%m-%d"),
    )
    cambio = forms.FloatField(
        required=False,
        label="Cambio",
        disabled=True,
        widget=forms.NumberInput(attrs={**_NUM, "step": "0.000001"}),
    )

    class Meta:
        model = Primanota
        fields = [
            "tipo",
            "numero_reg",
            "data_reg",
            "causale",
            "numero_doc",
            "data_doc",
            "data_valuta",
            "codice_partita",
            "registro",
            "numero_prot",
            "alfa_prot",
            "codice_paga",
            "fornitore_cee",
            "valuta",
            "acconto",
            "scadenze_ins",
            *SCAD_DATE_FIELDS,
            *SCAD_IMP_FIELDS,
            *SCAD_RA_FIELDS,
        ]
        labels = {
            "tipo": "Tipo di movimento",
            "numero_reg": "Registrazione n°",
            "data_reg": "Data registrazione",
            "causale": "Causale",
            "numero_doc": "Documento n°",
            "data_doc": "Data documento",
            "data_valuta": "Competenza",
            "codice_partita": "Codice Partita",
            "registro": "Registro",
            "numero_prot": "Protocollo numero",
            "alfa_prot": "Serie protocollo",
            "codice_paga": "Condizione di pagamento",
            "fornitore_cee": "Fornitore",
            "valuta": "Valuta",
            "acconto": "Acconto",
            "scadenze_ins": "Scadenze e importi inseribili manualmente",
        }
        widgets = {
            **{name: forms.DateInput(attrs=_DATE, format="%Y-%m-%d") for name in DATE_FIELDS},
            "tipo": _RequiredChoiceSelect(),
            "acconto": forms.NumberInput(attrs=_NUM),
            **{name: forms.NumberInput(attrs=_NUM) for name in SCAD_IMP_FIELDS},
            **{name: forms.CheckboxInput() for name in BOOL_FIELDS},
        }

    def __init__(self, *args, is_create: bool = False, **kwargs):
        self.is_create = is_create
        super().__init__(*args, **kwargs)
        self.fields["tipo"].required = True
        self.fields["tipo"].choices = list(Primanota.TIPO_CHOICES)
        if self.instance and self.instance.pk and self.instance.tipo not in (None, ""):
            self.fields["tipo"].disabled = True
        for name in self.fields:
            if name != "tipo":
                self.fields[name].required = False
        self.fields["causale"].required = True
        self.fields["causale"].error_messages["required"] = "Campo obbligatorio."
        self.fields["data_reg"].required = True
        self.fields["data_reg"].error_messages["required"] = "Campo obbligatorio."
        for i, name in enumerate(SCAD_DATE_FIELDS, start=1):
            self.fields[name].label = f"Scadenza {i}"
        for i, name in enumerate(SCAD_IMP_FIELDS, start=1):
            self.fields[name].label = f"Importo {i}"
        for i, name in enumerate(SCAD_RA_FIELDS, start=1):
            self.fields[name].label = f"Rit. acc. {i}"
        for name in DATE_FIELDS:
            self.fields[name].input_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"]
            current = self.initial.get(name, getattr(self.instance, name, None))
            self.initial[name] = _dt_to_date(current)
        # 4D lascia spesso Scad* vuote con ScadenzeIns=No: mostra le date calcolate.
        if (
            self.instance
            and self.instance.pk
            and not self.is_bound
            and not self.instance.scadenze_ins
        ):
            from apps.primanota.scadenze import enrich_scadenze_dates

            for row in enrich_scadenze_dates(self.instance):
                key = f"scad{row['n']}"
                if row.get("data") is not None and self.initial.get(key) is None:
                    self.initial[key] = row["data"]
        apply_control_widgets(self)
        for name in DATE_FIELDS:
            self.fields[name].widget.attrs["type"] = "date"
            self.fields[name].widget.format = "%Y-%m-%d"
        current_causale = ""
        if self.is_bound:
            current_causale = (self.data.get("causale") or "").strip()
        elif self.instance and getattr(self.instance, "causale", None):
            current_causale = (self.instance.causale or "").strip()
        else:
            current_causale = (self.initial.get("causale") or "").strip()
        is_generico = _tipo_is_generico(_form_tipo(self))
        is_iva = _tipo_is_iva(_form_tipo(self))
        is_corrispettivi = _tipo_is_corrispettivi(_form_tipo(self))
        is_iva_autofattura = _tipo_is_iva_autofattura(_form_tipo(self))
        is_iva_layout = is_iva or is_corrispettivi
        try:
            self.causali_catalog = causali_contabili_catalog()
        except Exception:
            self.causali_catalog = []
        self.fields["causale"].choices = causali_contabili_choices(
            current_causale,
            senza_registro_iva=is_generico,
            con_registro_iva=is_iva and not is_iva_autofattura,
            registro_corrispettivi=is_corrispettivi,
            iva_autofattura=is_iva_autofattura,
            catalog=self.causali_catalog,
        )
        current_registro = ""
        if not is_generico:
            if self.is_bound:
                current_registro = registro_from_causale(
                    resolve_causale_contabile(current_causale)
                )
                if current_registro:
                    self.initial["registro"] = current_registro
                    if self.is_create:
                        peeked = peek_next_protocollo(current_registro)
                        if peeked is not None:
                            self.initial["numero_prot"] = peeked
            elif self.instance and getattr(self.instance, "registro", None):
                current_registro = (self.instance.registro or "").strip()
            if not current_registro:
                current_registro = (self.initial.get("registro") or "").strip()
        self.fields["registro"].choices = registro_iva_choices(current_registro)
        self.fields["registro"].disabled = True
        current_valuta = ""
        if self.is_bound:
            current_valuta = (self.data.get("valuta") or "").strip()
        elif self.instance and getattr(self.instance, "valuta", None):
            current_valuta = (self.instance.valuta or "").strip()
        if not current_valuta:
            current_valuta = (self.initial.get("valuta") or "").strip()
        self.fields["valuta"].choices = valuta_choices(current_valuta)
        try:
            info = cambio_info(current_valuta, alla_data=_alla_data_cambio(self))
        except Exception:
            info = {"cambio": None, "data": None}
        if not self.is_bound:
            if info.get("cambio") is not None:
                self.initial.setdefault("cambio", info["cambio"])
            if info.get("data") is not None:
                self.initial.setdefault("data_cambio", info["data"])
        self.fields["data_cambio"].widget.attrs["type"] = "date"
        self.fields["data_cambio"].widget.format = "%Y-%m-%d"
        if self.is_create and not is_generico:
            self.fields["numero_prot"].widget.attrs["readonly"] = True
        extras = {"incasso_code": ""}
        if current_causale:
            try:
                extras = corrispettivi_extra_from_causale(
                    resolve_causale_contabile(current_causale)
                )
            except Exception:
                extras = {"incasso_code": ""}
        if not self.is_bound:
            self.initial.setdefault("causale_incasso", extras.get("incasso_code") or "")
        editable = _scadenze_ins_active(self)
        for name in SCADENZE_EDIT_FIELDS:
            self.fields[name].disabled = not editable

    def scadenze_editable(self) -> bool:
        return _scadenze_ins_active(self)

    def clean_tipo(self):
        tipo = self.cleaned_data.get("tipo")
        if tipo in (None, ""):
            raise forms.ValidationError("Selezionare il tipo di movimento.")
        try:
            key = int(tipo)
        except (TypeError, ValueError):
            raise forms.ValidationError("Selezionare il tipo di movimento.")
        if key not in dict(Primanota.TIPO_CHOICES):
            raise forms.ValidationError("Selezionare il tipo di movimento.")
        return key

    def clean_causale(self):
        code = (self.cleaned_data.get("causale") or "").strip() or None
        if not code:
            return None
        causale = resolve_causale_contabile(code)
        if _tipo_is_generico(_form_tipo(self)):
            if causale and (causale.registro_iva or "").strip():
                raise forms.ValidationError(
                    "Per il tipo Generico scegliere una causale senza registro IVA."
                )
        elif _tipo_is_corrispettivi(_form_tipo(self)):
            if not causale_is_registro_corrispettivi(causale):
                raise forms.ValidationError(
                    "Per i corrispettivi scegliere una causale con registro IVA "
                    "di tipo Corrispettivi."
                )
        elif _tipo_is_iva_autofattura(_form_tipo(self)):
            if not causale_is_iva_autofattura(causale):
                raise forms.ValidationError(
                    "Per Iva con Autofattura scegliere una causale con flag "
                    "IVA con autofattura (o Autofattura) e registro IVA."
                )
        elif _tipo_is_iva(_form_tipo(self)):
            if not causale or not (causale.registro_iva or "").strip():
                raise forms.ValidationError(
                    "Scegliere una causale con registro IVA."
                )
        return code

    def clean_registro(self):
        return (self.cleaned_data.get("registro") or "").strip() or None

    def clean_valuta(self):
        return (self.cleaned_data.get("valuta") or "").strip() or None

    def clean(self):
        data = super().clean()
        for name in DATE_FIELDS:
            data[name] = _date_to_dt(data.get(name))
        if not (data.get("causale") or "").strip() and not self.errors.get("causale"):
            self.add_error("causale", "Campo obbligatorio.")
        if not data.get("data_reg") and not self.errors.get("data_reg"):
            self.add_error("data_reg", "Campo obbligatorio.")
        if _tipo_is_generico(data.get("tipo")):
            data["registro"] = None
            data["numero_prot"] = None
            data["alfa_prot"] = None
            data["codice_partita"] = None
            data["codice_paga"] = None
            data["valuta"] = None
            data["acconto"] = None
            data["scadenze_ins"] = False
            for name in SCADENZE_EDIT_FIELDS:
                data[name] = None
        elif _tipo_is_corrispettivi(data.get("tipo")):
            data["codice_partita"] = None
            data["codice_paga"] = None
            data["acconto"] = None
            data["scadenze_ins"] = False
            for name in SCADENZE_EDIT_FIELDS:
                data[name] = None
            causale_code = data.get("causale")
            if causale_code:
                registro = registro_from_causale(
                    resolve_causale_contabile(causale_code)
                )
                data["registro"] = registro or None
        else:
            causale_code = data.get("causale")
            if causale_code:
                registro = registro_from_causale(
                    resolve_causale_contabile(causale_code)
                )
                data["registro"] = registro or None
        partita = data.get("codice_partita")
        if partita not in (None, ""):
            data["codice_partita"] = _upper_clifor_code(partita)
        if _tipo_is_iva_autofattura(data.get("tipo")):
            if causale_is_autofattura_automatica(
                resolve_causale_contabile(data.get("causale"))
            ):
                fornitore = data.get("fornitore_cee")
                if fornitore not in (None, ""):
                    data["fornitore_cee"] = _upper_clifor_code(fornitore)
            else:
                data["fornitore_cee"] = None
        else:
            data["fornitore_cee"] = None
        if self.is_create and not data.get("data_valuta") and data.get("data_reg"):
            data["data_valuta"] = data["data_reg"]
        if (
            not _tipo_is_generico(data.get("tipo"))
            and not _tipo_is_corrispettivi(data.get("tipo"))
            and not data.get("scadenze_ins")
            and getattr(self.instance, "pk", None)
        ):
            for name in SCADENZE_EDIT_FIELDS:
                data[name] = getattr(self.instance, name, None)
        return data

    def scadenza_slots(self) -> list[dict]:
        return [
            {
                "n": i,
                "data": self[f"scad{i}"],
                "importo": self[f"imp_scad{i}"],
                "rit": self[f"flag_ra{i:02d}"],
            }
            for i in range(1, 11)
        ]


class PrimanotaRigaForm(forms.ModelForm):
    conto_partita = forms.CharField(required=False, label="C/Partita")
    imp_val = ImportoField(label="Imponibile Valuta")
    imponibile = ImportoField(label="Imponibile")
    importo_iva = ImportoField(label="Importo IVA")
    dare = ImportoField(label="Dare")
    avere = ImportoField(label="Avere")

    class Meta:
        model = PrimanotaDettaglio
        fields = [
            "pos",
            "conto_dare",
            "dare",
            "conto_avere",
            "avere",
            "imp_val",
            "codice_iva",
            "importo_iva",
            "descrizione",
            "anno_doc",
        ]
        labels = {
            "pos": "Pos.",
            "conto_dare": "Conto dare",
            "dare": "Dare",
            "conto_avere": "Conto avere",
            "avere": "Avere",
            "imp_val": "Imponibile Valuta",
            "codice_iva": "C. IVA",
            "importo_iva": "Importo IVA",
            "descrizione": "Descrizione aggiuntiva",
            "anno_doc": "Anno doc",
        }
        widgets = {
            "pos": forms.HiddenInput(),
        }

    def __init__(self, *args, strict: bool = False, is_iva: bool = False, **kwargs):
        self.strict = strict
        self.is_iva = is_iva
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = False
        inst = self.instance
        if inst is not None and inst.pk:
            self.fields["conto_partita"].initial = inst.conto_partita
            impon = inst.imponibile
            self.fields["imponibile"].initial = impon if impon else None
            stored_val = getattr(inst, "imp_val", None)
            if stored_val in (None, 0, 0.0) and impon:
                self.fields["imp_val"].initial = impon
        apply_control_widgets(self)

    def _field_code(self, name: str, virtual: str | None = None) -> str:
        key = virtual or name
        if self.is_bound:
            return (self.data.get(key) or "").strip()
        if virtual == "conto_partita" and self.instance and self.instance.pk:
            return self.instance.conto_partita
        if self.instance and self.instance.pk:
            return (getattr(self.instance, name, None) or "").strip()
        return (self.initial.get(key) or "").strip()

    def linked_labels(self) -> dict[str, str]:
        from apps.articoli.lookups import resolve_descrizione

        return {
            "conto_partita": resolve_descrizione(
                "pdc_clifor", self._field_code("conto_partita", "conto_partita")
            ),
            "conto_dare": resolve_descrizione("pdc_clifor", self._field_code("conto_dare")),
            "conto_avere": resolve_descrizione("pdc_clifor", self._field_code("conto_avere")),
            "codice_iva": resolve_descrizione("iva", self._field_code("codice_iva")),
        }

    def _apply_importo_iva(self, data: dict) -> None:
        codice_iva = (data.get("codice_iva") or "").strip()
        if not codice_iva:
            return
        # Layout IVA usa Imponibile (formset create non passava is_iva → dare/avere vuoti).
        base = data.get("imponibile")
        if base in (None, ""):
            if data.get("dare") not in (None, ""):
                base = data.get("dare")
            elif data.get("avere") not in (None, ""):
                base = data.get("avere")
            else:
                base = None
        calc = calc_importo_iva(base, codice_iva)
        if calc is not None:
            data["importo_iva"] = calc

    def clean(self):
        data = super().clean()
        partita = (data.get("conto_partita") or "").strip()
        if partita:
            partita = _upper_clifor_code(partita)
            data["conto_partita"] = partita
        imp_val = data.get("imp_val")
        imponibile = data.get("imponibile")

        def _empty_importo(val) -> bool:
            return val in (None, "") or float(val or 0) == 0

        if not _empty_importo(imp_val) and _empty_importo(imponibile):
            imponibile = imp_val
            data["imponibile"] = imponibile
        elif not _empty_importo(imponibile) and _empty_importo(imp_val):
            data["imp_val"] = imponibile
        if partita or self.is_iva:
            inst = self.instance
            use_dare = bool((getattr(inst, "conto_dare", None) or "").strip()) and not (
                getattr(inst, "conto_avere", None) or ""
            ).strip()
            if partita:
                if use_dare:
                    data["conto_dare"] = partita
                    if imponibile not in (None, ""):
                        data["dare"] = imponibile
                else:
                    data["conto_avere"] = partita
                    if imponibile not in (None, ""):
                        data["avere"] = imponibile
        for name in ("conto_dare", "conto_avere"):
            val = data.get(name)
            if val not in (None, ""):
                data[name] = _upper_clifor_code(val)
        self._apply_importo_iva(data)
        if self.is_iva and not _riga_vuota(data):
            if not (data.get("conto_partita") or "").strip():
                self.add_error("conto_partita", "Campo obbligatorio.")
        if self.strict:
            if self.is_iva:
                if not (data.get("conto_partita") or "").strip():
                    self.add_error("conto_partita", "Campo obbligatorio.")
                if _empty_importo(data.get("imponibile")) and _empty_importo(
                    data.get("importo_iva")
                ):
                    self.add_error(
                        "imponibile",
                        "Inserire almeno un imponibile o un importo IVA.",
                    )
            else:
                dare_ok = (data.get("conto_dare") or "").strip() and data.get("dare") not in (
                    None,
                    "",
                )
                avere_ok = (data.get("conto_avere") or "").strip() and data.get(
                    "avere"
                ) not in (None, "")
                if not dare_ok and not avere_ok:
                    raise forms.ValidationError(
                        "Inserire almeno un conto dare o avere con importo."
                    )
        return data


def _riga_vuota(cleaned: dict) -> bool:
    if cleaned.get("DELETE"):
        return True
    keys = (
        "conto_dare",
        "conto_avere",
        "conto_partita",
        "descrizione",
        "codice_iva",
        "anno_doc",
    )
    if any(str(cleaned.get(k) or "").strip() for k in keys):
        return False
    for key in ("dare", "avere", "imp_val", "imponibile", "importo_iva"):
        val = cleaned.get(key)
        if val not in (None, "") and float(val or 0) != 0:
            return False
    return True


def _importo_presente(val) -> bool:
    if val in (None, ""):
        return False
    try:
        return float(val) != 0
    except (TypeError, ValueError):
        return False


def _fmt_sbilancio(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _sbilancio_from_formset(formset) -> float:
    tot_dare = tot_avere = 0.0
    for form in getattr(formset, "forms", None) or []:
        if getattr(formset, "can_delete", False) and formset._should_delete_form(form):
            continue
        cleaned = getattr(form, "cleaned_data", None)
        if not isinstance(cleaned, dict) or _riga_vuota(cleaned):
            continue
        tot_dare += float(cleaned.get("dare") or 0)
        tot_avere += float(cleaned.get("avere") or 0)
    return round(tot_dare - tot_avere, 2)


class PrimanotaRigaFormSet(BaseModelFormSet):
    require_balance = False
    is_iva = False

    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        if self.require_balance:
            sbilancio = _sbilancio_from_formset(self)
            if abs(sbilancio) > 0.005:
                raise forms.ValidationError(
                    "La registrazione è sbilanciata (sbilancio € %(importo)s). "
                    "Totale Dare e Totale Avere devono coincidere."
                    % {"importo": _fmt_sbilancio(sbilancio)}
                )
        if not self.is_iva:
            return
        has_importo = False
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not isinstance(data, dict) or data.get("DELETE"):
                continue
            if _riga_vuota(data):
                continue
            if _importo_presente(data.get("imponibile")) or _importo_presente(
                data.get("importo_iva")
            ):
                has_importo = True
        if not has_importo:
            raise forms.ValidationError(
                "Inserire almeno un imponibile o un importo IVA."
            )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            return
        pos = 10
        for form in self.forms:
            inst = form.instance
            if inst.pk and inst.pos is not None:
                form.initial["pos"] = inst.pos
                pos = int(inst.pos) + 10
            else:
                form.initial["pos"] = pos
                pos += 10


def riga_formset_for(data=None, queryset=None, *, is_iva: bool = False, extra=None, **kwargs):
    form_kwargs = dict(kwargs.pop("form_kwargs", None) or {})
    form_kwargs["is_iva"] = is_iva
    if queryset is None:
        queryset = PrimanotaDettaglio.objects.none()
    if extra is None:
        extra = 1
        try:
            extra = 0 if queryset.exists() else 1
        except Exception:
            extra = 1
    factory = modelformset_factory(
        PrimanotaDettaglio,
        form=PrimanotaRigaForm,
        formset=PrimanotaRigaFormSet,
        extra=extra,
        can_delete=True,
        min_num=0,
        validate_min=False,
    )
    formset = factory(
        data, queryset=queryset, prefix="righe", form_kwargs=form_kwargs, **kwargs
    )
    formset.require_balance = not is_iva
    formset.is_iva = is_iva
    return formset


def next_pos_for_testa(id_testa: int) -> int:
    max_pos = 0
    for pos in (
        PrimanotaDettaglio.objects.filter(id_testa=id_testa)
        .exclude(dummy=True)
        .values_list("pos", flat=True)
    ):
        if pos is not None and int(pos) > max_pos:
            max_pos = int(pos)
    return max_pos + 10 if max_pos else 10


def save_single_riga(registrazione: Primanota, form: PrimanotaRigaForm) -> PrimanotaDettaglio:
    with transaction.atomic():
        riga = form.save(commit=False)
        riga.id_testa = registrazione.id
        riga.dummy = False
        if not riga.pk:
            riga.id = next_dettaglio_id()
            if riga.pos in (None, ""):
                riga.pos = next_pos_for_testa(registrazione.id)
        stamp_modifica(riga)
        riga.save()
        stamp_modifica(registrazione)
        registrazione.save()
    return riga


def save_primanota_with_righe(form: PrimanotaForm, formset: PrimanotaRigaFormSet) -> Primanota:
    with transaction.atomic():
        adding = not form.instance.pk
        obj = form.save(commit=False)
        if adding:
            obj.id = next_primanota_id()
            if not obj.data_reg:
                obj.data_reg = _date_to_dt(timezone.localdate())
            obj.numero_reg = allocate_next_numero_reg(obj.data_reg)
            if not _tipo_is_generico(obj.tipo) and obj.registro:
                prot = allocate_next_protocollo(obj.registro, obj.data_reg)
                if prot is not None:
                    obj.numero_prot = prot
        if not _tipo_is_generico(obj.tipo):
            maybe_apply_scadenze(obj, formset)
        stamp_modifica(obj)
        if adding:
            obj.save()
        else:
            update_fields = [
                name
                for name in form.Meta.fields
                if name in form.fields and name in form.cleaned_data
            ]
            if not obj.scadenze_ins:
                for name in SCAD_DATE_FIELDS + SCAD_IMP_FIELDS:
                    if name not in update_fields:
                        update_fields.append(name)
            if "synced_at" not in update_fields:
                update_fields.append("synced_at")
            obj.save(update_fields=update_fields)

        for f in formset.deleted_forms:
            if f.instance.pk:
                delete_mirror_row(PrimanotaDettaglio, f.instance.pk)

        next_id = next_dettaglio_id()
        pos = 10
        for f in formset.forms:
            if f in formset.deleted_forms:
                continue
            if not hasattr(f, "cleaned_data") or not f.cleaned_data:
                continue
            if _riga_vuota(f.cleaned_data):
                if f.instance.pk:
                    delete_mirror_row(PrimanotaDettaglio, f.instance.pk)
                continue
            riga = f.save(commit=False)
            riga.id_testa = obj.id
            riga.dummy = False
            riga.pos = pos
            pos += 10
            if not riga.pk:
                riga.id = next_id
                next_id += 1
            stamp_modifica(riga)
            riga.save()
    return obj


def delete_primanota(registrazione: Primanota) -> None:
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            "DELETE FROM primanota_dettaglio WHERE id_added_by_converter = %s",
            [registrazione.id],
        )
    delete_mirror_row(Primanota, registrazione.id)
