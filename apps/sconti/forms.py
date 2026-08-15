from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.sconti.models import Sconto


class ScontoForm(forms.ModelForm):
    class Meta:
        model = Sconto
        fields = ["codice", "sconto"]
        labels = {
            "codice": "Codice",
            "sconto": "Sconto",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["sconto"].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self)
