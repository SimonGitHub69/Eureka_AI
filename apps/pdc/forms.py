from django import forms

from apps.core.mirror_crud import apply_control_widgets, clean_unique_pk
from apps.pdc.gruppo import gruppo_choice_field, raggruppamento_choices
from apps.pdc.hierarchy import (
    LIVELLO_CONTO,
    LIVELLO_MASTRO,
    LIVELLO_SOTTOCONTO,
    LIVELLO_LABELS,
    pdc_livello,
)
from apps.pdc.models import PianoConti

TIPO_CONTO_CHOICES = [
    ("", "---------"),
    ("Attivita'", "Attività"),
    ("Passivita'", "Passività"),
    ("Costi", "Costi"),
    ("Ricavi", "Ricavi"),
    ("Ordine", "Ordine"),
    ("Diversi", "Diversi"),
]

BOOL_FIELDS = ("modifica_cespiti", "disabilitato", "f_non_integrare")
NOLEGGIO_FIELDS = ("nomenclatura", "bene_servizio", "tipo_noleggio")

TIPO_NOLEGGIO_CHOICES = [
    ("", "---------"),
    ("0", "0 – Nessun noleggio"),
    ("1", "1 – Autovettura"),
    ("2", "2 – Caravan"),
    ("3", "3 – Altri veicoli"),
    ("4", "4 – Unità da diporto"),
    ("5", "5 – Aeromobili"),
]


