"""Lookup causale contabile: codice CausaliC → Descrizione."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.lookups import (
    LOOKUP_TIPI,
    descrizione_causale_contabile,
    search_opzioni,
)


class CausaleContabileLookupTests(SimpleTestCase):
    def test_tipo_in_lookup_tipi(self):
        self.assertIn("causale_contabile", LOOKUP_TIPI)

    @patch("apps.causali_contabili.models.CausaleContabile")
    def test_descrizione_returns_desc(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = (
            SimpleNamespace(descrizione="Incasso Corrispettivi", desc_pn="")
        )
        self.assertEqual(descrizione_causale_contabile("23"), "Incasso Corrispettivi")

    @patch("apps.causali_contabili.models.CausaleContabile")
    def test_search_returns_codice_desc(self, mock_model):
        qs = MagicMock()
        qs.only.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = [
            SimpleNamespace(codice="23", descrizione="Incasso Corrispettivi", desc_pn=""),
            SimpleNamespace(codice="24", descrizione="Corrispettivi (IVA)", desc_pn=""),
        ]
        mock_model.objects.all.return_value = qs

        rows = search_opzioni("causale_contabile", "")
        self.assertEqual(rows[0]["codice"], "23")
        self.assertEqual(rows[0]["descrizione"], "Incasso Corrispettivi")
        self.assertEqual(rows[1]["codice"], "24")
        self.assertEqual(rows[1]["descrizione"], "Corrispettivi (IVA)")
