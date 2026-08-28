from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.registri_iva.models import RegistroIva

TIPO_REGISTRO_CHOICES = [
    ("", "—"),
    ("Acquisto", "Acquisto"),
    ("Vendita", "Vendita"),
    ("Corrispettivi", "Corrispettivi"),
]

BOOL_FIELDS = (
    "registro_cee",
    "registro_art74",
    "iva_art17_ter",
    "disattivato",
    "disattiva_check_prot",
)


class RegistroIvaForm(forms.ModelForm):
    tipo_registro = forms.ChoiceField(
        label="Tipo registro",
        required=False,
        choices=TIPO_REGISTRO_CHOICES,
        widget=forms.Select(),
    )

    class Meta:
        model = RegistroIva
        fields = [
            "codice",
            "descrizione",
            "tipo_registro",
            "registro_cee",
            "perc_pro_rata",
            "registro_art74",
            "iva_art17_ter",
            "disattivato",
            "disattiva_check_prot",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "tipo_registro": "Tipo registro",
            "registro_cee": "Registro CEE",
            "perc_pro_rata": "% pro-rata",
            "registro_art74": "Registro art. 74",
            "iva_art17_ter": "IVA art. 17 ter",
            "disattivato": "Disattivato",
            "disattiva_check_prot": "Disattiva check protocollo",
        }
        widgets = {
            "perc_pro_rata": forms.NumberInput(attrs={"step": "0.01"}),
            **{name: forms.CheckboxInput() for name in BOOL_FIELDS},
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in self.fields:
            if name not in ("codice", "descrizione"):
                self.fields[name].required = False

        tipo_choices = list(TIPO_REGISTRO_CHOICES)
        current_tipo = ""
        if self.is_bound:
            current_tipo = (self.data.get("tipo_registro") or "").strip()
        elif self.instance and self.instance.pk:
            current_tipo = (self.instance.tipo_registro or "").strip()
        if current_tipo and current_tipo not in dict(tipo_choices):
            tipo_choices.append((current_tipo, current_tipo))
        self.fields["tipo_registro"].choices = tipo_choices

        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_tipo_registro(self):
        return (self.cleaned_data.get("tipo_registro") or "").strip() or None

    def clean_codice(self):
        return clean_unique_pk(self)
