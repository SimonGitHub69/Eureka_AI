from django import forms

from apps.condizioni.models import MODALITA_PAGAMENTO_SDI, Condizione
from apps.core.mirror_crud import apply_control_widgets

_CONTROL = {"class": "form-control"}
_SELECT = {"class": "form-select"}
_NUMBER = {"class": "form-control", "inputmode": "numeric"}

SDI_CHOICES = [("", "—")] + [
    (code, f"{code} - {label}") for code, label in MODALITA_PAGAMENTO_SDI.items()
]


class CondizioneForm(forms.ModelForm):
    pag_fatt_elett_pa = forms.ChoiceField(
        label="Modalità pagamento SDI",
        required=False,
        choices=SDI_CHOICES,
        widget=forms.Select(attrs=_SELECT),
    )

    class Meta:
        model = Condizione
        fields = [
            "codice",
            "descrizione",
            "tipo_pagamento",
            "numero_rate",
            "prima_rata",
            "intervallo",
            "fine_mese",
            "giorno_fisso",
            "mese_esclusione",
            "mese_esclusione2",
            "gg_mese_esclus",
            "gg_mese_esclus2",
            "codice_banca",
            "pag_fatt_elett_pa",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "tipo_pagamento": "Tipo pagamento",
            "numero_rate": "N. rate",
            "prima_rata": "Prima rata (giorni)",
            "intervallo": "Intervallo (giorni)",
            "fine_mese": "Fine mese",
            "giorno_fisso": "Giorno fisso",
            "mese_esclusione": "Mese esclusione 1",
            "mese_esclusione2": "Mese esclusione 2",
            "gg_mese_esclus": "GG mese esclus. 1",
            "gg_mese_esclus2": "GG mese esclus. 2",
            "codice_banca": "Codice banca",
            "pag_fatt_elett_pa": "Modalità pagamento SDI",
        }
        widgets = {
            "codice": forms.TextInput(attrs={**_CONTROL, "autocomplete": "off"}),
            "descrizione": forms.TextInput(attrs={**_CONTROL, "autocomplete": "off"}),
            "tipo_pagamento": forms.TextInput(attrs={**_CONTROL, "autocomplete": "off"}),
            "numero_rate": forms.NumberInput(attrs=_NUMBER),
            "prima_rata": forms.NumberInput(attrs=_NUMBER),
            "intervallo": forms.NumberInput(attrs=_NUMBER),
            "fine_mese": forms.CheckboxInput(),
            "giorno_fisso": forms.NumberInput(attrs={**_NUMBER, "min": 1, "max": 31}),
            "mese_esclusione": forms.NumberInput(attrs={**_NUMBER, "min": 0, "max": 12}),
            "mese_esclusione2": forms.NumberInput(attrs={**_NUMBER, "min": 0, "max": 12}),
            "gg_mese_esclus": forms.NumberInput(attrs={**_NUMBER, "min": 0, "max": 31}),
            "gg_mese_esclus2": forms.NumberInput(attrs={**_NUMBER, "min": 0, "max": 31}),
            "codice_banca": forms.TextInput(attrs={**_CONTROL, "autocomplete": "off"}),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        choices = list(SDI_CHOICES)
        current = ""
        if self.is_bound:
            current = (self.data.get("pag_fatt_elett_pa") or "").strip().upper()
        elif self.instance and self.instance.pk:
            current = (self.instance.pag_fatt_elett_pa or "").strip().upper()
        if current and current not in dict(choices):
            choices.append((current, current))
        self.fields["pag_fatt_elett_pa"].choices = choices
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in (
            "numero_rate",
            "prima_rata",
            "intervallo",
            "giorno_fisso",
            "mese_esclusione",
            "mese_esclusione2",
            "gg_mese_esclus",
            "gg_mese_esclus2",
            "tipo_pagamento",
            "codice_banca",
        ):
            self.fields[name].required = False
        self.fields["fine_mese"].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."
        self._apply_fine_mese_giorno_fisso()

    def _fine_mese_attivo(self) -> bool:
        if self.is_bound:
            return self.data.get("fine_mese") in {"on", "true", "1", "True"}
        if self.instance and self.instance.pk:
            return bool(self.instance.fine_mese)
        return False

    def _lock_giorno_fisso(self) -> None:
        field = self.fields["giorno_fisso"]
        attrs = field.widget.attrs
        attrs["readonly"] = "readonly"
        attrs["aria-readonly"] = "true"
        attrs["tabindex"] = "-1"
        attrs["data-field-locked"] = "true"
        classes = (attrs.get("class") or "").split()
        if "eureka-field-locked" not in classes:
            classes.append("eureka-field-locked")
        attrs["class"] = " ".join(classes)
        if not self.is_bound:
            self.initial["giorno_fisso"] = 31

    def _apply_fine_mese_giorno_fisso(self) -> None:
        if self._fine_mese_attivo():
            self._lock_giorno_fisso()

    def clean_codice(self):
        codice = (self.cleaned_data.get("codice") or "").strip()
        if not codice:
            raise forms.ValidationError("Il codice è obbligatorio.")
        qs = Condizione.objects.filter(codice=codice)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esiste già una condizione con questo codice.")
        return codice

    def clean_pag_fatt_elett_pa(self):
        value = (self.cleaned_data.get("pag_fatt_elett_pa") or "").strip().upper()
        return value or None

    def clean(self):
        cleaned = super().clean()
        fine_mese = bool(cleaned.get("fine_mese"))
        if fine_mese:
            cleaned["giorno_fisso"] = 31
        elif cleaned.get("giorno_fisso") not in (None, ""):
            try:
                giorno = int(cleaned["giorno_fisso"])
            except (TypeError, ValueError):
                raise forms.ValidationError({"giorno_fisso": "Inserire un giorno valido (1–31)."})
            if not 1 <= giorno <= 31:
                raise forms.ValidationError({"giorno_fisso": "Il giorno fisso deve essere tra 1 e 31."})
            cleaned["giorno_fisso"] = giorno
        return cleaned
