from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.vettori.models import Vettore


class VettoreForm(forms.ModelForm):
    class Meta:
        model = Vettore
        fields = [
            "codice",
            "denominazione",
            "indirizzo",
            "citta",
            "telefono",
            "partita_iva",
            "codice_fiscale",
            "iscrizione_albo",
            "email",
            "id_paese",
            "nazione",
            "cod_eori",
            "sigla_abbreviata",
        ]
        labels = {
            "codice": "Codice",
            "denominazione": "Denominazione",
            "indirizzo": "Indirizzo",
            "citta": "Città",
            "telefono": "Telefono",
            "partita_iva": "Partita IVA",
            "codice_fiscale": "Codice fiscale",
            "iscrizione_albo": "Iscrizione albo",
            "email": "Email",
            "id_paese": "ID Paese",
            "nazione": "Nazione",
            "cod_eori": "Codice EORI",
            "sigla_abbreviata": "Sigla",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["denominazione"].required = True
        for name in self.fields:
            if name not in ("codice", "denominazione"):
                self.fields[name].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self)
