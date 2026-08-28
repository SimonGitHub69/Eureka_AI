from pathlib import Path

from django import forms

from apps.aziende.models import Azienda, AziendaDati
from apps.core.mirror_crud import apply_control_widgets

ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_LOGO_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg"}

AZIENDA_BOOL_FIELDS = ("persona_fisica", "socio_unico", "in_liquidazione")


class AziendaForm(forms.ModelForm):
    persona_fisica = forms.BooleanField(required=False, label="Persona fisica")
    socio_unico = forms.BooleanField(required=False, label="Socio unico")
    in_liquidazione = forms.BooleanField(required=False, label="In liquidazione")

    class Meta:
        model = Azienda
        fields = [
            "id",
            "ragione_sociale",
            "indirizzo",
            "localita",
            "provincia",
            "cap",
            "partita_iva",
            "codice_fiscale",
            "telefono",
            "fax",
            "email",
            "email_pec",
            "anno_competenza",
            "cod_attivita",
            "desc_attivita",
            "note",
            "cod_regime_fiscale",
            "cod_unico_sdi",
            "cod_paese",
            "persona_fisica",
            "cognome",
            "nome",
            "num_civico",
            "prov_rea",
            "num_iscrizione_rea",
            "capitale_soc",
            "socio_unico",
            "in_liquidazione",
        ]
        labels = {
            "id": "ID",
            "ragione_sociale": "Ragione sociale",
            "indirizzo": "Indirizzo",
            "localita": "Località",
            "provincia": "Provincia",
            "cap": "CAP",
            "partita_iva": "Partita IVA",
            "codice_fiscale": "Codice fiscale",
            "telefono": "Telefono",
            "fax": "Fax",
            "email": "Email",
            "email_pec": "PEC",
            "anno_competenza": "Anno competenza",
            "cod_attivita": "Cod. attività",
            "desc_attivita": "Desc. attività",
            "note": "Note",
            "cod_regime_fiscale": "Regime fiscale",
            "cod_unico_sdi": "Codice SDI",
            "cod_paese": "Cod. paese",
            "persona_fisica": "Persona fisica",
            "cognome": "Cognome",
            "nome": "Nome",
            "num_civico": "N. civico",
            "prov_rea": "Prov. REA",
            "num_iscrizione_rea": "N. iscrizione REA",
            "capitale_soc": "Capitale sociale",
            "socio_unico": "Socio unico",
            "in_liquidazione": "In liquidazione",
        }
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),
            "desc_attivita": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, id_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_widgets(self, exclude=set(AZIENDA_BOOL_FIELDS))
        self.fields["id"].required = True
        for name in self.fields:
            if name != "id":
                self.fields[name].required = False
        for name in AZIENDA_BOOL_FIELDS:
            if self.instance and self.instance.pk:
                val = getattr(self.instance, name, None)
                if val is not None:
                    self.fields[name].initial = bool(val)
        if id_readonly:
            self.fields["id"].disabled = True
            self.fields["id"].help_text = "L'ID non è modificabile."

    def clean_id(self):
        value = self.cleaned_data.get("id")
        if value is None:
            raise forms.ValidationError("L'ID è obbligatorio.")
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise forms.ValidationError("ID non valido.")
        if value <= 0:
            raise forms.ValidationError("L'ID deve essere un intero positivo.")
        qs = Azienda.objects.filter(pk=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esiste già un'azienda con questo ID.")
        return value


class AziendaConfigForm(forms.ModelForm):
    """Opzioni locali Eureka (non sincronizzate da 4D)."""

    class Meta:
        model = AziendaDati
        fields = ["azienda_noleggio"]
        labels = {
            "azienda_noleggio": "Azienda di noleggio",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["azienda_noleggio"].help_text = (
            "Abilita nel Piano dei Conti i campi Nomenclatura Intrastat, "
            "Bene o servizio e Tipo noleggio."
        )


class AziendaDatiForm(forms.ModelForm):
    class Meta:
        model = AziendaDati
        fields = ["logo", "logo_documenti", "azienda_noleggio", "note"]
        widgets = {
            "logo": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/png,image/jpeg,.png,.jpg,.jpeg",
                }
            ),
            "logo_documenti": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/png,image/jpeg,.png,.jpg,.jpeg",
                }
            ),
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_widgets(self)
        self.fields["logo"].help_text = (
            "Logo generale per elenchi stampati e interfaccia."
        )
        self.fields["logo_documenti"].help_text = (
            "Usato come intestazione nelle stampe di preventivi, fatture "
            "e altri documenti. Se vuoto, viene usato il logo generale."
        )

    def _clean_logo_file(self, logo):
        if not logo:
            return logo

        # ClearableFileInput: False significa "rimuovi file esistente"
        if logo is False:
            return logo

        name = getattr(logo, "name", "") or ""
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_LOGO_EXTENSIONS:
            raise forms.ValidationError(
                "Formato non supportato. Carica un file PNG o JPG."
            )

        content_type = (getattr(logo, "content_type", "") or "").lower().strip()
        if content_type and content_type not in ALLOWED_LOGO_CONTENT_TYPES:
            raise forms.ValidationError(
                "Tipo file non valido. Sono ammessi solo PNG e JPG."
            )

        return logo

    def clean_logo(self):
        return self._clean_logo_file(self.cleaned_data.get("logo"))

    def clean_logo_documenti(self):
        return self._clean_logo_file(self.cleaned_data.get("logo_documenti"))
