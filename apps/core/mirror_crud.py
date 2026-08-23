"""Helper comuni per CRUD su tabelle mirror 4D / tabelle di lookup."""

from __future__ import annotations

from django import forms
from django.utils import timezone

CONTROL = {"class": "form-control", "autocomplete": "off"}
SELECT = {"class": "form-select"}
NUMBER = {"class": "form-control", "inputmode": "numeric"}
CHECK = {"class": "form-check-input"}
COLOR = {"class": "form-control form-control-color", "title": "Scegli colore"}

# Solo questi campi restano multilinea nelle maschere Tabelle.
TEXTAREA_FIELDS = frozenset({"note", "notes", "desc_attivita"})


def packed_rgb_to_hex(value) -> str:
    """Converte intero COLORREF 4D/Windows (R + G*256 + B*65536) in #rrggbb."""
    if value in (None, ""):
        return "#000000"
    try:
        v = int(value) & 0xFFFFFF
    except (TypeError, ValueError):
        return "#000000"
    r, g, b = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_packed_rgb(value) -> int | None:
    """Converte #rrggbb (o rrggbb) in intero COLORREF 4D/Windows."""
    if value in (None, ""):
        return None
    raw = str(value).strip().lstrip("#")
    if len(raw) != 6:
        raise ValueError("Colore RGB non valido")
    r = int(raw[0:2], 16)
    g = int(raw[2:4], 16)
    b = int(raw[4:6], 16)
    return r + (g << 8) + (b << 16)


class PackedRgbColorWidget(forms.TextInput):
    """Color picker HTML che legge/scrive interi RGB packed (4D/Windows)."""

    input_type = "color"
    template_name = "django/forms/widgets/input.html"

    def __init__(self, attrs=None):
        base = {**COLOR}
        if attrs:
            base.update(attrs)
        super().__init__(attrs=base)

    def format_value(self, value):
        return packed_rgb_to_hex(value)

    def value_from_datadict(self, data, files, name):
        raw = data.get(name)
        if raw in (None, ""):
            return None
        try:
            return hex_to_packed_rgb(raw)
        except ValueError:
            return raw


def stamp_modifica(instance) -> None:
    """Aggiorna timestamp di modifica se presenti sul model."""
    now = timezone.localtime()
    if hasattr(instance, "data_modifica"):
        instance.data_modifica = timezone.make_naive(now)
    if hasattr(instance, "ora_modifica"):
        instance.ora_modifica = now.time().replace(microsecond=0)
    if hasattr(instance, "synced_at"):
        instance.synced_at = now


def format_mirror_display_value(value):
    """Valori booleani → Si/No (niente True/False in italiano)."""
    if value is True:
        return "Si"
    if value is False:
        return "No"
    if isinstance(value, str):
        low = value.strip().lower()
        if low == "true":
            return "Si"
        if low == "false":
            return "No"
    return value


def mirror_row_to_campi(
    row: list[tuple[str, object]],
    *,
    exclude: set[str] | frozenset[str] | None = None,
    skip_empty: bool = True,
) -> list[tuple[str, object]]:
    """Converte una riga SQL grezza in coppie (nome, valore) per maschere dettaglio."""
    skip = {"synced_at", *(exclude or ())}
    campi: list[tuple[str, object]] = []
    for name, value in row:
        if name in skip:
            continue
        if skip_empty and value in (None, ""):
            continue
        campi.append((name, format_mirror_display_value(value)))
    return campi


def save_mirror_form_instance(form: forms.ModelForm):
    """Salva solo i campi della form (+ timestamp), evitando colonne fuori maschera.

    Su tabelle mirror unmanaged evita errori di tipo su campi non editati
    (es. boolean letti come float e riscritti numeric).
    """
    obj = form.save(commit=False)
    stamp_modifica(obj)

    pk_name = obj._meta.pk.name
    update_fields: list[str] = []
    for name in form.Meta.fields:
        if name not in form.fields:
            continue
        # Disabled / PK: non vanno in UPDATE (Django rifiuta la PK in update_fields).
        if form.fields[name].disabled or name == pk_name:
            continue
        if name in form.cleaned_data:
            update_fields.append(name)
    for extra in ("data_modifica", "ora_modifica", "synced_at"):
        if extra in {f.name for f in obj._meta.fields} and extra not in update_fields:
            update_fields.append(extra)

    if obj._state.adding:
        obj.save()
    else:
        obj.save(update_fields=update_fields)
    return obj


def apply_control_widgets(
    form: forms.BaseForm,
    exclude: set[str] | None = None,
    keep_textarea: set[str] | None = None,
) -> None:
    """Applica classi Bootstrap e forza input a riga singola sui TextField.

    Django usa Textarea(rows=10) per TextField: qui li convertiamo in TextInput,
    tranne i campi in TEXTAREA_FIELDS / keep_textarea.
    """
    exclude = exclude or set()
    keep = set(TEXTAREA_FIELDS) | set(keep_textarea or ())
    for name, field in form.fields.items():
        if name in exclude:
            continue
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", "form-check-input")
            field.widget.attrs.setdefault("role", "switch")
        elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
            field.widget.attrs.setdefault("class", "form-select")
        elif getattr(field.widget, "input_type", None) == "color":
            field.widget.attrs.setdefault("class", "form-control form-control-color")
        elif isinstance(field.widget, forms.NumberInput):
            field.widget.attrs.setdefault("class", "form-control")
            field.widget.attrs.setdefault("inputmode", "numeric")
        elif isinstance(field.widget, forms.Textarea):
            if name in keep:
                field.widget.attrs["class"] = "form-control"
                field.widget.attrs["rows"] = str(field.widget.attrs.get("rows") or 3)
                field.widget.attrs.pop("cols", None)
            else:
                attrs = {
                    k: v
                    for k, v in field.widget.attrs.items()
                    if k not in {"rows", "cols"}
                }
                attrs["class"] = "form-control"
                attrs.setdefault("autocomplete", "off")
                field.widget = forms.TextInput(attrs=attrs)
        else:
            field.widget.attrs.setdefault("class", "form-control")
            field.widget.attrs.setdefault("autocomplete", "off")


def clean_unique_pk(form: forms.ModelForm, pk_field: str = "codice"):
    value = (form.cleaned_data.get(pk_field) or "").strip()
    if not value:
        raise forms.ValidationError("Il codice è obbligatorio.")
    model = form._meta.model
    qs = model.objects.filter(**{pk_field: value})
    if form.instance and form.instance.pk:
        qs = qs.exclude(pk=form.instance.pk)
    if qs.exists():
        raise forms.ValidationError(
            f"Il codice «{value}» esiste già: non è possibile inserire due codici uguali."
        )
    return value


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def delete_mirror_row(model, pk_value) -> int:
    """DELETE SQL esplicito su tabella mirror unmanaged.

    Usa la colonna DB della PK (db_column) e verifica che la riga sparisca.
    Ritorna il numero di righe eliminate (0 se assente).
    """
    from django.db import connection

    table = _quote_ident(model._meta.db_table)
    pk_field = model._meta.pk
    pk_col = _quote_ident(pk_field.db_column or pk_field.column)
    with connection.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {pk_col} = %s", [pk_value])
        deleted = int(cur.rowcount or 0)
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {pk_col} = %s", [pk_value])
        remaining = int(cur.fetchone()[0])
    if remaining:
        raise RuntimeError(
            f"Eliminazione fallita: la riga {pk_value!r} è ancora presente "
            f"in {model._meta.db_table}."
        )
    return deleted
