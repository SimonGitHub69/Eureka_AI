from django import forms

from apps.core.dashboard_shortcuts import (
    DASHBOARD_SHORTCUT_CATALOG,
    SHORTCUT_MODE_CHOICES,
    catalog_by_section,
    resolve_shortcut_configs,
)
from apps.core.mirror_crud import CONTROL, apply_control_widgets
from apps.core.models import (
    AzioneComandoVocale,
    ComandoVocale,
    Configurazione4D,
    ConfigurazionePC,
    ConfigurazioneProgramma,
    ParametriContabili,
    ParametriMail,
    SPESE_CONTROPARTITA_FIELDS,
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
        fields = [
            "suono_errore_attivo",
            "suono_errore_wav",
            "debug_ai_sql",
            "ai_recent_searches_limit",
            "ai_example_prompt",
            "prezzo_decimali",
            "prezzo_decimali_stampa",
            "inventario_discrepanza_pct",
            "doc_prv",
            "doc_orv",
            "doc_ora",
            "doc_ddt",
            "doc_fat",
            "doc_ncr",
            "doc_ndb",
            "extra_carbon",
            "note",
        ]
        widgets = {
            "suono_errore_attivo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "debug_ai_sql": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ai_recent_searches_limit": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "max": "100",
                    "step": "1",
                }
            ),
            "ai_example_prompt": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "maxlength": "500",
                }
            ),
            "inventario_discrepanza_pct": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "max": "100",
                    "step": "1",
                }
            ),
            "prezzo_decimali": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "2",
                    "max": "6",
                    "step": "1",
                }
            ),
            "prezzo_decimali_stampa": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "2",
                    "max": "6",
                    "step": "1",
                }
            ),
            "doc_prv": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "doc_orv": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "doc_ora": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "doc_ddt": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "doc_fat": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "doc_ncr": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "doc_ndb": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "extra_carbon": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "suono_errore_wav": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": ".wav,audio/wav"}
            ),
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in (
            "suono_errore_attivo",
            "debug_ai_sql",
            "prezzo_decimali",
            "prezzo_decimali_stampa",
            "inventario_discrepanza_pct",
            "doc_prv",
            "doc_orv",
            "doc_ora",
            "doc_ddt",
            "doc_fat",
            "doc_ncr",
            "doc_ndb",
            "extra_carbon",
        ):
            if name in self.fields:
                self.fields[name].required = False

    def clean_suono_errore_wav(self):
        uploaded = self.cleaned_data.get("suono_errore_wav")
        if not uploaded:
            return uploaded
        name = (getattr(uploaded, "name", "") or "").lower()
        if not name.endswith(".wav"):
            raise forms.ValidationError("Caricare un file in formato .wav.")
        return uploaded

    def clean_ai_recent_searches_limit(self):
        value = self.cleaned_data.get("ai_recent_searches_limit")
        if value in (None, ""):
            return 10
        if value < 1:
            raise forms.ValidationError("Indicare almeno 1 ricerca recente.")
        if value > 100:
            raise forms.ValidationError("Indicare al massimo 100 ricerche recenti.")
        return value

    def clean_ai_example_prompt(self):
        value = (self.cleaned_data.get("ai_example_prompt") or "").strip()
        if not value:
            return ConfigurazioneProgramma._meta.get_field("ai_example_prompt").default
        return value

    def clean_inventario_discrepanza_pct(self):
        value = self.cleaned_data.get("inventario_discrepanza_pct")
        if value in (None, ""):
            return 25
        if value < 1:
            raise forms.ValidationError("Indicare almeno l'1%.")
        if value > 100:
            raise forms.ValidationError("Indicare al massimo il 100%.")
        return value

    def clean_prezzo_decimali(self):
        from apps.core.prezzi import PREZZO_DECIMALI_DEFAULT, clamp_prezzo_decimali

        value = self.cleaned_data.get("prezzo_decimali")
        if value in (None, ""):
            return PREZZO_DECIMALI_DEFAULT
        clamped = clamp_prezzo_decimali(value)
        if clamped != int(value):
            raise forms.ValidationError("Indicare un valore tra 2 e 6 decimali.")
        return clamped

    def clean_prezzo_decimali_stampa(self):
        from apps.core.prezzi import PREZZO_DECIMALI_DEFAULT, clamp_prezzo_decimali

        value = self.cleaned_data.get("prezzo_decimali_stampa")
        if value in (None, ""):
            return PREZZO_DECIMALI_DEFAULT
        clamped = clamp_prezzo_decimali(value)
        if clamped != int(value):
            raise forms.ValidationError("Indicare un valore tra 2 e 6 decimali.")
        return clamped


