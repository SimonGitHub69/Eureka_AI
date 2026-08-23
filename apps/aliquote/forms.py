from django import forms

from apps.aliquote.models import NATURE_SDI, RIFERIMENTO_CHOICES_VALUES, Aliquota
from apps.core.mirror_crud import SELECT, apply_control_widgets, clean_unique_pk

BOOL_FIELDS = (
    "fl_reverse_charge",
    "flag_omaggio",
    "calc_spese_bolli",
    "flag_certificaz_esp",
    "disabilitato",
    "non_visibile",
)

NATURE_CHOICES = [("", "—")] + [
    (code, f"{code} - {label}") for code, label in NATURE_SDI.items()
]

RIFERIMENTO_CHOICES = [("", "—")] + [(v, v) for v in RIFERIMENTO_CHOICES_VALUES]

ESIGIBILITA_CHOICES = [
    ("", "—"),
    ("I", "I - Immediata"),
    ("D", "D - Differita"),
    ("S", "S - Scissione dei pagamenti"),
]


class AliquotaForm(forms.ModelForm):
    riferimento = forms.ChoiceField(
        label="Riferimento",
        required=False,
        choices=RIFERIMENTO_CHOICES,
        widget=forms.Select(attrs=SELECT),
    )
    natura_cod_ese_edi = forms.ChoiceField(
        label="Natura SDI",
        required=False,
        choices=NATURE_CHOICES,
        widget=forms.Select(attrs=SELECT),
    )
    tipo_esigibilita = forms.ChoiceField(
        label="Tipo esigibilità",
        required=False,
        choices=ESIGIBILITA_CHOICES,
        widget=forms.Select(attrs=SELECT),
    )

    class Meta:
        model = Aliquota
        fields = [
            "codice",
            "descrizione",
            "percentuale",
            "percentuale_ind",
            "riferimento",
            "natura_cod_ese_edi",
            "des_ese_edi",
            "desc_fattura1",
            "desc_fattura2",
            "desc_fattura_corpo",
            "fl_reverse_charge",
            "flag_omaggio",
            "cod_reparto",
            "tipo_esigibilita",
            "calc_spese_bolli",
            "flag_certificaz_esp",
            "disabilitato",
            "non_visibile",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "percentuale": "Percentuale",
            "percentuale_ind": "% indetraibile",
            "riferimento": "Riferimento",
            "natura_cod_ese_edi": "Natura SDI",
            "des_ese_edi": "Descrizione esenzione EDI",
            "desc_fattura1": "Desc. fattura 1",
            "desc_fattura2": "Desc. fattura 2",
            "desc_fattura_corpo": "Desc. fattura corpo",
            "fl_reverse_charge": "Reverse charge",
            "flag_omaggio": "Omaggio",
            "cod_reparto": "Cod. reparto",
            "tipo_esigibilita": "Tipo esigibilità",
            "calc_spese_bolli": "Calc. spese bolli",
            "flag_certificaz_esp": "Certificazione esportatore",
            "disabilitato": "Disabilitato",
            "non_visibile": "Non visibile",
        }
        widgets = {
            "percentuale": forms.NumberInput(attrs={"step": "0.01"}),
            "percentuale_ind": forms.NumberInput(attrs={"step": "0.01"}),
            **{name: forms.CheckboxInput() for name in BOOL_FIELDS},
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in self.fields:
            if name not in ("codice", "descrizione"):
                self.fields[name].required = False

        natura_choices = list(NATURE_CHOICES)
        current_natura = ""
        if self.is_bound:
            current_natura = (self.data.get("natura_cod_ese_edi") or "").strip().upper()
        elif self.instance and self.instance.pk:
            current_natura = (self.instance.natura_cod_ese_edi or "").strip().upper()
        if current_natura and current_natura not in dict(natura_choices):
            natura_choices.append((current_natura, current_natura))
        self.fields["natura_cod_ese_edi"].choices = natura_choices

        rif_choices = list(RIFERIMENTO_CHOICES)
        current_rif = ""
        if self.is_bound:
            current_rif = (self.data.get("riferimento") or "").strip()
        elif self.instance and self.instance.pk:
            current_rif = (self.instance.riferimento or "").strip()
        if current_rif and current_rif not in dict(rif_choices):
            rif_choices.append((current_rif, current_rif))
        self.fields["riferimento"].choices = rif_choices

        esig_choices = list(ESIGIBILITA_CHOICES)
        current_esig = ""
        if self.is_bound:
            current_esig = (self.data.get("tipo_esigibilita") or "").strip().upper()
        elif self.instance and self.instance.pk:
            current_esig = (self.instance.tipo_esigibilita or "").strip().upper()
        if current_esig and current_esig not in dict(esig_choices):
            esig_choices.append((current_esig, current_esig))
        self.fields["tipo_esigibilita"].choices = esig_choices

        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_riferimento(self):
        return (self.cleaned_data.get("riferimento") or "").strip() or None

    def clean_natura_cod_ese_edi(self):
        return (self.cleaned_data.get("natura_cod_ese_edi") or "").strip().upper() or None

    def clean_tipo_esigibilita(self):
        return (self.cleaned_data.get("tipo_esigibilita") or "").strip().upper() or None

    def clean_codice(self):
        return clean_unique_pk(self)
