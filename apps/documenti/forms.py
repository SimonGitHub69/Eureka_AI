from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.mirror_crud import apply_control_widgets
from apps.core.models import ParametriContabili
from apps.documenti.layout import CAMPO_RIGA_CHOICES
from apps.documenti.models import (
    ColonnaRigaDocumento,
    ContatoreDocumento,
    RigaDocumento,
    TestaDocumento,
    TipoDocumento,
)
from apps.documenti.numerazione import label_contatore_serie

_DATE = {"type": "date"}
_NUMBER = {"class": "form-control", "inputmode": "numeric"}
_PREZZO_UNITARIO = {
    "class": "form-control",
    "inputmode": "decimal",
    "step": "0.001",
}


class PrezzoUnitarioInput(forms.NumberInput):
    """Prezzo unitario riga: 3 decimali (es. 12.500)."""

    def format_value(self, value):
        if value in (None, ""):
            return None
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return value


class ContatoreSerieSelect(forms.Select):
    """Select Serie con data-serie / data-prossimo per aggiornare anteprima numero."""

    def __init__(self, *args, contatori_meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contatori_meta = contatori_meta or {}

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        key = str(value) if value is not None else ""
        meta = self.contatori_meta.get(key) or {}
        if meta:
            option["attrs"]["data-serie"] = meta.get("serie", "")
            option["attrs"]["data-prossimo"] = str(meta.get("prossimo", "") or "")
        return option


class TestaDocumentoForm(forms.ModelForm):
    class Meta:
        model = TestaDocumento
        fields = [
            "numero",
            "alfa",
            "data_documento",
            "validita",
            "data_consegna",
            "tipo_preventivo",
            "confermato",
            "valuta",
            "cambio",
            "codice_clifor",
            "codice_agente",
            "destinatario",
            "indirizzo",
            "localita",
            "cap",
            "provincia",
            "nazione",
            "telefono",
            "imponibile",
            "totale",
            "spese_imballo",
            "spese_trasporto",
            "spese_incasso",
            "spese_varie",
            "spese_bolli",
            "add_spese",
            "cod_pagamento",
            "porto",
            "cod_cau_trasp",
            "iban",
            "cod_banca",
            "codice_sconto",
            "sconto",
            "num_ordine_acq",
            "data_ordine_acq",
            "note",
            "annotazioni",
        ]
        labels = {
            "numero": "Numero",
            "alfa": "Serie",
            "data_documento": "Data",
            "validita": "Validità",
            "data_consegna": "Data consegna",
            "tipo_preventivo": "Tipo preventivo",
            "confermato": "Confermato",
            "valuta": "Valuta",
            "cambio": "Cambio (€)",
            "codice_clifor": "Cliente / Fornitore",
            "codice_agente": "Agente",
            "destinatario": "Luogo di destinazione",
            "indirizzo": "Indirizzo",
            "localita": "Località",
            "cap": "CAP",
            "provincia": "Provincia",
            "nazione": "Nazione",
            "telefono": "Telefono",
            "imponibile": "Imponibile",
            "totale": "Totale",
            "spese_imballo": "Spese imballo",
            "spese_trasporto": "Spese trasporto",
            "spese_incasso": "Spese incasso",
            "spese_varie": "Spese varie",
            "spese_bolli": "Spese bolli",
            "add_spese": "Addebita spese",
            "cod_pagamento": "Condizioni di pagamento",
            "porto": "Porto",
            "cod_cau_trasp": "Causale trasporto",
            "iban": "IBAN",
            "cod_banca": "Banca",
            "codice_sconto": "Codice",
            "sconto": "Sconto",
            "num_ordine_acq": "N. ordine acquisto",
            "data_ordine_acq": "Data ordine acquisto",
            "note": "Note",
            "annotazioni": "Annotazioni",
        }
        widgets = {
            "data_documento": forms.DateTimeInput(
                attrs=_DATE, format="%Y-%m-%d"
            ),
            "data_ordine_acq": forms.DateTimeInput(
                attrs=_DATE, format="%Y-%m-%d"
            ),
            "data_consegna": forms.DateTimeInput(
                attrs=_DATE, format="%Y-%m-%d"
            ),
            "validita": forms.TextInput(attrs={"class": "form-control", "maxlength": "40"}),
            "tipo_preventivo": forms.TextInput(
                attrs={"class": "form-control", "maxlength": "40"}
            ),
            "confermato": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "add_spese": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "valuta": forms.TextInput(attrs={"class": "form-control", "maxlength": "20"}),
            "cambio": forms.NumberInput(
                attrs={"class": "form-control", "inputmode": "decimal", "step": "0.0001"}
            ),
            "numero": forms.NumberInput(attrs=_NUMBER),
            "imponibile": forms.NumberInput(attrs=_NUMBER),
            "totale": forms.NumberInput(attrs=_NUMBER),
            "spese_imballo": forms.NumberInput(attrs={**_NUMBER, "step": "0.01", "data-spese-importo": "1"}),
            "spese_trasporto": forms.NumberInput(attrs={**_NUMBER, "step": "0.01", "data-spese-importo": "1"}),
            "spese_incasso": forms.NumberInput(attrs={**_NUMBER, "step": "0.01", "data-spese-importo": "1"}),
            "spese_varie": forms.NumberInput(attrs={**_NUMBER, "step": "0.01", "data-spese-importo": "1"}),
            "spese_bolli": forms.NumberInput(attrs={**_NUMBER, "step": "0.01", "data-spese-importo": "1"}),
            "note": forms.Textarea(
                attrs={
                    "rows": 3,
                    "data-long-text-edit": "1",
                    "data-long-text-title": "Note",
                }
            ),
            "annotazioni": forms.Textarea(
                attrs={
                    "rows": 3,
                    "data-long-text-edit": "1",
                    "data-long-text-title": "Annotazioni",
                }
            ),
        }

    def __init__(
        self,
        *args,
        clifor_label: str | None = None,
        scadenze_obbligatorie: bool = False,
        tipo: TipoDocumento | None = None,
        is_create: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.scadenze_obbligatorie = bool(scadenze_obbligatorie)
        self.tipo = tipo
        self.is_create = bool(is_create)
        for name in self.fields:
            self.fields[name].required = False
        for name in (
            "data_documento",
            "data_ordine_acq",
            "data_consegna",
        ):
            field = self.fields.get(name)
            if field is not None:
                field.input_formats = [
                    "%Y-%m-%d",
                    "%d/%m/%Y",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                ]
        if clifor_label:
            self.fields["codice_clifor"].label = clifor_label
        # Solo UI: sceglie DestCliFor e riempie Luogo di Destinazione (non persistito).
        self.fields["codice_dest"] = forms.CharField(
            required=False,
            label="Destinazione diversa",
            widget=forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "spellcheck": "false",
                    "placeholder": "Cod. destinazione",
                }
            ),
        )
        self._setup_serie_contatore()
        apply_control_widgets(
            self,
            exclude={"contatore_scelto"},
            keep_textarea={"note", "annotazioni"},
        )
        for name in (
            "spese_imballo",
            "spese_trasporto",
            "spese_incasso",
            "spese_varie",
            "spese_bolli",
            "spese_e15",
        ):
            field = self.fields.get(name)
            if field is not None:
                field.widget.attrs["data-spese-importo"] = "1"
                field.widget.attrs["step"] = "0.01"
        # Imponibile / Totale documento: ricalcolati dal castelletto (campi hidden)
        for name in ("imponibile", "totale"):
            field = self.fields.get(name)
            if field is not None:
                field.widget.attrs["readonly"] = True
                field.widget.attrs["data-castelletto-field"] = name

    def _setup_serie_contatore(self) -> None:
        """Su Nuovo: combo Serie → contatore; alfa sincronizzata dalla selezione."""
        if "contatore_scelto" in self.fields:
            del self.fields["contatore_scelto"]
        if not self.is_create or self.tipo is None:
            return
        disponibili = self.tipo.contatori_disponibili()
        if not disponibili:
            return
        pks = [c.pk for c in disponibili]
        labels = {c.pk: label_contatore_serie(c) for c in disponibili}
        serie_tipo = (self.tipo.serie or "").strip()
        default_pk = self.tipo.contatore_id
        propri = TipoDocumento._contatori_del_tipo(self.tipo)
        has_propri = bool(default_pk) or bool(propri)
        meta = {}
        for c in disponibili:
            serie = (c.serie_default or "").strip()
            if serie_tipo and default_pk and c.pk == default_pk:
                serie = serie_tipo
            meta[c.pk] = {
                "serie": serie,
                "prossimo": int(c.ultimo_numero or 0) + 1,
            }
        field = forms.ModelChoiceField(
            queryset=ContatoreDocumento.objects.filter(pk__in=pks).order_by(
                "serie_default", "codice", "label"
            ),
            label="Serie",
            required=has_propri,
            empty_label=None if has_propri else "— automatica (per tipo) —",
            widget=ContatoreSerieSelect(
                attrs={
                    "class": "form-select",
                    "data-serie-contatore": "1",
                },
                contatori_meta=meta,
            ),
        )
        field.label_from_instance = lambda obj, _labels=labels: _labels.get(
            obj.pk, label_contatore_serie(obj)
        )
        self.fields["contatore_scelto"] = field
        # Ordine UI: numero, contatore_scelto, poi resto (alfa nascosta)
        self.fields["alfa"].widget = forms.HiddenInput()
        ordered = {}
        for name in ("numero", "contatore_scelto", "alfa"):
            if name in self.fields:
                ordered[name] = self.fields.pop(name)
        ordered.update(self.fields)
        self.fields = ordered
        initial_c = self.initial.get("contatore_scelto")
        if initial_c and not self.is_bound:
            self.fields["contatore_scelto"].initial = initial_c

    def _posted_scadenze_raw(self) -> list[str]:
        data = self.data
        if not data:
            return []
        if hasattr(data, "getlist"):
            return [str(v) for v in data.getlist("scadenza")]
        raw = data.get("scadenza")
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return [str(v) for v in raw]
        return [str(raw)]

    @property
    def scadenze_input_values(self) -> list[str]:
        """Valori ISO (anche vuoti) da rimostrare nella card."""
        if self.is_bound:
            raw = self._posted_scadenze_raw()
            return raw if raw else [""]
        instance = getattr(self, "instance", None)
        stored = list(getattr(instance, "scadenze", None) or []) if instance else []
        values = [str(v) for v in stored if v]
        return values if values else [""]

    def clean(self):
        cleaned = super().clean()
        from apps.documenti.scadenze import _as_date, calcola_scadenze, dates_to_iso_list, load_condizione

        contatore = cleaned.get("contatore_scelto")
        if contatore is not None:
            from apps.documenti.numerazione import serie_default_for

            serie = serie_default_for(self.tipo, contatore) if self.tipo else (
                contatore.serie_default or ""
            ).strip()
            cleaned["alfa"] = serie
            self.instance.alfa = serie
        dates = []
        for raw in self._posted_scadenze_raw():
            d = _as_date(raw)
            if d:
                dates.append(d)
        cleaned["scadenze"] = dates_to_iso_list(dates)
        if not self.scadenze_obbligatorie:
            return cleaned
        if cleaned["scadenze"]:
            return cleaned
        slots = calcola_scadenze(
            data_documento=cleaned.get("data_documento"),
            condizione=load_condizione(cleaned.get("cod_pagamento")),
            totale=cleaned.get("totale"),
        )
        auto = dates_to_iso_list([slot.get("data") for slot in slots])
        if auto:
            cleaned["scadenze"] = auto
            return cleaned
        self.add_error(
            None,
            "Le scadenze sono obbligatorie per questo tipo documento.",
        )
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.scadenze = self.cleaned_data.get("scadenze") or []
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class RigaDocumentoForm(forms.ModelForm):
    class Meta:
        model = RigaDocumento
        fields = [
            "numero_riga",
            "codice",
            "descrizione",
            "quantita",
            "unita_misura",
            "prezzo_unitario",
            "sconto",
            "iva",
        ]
        labels = {
            "numero_riga": "#",
            "codice": "Codice",
            "descrizione": "Descrizione",
            "quantita": "Qtà",
            "unita_misura": "U.M.",
            "prezzo_unitario": "Prezzo",
            "sconto": "Sconto",
            "iva": "IVA",
        }
        widgets = {
            "numero_riga": forms.NumberInput(attrs=_NUMBER),
            "quantita": forms.NumberInput(attrs=_NUMBER),
            "prezzo_unitario": PrezzoUnitarioInput(attrs=_PREZZO_UNITARIO),
        }

    def __init__(self, *args, visible_campos=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = False
        apply_control_widgets(self)
        # Extra/empty form: nessun default 10 — lo assegna il JS (max+10) o il save.
        if not getattr(self.instance, "pk", None):
            if self.initial.get("numero_riga") in (10, "10"):
                self.initial["numero_riga"] = None
            field = self.fields.get("numero_riga")
            if field is not None and field.initial in (10, "10"):
                field.initial = None
        prezzo = self.fields.get("prezzo_unitario")
        if prezzo is not None:
            prezzo.widget.attrs["step"] = "0.001"
            prezzo.widget.attrs["inputmode"] = "decimal"
        desc = self.fields.get("descrizione")
        if desc is not None:
            desc.widget.attrs["data-long-text-edit"] = "1"
            desc.widget.attrs["data-long-text-title"] = "Descrizione riga"
        if visible_campos:
            visible = set(visible_campos)
            for name, field in self.fields.items():
                if name not in visible:
                    field.widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        if self.cleaned_data.get("DELETE"):
            return cleaned
        # Riga vuota: ok (formset extra)
        meaningful = any(
            cleaned.get(name) not in (None, "")
            for name in (
                "codice",
                "descrizione",
                "quantita",
                "prezzo_unitario",
                "iva",
                "sconto",
                "unita_misura",
            )
        )
        if not meaningful and not (self.instance and self.instance.pk):
            return cleaned
        return cleaned


class RigaDocumentoInlineFormSet(BaseInlineFormSet):
    """Formset righe con DELETE nascosto (gestito da pulsante cestino in UI)."""

    def add_fields(self, form, index):
        super().add_fields(form, index)
        delete = form.fields.get("DELETE")
        if delete is not None:
            delete.label = ""
            delete.widget.attrs.update(
                {
                    "class": "form-check-input riga-delete-input",
                    "tabindex": "-1",
                    "aria-hidden": "true",
                }
            )

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        # Rinumera le righe non cancellate (ordine formset) a 10, 20, 30…
        # Le righe DELETE non vengono toccate. Extra vuote senza pk restano blank.
        next_num = 10
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            meaningful = any(
                form.cleaned_data.get(name) not in (None, "")
                for name in (
                    "codice",
                    "descrizione",
                    "quantita",
                    "prezzo_unitario",
                    "iva",
                    "sconto",
                    "unita_misura",
                )
            )
            if not meaningful and not (form.instance and form.instance.pk):
                continue
            form.cleaned_data["numero_riga"] = next_num
            form.instance.numero_riga = next_num
            next_num += 10


RigaDocumentoFormSet = inlineformset_factory(
    TestaDocumento,
    RigaDocumento,
    form=RigaDocumentoForm,
    formset=RigaDocumentoInlineFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)
_CONTROL = {"class": "form-control", "autocomplete": "off"}
_SELECT = {"class": "form-select"}
_NUMBER = {"class": "form-control", "inputmode": "numeric"}


class ContatoreDocumentoForm(forms.ModelForm):
    class Meta:
        model = ContatoreDocumento
        fields = ["codice", "label", "ultimo_numero", "serie_default"]
        widgets = {
            "codice": forms.TextInput(attrs={**_CONTROL, "maxlength": "16"}),
            "label": forms.TextInput(attrs=_CONTROL),
            "ultimo_numero": forms.NumberInput(attrs={**_NUMBER, "min": "0"}),
            "serie_default": forms.TextInput(attrs={**_CONTROL, "maxlength": "16"}),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["label"].required = True
        self.fields["ultimo_numero"].required = False
        self.fields["serie_default"].required = False
        apply_control_widgets(self)
        self.fields["codice"].help_text = ""
        self.fields["ultimo_numero"].help_text = (
            "Imposta il valore di partenza (es. ultimo già emesso). "
            "Il prossimo documento riceverà questo valore + 1."
        )
        self.fields["serie_default"].help_text = (
            "Opzionale: serie (alfa) precompilata sui nuovi documenti."
        )
        if codice_readonly:
            self.fields["codice"].disabled = True

    def clean_codice(self):
        codice = (self.cleaned_data.get("codice") or "").strip().upper()
        if not codice:
            raise forms.ValidationError("Il codice è obbligatorio.")
        if not codice.replace("_", "").isalnum():
            raise forms.ValidationError("Usa solo lettere, numeri e underscore (es. FAT, ORD_V).")
        qs = ContatoreDocumento.objects.filter(codice=codice)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esiste già un contatore con questo codice.")
        return codice

    def clean_ultimo_numero(self):
        value = self.cleaned_data.get("ultimo_numero")
        return 0 if value in (None, "") else value

    def clean_serie_default(self):
        return (self.cleaned_data.get("serie_default") or "").strip().upper()


class TipoDocumentoForm(forms.ModelForm):
    class Meta:
        model = TipoDocumento
        fields = [
            "codice",
            "label",
            "categoria",
            "clifor_tipo",
            "scadenze",
            "contatore",
            "contatori",
            "serie",
            "attivo",
            "ordine",
            "descrizione",
            "source_table_4d",
            "source_detail_4d",
        ]
        widgets = {
            "codice": forms.TextInput(attrs={**_CONTROL, "maxlength": "8"}),
            "label": forms.TextInput(attrs=_CONTROL),
            "categoria": forms.Select(attrs=_SELECT),
            "clifor_tipo": forms.Select(attrs=_SELECT),
            "scadenze": forms.Select(attrs=_SELECT),
            "contatore": forms.Select(attrs=_SELECT),
            "contatori": forms.SelectMultiple(attrs={**_SELECT, "size": "6"}),
            "serie": forms.TextInput(attrs={**_CONTROL, "maxlength": "16"}),
            "attivo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordine": forms.NumberInput(attrs={**_NUMBER, "min": "0"}),
            "descrizione": forms.TextInput(attrs=_CONTROL),
            "source_table_4d": forms.TextInput(attrs=_CONTROL),
            "source_detail_4d": forms.TextInput(attrs=_CONTROL),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["label"].required = True
        self.fields["categoria"].required = True
        self.fields["clifor_tipo"].required = True
        self.fields["scadenze"].required = True
        self.fields["contatore"].required = False
        self.fields["contatore"].queryset = ContatoreDocumento.objects.all()
        self.fields["contatore"].empty_label = "— nessun contatore (per tipo) —"
        self.fields["contatore"].label = "Contatore predefinito"
        self.fields["contatori"].required = False
        self.fields["contatori"].queryset = ContatoreDocumento.objects.all()
        self.fields["contatori"].label = "Contatori / serie"
        self.fields["contatori"].help_text = (
            "Contatori di questo tipo nel combo Serie. In Nuovo documento "
            "compaiono anche quelli dei tipi affini (Preventivi↔Ordini, "
            "Fatture↔NC/ND)."
        )
        self.fields["serie"].required = False
        self.fields["descrizione"].required = False
        self.fields["source_table_4d"].required = False
        self.fields["source_detail_4d"].required = False
        self.fields["ordine"].required = False
        apply_control_widgets(self)
        self.fields["codice"].help_text = ""
        self.fields["categoria"].help_text = ""
        self.fields["clifor_tipo"].help_text = ""
        self.fields["scadenze"].help_text = ""
        self.fields["contatore"].help_text = (
            "Preselezionato in Nuovo. Stesso contatore = sequenza condivisa tra tipi."
        )
        self.fields["serie"].help_text = (
            "Opzionale: ha priorità sulla serie del contatore predefinito "
            "(non se l'utente sceglie un'altra serie dal combo)."
        )
        if codice_readonly:
            self.fields["codice"].disabled = True

    def clean_codice(self):
        codice = (self.cleaned_data.get("codice") or "").strip().upper()
        if not codice:
            raise forms.ValidationError("Il codice è obbligatorio.")
        if not codice.isalnum():
            raise forms.ValidationError("Usa solo lettere e numeri (es. ORV, OR2).")
        qs = TipoDocumento.objects.filter(codice=codice)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esiste già un parametro documento con questo codice.")
        return codice

    def clean_serie(self):
        return (self.cleaned_data.get("serie") or "").strip().upper()

    def clean_ordine(self):
        value = self.cleaned_data.get("ordine")
        return 0 if value in (None, "") else value

    def clean(self):
        cleaned = super().clean()
        default = cleaned.get("contatore")
        multi = list(cleaned.get("contatori") or [])
        if default is not None and default not in multi:
            multi.append(default)
            cleaned["contatori"] = multi
        return cleaned


class ColonnaRigaDocumentoForm(forms.ModelForm):
    class Meta:
        model = ColonnaRigaDocumento
        fields = ["campo", "posizione", "etichetta", "larghezza"]
        widgets = {
            "campo": forms.Select(attrs=_SELECT, choices=CAMPO_RIGA_CHOICES),
            "posizione": forms.NumberInput(attrs={**_NUMBER, "min": "1"}),
            "etichetta": forms.TextInput(attrs=_CONTROL),
            "larghezza": forms.TextInput(
                attrs={**_CONTROL, "placeholder": "es. 8rem"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["campo"].choices = [("", "— campo —")] + list(CAMPO_RIGA_CHOICES)
        self.fields["campo"].required = True
        self.fields["posizione"].required = False
        self.fields["etichetta"].required = False
        self.fields["larghezza"].required = False
        apply_control_widgets(self)

    def clean_campo(self):
        campo = (self.cleaned_data.get("campo") or "").strip()
        if not campo:
            raise forms.ValidationError("Scegli un campo.")
        allowed = {item[0] for item in CAMPO_RIGA_CHOICES}
        if campo not in allowed:
            raise forms.ValidationError("Campo non valido.")
        return campo

    def clean_posizione(self):
        value = self.cleaned_data.get("posizione")
        return 10 if value in (None, "") else value


class ColonnaRigaInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen: set[str] = set()
        next_pos = 10
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            campo = form.cleaned_data.get("campo")
            if not campo:
                continue
            if campo in seen:
                form.add_error("campo", "Questo campo è già in una colonna.")
                continue
            seen.add(campo)
            form.cleaned_data["posizione"] = next_pos
            form.instance.posizione = next_pos
            next_pos += 10


ColonnaRigaFormSet = inlineformset_factory(
    TipoDocumento,
    ColonnaRigaDocumento,
    form=ColonnaRigaDocumentoForm,
    formset=ColonnaRigaInlineFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


def riga_formset_for(tipo, *args, **kwargs):
    """Formset righe con campi visibili secondo il layout del tipo documento."""
    from apps.documenti.layout import campi_visibili, colonne_riga_for

    form_kwargs = dict(kwargs.pop("form_kwargs", None) or {})
    form_kwargs["visible_campos"] = campi_visibili(colonne_riga_for(tipo))
    kwargs["form_kwargs"] = form_kwargs
    return RigaDocumentoFormSet(*args, **kwargs)


class AliquotaIvaSpeseForm(forms.ModelForm):
    """Solo aliquota IVA spese (Parametri contabili), da maschera Preventivi."""

    class Meta:
        model = ParametriContabili
        fields = ["aliquota_iva_spese"]
        labels = {"aliquota_iva_spese": "Aliquota IVA spese"}
        widgets = {
            "aliquota_iva_spese": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["aliquota_iva_spese"].required = False

    def clean_aliquota_iva_spese(self):
        return (self.cleaned_data.get("aliquota_iva_spese") or "").strip()
