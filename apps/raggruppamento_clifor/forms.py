from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.raggruppamento_clifor.models import RaggruppamentoClifor

BOOL_FIELDS = ("escludi_regola_newcli",)


class RaggruppamentoCliforForm(forms.ModelForm):
    escludi_regola_newcli = forms.BooleanField(
        required=False,
        label="Escludi regola nuovo cliente",
    )

    class Meta:
        model = RaggruppamentoClifor
        fields = ["codice", "descrizione", "escludi_regola_newcli"]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        apply_control_widgets(self, exclude=set(BOOL_FIELDS))
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self)
