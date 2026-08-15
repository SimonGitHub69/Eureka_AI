"""Test risoluzione sconto codice → formula % (solo calcolo, non sulle righe)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.documenti.sconto import effective_sconto_formula, resolve_sconto_percentuale


class ResolveScontoPercentualeTests(SimpleTestCase):
    @patch("apps.sconti.models.Sconto")
    def test_50a_risolve_a_50_piu_10(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = (
            SimpleNamespace(sconto="50+10")
        )
        self.assertEqual(resolve_sconto_percentuale("50A"), "50+10")

    @patch("apps.sconti.models.Sconto")
    def test_formula_gia_composta_resta(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = None
        self.assertEqual(resolve_sconto_percentuale("10+5"), "10+5")

    @patch("apps.sconti.models.Sconto")
    def test_codice_assente_torna_raw(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = None
        self.assertEqual(resolve_sconto_percentuale("NG"), "NG")

    def test_vuoto(self):
        self.assertEqual(resolve_sconto_percentuale(""), "")
        self.assertEqual(resolve_sconto_percentuale(None), "")


class EffectiveScontoFormulaTests(SimpleTestCase):
    @patch(
        "apps.documenti.sconto.resolve_sconto_percentuale",
        side_effect=lambda x: {"50A": "50+10", "3": "3", "10+5": "10+5"}.get(
            (x or "").strip(), (x or "").strip()
        ),
    )
    def test_riga_con_codice_in_cascata_con_testata(self, _mock):
        self.assertEqual(effective_sconto_formula("50A", header_sconto="3"), "50+10+3")

    @patch(
        "apps.documenti.sconto.resolve_sconto_percentuale",
        side_effect=lambda x: x,
    )
    def test_riga_vuota_usa_testata_in_calcolo(self, _mock):
        self.assertEqual(effective_sconto_formula("", header_sconto="10+5"), "10+5")

    @patch(
        "apps.documenti.sconto.resolve_sconto_percentuale",
        side_effect=lambda x: (x or "").strip(),
    )
    def test_riga_e_testata_in_cascata(self, _mock):
        self.assertEqual(effective_sconto_formula("2", header_sconto="10"), "2+10")

    @patch(
        "apps.documenti.sconto.resolve_sconto_percentuale",
        side_effect=lambda x: (x or "").strip(),
    )
    def test_riga_e_testata_uguali_una_sola_volta(self, _mock):
        self.assertEqual(effective_sconto_formula("3", header_sconto="3"), "3")
