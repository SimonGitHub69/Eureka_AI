from datetime import date, datetime

from django import forms

from apps.articoli.lookups import resolve_articolo
from apps.core.mirror_crud import apply_control_widgets
from apps.set_articoli.models import SetArticoloD, SetArticoloH


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return value


class SetArticoloHForm(forms.ModelForm):
    class Meta:
        model = SetArticoloH
        fields = [
            "numero_set",
            "nome_set",
            "data_set",
            "fornitore",
            "note",
            "controllo_doc",
            "note_controllo",
            "disattivato",
        ]
        labels = {
            "numero_set": "Numero",
            "nome_set": "Nome set",
            "data_set": "Data",
            "fornitore": "Fornitore",
            "note": "Note",
            "controllo_doc": "Controllo documento",
            "note_controllo": "Note controllo",
            "disattivato": "Disattivato",
        }
        widgets = {
            "numero_set": forms.NumberInput(),
            "data_set": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "note": forms.Textarea(attrs={"rows": 3}),
            "note_controllo": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome_set"].required = True
        self.fields["data_set"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        for name in self.fields:
            if name != "nome_set":
                self.fields[name].required = False
        instance = kwargs.get("instance")
        if instance and instance.data_set and not self.is_bound:
            self.initial["data_set"] = _as_date(instance.data_set)
        apply_control_widgets(self, keep_textarea={"note_controllo"})

    def clean_data_set(self):
        value = self.cleaned_data.get("data_set")
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())
        return value


class SetArticoloDForm(forms.ModelForm):
    class Meta:
        model = SetArticoloD
        fields = ["cod_art", "desc_art", "qta", "um", "pos"]
        labels = {
            "cod_art": "Codice articolo",
            "desc_art": "Descrizione",
            "qta": "Quantità",
            "um": "U.M.",
            "pos": "Posizione",
        }
        widgets = {
            "qta": forms.NumberInput(),
            "pos": forms.NumberInput(),
        }

    def __init__(self, *args, testa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.testa = testa
        if self.testa is None and getattr(self.instance, "testa_id", None):
            self.testa = self.instance.testa
        self.fields["cod_art"].required = True
        for name in self.fields:
            if name != "cod_art":
                self.fields[name].required = False
        apply_control_widgets(self)

    def clean(self):
        cleaned = super().clean()
        codice = (cleaned.get("cod_art") or "").strip()
        cleaned["cod_art"] = codice
        if codice:
            info = resolve_articolo(codice)
            if info.get("found"):
                cleaned["cod_art"] = info["codice"] or codice
                if not (cleaned.get("desc_art") or "").strip():
                    cleaned["desc_art"] = info.get("descrizione") or ""
                if not (cleaned.get("um") or "").strip():
                    cleaned["um"] = info.get("unita_misura") or ""
            codice = cleaned["cod_art"]
            if self.testa is not None and codice:
                qs = SetArticoloD.objects.filter(
                    testa=self.testa,
                    cod_art__iexact=codice,
                )
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    self.add_error(
                        "cod_art",
                        f"Il codice «{codice}» è già presente in questo set.",
                    )
        return cleaned
