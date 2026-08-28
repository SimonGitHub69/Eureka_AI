from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db.utils import ProgrammingError
from django.test import SimpleTestCase
from django.urls import reverse

from apps.causali_contabili.forms import CausaleContabileForm
from apps.causali_contabili.models import CausaleContabile
from apps.causali_contabili.lookups import (
    TIPO_DOC_FEL,
    attach_registri_iva_causali,
    build_conti_righe,
    conto_url_label,
    linked_labels_for_causale,
    tipo_doc_fel_choices,
    tipo_doc_fel_display,
    tipo_doc_fel_matching_codes,
)


class CausaliContabiliLookupTests(SimpleTestCase):
    def test_attach_registro_iva_by_trimmed_code(self):
        registro = MagicMock()
        registro.codice = "1"
        registro.descrizione = "VENDITE ITALIA"
        filtered = [registro]
        qs = MagicMock()
        qs.annotate.return_value.filter.return_value = filtered
        with (
            patch("apps.registri_iva.lookups.RegistroIva") as mock_model,
            patch("apps.registri_iva.lookups.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            causale = MagicMock()
            causale.registro_iva = " 1 "
            attach_registri_iva_causali([causale])
        self.assertIs(causale.registro_collegato, registro)

    def test_form_registro_iva_sets_desc_reg_iva(self):
        registro = MagicMock()
        registro.label = "VENDITE ITALIA"
        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.exists.return_value = False
        with (
            patch("apps.causali_contabili.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite")]),
            patch("apps.causali_contabili.forms.resolve_registro_iva", return_value=registro),
            patch("apps.causali_contabili.forms.CausaleContabile.objects.filter", return_value=qs),
        ):
            form = CausaleContabileForm(
                data={
                    "codice": "01",
                    "descrizione": "Fattura",
                    "registro_iva": "1",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["registro_iva"], "1")
            self.assertEqual(form.cleaned_data["desc_reg_iva"], "VENDITE ITALIA")

    def test_resolve_registro_ok_if_table_missing(self):
        qs = MagicMock()
        qs.annotate.side_effect = ProgrammingError("missing")
        with (
            patch("apps.registri_iva.lookups.RegistroIva") as mock_model,
            patch("apps.registri_iva.lookups.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            from apps.registri_iva.lookups import resolve_registro_iva

            self.assertIsNone(resolve_registro_iva("1"))

    def test_form_template_uses_facilitated_conti(self):
        html = Path(
            "apps/causali_contabili/templates/causali_contabili/causale_form.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-linked-lookups", html)
        self.assertIn("mask_linked_code.html", html)
        self.assertIn('tipo="pdc_clifor"', html)
        self.assertIn("field=form.c_dare_1", html)
        self.assertIn("field=form.c_avere_1", html)
        self.assertIn("field=form.cassa_corrispettivi", html)
        self.assertIn('tipo="causale_contabile"', html)
        self.assertIn("field=form.cliente_auto_f", html)
        self.assertIn("linked-lookups.js", html)

    def test_list_template_has_tipo_doc_fel_column(self):
        html = Path(
            "apps/causali_contabili/templates/causali_contabili/causale_list.html"
        ).read_text(encoding="utf-8")
        self.assertIn('sort_th "tipo_doc_fel" "TipoDoc FEL"', html)
        self.assertIn("causale.tipo_doc_fel_code", html)
        self.assertIn("TipoDoc FEL", html)
        self.assertIn("colspan=\"6\"", html)
        self.assertIn("tipo_doc_fel", Path("apps/causali_contabili/views.py").read_text(encoding="utf-8"))

    def test_tipo_doc_fel_matching_codes(self):
        self.assertIn("TD04", tipo_doc_fel_matching_codes("credito"))
        self.assertIn("TD01", tipo_doc_fel_matching_codes("td01"))
        self.assertEqual(tipo_doc_fel_matching_codes(""), [])

    def test_linked_labels_for_causale_uses_pdc_clifor(self):
        form = MagicMock()
        form.is_bound = False
        form.instance = SimpleNamespace(c_dare_1="1.10.1", c_avere_1="C4425")
        form.initial = {}
        form.data = {}
        with patch(
            "apps.articoli.lookups.resolve_descrizione",
            side_effect=lambda tipo, code: f"{tipo}:{code}" if code else "",
        ):
            labels = linked_labels_for_causale(form)
        self.assertEqual(labels["c_dare_1"], "pdc_clifor:1.10.1")
        self.assertEqual(labels["c_avere_1"], "pdc_clifor:C4425")
        self.assertEqual(labels["cassa_corrispettivi"], "")

    def test_conto_url_label_clifor_fallback(self):
        with patch(
            "apps.articoli.lookups.resolve_clifor",
            return_value={
                "found": True,
                "kind": "cliente",
                "codice": "C4425",
                "descrizione": "CLIENTE CORRISPETTIVI",
            },
        ):
            url, label = conto_url_label("C4425", None)
        self.assertEqual(label, "CLIENTE CORRISPETTIVI")
        self.assertEqual(url, reverse("anagrafiche:cliente_detail", kwargs={"codice": "C4425"}))

    def test_build_conti_righe_uses_pdc_then_clifor(self):
        pdc = SimpleNamespace(codice="1.10.1", label="ASSEGNI E/O CONTANTI")
        causale = SimpleNamespace(
            c_dare_1="1.10.1",
            c_avere_1="C4425",
            pdc_dare_1=pdc,
            pdc_avere_1=None,
        )
        for i in range(2, 11):
            setattr(causale, f"c_dare_{i}", "")
            setattr(causale, f"c_avere_{i}", "")
            setattr(causale, f"pdc_dare_{i}", None)
            setattr(causale, f"pdc_avere_{i}", None)
        with patch(
            "apps.articoli.lookups.resolve_clifor",
            return_value={
                "found": True,
                "kind": "cliente",
                "codice": "C4425",
                "descrizione": "CLIENTE CORRISPETTIVI",
            },
        ):
            righe = build_conti_righe(causale)
        self.assertEqual(len(righe), 1)
        self.assertEqual(righe[0]["pdc_dare_label"], "ASSEGNI E/O CONTANTI")
        self.assertEqual(
            righe[0]["pdc_dare_url"],
            reverse("pdc:detail", kwargs={"codice": "1.10.1"}),
        )
        self.assertEqual(righe[0]["pdc_avere_label"], "CLIENTE CORRISPETTIVI")
        self.assertEqual(
            righe[0]["pdc_avere_url"],
            reverse("anagrafiche:cliente_detail", kwargs={"codice": "C4425"}),
        )

    def test_tipo_doc_fel_catalog_matches_fatturapa(self):
        codes = [code for code, _label in TIPO_DOC_FEL]
        self.assertEqual(codes[0], "TD01")
        self.assertIn("TD04", codes)
        self.assertIn("TD12", codes)
        self.assertIn("TD16", codes)
        self.assertIn("TD29", codes)
        self.assertNotIn("TD13", codes)
        self.assertNotIn("TD14", codes)
        self.assertNotIn("TD15", codes)
        self.assertEqual(len(codes), 26)
        labels = dict(TIPO_DOC_FEL)
        self.assertEqual(labels["TD04"], "Nota di Credito")
        self.assertIn("TD28 e TD29", labels["TD20"])
        choices = tipo_doc_fel_choices()
        values = [value for value, _label in choices]
        self.assertEqual(values[0], "")
        self.assertIn("TD01 - Fattura", dict(choices)["TD01"])
        self.assertIn("Nota di Credito", dict(choices)["TD04"])
        orphan = tipo_doc_fel_choices("ALTRO")
        self.assertIn(("ALTRO", "ALTRO"), orphan)
        self.assertEqual(tipo_doc_fel_display("TD04"), "TD04 - Nota di Credito")
        self.assertEqual(tipo_doc_fel_display("TD04 - Nota di Credito"), "TD04 - Nota di Credito")

    def test_form_tipo_doc_fel_saves_code(self):
        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.exists.return_value = False
        with (
            patch(
                "apps.causali_contabili.forms.registro_iva_choices",
                return_value=[("", "—")],
            ),
            patch("apps.causali_contabili.forms.CausaleContabile.objects.filter", return_value=qs),
        ):
            form = CausaleContabileForm(
                data={
                    "codice": "NC",
                    "descrizione": "Nota credito",
                    "tipo_doc_fel": "TD04",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["tipo_doc_fel"], "TD04")
            shown = CausaleContabileForm(
                instance=CausaleContabile(
                    codice="NC",
                    tipo_doc_fel="TD04 - Nota di Credito",
                )
            )
        values = [value for value, _label in shown.fields["tipo_doc_fel"].choices]
        self.assertIn("TD04", values)
        self.assertEqual(shown.initial.get("tipo_doc_fel"), "TD04")
