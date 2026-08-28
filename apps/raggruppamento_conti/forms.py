from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.raggruppamento_conti.models import RaggruppamentoConto


class RaggruppamentoContoForm(forms.ModelForm):
    class Meta:
        model = RaggruppamentoConto
        fields = ["codice", "descrizione"]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self)
