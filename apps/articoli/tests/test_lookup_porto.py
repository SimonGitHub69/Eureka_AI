"""Lookup Porto: combo memorizza TabPorto.Descrizione, chip = Incoterm."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.lookups import LOOKUP_TIPI, descrizione_porto, search_opzioni


class PortoLookupTests(SimpleTestCase):
    def test_tipo_in_lookup_tipi(self):
        self.assertIn("porto", LOOKUP_TIPI)

    @patch("apps.documenti.models.Porto")
    def test_descrizione_returns_incoterm(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = (
            SimpleNamespace(cod_incoterm="EXW")
        )
        self.assertEqual(descrizione_porto("FRANCO"), "EXW")

    @patch("apps.documenti.models.Porto")
    def test_search_uses_descrizione_as_codice(self, mock_model):
        qs = MagicMock()
        qs.only.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = [
            SimpleNamespace(descrizione="FRANCO", cod_incoterm="EXW", id=1),
            SimpleNamespace(descrizione="ASSEGNATO", cod_incoterm="FCA", id=2),
        ]
        mock_model.objects.all.return_value = qs

        rows = search_opzioni("porto", "")
        self.assertEqual(rows[0]["codice"], "FRANCO")
        self.assertEqual(rows[0]["descrizione"], "EXW")
        self.assertEqual(rows[1]["codice"], "ASSEGNATO")
        self.assertEqual(rows[1]["descrizione"], "FCA")
