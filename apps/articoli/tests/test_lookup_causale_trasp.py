"""Lookup Causale trasporto: codice CausaliTrasp → Desc."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.lookups import (
    LOOKUP_TIPI,
    descrizione_causale_trasp,
    search_opzioni,
)


class CausaleTraspLookupTests(SimpleTestCase):
    def test_tipo_in_lookup_tipi(self):
        self.assertIn("causale_trasp", LOOKUP_TIPI)

    @patch("apps.causali_trasp.models.CausaleTrasporto")
    def test_descrizione_returns_desc(self, mock_model):
        mock_model.objects.filter.return_value.only.return_value.first.return_value = (
            SimpleNamespace(descrizione="VENDITA")
        )
        self.assertEqual(descrizione_causale_trasp("01"), "VENDITA")

    @patch("apps.causali_trasp.models.CausaleTrasporto")
    def test_search_returns_codice_desc(self, mock_model):
        qs = MagicMock()
        qs.only.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = [
            SimpleNamespace(codice="01", descrizione="VENDITA"),
            SimpleNamespace(codice="02", descrizione="RESTITUZIONE"),
        ]
        mock_model.objects.all.return_value = qs

        rows = search_opzioni("causale_trasp", "")
        self.assertEqual(rows[0]["codice"], "01")
        self.assertEqual(rows[0]["descrizione"], "VENDITA")
        self.assertEqual(rows[1]["codice"], "02")
        self.assertEqual(rows[1]["descrizione"], "RESTITUZIONE")