class ParametriContabiliForm(forms.ModelForm):
    class Meta:
        model = ParametriContabili
        fields = [
            "aliquota_iva_spese",
            *[name for name, _label in SPESE_CONTROPARTITA_FIELDS],
            "note",
        ]
        widgets = {
            "aliquota_iva_spese": forms.TextInput(attrs={**CONTROL}),
            **{
                name: forms.TextInput(attrs={**CONTROL})
                for name, _label in SPESE_CONTROPARTITA_FIELDS
            },
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = False
        apply_control_widgets(self)

    def clean_aliquota_iva_spese(self):
        return (self.cleaned_data.get("aliquota_iva_spese") or "").strip()

    def clean(self):
        from apps.pdc.hierarchy import pdc_is_contropartita, pdc_livello_label

        cleaned = super().clean()
        for name, _label in SPESE_CONTROPARTITA_FIELDS:
            codice = (cleaned.get(name) or "").strip()
            cleaned[name] = codice
            if not codice:
                continue
            if not pdc_is_contropartita(codice):
                self.add_error(
                    name,
                    (
                        f"Selezionare una contropartita PDC "
                        f"(formato Mastro.Conto.Sottoconto), non "
                        f"{pdc_livello_label(codice).lower()}."
                    ),
                )
        return cleaned


class ParametriMailForm(forms.ModelForm):
    class Meta:
        model = ParametriMail
        fields = [
            "attiva",
            "server_smtp",
            "porta",
            "usa_tls",
            "usa_ssl",
            "utente",
            "password",
            "mittente",
            "nome_mittente",
            "reply_to",
            "copia_nascosta",
            "email_test",
            "timeout_secondi",
            "note",
        ]
        widgets = {
            "attiva": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "usa_tls": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "usa_ssl": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "server_smtp": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "smtp.gmail.com",
                }
            ),
            "porta": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "utente": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            ),
            "password": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "type": "password",
                    "autocomplete": "new-password",
                    "placeholder": "Lascia vuoto per non modificare",
                }
            ),
            "mittente": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            ),
            "nome_mittente": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            ),
            "reply_to": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            ),
            "copia_nascosta": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "placeholder": "mail1@azienda.it; mail2@azienda.it",
                }
            ),
            "email_test": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            ),
            "timeout_secondi": forms.NumberInput(
                attrs={"class": "form-control", "min": "5"}
            ),
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = False
        # Non mostrare la password salvata
        self.fields["password"].initial = ""

    def clean_password(self):
        password = (self.cleaned_data.get("password") or "").strip()
        if password:
            return password
        if self.instance.pk and self.instance.password:
            return self.instance.password
        return ""

    def clean_server_smtp(self):
        from apps.core.mail import normalize_smtp_host

        host, port = normalize_smtp_host(self.cleaned_data.get("server_smtp"))
        if port:
            self._smtp_port_from_host = port
        if host and "@" in host:
            raise forms.ValidationError(
                "Inserisci solo il nome del server (es. smtp.gmail.com), non un indirizzo email."
            )
        return host

    def clean(self):
        cleaned = super().clean()
        usa_tls = bool(cleaned.get("usa_tls"))
        usa_ssl = bool(cleaned.get("usa_ssl"))
        if usa_tls and usa_ssl:
            self.add_error(
                "usa_ssl",
                "Non usare insieme STARTTLS e SSL/TLS: scegline uno (587+TLS o 465+SSL).",
            )

        port_from_host = getattr(self, "_smtp_port_from_host", None)
        if port_from_host:
            cleaned["porta"] = port_from_host

        if not cleaned.get("attiva"):
            return cleaned

        if not (cleaned.get("server_smtp") or "").strip():
            self.add_error("server_smtp", "Inserisci il server SMTP.")
        if not cleaned.get("porta"):
            self.add_error("porta", "Inserisci la porta SMTP.")
        if not (cleaned.get("mittente") or "").strip():
            self.add_error("mittente", "Inserisci l'email mittente.")
        return cleaned

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


