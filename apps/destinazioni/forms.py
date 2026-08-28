from django import forms

from apps.core.mirror_crud import apply_control_widgets
from apps.destinazioni.models import DestinazioneDiversa, compact_codice
from apps.destinazioni.numerazione import next_codice_dest_for_anagrafica


class DestinazioneDiversaForm(forms.ModelForm):
    class Meta:
        model = DestinazioneDiversa
        fields = [
            "codice",
            "codice_dest",
            "ragione_sociale",
            "indirizzo",
            "cap",
            "citta",
            "provincia",
            "telefono",
            "email",
            "cod_nazione",
            "codice_iso",
            "desc_nazione",
            "punto_vendita",
            "cod_esenz_iva",
            "codice_filconad",
            "gruppo_cadla",
            "prezzi_bolle",
            "black_list",
        ]
        labels = {
            "codice": "Codice Cli/For",
            "codice_dest": "Codice destinazione",
            "ragione_sociale": "Ragione sociale",
            "indirizzo": "Indirizzo",
            "cap": "CAP",
            "citta": "Città",
            "provincia": "Provincia",
            "telefono": "Telefono",
            "email": "Email",
            "cod_nazione": "Nazione",
            "codice_iso": "Codice ISO",
            "desc_nazione": "Descrizione nazione",
            "punto_vendita": "Punto vendita",
            "cod_esenz_iva": "Cod. esenz. IVA",
            "codice_filconad": "Codice Filconad",
            "gruppo_cadla": "Gruppo CADLA",
            "prezzi_bolle": "Prezzi bolle",
            "black_list": "Black list",
        }
        widgets = {
            "prezzi_bolle": forms.CheckboxInput(),
            "black_list": forms.CheckboxInput(),
            "provincia": forms.TextInput(attrs={"maxlength": "4"}),
        }

    def __init__(self, *args, chiave_readonly: bool = False, auto_codice_dest: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.chiave_readonly = bool(chiave_readonly)
        self.auto_codice_dest = bool(auto_codice_dest)
        self.fields["codice"].required = True
        for name in self.fields:
            if name != "codice":
                self.fields[name].required = False
        apply_control_widgets(self)

        is_edit = bool(self.instance and self.instance.pk)
        codice_iniziale = compact_codice(
            self.initial.get("codice") or getattr(self.instance, "codice", None)
        )
        # Blocca Codice Cli/For: in modifica sempre; in creazione se arriva da anagrafica (?codice=).
        lock_codice = is_edit or self.chiave_readonly or bool(codice_iniziale)
        if lock_codice:
            self.fields["codice"].disabled = True

        # Blocca Codice destinazione: in modifica sempre; in creazione se auto-contatore.
        lock_codice_dest = is_edit or self.auto_codice_dest
        if lock_codice_dest:
            self.fields["codice_dest"].disabled = True
            if self.auto_codice_dest and not is_edit:
                # Prefill (GET) e initial per POST: campo disabled non arriva nel body.
                suggested = ""
                if codice_iniziale:
                    suggested = next_codice_dest_for_anagrafica(codice_iniziale) or ""
                if suggested:
                    self.fields["codice_dest"].initial = suggested
                    if "codice_dest" not in self.initial:
                        self.initial = {**self.initial, "codice_dest": suggested}

    def clean_codice(self):
        # Campo disabled: Django usa initial/instance; altrimenti il POST.
        value = compact_codice(self.cleaned_data.get("codice"))
        if not value:
            raise forms.ValidationError("Il codice Cliente/Fornitore è obbligatorio.")
        if value[0] not in {"C", "F"}:
            raise forms.ValidationError("Il codice deve iniziare con C (cliente) o F (fornitore).")
        return value

    def clean_codice_dest(self):
        return (self.cleaned_data.get("codice_dest") or "").strip()

    def clean(self):
        cleaned = super().clean()
        # In creazione con auto-contatore: ricalcola sempre al salvataggio
        # (il campo è disabled → non arriva in POST; evita collisioni sul suggerimento GET).
        if self.auto_codice_dest and not (self.instance and self.instance.pk):
            if "codice" not in cleaned:
                return cleaned
            suggested = next_codice_dest_for_anagrafica(cleaned.get("codice"))
            if suggested:
                cleaned["codice_dest"] = suggested
            else:
                self.add_error(
                    "codice_dest",
                    "Impossibile assegnare CodiceDest: codice Cli/For non valido.",
                )
        return cleaned
