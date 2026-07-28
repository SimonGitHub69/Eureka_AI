from django import forms

from apps.core.models import (
    AzioneComandoVocale,
    ComandoVocale,
    Configurazione4D,
    ConfigurazionePC,
    ConfigurazioneProgramma,
)


class Configurazione4DForm(forms.ModelForm):
    class Meta:
        model = Configurazione4D
        fields = [
            "attiva",
            "server",
            "porta",
            "utente",
            "password",
            "driver_odbc",
            "usa_ssl",
            "dsn",
            "note",
        ]
        widgets = {
            "attiva": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "usa_ssl": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "server": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "192.168.1.50 oppure hostname",
                }
            ),
            "porta": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "utente": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "Designer",
                }
            ),
            "password": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "type": "password",
                    "autocomplete": "off",
                }
            ),
            "driver_odbc": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "4D ODBC Driver 64-bit",
                }
            ),
            "dsn": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "Nome DSN (opzionale)",
                }
            ),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].required = False
        if self.instance.pk and self.instance.password:
            self.fields["password"].widget.attrs["placeholder"] = (
                "Password salvata: lascia vuoto per mantenerla"
            )

    def clean_password(self):
        password = (self.cleaned_data.get("password") or "").strip()
        if password:
            return password
        if self.instance.pk and self.instance.password:
            return self.instance.password
        return ""

    def clean(self):
        cleaned_data = super().clean()

        if not cleaned_data.get("attiva"):
            return cleaned_data

        dsn = (cleaned_data.get("dsn") or "").strip()
        if dsn:
            return cleaned_data

        if not (cleaned_data.get("server") or "").strip():
            self.add_error("server", "Inserisci il server 4D oppure un DSN.")
        if not (cleaned_data.get("utente") or "").strip():
            self.add_error("utente", "Inserisci l'utente.")
        if not cleaned_data.get("password"):
            self.add_error("password", "Inserisci la password.")

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            obj.password = password
        elif self.instance.pk and self.instance.password:
            obj.password = self.instance.password
        if commit:
            obj.save()
        return obj


class ConfigurazioneProgrammaForm(forms.ModelForm):
    class Meta:
        model = ConfigurazioneProgramma
        fields = ["assistente_vocale_attivo", "navbar_fissa", "note"]
        widgets = {
            "assistente_vocale_attivo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "navbar_fissa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}
            ),
        }


class ConfigurazionePCForm(forms.ModelForm):
    class Meta:
        model = ConfigurazionePC
        fields = [
            "nome_pc",
            "descrizione",
            "assistente_vocale_attivo",
            "navbar_fissa",
            "note",
        ]
        widgets = {
            "nome_pc": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "Es. iPad-Magazzino o DESKTOP-UFFICIO01",
                }
            ),
            "descrizione": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "Es. Tablet magazzino",
                }
            ),
            "assistente_vocale_attivo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "navbar_fissa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, nome_pc_readonly=False, forced_nome_pc="", **kwargs):
        super().__init__(*args, **kwargs)
        self.nome_pc_readonly = bool(nome_pc_readonly)
        self.forced_nome_pc = (forced_nome_pc or "").strip()
        if self.nome_pc_readonly:
            self.fields["nome_pc"].widget.attrs.update(
                {
                    "readonly": True,
                    "class": "form-control-plaintext border rounded px-2 bg-secondary-lt",
                }
            )
            if self.forced_nome_pc:
                self.fields["nome_pc"].initial = self.forced_nome_pc

    def clean_nome_pc(self):
        if self.nome_pc_readonly and self.forced_nome_pc:
            nome = self.forced_nome_pc
        elif self.nome_pc_readonly and self.instance and self.instance.pk:
            nome = (self.instance.nome_pc or "").strip()
        else:
            nome = (self.cleaned_data.get("nome_pc") or "").strip()
        if not nome:
            raise forms.ValidationError("Indicare il nome fisico del PC.")
        qs = ConfigurazionePC.objects.filter(is_active=True, nome_pc__iexact=nome)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esiste già una postazione con questo nome PC.")
        return nome


class ComandoVocaleForm(forms.ModelForm):
    class Meta:
        model = ComandoVocale
        fields = [
            "frase",
            "azione",
            "destinazione",
            "query",
            "attivo",
            "ordine",
            "match_mode",
            "note",
        ]
        widgets = {
            "frase": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": 'Es. "apri clienti" o "cerca cliente"',
                }
            ),
            "azione": forms.Select(attrs={"class": "form-select"}),
            "destinazione": forms.Select(attrs={"class": "form-select"}),
            "query": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": 'Es. "Rossi" (opzionale, solo per ricerca)',
                }
            ),
            "attivo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordine": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "match_mode": forms.Select(attrs={"class": "form-select"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 2, "autocomplete": "off"}),
        }

    def clean_frase(self):
        frase = (self.cleaned_data.get("frase") or "").strip()
        if not frase:
            raise forms.ValidationError("Inserisci una frase.")
        return frase

    def clean(self):
        cleaned_data = super().clean()
        azione = cleaned_data.get("azione")
        destinazione = cleaned_data.get("destinazione")

        if azione == AzioneComandoVocale.SEARCH and destinazione in {
            "dashboard",
            "agenda",
            "parametri_4d",
            "sistema",
            "sync_fatture",
            "sync_anagrafiche",
            "sync_aziende",
            "sync_categorie",
            "sync_gruppi_articoli",
        }:
            self.add_error(
                "destinazione",
                "Per la ricerca scegli clienti, fornitori, agenti, articoli, fatture, categorie, aziende o gruppi articoli.",
            )

        return cleaned_data
