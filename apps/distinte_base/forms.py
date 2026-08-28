from django import forms

from apps.core.mirror_crud import apply_control_widgets
from apps.distinte_base.models import DistintaBase


class DistintaBaseForm(forms.ModelForm):
    class Meta:
        model = DistintaBase
        fields = [
            "codice_db",
            "codice_art",
            "descrizione",
            "qta",
            "um",
            "qta2",
            "um2",
            "costo",
            "costo_medio",
            "listino",
            "ricarico",
            "totale_costo",
            "costo_manuale",
            "fase",
            "lavoraz_mater",
            "cod_gruppo_art",
            "cod_cat_merc",
            "cod_forn",
            "da_cancellare",
        ]
        labels = {
            "codice_db": "Codice distinta (padre)",
            "codice_art": "Codice articolo (componente)",
            "descrizione": "Descrizione",
            "qta": "Quantità",
            "um": "U.M.",
            "qta2": "Quantità 2",
            "um2": "U.M. 2",
            "costo": "Costo",
            "costo_medio": "Costo medio",
            "listino": "Listino",
            "ricarico": "Ricarico",
            "totale_costo": "Totale costo",
            "costo_manuale": "Costo manuale",
            "fase": "Fase",
            "lavoraz_mater": "Lavorazione / materiale",
            "cod_gruppo_art": "Gruppo articoli",
            "cod_cat_merc": "Cat. merceologica",
            "cod_forn": "Cod. fornitore",
            "da_cancellare": "Da cancellare",
        }
        widgets = {
            "qta": forms.NumberInput(),
            "qta2": forms.NumberInput(),
            "costo": forms.NumberInput(),
            "costo_medio": forms.NumberInput(),
            "listino": forms.NumberInput(),
            "ricarico": forms.NumberInput(),
            "totale_costo": forms.NumberInput(),
            "costo_manuale": forms.NumberInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice_db"].required = True
        self.fields["codice_art"].required = True
        for name in self.fields:
            if name not in ("codice_db", "codice_art"):
                self.fields[name].required = False
        apply_control_widgets(self)
