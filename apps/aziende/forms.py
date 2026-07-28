from pathlib import Path

from django import forms

from apps.aziende.models import AziendaDati

ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_LOGO_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg"}


class AziendaDatiForm(forms.ModelForm):
    class Meta:
        model = AziendaDati
        fields = ["logo", "note"]
        widgets = {
            "logo": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/png,image/jpeg,.png,.jpg,.jpeg",
                }
            ),
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"}
            ),
        }

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo:
            return logo

        # ClearableFileInput: False significa "rimuovi file esistente"
        if logo is False:
            return logo

        name = getattr(logo, "name", "") or ""
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_LOGO_EXTENSIONS:
            raise forms.ValidationError(
                "Formato non supportato. Carica un file PNG o JPG."
            )

        content_type = (getattr(logo, "content_type", "") or "").lower().strip()
        if content_type and content_type not in ALLOWED_LOGO_CONTENT_TYPES:
            raise forms.ValidationError(
                "Tipo file non valido. Sono ammessi solo PNG e JPG."
            )

        return logo
