"""Lookup Banca: codice Banche → Descrizione."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.lookups import LOOKUP_TIPI, descrizione_banca, search_opzioni


class BancaLookupTests(SimpleTestCase):
    def test_tipo_in_lookup_tipi(self):
        self.assertIn("banca", LOOKUP_TIPI)

    @patch("apps.banche.models.Banca")
    def test_descrizione_returns_desc(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = (
            SimpleNamespace(descrizione="BANCA INTESA")
        )
        self.assertEqual(descrizione_banca("000683"), "BANCA INTESA")

    @patch("apps.banche.models.Banca")
    def test_search_returns_codice_desc(self, mock_model):
        qs = MagicMock()
        qs.only.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = [
            SimpleNamespace(codice="000683", descrizione="BANCA INTESA"),
            SimpleNamespace(codice="000105", descrizione="UNICREDIT"),
        ]
        mock_model.objects.all.return_value = qs

        rows = search_opzioni("banca", "")
        self.assertEqual(rows[0]["codice"], "000683")
        self.assertEqual(rows[0]["descrizione"], "BANCA INTESA")
        self.assertEqual(rows[1]["codice"], "000105")
        self.assertEqual(rows[1]["descrizione"], "UNICREDIT")
