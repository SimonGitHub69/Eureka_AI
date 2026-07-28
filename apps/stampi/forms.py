from django import forms

from apps.stampi.models import Stampo


class StampoArticoliCdForm(forms.ModelForm):
    class Meta:
        model = Stampo
        fields = list(Stampo.ARTICOLI_CD_FIELDS)
        widgets = {
            name: forms.TextInput(
                attrs={
                    "class": "form-control font-monospace",
                    "autocomplete": "off",
                    "placeholder": "Codice articolo",
                }
            )
            for name in Stampo.ARTICOLI_CD_FIELDS
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i, name in enumerate(Stampo.ARTICOLI_CD_FIELDS, start=1):
            self.fields[name].label = f"{i:02d}"
            self.fields[name].required = False
