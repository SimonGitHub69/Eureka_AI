from django import forms

from apps.core.mirror_crud import PackedRgbColorWidget, apply_control_widgets, clean_unique_pk
from apps.gruppi_articoli.models import GruppoArticolo

FONT_STYLE_KEYS = ("plain", "bold", "italic", "underline")
FONT_STYLE_CHOICES = (
    ("plain", "Plain"),
    ("bold", "Bold"),
    ("italic", "Italic"),
    ("underline", "Underline"),
)

# (suffix, titolo sezione, campo font, rgb fore, rgb back)
STYLE_SECTIONS = (
    ("", "Giacenza > 0", "font_style", "rgb_color_fore", "rgb_color_back"),
    ("_mz", "Giacenza < 0", "font_style_mz", "rgb_color_fore_mz", "rgb_color_back_mz"),
    ("_gz", "Giacenza = 0", "font_style_gz", "rgb_color_fore_gz", "rgb_color_back_gz"),
)


def decode_font_style(value) -> list[str]:
    raw = "".join(ch for ch in str(value or "") if ch in "01")
    if not raw:
        return []
    raw = (raw + "0000")[:4]
    return [FONT_STYLE_KEYS[i] for i in range(4) if raw[i] == "1"]


def encode_font_style(selected) -> str:
    selected = set(selected or [])
    styles = selected & {"bold", "italic", "underline"}
    if styles:
        selected = styles
    elif "plain" in selected or not selected:
        selected = {"plain"}
    return "".join("1" if key in selected else "0" for key in FONT_STYLE_KEYS)


def label_font_style(value) -> str:
    flags = decode_font_style(value)
    if not flags:
        return "—"
    labels = dict(FONT_STYLE_CHOICES)
    return ", ".join(labels[k] for k in FONT_STYLE_KEYS if k in flags)


def flags_field_name(suffix: str) -> str:
    return f"font_style_flags{suffix}"


class FontStyleCheckboxSelect(forms.CheckboxSelectMultiple):
    option_template_name = "gruppi_articoli/widgets/font_style_option.html"
    template_name = "gruppi_articoli/widgets/font_style_select.html"


class GruppoArticoloForm(forms.ModelForm):
    class Meta:
        model = GruppoArticolo
        fields = [
            "codice",
            "descrizione",
            "f_disattivato",
            "font_style",
            "rgb_color_fore",
            "rgb_color_back",
            "font_style_mz",
            "rgb_color_fore_mz",
            "rgb_color_back_mz",
            "font_style_gz",
            "rgb_color_fore_gz",
            "rgb_color_back_gz",
        ]
        labels = {
            "codice": "Codice",
            "descrizione": "Descrizione",
            "f_disattivato": "Disattivato",
            "font_style": "Font-style",
            "rgb_color_fore": "Colore testo (RGB)",
            "rgb_color_back": "Colore sfondo (RGB)",
            "font_style_mz": "Font-style",
            "rgb_color_fore_mz": "Colore testo (RGB)",
            "rgb_color_back_mz": "Colore sfondo (RGB)",
            "font_style_gz": "Font-style",
            "rgb_color_fore_gz": "Colore testo (RGB)",
            "rgb_color_back_gz": "Colore sfondo (RGB)",
        }
        widgets = {
            "f_disattivato": forms.CheckboxInput(),
            "font_style": forms.HiddenInput(),
            "font_style_mz": forms.HiddenInput(),
            "font_style_gz": forms.HiddenInput(),
            "rgb_color_fore": PackedRgbColorWidget(),
            "rgb_color_back": PackedRgbColorWidget(),
            "rgb_color_fore_mz": PackedRgbColorWidget(),
            "rgb_color_back_mz": PackedRgbColorWidget(),
            "rgb_color_fore_gz": PackedRgbColorWidget(),
            "rgb_color_back_gz": PackedRgbColorWidget(),
        }

    def __init__(self, *args, codice_readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codice"].required = True
        self.fields["descrizione"].required = True
        for name in self.fields:
            if name not in ("codice", "descrizione"):
                self.fields[name].required = False

        self.style_sections = []
        for suffix, title, font_field, rgb_fore, rgb_back in STYLE_SECTIONS:
            flags_name = flags_field_name(suffix)
            widget_id = f"eureka-font-style{suffix or '-gt0'}"
            self.fields[flags_name] = forms.MultipleChoiceField(
                choices=FONT_STYLE_CHOICES,
                required=False,
                label="Font-style",
                widget=FontStyleCheckboxSelect(attrs={"id": widget_id}),
            )
            initial_style = ""
            if self.is_bound:
                initial_style = self.data.get(font_field, "")
            elif self.instance and self.instance.pk:
                initial_style = getattr(self.instance, font_field, "") or ""
            self.fields[flags_name].initial = decode_font_style(initial_style) or ["plain"]
            self.style_sections.append(
                {
                    "suffix": suffix,
                    "title": title,
                    "flags_name": flags_name,
                    "font_field": font_field,
                    "rgb_fore": rgb_fore,
                    "rgb_back": rgb_back,
                    "widget_id": widget_id,
                }
            )

        apply_control_widgets(
            self,
            exclude={flags_field_name(s) for s, *_ in STYLE_SECTIONS},
        )
        if codice_readonly:
            self.fields["codice"].disabled = True
            self.fields["codice"].help_text = "Il codice non è modificabile."

    @property
    def style_section_rows(self):
        rows = []
        for section in self.style_sections:
            rows.append(
                {
                    **section,
                    "flags": self[section["flags_name"]],
                    "font": self[section["font_field"]],
                    "fore": self[section["rgb_fore"]],
                    "back": self[section["rgb_back"]],
                }
            )
        return rows

    def clean_codice(self):
        return clean_unique_pk(self)

    def clean(self):
        cleaned = super().clean()
        for suffix, _title, font_field, _fore, _back in STYLE_SECTIONS:
            flags = cleaned.get(flags_field_name(suffix)) or []
            cleaned[font_field] = encode_font_style(flags)
        return cleaned
