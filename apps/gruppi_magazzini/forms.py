from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.gruppi_magazzini.models import GruppoMagazzino


class GruppoMagazzinoForm(forms.ModelForm):
    class Meta:
        model = GruppoMagazzino
        fields = [
            "cod",
            "descrizione",
            "tipo_doc_alfa_ddt",
            "tipo_doc_alfa_fat",
            "tipo_doc_alfa_ord",
        ]
        labels = {
            "cod": "Codice",
            "descrizione": "Descrizione",
            "tipo_doc_alfa_ddt": "Tipo doc. DDT",
            "tipo_doc_alfa_fat": "Tipo doc. fattura",
            "tipo_doc_alfa_ord": "Tipo doc. ordine",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cod"].required = True
        self.fields["descrizione"].required = True
        for name in ("tipo_doc_alfa_ddt", "tipo_doc_alfa_fat", "tipo_doc_alfa_ord"):
            self.fields[name].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["cod"].disabled = True
            self.fields["cod"].help_text = "Il codice non è modificabile."

    def clean_cod(self):
        return clean_unique_pk(self, "cod")
