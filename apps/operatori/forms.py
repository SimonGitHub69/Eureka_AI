from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.operatori.models import Operatore


class OperatoreForm(forms.ModelForm):
    class Meta:
        model = Operatore
        fields = [
            "codice",
            "nome",
            "nome_breve",
            "sigla",
            "email",
            "reparto",
            "num_badge",
            "matricola_timbratore",
            "operatore_disattivo",
            "data_assunzione",
            "data_dimissioni",
            "tutor",
            "ora_e1",
            "ora_u1",
            "ora_e2",
            "ora_u2",
            "calendario_google",
            "firma_privacy",
            "firma_consegna_dpi",
            "data_verifica_formazione",
            "esito_formazione",
            "tessera_vaccinazioni",
            "data_scadenza_vaccinazione",
        ]
        labels = {
            "codice": "Codice",
            "nome": "Nome",
            "nome_breve": "Nome breve",
            "sigla": "Sigla",
            "email": "Email",
            "reparto": "Reparto",
            "num_badge": "N. badge",
            "matricola_timbratore": "Matricola timbratore",
            "operatore_disattivo": "Disattivo",
            "data_assunzione": "Data assunzione",
            "data_dimissioni": "Data dimissioni",
            "tutor": "Tutor",
            "ora_e1": "Ora entrata 1",
            "ora_u1": "Ora uscita 1",
            "ora_e2": "Ora entrata 2",
            "ora_u2": "Ora uscita 2",
            "calendario_google": "Calendario Google",
            "firma_privacy": "Firma privacy",
            "firma_consegna_dpi": "Firma consegna DPI",
            "data_verifica_formazione": "Data verifica formazione",
            "esito_formazione": "Esito formazione",
            "tessera_vaccinazioni": "Tessera vaccinazioni",
            "data_scadenza_vaccinazione": "Scadenza vaccinazione",
        }
        widgets = {
            "data_assunzione": forms.DateInput(attrs={"type": "date"}),
            "data_dimissioni": forms.DateInput(attrs={"type": "date"}),
            "data_verifica_formazione": forms.DateInput(attrs={"type": "date"}),
            "data_scadenza_vaccinazione": forms.DateInput(attrs={"type": "date"}),
            "ora_e1": forms.TimeInput(attrs={"type": "time"}),
            "ora_u1": forms.TimeInput(attrs={"type": "time"}),
            "ora_e2": forms.TimeInput(attrs={"type": "time"}),
            "ora_u2": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_widgets(self)
        self.fields["codice"].required = True
        self.fields["nome"].required = False
        for name in self.fields:
            if name != "codice":
                self.fields[name].required = False
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self, "codice")
