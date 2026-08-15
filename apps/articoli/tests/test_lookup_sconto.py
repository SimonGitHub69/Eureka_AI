"""Lookup Sconto: codice Sconti → valore %."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.lookups import LOOKUP_TIPI, descrizione_sconto, search_opzioni


class ScontoLookupTests(SimpleTestCase):
    def test_tipo_in_lookup_tipi(self):
        self.assertIn("sconto", LOOKUP_TIPI)

    @patch("apps.sconti.models.Sconto")
    def test_descrizione_returns_sconto(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = (
            SimpleNamespace(sconto="10")
        )
        self.assertEqual(descrizione_sconto("10"), "10")

    @patch("apps.sconti.models.Sconto")
    def test_search_returns_codice_sconto(self, mock_model):
        qs = MagicMock()
        qs.only.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = [
            SimpleNamespace(codice="2", sconto="2"),
            SimpleNamespace(codice="3", sconto="3"),
        ]
        mock_model.objects.all.return_value = qs

        rows = search_opzioni("sconto", "")
        self.assertEqual(rows[0]["codice"], "2")
        self.assertEqual(rows[0]["descrizione"], "2")
        self.assertEqual(rows[1]["codice"], "3")