class PianoContiForm(forms.ModelForm):
    gruppo = gruppo_choice_field()

    tipo_conto = forms.ChoiceField(
        choices=TIPO_CONTO_CHOICES,
        required=False,
        label="Tipo conto",
    )
    modifica_cespiti = forms.BooleanField(
        required=False,
        label="Movimenta cespiti",
    )
    tipo_noleggio = forms.ChoiceField(
        choices=TIPO_NOLEGGIO_CHOICES,
        required=False,
        label="Tipo noleggio",
    )

    class Meta:
        model = PianoConti
        fields = [
            "codice",
            "descrizione",
            "desc_conto",
            "tipo_conto",
            "gruppo",
            "gruppo_cee",
            "tipo_controllo",
            "bene_servizio",
            "nomenclatura",
            "cod_voce_analitica",
            "cod_centro_analisi",
            "codice_art_edifir",
            "modifica_cespiti",
            "tipo_noleggio",
            "disabilitato",
            "f_non_integrare",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "desc_conto": "Descrizione conto",
            "tipo_conto": "Tipo conto",
            "gruppo": "Gruppo",
            "gruppo_cee": "Gruppo CEE",
            "tipo_controllo": "Tipo controllo",
            "bene_servizio": "Bene o servizio",
            "nomenclatura": "Nomenclatura Intrastat",
            "cod_voce_analitica": "Voce analitica collegata",
            "cod_centro_analisi": "Centro analisi collegato",
            "codice_art_edifir": "Codice art. EDIFIR",
            "disabilitato": "Sottoconto disattivato",
            "f_non_integrare": "NON INTEGRARE (controllo analitica)",
        }
        widgets = {
            **{name: forms.CheckboxInput() for name in BOOL_FIELDS},
        }

    def __init__(
        self,
        *args,
        codice_readonly: bool = False,
        livello: int | None = None,
        parent_prefix: str = "",
        azienda_noleggio: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.azienda_noleggio = azienda_noleggio
        if livello is None and self.instance and self.instance.pk:
            livello = pdc_livello(self.instance.codice)
        self.livello = livello if livello is not None else LIVELLO_MASTRO
        self.parent_prefix = (parent_prefix or "").strip()
        self.split_codice = (
            not codice_readonly
            and not (self.instance and self.instance.pk)
            and self.parent_prefix
            and self.livello in (LIVELLO_CONTO, LIVELLO_SOTTOCONTO)
        )
        self.codice_prefix = f"{self.parent_prefix}." if self.split_codice else ""

        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in self.fields:
            if name not in ("codice", "descrizione"):
                self.fields[name].required = False

        codice_labels = {
            LIVELLO_MASTRO: "Codice mastro",
            LIVELLO_CONTO: "Codice conto",
            LIVELLO_SOTTOCONTO: "Codice sottoconto",
        }
        self.fields["codice"].label = codice_labels.get(
            self.livello, codice_labels[LIVELLO_MASTRO]
        )

        if self.livello == LIVELLO_MASTRO:
            self.fields["codice"].help_text = "Solo numeri, senza punti (es. 1)."
        elif self.parent_prefix and not self.split_codice:
            self.fields["codice"].help_text = (
                f"Formato: {self.parent_prefix}.XX (es. {self.parent_prefix}.10)."
            )

        if self.split_codice:
            suffix_label = (
                "Codice conto" if self.livello == LIVELLO_CONTO else "Codice sottoconto"
            )
            self.fields["codice_suffix"] = forms.CharField(
                label=suffix_label,
                required=True,
                help_text=f"Codice completo: {self.codice_prefix}…",
            )
            self.fields["codice"].required = False
            self.fields["codice"].widget = forms.HiddenInput()

        self._ensure_choice("tipo_conto", TIPO_CONTO_CHOICES)
        self._ensure_choice("gruppo", raggruppamento_choices())
        if self.azienda_noleggio:
            self._ensure_choice("tipo_noleggio", TIPO_NOLEGGIO_CHOICES)
        else:
            for name in NOLEGGIO_FIELDS:
                self.fields.pop(name, None)

        if self.livello in (LIVELLO_MASTRO, LIVELLO_CONTO):
            self.fields["gruppo"].help_text = "Collegato a Raggruppamento Conti."

        apply_control_widgets(self, keep_textarea=set())
        if self.split_codice:
            self.fields["codice_suffix"].widget.attrs.setdefault("class", "form-control")
            self.fields["codice_suffix"].widget.attrs.setdefault("autocomplete", "off")
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def _ensure_choice(self, field_name, choices):
        field = self.fields[field_name]
        current = ""
        if self.is_bound:
            current = (self.data.get(field_name) or "").strip()
        elif self.instance and self.instance.pk:
            val = getattr(self.instance, field_name, None)
            current = str(val).strip() if val is not None and val != "" else ""
        opts = list(choices)
        if current and current not in dict(opts):
            opts.append((current, current))
        field.choices = opts

    def clean(self):
        return super().clean()

    def clean_codice(self):
        if self.split_codice:
            return None
        codice = clean_unique_pk(self)
        livello = pdc_livello(codice)
        if self.livello == LIVELLO_MASTRO:
            if livello != LIVELLO_MASTRO:
                raise forms.ValidationError(
                    "Il mastro non deve contenere punti (es. 1, 2, 3)."
                )
        elif self.livello == LIVELLO_CONTO:
            if livello != LIVELLO_CONTO:
                raise forms.ValidationError(
                    "Il conto deve avere il formato Mastro.Conto (es. 1.10)."
                )
            if self.parent_prefix and not codice.startswith(f"{self.parent_prefix}."):
                raise forms.ValidationError(
                    f"Il conto deve iniziare con {self.parent_prefix}."
                )
        elif self.livello == LIVELLO_SOTTOCONTO:
            if livello != LIVELLO_SOTTOCONTO:
                raise forms.ValidationError(
                    "Il sottoconto deve avere il formato Mastro.Conto.Sottoconto (es. 1.10.9)."
                )
            if self.parent_prefix and not codice.startswith(f"{self.parent_prefix}."):
                raise forms.ValidationError(
                    f"Il sottoconto deve iniziare con {self.parent_prefix}."
                )
        return codice

    def clean(self):
        cleaned = super().clean()
        if not self.split_codice:
            return cleaned

        suffix = (cleaned.get("codice_suffix") or "").strip()
        if not suffix:
            self.add_error("codice_suffix", "Il codice è obbligatorio.")
            return cleaned
        if "." in suffix:
            self.add_error(
                "codice_suffix",
                "Inserire solo la parte finale del codice, senza punti.",
            )
            return cleaned

        codice = f"{self.parent_prefix}.{suffix}"
        if self._meta.model.objects.filter(codice=codice).exists():
            self.add_error(
                "codice_suffix",
                f"Il codice «{codice}» esiste già: non è possibile inserire due codici uguali.",
            )
            return cleaned

        cleaned["codice"] = codice
        return cleaned

    def clean_tipo_conto(self):
        return (self.cleaned_data.get("tipo_conto") or "").strip() or None

    def clean_gruppo(self):
        return (self.cleaned_data.get("gruppo") or "").strip() or None

    def clean_tipo_noleggio(self):
        raw = (self.cleaned_data.get("tipo_noleggio") or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise forms.ValidationError("Valore numerico non valido.")