class ConfigurazionePCForm(forms.ModelForm):
    class Meta:
        model = ConfigurazionePC
        fields = [
            "nome_pc",
            "descrizione",
            "assistente_vocale_attivo",
            "navbar_fissa",
            "liste_fisse",
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
            "assistente_vocale_attivo": forms.CheckboxInput(),
            "navbar_fissa": forms.CheckboxInput(),
            "liste_fisse": forms.CheckboxInput(),
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

        stored = {}
        if self.instance and self.instance.pk:
            stored = self.instance.dashboard_shortcuts or {}
        configs = resolve_shortcut_configs(stored)
        self.dashboard_shortcut_sections = []
        for section_label, items in catalog_by_section():
            section_fields = []
            for item in items:
                key = item["key"]
                cfg = configs[key]
                field_name = f"dash_{key}"
                gruppo_name = f"dash_{key}_gruppo"
                pos_name = f"dash_{key}_posizione"
                etichetta_name = f"dash_{key}_etichetta"
                self.fields[field_name] = forms.ChoiceField(
                    choices=SHORTCUT_MODE_CHOICES,
                    required=True,
                    label=item["label"],
                    initial=cfg["mode"],
                    widget=forms.RadioSelect(
                        attrs={"class": "btn-check eureka-tri-state__input"}
                    ),
                )
                self.fields[etichetta_name] = forms.CharField(
                    required=False,
                    label="Etichetta barra",
                    initial=cfg.get("etichetta") or item["label"],
                    max_length=60,
                    widget=forms.TextInput(
                        attrs={
                            "class": "form-control form-control-sm eureka-shortcut-config__text",
                            "placeholder": item["label"],
                            "title": "Testo sotto l'icona in barra alta (default: voce di menu)",
                            "autocomplete": "off",
                        }
                    ),
                )
                self.fields[gruppo_name] = forms.IntegerField(
                    required=True,
                    min_value=1,
                    label="Gruppo",
                    initial=cfg["gruppo"],
                    widget=forms.NumberInput(
                        attrs={
                            "class": "form-control form-control-sm eureka-shortcut-config__num",
                            "min": "1",
                            "step": "1",
                            "title": "Gruppo in barra alta (1, 2, … da sinistra)",
                        }
                    ),
                )
                self.fields[pos_name] = forms.IntegerField(
                    required=True,
                    label="Posizione",
                    initial=cfg["posizione"],
                    widget=forms.NumberInput(
                        attrs={
                            "class": "form-control form-control-sm eureka-shortcut-config__num",
                            "step": "1",
                            "title": "Ordine da sinistra a destra nel gruppo",
                        }
                    ),
                )
                section_fields.append(
                    {
                        "field": self[field_name],
                        "etichetta": self[etichetta_name],
                        "gruppo": self[gruppo_name],
                        "posizione": self[pos_name],
                        "icon": item.get("icon") or "ti-click",
                        "key": key,
                        "menu_label": item["label"],
                    }
                )
            self.dashboard_shortcut_sections.append((section_label, section_fields))

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

    def save(self, commit=True):
        obj = super().save(commit=False)
        from apps.core.dashboard_shortcuts import normalize_shortcut_mode

        payload = {}
        for item in DASHBOARD_SHORTCUT_CATALOG:
            key = item["key"]
            etichetta = (self.cleaned_data.get(f"dash_{key}_etichetta") or "").strip()
            if not etichetta:
                etichetta = item["label"]
            payload[key] = {
                "mode": normalize_shortcut_mode(
                    self.cleaned_data.get(f"dash_{key}")
                ),
                "gruppo": int(self.cleaned_data.get(f"dash_{key}_gruppo") or 1),
                "posizione": int(
                    self.cleaned_data.get(f"dash_{key}_posizione") or 0
                ),
                "etichetta": etichetta[:60],
            }
        obj.dashboard_shortcuts = payload
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
