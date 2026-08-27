from django import forms

from apps.articoli.lookups import descrizione_deposito
from apps.causali_magazzino.models import CausaleMagazzino
from apps.core.mirror_crud import SELECT, apply_control_widgets, clean_unique_pk

SI_NO_CHOICES = (
    ("", "No"),
    ("Si", "Sì"),
)

SI_NO_FIELD_NAMES = ("scar_db", "update_listino", "update_prezzo_medio")


def norm_si_no(value: str | None) -> str:
    """Normalizza flag 4D testuali a «Si» o vuoto (No)."""
    text = (value or "").strip().casefold()
    if text.startswith("si") or text in {"s", "1", "true", "y", "yes"}:
        return "Si"
    return ""


def si_no_label(value: str | None) -> str:
    return "Sì" if norm_si_no(value) == "Si" else "No"


# Alias retrocompatibili
norm_update_listino = norm_si_no
update_listino_label = si_no_label


class CausaleMagazzinoForm(forms.ModelForm):
    scar_db = forms.ChoiceField(
        label="Scarico distinta base",
        required=False,
        choices=SI_NO_CHOICES,
        widget=forms.Select(attrs=SELECT),
    )
    update_listino = forms.ChoiceField(
        label="Aggiorna ultimo prezzo",
        required=False,
        choices=SI_NO_CHOICES,
        widget=forms.Select(attrs=SELECT),
    )
    update_prezzo_medio = forms.ChoiceField(
        label="Aggiorna prezzo medio",
        required=False,
        choices=SI_NO_CHOICES,
        widget=forms.Select(attrs=SELECT),
    )

    class Meta:
        model = CausaleMagazzino
        fields = [
            "codice",
            "descrizione",
            "tipo_causale",
            "deposito_entrata",
            "deposito_uscita",
            "scar_db",
            "update_listino",
            "update_prezzo_medio",
            "cod_market",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "tipo_causale": "Tipo causale",
            "deposito_entrata": "Deposito entrata",
            "deposito_uscita": "Deposito uscita",
            "scar_db": "Scarico distinta base",
            "update_listino": "Aggiorna ultimo prezzo",
            "update_prezzo_medio": "Aggiorna prezzo medio",
            "cod_market": "Cod. market",
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in (
            "tipo_causale",
            "deposito_entrata",
            "deposito_uscita",
            "scar_db",
            "update_listino",
            "update_prezzo_medio",
            "cod_market",
        ):
            self.fields[name].required = False
        apply_control_widgets(self)
        if not self.is_bound and self.instance and getattr(self.instance, "pk", None):
            for name in SI_NO_FIELD_NAMES:
                self.initial[name] = norm_si_no(getattr(self.instance, name, None))
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    def clean_scar_db(self):
        return norm_si_no(self.cleaned_data.get("scar_db"))

    def clean_update_listino(self):
        return norm_si_no(self.cleaned_data.get("update_listino"))

    def clean_update_prezzo_medio(self):
        return norm_si_no(self.cleaned_data.get("update_prezzo_medio"))

    def clean_deposito_entrata(self):
        return (self.cleaned_data.get("deposito_entrata") or "").strip() or None

    def clean_deposito_uscita(self):
        return (self.cleaned_data.get("deposito_uscita") or "").strip() or None

    def clean_codice(self):
        return clean_unique_pk(self)


def linked_labels_for_causale(form_or_obj) -> dict[str, str]:
    """Descrizioni deposito per form/dettaglio."""
    if hasattr(form_or_obj, "data") and getattr(form_or_obj, "is_bound", False):
        data = form_or_obj.data
        entrata = data.get("deposito_entrata")
        uscita = data.get("deposito_uscita")
    elif hasattr(form_or_obj, "instance"):
        inst = form_or_obj.instance
        entrata = getattr(inst, "deposito_entrata", None)
        uscita = getattr(inst, "deposito_uscita", None)
    else:
        entrata = getattr(form_or_obj, "deposito_entrata", None)
        uscita = getattr(form_or_obj, "deposito_uscita", None)
    return {
        "deposito_entrata": descrizione_deposito(entrata),
        "deposito_uscita": descrizione_deposito(uscita),
    }
