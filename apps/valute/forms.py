from __future__ import annotations

from datetime import date, datetime, time, timezone as dt_timezone

from django import forms
from django.db import connection, transaction
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk, stamp_modifica
from apps.valute.models import Valuta, ValutaDet

_DATE = {"type": "date", "class": "form-control"}
_NUMBER = {"class": "form-control", "inputmode": "decimal", "step": "0.0001"}


def next_valuta_det_id() -> int:
    with connection.cursor() as cur:
        cur.execute('SELECT COALESCE(MAX("ID"), 0) FROM valuta_det')
        return int(cur.fetchone()[0] or 0) + 1


def _det_row_empty(cleaned: dict) -> bool:
    if cleaned.get("DELETE"):
        return True
    return cleaned.get("data") in (None, "") and cleaned.get("cambio") in (None, "")


def det_value_to_date(value) -> date | None:
    """Converte timestamp mirror (anche spostati da UTC) in data di calendario locale."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        if value.time() != time.min:
            # Valori salvati come UTC naive (es. 22:00 = mezzanotte Europe/Rome).
            aware = timezone.make_aware(value, dt_timezone.utc)
            return timezone.localtime(aware).date()
        return value.date()
    if isinstance(value, date):
        return value
    return None


def date_to_det_value(value) -> datetime | None:
    """Salva sempre mezzanotte naive sulla data scelta (niente shift UTC)."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        d = det_value_to_date(value)
    elif isinstance(value, date):
        d = value
    else:
        return None
    if d is None:
        return None
    return datetime.combine(d, time.min)


class ValutaForm(forms.ModelForm):
    class Meta:
        model = Valuta
        fields = ["codice", "descrizione", "abbrev"]
        labels = {
            "codice": "Codice valuta",
            "descrizione": "Descrizione",
            "abbrev": "Abbreviazione",
        }
        widgets = {
            "abbrev": forms.TextInput(attrs={"maxlength": "8"}),
            "codice": forms.TextInput(attrs={"maxlength": "16"}),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        self.fields["abbrev"].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self)


class ValutaDetForm(forms.ModelForm):
    data = forms.DateField(
        required=False,
        label="Data",
        input_formats=["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"],
        widget=forms.DateInput(attrs=_DATE, format="%Y-%m-%d"),
    )

    class Meta:
        model = ValutaDet
        fields = ["data", "cambio"]
        labels = {
            "data": "Data",
            "cambio": "Cambio (€)",
        }
        widgets = {
            "cambio": forms.NumberInput(attrs=_NUMBER),
        }

    def __init__(self, *args, strict: bool = False, **kwargs):
        self.strict = strict
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = False
        self.fields["data"].widget.format = "%Y-%m-%d"
        if self.instance is not None and self.instance.pk and "data" not in self.initial:
            self.initial["data"] = det_value_to_date(self.instance.data)
        elif self.instance is not None and self.instance.data is not None:
            self.initial["data"] = det_value_to_date(
                self.initial.get("data", self.instance.data)
            )
        apply_control_widgets(self)

    def clean_data(self):
        return date_to_det_value(self.cleaned_data.get("data"))

    def clean(self):
        cleaned = super().clean()
        if not self.strict:
            return cleaned
        if cleaned.get("data") in (None, "") and cleaned.get("cambio") in (None, ""):
            raise forms.ValidationError("Inserire data e cambio.")
        if cleaned.get("data") in (None, ""):
            self.add_error("data", "Campo obbligatorio.")
        if cleaned.get("cambio") in (None, ""):
            self.add_error("cambio", "Campo obbligatorio.")
        return cleaned


class ValutaDetInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()


ValutaDetFormSet = inlineformset_factory(
    Valuta,
    ValutaDet,
    form=ValutaDetForm,
    formset=ValutaDetInlineFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


def save_valuta_with_cambi(form: ValutaForm, formset: ValutaDetInlineFormSet) -> Valuta:
    with transaction.atomic():
        valuta = form.save(commit=False)
        if getattr(valuta, "dummy", None) is None:
            valuta.dummy = False
        stamp_modifica(valuta)
        valuta.save()
        formset.instance = valuta

        for f in formset.deleted_forms:
            if f.instance.pk is not None:
                f.instance.delete()

        next_id = next_valuta_det_id()
        for f in formset.forms:
            if f in formset.deleted_forms:
                continue
            if not hasattr(f, "cleaned_data") or not f.cleaned_data:
                continue
            if _det_row_empty(f.cleaned_data):
                continue
            obj = f.save(commit=False)
            obj.valuta = valuta
            obj.data = date_to_det_value(obj.data)
            if obj.pk is None:
                obj.id = next_id
                next_id += 1
            stamp_modifica(obj)
            obj.save()
    return valuta


def save_single_cambio(valuta: Valuta, form: ValutaDetForm) -> ValutaDet:
    with transaction.atomic():
        obj = form.save(commit=False)
        obj.valuta = valuta
        obj.data = form.cleaned_data.get("data")
        if obj.pk is None:
            obj.id = next_valuta_det_id()
        stamp_modifica(obj)
        obj.save()
        stamp_modifica(valuta)
        valuta.save()
    return obj
