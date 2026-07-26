from django import forms

from apps.core.models import AzioneComandoVocale, ComandoVocale, Configurazione4D


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
            "parametri_4d",
            "sistema",
            "sync_fatture",
            "sync_anagrafiche",
            "sync_categorie",
            "sync_gruppi_articoli",
        }:
            self.add_error(
                "destinazione",
                "Per la ricerca scegli clienti, fornitori, agenti, articoli, fatture, categorie o gruppi articoli.",
            )

        return cleaned_data
