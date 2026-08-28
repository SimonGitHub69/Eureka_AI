from django import forms

from apps.core.mirror_crud import CONTROL, NUMBER, apply_control_widgets, clean_unique_pk
from apps.categorie.models import Categoria


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = [
            "codice",
            "descrizione",
            "c_vendita_prop",
            "provvigione",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "c_vendita_prop": "Conto vendita prop.",
            "provvigione": "Provvigione",
        }
        widgets = {
            "codice": forms.TextInput(attrs=CONTROL),
            "descrizione": forms.TextInput(attrs=CONTROL),
            "c_vendita_prop": forms.TextInput(attrs=CONTROL),
            "provvigione": forms.NumberInput(attrs=NUMBER),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in ("c_vendita_prop", "provvigione"):
            self.fields[name].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self, "codice")
