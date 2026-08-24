from django import forms

from apps.articoli.models import Articolo
from apps.aliquote.models import NATURE_SDI
from apps.core.mirror_crud import SELECT, apply_control_widgets, clean_unique_pk

NATURE_CHOICES = [("", "—")] + [
    (code, f"{code} - {label}") for code, label in NATURE_SDI.items()
]

BOOL_FIELDS = (
    "descr_express",
    "giacenza",
    "disponibile",
    "fl_disattivato",
    "gest_lotti",
    "kit",
    "no_magazzino",
    "confezionato",
    "articolo_tag",
    "richiesta_patentino",
)

NUMBER_FIELDS = (
    "colli",
    "listino1",
    "sconto1",
    "listino2",
    "sconto2",
    "listino3",
    "sconto3",
    "prezzo_ult_car",
    "prezzo_medio_acquisto",
    "scorta_min",
    "volume",
    "peso_netto",
    "peso_lordo_manodopera",
)


BENE_SERVIZIO_CHOICES = [
    ("", "---------"),
    ("Bene", "Bene"),
    ("Servizio", "Servizio"),
]


class ArticoloForm(forms.ModelForm):
    bene_servizio = forms.ChoiceField(
        choices=BENE_SERVIZIO_CHOICES,
        required=False,
        label="Bene o servizio",
    )
    chi1_natura = forms.ChoiceField(
        label="Natura",
        required=False,
        choices=NATURE_CHOICES,
        widget=forms.Select(attrs=SELECT),
    )

    class Meta:
        model = Articolo
        fields = [
            "codice",
            "descrizione",
            "cod_magazzino",
            "cat_omogenea",
            "cod_gruppo",
            "cod_fornitore",
            "cod_iva",
            "unita_misura",
            "codice_alternativo1",
            "codice_alternativo2",
            "cod_breve_art",
            "colli",
            "descr_express",
            "scorta_min",
            "volume",
            "peso_netto",
            "peso_lordo_manodopera",
            "origine",
            "chi1_natura",
            "c_partita_vend",
            "c_partita_acq",
            "nomenclatura",
            "bene_servizio",
            "listino1",
            "sconto1",
            "listino2",
            "sconto2",
            "listino3",
            "sconto3",
            "prezzo_ult_car",
            "prezzo_medio_acquisto",
            "giacenza",
            "disponibile",
            "fl_disattivato",
            "gest_lotti",
            "kit",
            "no_magazzino",
            "confezionato",
            "articolo_tag",
            "richiesta_patentino",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "cod_magazzino": "Codice magazzino",
            "cat_omogenea": "Categ. merceologica",
            "cod_gruppo": "Gruppo articolo",
            "cod_fornitore": "Codice fornitore",
            "cod_iva": "Codice IVA",
            "unita_misura": "Unità di misura",
            "codice_alternativo1": "Cod. art. fornitore",
            "codice_alternativo2": "Cod. alternativo 2",
            "cod_breve_art": "Cod. breve",
            "colli": "Numero colli",
            "descr_express": "Chiede descriz. in DDT",
            "scorta_min": "Scorta minima",
            "volume": "Volume m³",
            "peso_netto": "Peso netto kg",
            "peso_lordo_manodopera": "Peso lordo kg",
            "origine": "Origine",
            "chi1_natura": "Natura",
            "c_partita_vend": "C/Partita vendita",
            "c_partita_acq": "C/Partita acquisto",
            "nomenclatura": "Nomenclatura Intrastat",
            "bene_servizio": "Bene o servizio",
            "listino1": "Listino attuale",
            "sconto1": "Sconto listino 1 %",
            "listino2": "Listino futuro",
            "sconto2": "Sconto listino 2 %",
            "listino3": "Prezzo negozio",
            "sconto3": "Sconto listino 3 %",
            "prezzo_ult_car": "Prezzo ultimo carico",
            "prezzo_medio_acquisto": "Prezzo medio acquisto",
            "giacenza": "Giacenza",
            "disponibile": "Disponibile",
            "fl_disattivato": "Articolo disattivato",
            "gest_lotti": "Gestione lotti",
            "kit": "Articolo con kit",
            "no_magazzino": "Non movimenta mag.",
            "confezionato": "Confezionato",
            "articolo_tag": "Articolo TAG",
            "richiesta_patentino": "Patentino",
        }
        widgets = {
            **{name: forms.NumberInput(attrs={"step": "any"}) for name in NUMBER_FIELDS},
            **{name: forms.CheckboxInput() for name in BOOL_FIELDS},
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in self.fields:
            if name not in ("codice", "descrizione"):
                self.fields[name].required = False
        apply_control_widgets(self)
        if codice_readonly:
            self.fields["codice"].disabled = True
        current_natura = ""
        if self.is_bound:
            current_natura = (self.data.get("chi1_natura") or "").strip().upper()
        elif self.instance and getattr(self.instance, "pk", None):
            current_natura = (self.instance.chi1_natura or "").strip().upper()
        natura_choices = list(NATURE_CHOICES)
        if current_natura and current_natura not in dict(natura_choices):
            natura_choices.append((current_natura, current_natura))
        self.fields["chi1_natura"].choices = natura_choices
        from apps.core.prezzi import prezzo_input_step

        prezzo_step = prezzo_input_step()
        for name in (
            "listino1",
            "listino2",
            "listino3",
            "prezzo_ult_car",
            "prezzo_medio_acquisto",
        ):
            field = self.fields.get(name)
            if field is not None:
                field.widget.attrs["step"] = prezzo_step
                field.widget.attrs["inputmode"] = "decimal"

    def clean_chi1_natura(self):
        return (self.cleaned_data.get("chi1_natura") or "").strip().upper() or None

    def clean_codice(self):
        return clean_unique_pk(self)
