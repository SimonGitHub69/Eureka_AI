from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.geografia.models import Citta, Provincia, Regione


class RegioneForm(forms.ModelForm):
    class Meta:
        model = Regione
        fields = ["codice", "nome"]
        labels = {
            "codice": "Codice ISTAT",
            "nome": "Nome",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_widgets(self)
        self.fields["codice"].required = True
        self.fields["nome"].required = True
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_codice(self):
        return clean_unique_pk(self, "codice")


class ProvinciaForm(forms.ModelForm):
    class Meta:
        model = Provincia
        fields = ["sigla", "codice_istat", "nome", "regione"]
        labels = {
            "sigla": "Sigla",
            "codice_istat": "Codice ISTAT",
            "nome": "Nome",
            "regione": "Regione",
        }

    def __init__(self, *args, sigla_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_widgets(self)
        self.fields["sigla"].required = True
        self.fields["codice_istat"].required = True
        self.fields["nome"].required = True
        self.fields["regione"].required = True
        self.fields["regione"].queryset = Regione.objects.order_by("nome")
        if sigla_readonly:
            self.fields["sigla"].disabled = True
            self.fields["sigla"].help_text = "La sigla non è modificabile."

    def clean_sigla(self):
        value = (self.cleaned_data.get("sigla") or "").strip().upper()
        if not value:
            raise forms.ValidationError("La sigla è obbligatoria.")
        qs = Provincia.objects.filter(sigla=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esiste già una provincia con questa sigla.")
        return value

    def clean_codice_istat(self):
        value = (self.cleaned_data.get("codice_istat") or "").strip()
        if not value:
            raise forms.ValidationError("Il codice ISTAT è obbligatorio.")
        qs = Provincia.objects.filter(codice_istat=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esiste già una provincia con questo codice ISTAT.")
        return value


class CittaForm(forms.ModelForm):
    class Meta:
        model = Citta
        fields = ["codice_istat", "nome", "provincia", "cap", "codice_catastale"]
        labels = {
            "codice_istat": "Codice ISTAT",
            "nome": "Nome",
            "provincia": "Provincia",
            "cap": "CAP",
            "codice_catastale": "Codice catastale",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_widgets(self)
        self.fields["codice_istat"].required = True
        self.fields["nome"].required = True
        self.fields["provincia"].required = True
        self.fields["cap"].required = False
        self.fields["codice_catastale"].required = False
        self.fields["provincia"].queryset = Provincia.objects.select_related("regione").order_by(
            "nome"
        )
        if codice_readonly:
            self.fields["codice_istat"].disabled = True
            self.fields["codice_istat"].help_text = "Il codice ISTAT non è modificabile."

    def clean_codice_istat(self):
        return clean_unique_pk(self, "codice_istat")

    def clean_cap(self):
        return (self.cleaned_data.get("cap") or "").strip()

    def clean_codice_catastale(self):
        return (self.cleaned_data.get("codice_catastale") or "").strip()

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.cap is None:
            instance.cap = ""
        if instance.codice_catastale is None:
            instance.codice_catastale = ""
        if commit:
            instance.save()
        return instance
