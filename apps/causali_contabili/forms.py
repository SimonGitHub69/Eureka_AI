from django import forms

from apps.causali_contabili.lookups import (
    TIPO_DOC_FEL_CODES,
    tipo_doc_fel_choices,
    norm_tipo_doc_fel,
)
from apps.causali_contabili.models import CausaleContabile
from apps.core.mirror_crud import SELECT, apply_control_widgets, clean_unique_pk
from apps.registri_iva.lookups import registro_iva_choices, resolve_registro_iva

BOOL_FIELDS = (
    "causale_17_6",
    "tipo_sa",
    "flag_red_partitari",
    "esterometro",
    "autofattura",
    "iva_con_autofattura",
    "flag_cond_pag",
    "cont_analitica_no_control",
    "xml_default",
)

DARE_AVERE_FIELDS = (
    "c_dare_1",
    "c_avere_1",
    "c_dare_2",
    "c_avere_2",
    "c_dare_3",
    "c_avere_3",
    "c_dare_4",
    "c_avere_4",
    "c_dare_5",
    "c_avere_5",
    "c_dare_6",
    "c_avere_6",
    "c_dare_7",
    "c_avere_7",
    "c_dare_8",
    "c_avere_8",
    "c_dare_9",
    "c_avere_9",
    "c_dare_10",
    "c_avere_10",
)


class CausaleContabileForm(forms.ModelForm):
    registro_iva = forms.ChoiceField(
        label="Registro IVA",
        required=False,
        choices=[("", "—")],
        widget=forms.Select(attrs=SELECT),
    )
    tipo_doc_fel = forms.ChoiceField(
        label="Tipo documento FEL",
        required=False,
        choices=[("", "—")],
        widget=forms.Select(attrs=SELECT),
    )

    class Meta:
        model = CausaleContabile
        fields = [
            "codice",
            "descrizione",
            "desc_pn",
            "tipo_causale",
            "registro_iva",
            "desc_reg_iva",
            "partite_aperte",
            "incrementa_doc",
            "cassa_corrispettivi",
            *DARE_AVERE_FIELDS,
            "tipo_doc_fel",
            "testo_auto_fattura",
            "causale_colleg_auto_f",
            "cliente_auto_f",
            "sotto_conto_iva_acq_auto_f",
            "sotto_conto_iva_vend_auto_f",
            "contatore_auto_f",
            *BOOL_FIELDS,
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "desc_pn": "Descrizione Pn",
            "tipo_causale": "Tipo causale",
            "registro_iva": "Registro IVA",
            "partite_aperte": "Partite aperte",
            "incrementa_doc": "Incrementa documento",
            "cassa_corrispettivi": "Cassa corrispettivi",
            "c_dare_1": "Conto dare 1",
            "c_avere_1": "Conto avere 1",
            "c_dare_2": "Conto dare 2",
            "c_avere_2": "Conto avere 2",
            "c_dare_3": "Conto dare 3",
            "c_avere_3": "Conto avere 3",
            "c_dare_4": "Conto dare 4",
            "c_avere_4": "Conto avere 4",
            "c_dare_5": "Conto dare 5",
            "c_avere_5": "Conto avere 5",
            "c_dare_6": "Conto dare 6",
            "c_avere_6": "Conto avere 6",
            "c_dare_7": "Conto dare 7",
            "c_avere_7": "Conto avere 7",
            "c_dare_8": "Conto dare 8",
            "c_avere_8": "Conto avere 8",
            "c_dare_9": "Conto dare 9",
            "c_avere_9": "Conto avere 9",
            "c_dare_10": "Conto dare 10",
            "c_avere_10": "Conto avere 10",
            "tipo_doc_fel": "Tipo documento FEL",
            "testo_auto_fattura": "Testo autofattura",
            "causale_colleg_auto_f": "Causale collegata autofattura",
            "cliente_auto_f": "Cliente autofattura",
            "sotto_conto_iva_acq_auto_f": "Sottoconto IVA acquisti autofattura",
            "sotto_conto_iva_vend_auto_f": "Sottoconto IVA vendite autofattura",
            "contatore_auto_f": "Contatore autofattura",
            "causale_17_6": "Causale 17/6",
            "tipo_sa": "Tipo SA",
            "flag_red_partitari": "Flag red partitari",
            "esterometro": "Esterometro",
            "autofattura": "Autofattura",
            "iva_con_autofattura": "IVA con autofattura",
            "flag_cond_pag": "Flag condizioni pagamento",
            "cont_analitica_no_control": "Contabilità analitica senza controllo",
            "xml_default": "XML default",
        }
        widgets = {
            **{name: forms.CheckboxInput() for name in BOOL_FIELDS},
            "testo_auto_fattura": forms.Textarea(attrs={"rows": 3}),
            "desc_reg_iva": forms.HiddenInput(),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in self.fields:
            if name not in ("codice", "descrizione"):
                self.fields[name].required = False
        apply_control_widgets(self, keep_textarea={"testo_auto_fattura"})
        current_registro = ""
        if self.is_bound:
            current_registro = (self.data.get("registro_iva") or "").strip()
        elif self.instance and getattr(self.instance, "registro_iva", None):
            current_registro = (self.instance.registro_iva or "").strip()
        self.fields["registro_iva"].choices = registro_iva_choices(current_registro)
        current_fel = ""
        if self.is_bound:
            current_fel = (self.data.get("tipo_doc_fel") or "").strip()
        elif self.instance and getattr(self.instance, "tipo_doc_fel", None):
            current_fel = (self.instance.tipo_doc_fel or "").strip()
        fel_code = norm_tipo_doc_fel(current_fel)
        if not self.is_bound and fel_code in TIPO_DOC_FEL_CODES:
            self.initial["tipo_doc_fel"] = fel_code
        self.fields["tipo_doc_fel"].choices = tipo_doc_fel_choices(current_fel)
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_registro_iva(self):
        return (self.cleaned_data.get("registro_iva") or "").strip() or None

    def clean_tipo_doc_fel(self):
        raw = (self.cleaned_data.get("tipo_doc_fel") or "").strip()
        if not raw:
            return None
        code = norm_tipo_doc_fel(raw)
        if code in TIPO_DOC_FEL_CODES:
            return code
        return raw

    def clean(self):
        data = super().clean()
        registro_code = data.get("registro_iva")
        if registro_code:
            registro = resolve_registro_iva(registro_code)
            label = (getattr(registro, "label", None) or "").strip()
            if label:
                data["desc_reg_iva"] = label
        return data

    def clean_codice(self):
        return clean_unique_pk(self)
