from django import forms
from django.core.exceptions import ValidationError

from apps.anagrafiche.codice_fiscale import check_anagrafica_cf
from apps.anagrafiche.models import Agente, Cliente, Fornitore
from apps.anagrafiche.numerazione import (
    next_codice_agente,
    next_codice_cliente,
    next_codice_fornitore,
)
from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk


def _validate_cod_fiscale(cleaned_data: dict, *, persona_fisica=None) -> dict:
    cf = cleaned_data.get("cod_fiscale")
    result = check_anagrafica_cf(
        cf,
        cleaned_data.get("cod_nazione"),
        partita_iva=cleaned_data.get("partita_iva"),
        persona_fisica=persona_fisica,
    )
    if cf and result.eligible and result.valid is False:
        raise ValidationError(result.message)
    if result.normalized:
        cleaned_data["cod_fiscale"] = result.normalized
    return cleaned_data


class AgenteForm(forms.ModelForm):
    class Meta:
        model = Agente
        fields = [
            "codice",
            "ragione_sociale",
            "email",
            "provvigione",
            "sconto_base",
            "ritenuta_acconto",
            "perc_imp_rit_acc",
            "listino_art",
            "flag_mono_mandatario",
            "flag_agente_venditore",
            "flag_soc_capitale",
            "target_annuale1",
            "target_annuale2",
            "target_annuale3",
        ]
        labels = {
            "codice": "Codice",
            "ragione_sociale": "Ragione sociale",
            "email": "Email",
            "provvigione": "Provvigione %",
            "sconto_base": "Sconto base %",
            "ritenuta_acconto": "Ritenuta acconto %",
            "perc_imp_rit_acc": "% imp. rit. acc.",
            "listino_art": "Listino articoli",
            "flag_mono_mandatario": "Mono mandatario",
            "flag_agente_venditore": "Agente venditore",
            "flag_soc_capitale": "Soc. di capitale",
            "target_annuale1": "Target annuale 1",
            "target_annuale2": "Target annuale 2",
            "target_annuale3": "Target annuale 3",
        }
        widgets = {
            "provvigione": forms.NumberInput(attrs={"step": "0.01"}),
            "sconto_base": forms.NumberInput(attrs={"step": "0.01"}),
            "ritenuta_acconto": forms.NumberInput(attrs={"step": "0.01"}),
            "perc_imp_rit_acc": forms.NumberInput(attrs={"step": "0.01"}),
            "listino_art": forms.NumberInput(),
            "target_annuale1": forms.NumberInput(attrs={"step": "0.01"}),
            "target_annuale2": forms.NumberInput(attrs={"step": "0.01"}),
            "target_annuale3": forms.NumberInput(attrs={"step": "0.01"}),
            "flag_mono_mandatario": forms.CheckboxInput(),
            "flag_agente_venditore": forms.CheckboxInput(),
            "flag_soc_capitale": forms.CheckboxInput(),
        }

    def __init__(self, *args, codice_readonly: bool = False, auto_codice: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.auto_codice = bool(auto_codice)
        self.fields["codice"].required = True
        self.fields["ragione_sociale"].required = True
        for name in self.fields:
            if name not in ("codice", "ragione_sociale"):
                self.fields[name].required = False
        apply_control_widgets(self)
        if self.auto_codice and not (self.instance and self.instance.pk):
            suggested = next_codice_agente()
            self.fields["codice"].initial = suggested
            self.fields["codice"].disabled = True
        elif codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        if self.auto_codice and not (self.instance and self.instance.pk):
            return next_codice_agente()
        return clean_unique_pk(self)


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "codice",
            "ragione_sociale1",
            "ragione_sociale2",
            "indirizzo",
            "cap",
            "localita",
            "provincia",
            "cod_nazione",
            "partita_iva",
            "cod_fiscale",
            "telefono",
            "fax",
            "cellulare",
            "email",
            "pec",
            "email_commerciale",
            "www",
            "agente",
            "agente2",
            "zona",
            "gruppo",
            "cond_paga",
            "listino",
            "annotazioni",
            "note",
            "fl_disattivato",
            "cliente_fittizio",
            "codice_ufficio",
            "flag_pa",
            "persona_fisica",
            "cognome",
            "nome",
            "cod_esenz_iva",
        ]
        labels = {
            "codice": "Codice",
            "ragione_sociale1": "Ragione sociale 1",
            "ragione_sociale2": "Ragione sociale 2",
            "indirizzo": "Indirizzo",
            "cap": "CAP",
            "localita": "Località",
            "provincia": "Provincia",
            "cod_nazione": "Nazione",
            "partita_iva": "P. IVA",
            "cod_fiscale": "Codice fiscale",
            "telefono": "Telefono",
            "fax": "Fax",
            "cellulare": "Cellulare",
            "email": "Email",
            "pec": "PEC",
            "email_commerciale": "Email commerciale",
            "www": "Sito web",
            "agente": "Agente",
            "agente2": "Agente 2",
            "zona": "Zona",
            "gruppo": "Gruppo",
            "cond_paga": "Cond. pagamento",
            "listino": "Listino",
            "annotazioni": "Annotazioni",
            "note": "Note",
            "fl_disattivato": "Disattivato",
            "cliente_fittizio": "Cliente fittizio",
            "codice_ufficio": "Codice ufficio",
            "flag_pa": "Pubblica amministrazione",
            "persona_fisica": "Persona fisica",
            "cognome": "Cognome",
            "nome": "Nome",
            "cod_esenz_iva": "Cod. esenz. IVA",
        }
        widgets = {
            "listino": forms.NumberInput(),
            "provincia": forms.TextInput(attrs={"maxlength": "4"}),
            "note": forms.Textarea(attrs={"rows": 3}),
            "annotazioni": forms.Textarea(attrs={"rows": 3}),
            "fl_disattivato": forms.CheckboxInput(),
            "cliente_fittizio": forms.CheckboxInput(),
            "flag_pa": forms.CheckboxInput(),
            "persona_fisica": forms.CheckboxInput(),
            "cod_esenz_iva": forms.TextInput(attrs={"maxlength": "16"}),
            "cod_fiscale": forms.TextInput(attrs={"maxlength": "16", "autocapitalize": "characters"}),
        }

    def __init__(self, *args, codice_readonly: bool = False, auto_codice: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.auto_codice = bool(auto_codice)
        self.fields["codice"].required = True
        self.fields["ragione_sociale1"].required = True
        for name in self.fields:
            if name not in ("codice", "ragione_sociale1"):
                self.fields[name].required = False
        apply_control_widgets(self, keep_textarea={"annotazioni"})
        if self.auto_codice and not (self.instance and self.instance.pk):
            suggested = next_codice_cliente()
            self.fields["codice"].initial = suggested
            self.fields["codice"].disabled = True
        elif codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        if self.auto_codice and not (self.instance and self.instance.pk):
            # Campo disabled: non arriva in POST → ricalcola al salvataggio
            return next_codice_cliente()
        return clean_unique_pk(self)

    def clean(self):
        cleaned_data = super().clean()
        persona_fisica = cleaned_data.get("persona_fisica")
        try:
            return _validate_cod_fiscale(cleaned_data, persona_fisica=persona_fisica)
        except ValidationError as exc:
            self.add_error("cod_fiscale", exc.message)
            return cleaned_data


class FornitoreForm(forms.ModelForm):
    class Meta:
        model = Fornitore
        fields = [
            "codice",
            "ragione_sociale1",
            "ragione_sociale2",
            "indirizzo",
            "cap",
            "localita",
            "provincia",
            "cod_nazione",
            "partita_iva",
            "cod_fiscale",
            "telefono",
            "fax",
            "cellulare",
            "email",
            "pec",
            "email_commerciale",
            "www",
            "agente",
            "zona",
            "gruppo",
            "cond_paga",
            "banca",
            "listino",
            "annotazioni",
            "note",
            "fl_disattivato",
        ]
        labels = {
            "codice": "Codice",
            "ragione_sociale1": "Ragione sociale 1",
            "ragione_sociale2": "Ragione sociale 2",
            "indirizzo": "Indirizzo",
            "cap": "CAP",
            "localita": "Località",
            "provincia": "Provincia",
            "cod_nazione": "Nazione",
            "partita_iva": "P. IVA",
            "cod_fiscale": "Codice fiscale",
            "telefono": "Telefono",
            "fax": "Fax",
            "cellulare": "Cellulare",
            "email": "Email",
            "pec": "PEC",
            "email_commerciale": "Email commerciale",
            "www": "Sito web",
            "agente": "Agente",
            "zona": "Zona",
            "gruppo": "Gruppo",
            "cond_paga": "Cond. pagamento",
            "banca": "Banca",
            "listino": "Listino",
            "annotazioni": "Annotazioni",
            "note": "Note",
            "fl_disattivato": "Disattivato",
        }
        widgets = {
            "listino": forms.NumberInput(),
            "provincia": forms.TextInput(attrs={"maxlength": "4"}),
            "note": forms.Textarea(attrs={"rows": 3}),
            "annotazioni": forms.Textarea(attrs={"rows": 3}),
            "fl_disattivato": forms.CheckboxInput(),
            "cod_fiscale": forms.TextInput(attrs={"maxlength": "16", "autocapitalize": "characters"}),
        }

    def __init__(self, *args, codice_readonly: bool = False, auto_codice: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.auto_codice = bool(auto_codice)
        self.fields["codice"].required = True
        self.fields["ragione_sociale1"].required = True
        for name in self.fields:
            if name not in ("codice", "ragione_sociale1"):
                self.fields[name].required = False
        apply_control_widgets(self, keep_textarea={"annotazioni"})
        if self.auto_codice and not (self.instance and self.instance.pk):
            suggested = next_codice_fornitore()
            self.fields["codice"].initial = suggested
            self.fields["codice"].disabled = True
        elif codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        if self.auto_codice and not (self.instance and self.instance.pk):
            return next_codice_fornitore()
        return clean_unique_pk(self)

    def clean(self):
        cleaned_data = super().clean()
        try:
            return _validate_cod_fiscale(cleaned_data)
        except ValidationError as exc:
            self.add_error("cod_fiscale", exc.message)
            return cleaned_data
