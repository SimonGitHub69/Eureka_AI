from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.causali_trasp.models import CausaleTrasporto

BOOL_FIELDS = ("fatturabile",)


class CausaleTrasportoForm(forms.ModelForm):
    class Meta:
        model = CausaleTrasporto
        fields = [
            "codice",
            "descrizione",
            "fatturabile",
            "causale_maga",
            "reparto_ecr",
            "c_partita_vend",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "fatturabile": "Fatturabile",
            "causale_maga": "Causale magazzino",
            "reparto_ecr": "Reparto ECR",
            "c_partita_vend": "Conto partita vendite",
        }
        widgets = {
            **{name: forms.CheckboxInput() for name in BOOL_FIELDS},
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in self.fields:
            if name not in ("codice", "descrizione"):
                self.fields[name].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self)
