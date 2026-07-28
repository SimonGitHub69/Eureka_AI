from django import forms
from django.utils import timezone

from apps.operatori.lookup import list_operatori_attivi, lookup_operatore
from apps.schede_lavorazione.models import SchedaLavorazione


class SchedaLavorazioneCreateForm(forms.ModelForm):
    """Form testata scheda: data + operatore (matricola/nome da lookup). Usato anche in modifica."""

    class Meta:
        model = SchedaLavorazione
        fields = ["data", "operatore_codice"]
        widgets = {
            "data": forms.DateInput(
                attrs={"class": "form-control", "type": "date"},
                format="%Y-%m-%d",
            ),
            "operatore_codice": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["data"].initial = timezone.localdate()
        self.fields["data"].input_formats = ["%Y-%m-%d"]
        self.fields["operatore_codice"].label = "Operatore"
        self.fields["operatore_codice"].required = True
        self.operatori = list_operatori_attivi()
        self._ensure_operatore_corrente()

    def _ensure_operatore_corrente(self):
        """In modifica, mantieni l'operatore già salvato anche se non più in elenco attivi."""
        codice = (getattr(self.instance, "operatore_codice", None) or "").strip()
        if not codice:
            return
        if any(op.get("codice") == codice for op in self.operatori):
            return
        operatore = lookup_operatore(codice)
        if operatore:
            self.operatori.insert(
                0,
                {
                    "codice": operatore["codice"],
                    "nome": operatore["nome"],
                    "matricola": operatore["matricola"],
                    "nome_breve": "",
                },
            )
        else:
            self.operatori.insert(
                0,
                {
                    "codice": codice,
                    "nome": self.instance.operatore_nome or codice,
                    "matricola": self.instance.matricola or "",
                    "nome_breve": "",
                },
            )

    def clean_operatore_codice(self):
        codice = (self.cleaned_data.get("operatore_codice") or "").strip()
        if not codice:
            raise forms.ValidationError("Seleziona un operatore dalla ricerca.")
        operatore = lookup_operatore(codice)
        current_codice = (self.instance.operatore_codice or "").strip() if self.instance.pk else ""
        is_current = bool(self.instance.pk and codice == current_codice)

        if not operatore:
            # In modifica: se l'operatore non è più in tabella ma è quello già salvato, mantieni i dati.
            if is_current and (self.instance.operatore_nome or self.instance.matricola):
                self._operatore = {
                    "codice": codice,
                    "nome": self.instance.operatore_nome or codice,
                    "matricola": self.instance.matricola or "",
                }
                return codice
            raise forms.ValidationError(
                "Operatore non trovato. Sincronizza la tabella Operatori."
            )

        # Nuova selezione: solo operatori attivi. In modifica resta ammesso quello già salvato.
        if operatore.get("disattivo") and not is_current:
            raise forms.ValidationError(
                "Operatore disattivato: non è selezionabile. Scegline uno attivo."
            )

        self._operatore = operatore
        return codice

    def save(self, commit=True):
        obj = super().save(commit=False)
        operatore = getattr(self, "_operatore", None) or lookup_operatore(obj.operatore_codice)
        if operatore:
            obj.operatore_nome = operatore["nome"]
            obj.matricola = operatore["matricola"]
        if commit:
            obj.save()
        return obj


# Alias esplicito per le view di modifica (stessa validazione della create).
SchedaLavorazioneUpdateForm = SchedaLavorazioneCreateForm
