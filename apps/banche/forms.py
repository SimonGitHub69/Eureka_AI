from django import forms

from apps.banche.models import Banca
from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk


class BancaForm(forms.ModelForm):
    class Meta:
        model = Banca
        fields = [
            "codice",
            "descrizione",
            "indirizzo",
            "cap",
            "localita",
            "provincia",
            "telefono",
            "fax",
            "codice_abi",
            "codice_cab",
            "numero_cc",
            "agenzia",
            "note",
            "iban",
            "swift_code",
        ]
        labels = {
            "codice": "Codice banca",
            "descrizione": "Descrizione",
            "indirizzo": "Indirizzo",
            "cap": "CAP",
            "localita": "Località",
            "provincia": "Prov.",
            "telefono": "Telefono",
            "fax": "Fax",
            "codice_abi": "Codice ABI",
            "codice_cab": "Codice CAB",
            "numero_cc": "Numero C/C",
            "agenzia": "Agenzia numero",
            "note": "Note",
            "iban": "Codice IBAN",
            "swift_code": "Swift Code (BIC)",
        }
        help_texts = {
            "numero_cc": (
                "Da riempire per distinta bonifici fornitori e RIBA telematiche."
            ),
            "iban": (
                "Da riempire per stampare l'IBAN di riferimento nei pagamenti "
                "di tipo Bonifico o Rimessa diretta."
            ),
        }
        widgets = {
            "note": forms.Textarea(attrs={"rows": 4}),
            "provincia": forms.TextInput(attrs={"maxlength": "4"}),
            "iban": forms.TextInput(attrs={"class": "font-monospace"}),
            "numero_cc": forms.TextInput(attrs={"class": "font-monospace"}),
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
