"""Lookup PDC: solo contropartite (Tipo=1), non mastri/conti."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.lookups import descrizione_pdc, search_opzioni
from apps.pdc.hierarchy import (
    PDC_TIPO_CONTROPARTITA,
    pdc_is_contropartita,
)


class _SliceCapture(list):
    """Lista che memorizza lo slice usato (per verificare il limit)."""

    def __getitem__(self, key):
        self.captured = key
        if isinstance(key, slice):
            return list.__getitem__(self, key)
        return list.__getitem__(self, key)


class PdcContropartitaHelperTests(SimpleTestCase):
    def test_is_contropartita_by_codice(self):
        self.assertFalse(pdc_is_contropartita("1"))
        self.assertFalse(pdc_is_contropartita("1.10"))
        self.assertTrue(pdc_is_contropartita("1.10.1"))
        self.assertTrue(pdc_is_contropartita(" 6.01.01 "))
        self.assertFalse(pdc_is_contropartita(""))


class DescrizionePdcTests(SimpleTestCase):
    def test_empty_or_non_contropartita(self):
        self.assertEqual(descrizione_pdc(""), "")
        self.assertEqual(descrizione_pdc("1"), "")
        self.assertEqual(descrizione_pdc("1.10"), "")

    @patch("apps.pdc.hierarchy.pdc_contropartite_qs")
    def test_resolve_contropartita(self, mock_qs):
        obj = MagicMock()
        obj.descrizione = "Cassa contanti"
        mock_qs.return_value.filter.return_value.only.return_value.first.return_value = (
            obj
        )
        self.assertEqual(descrizione_pdc("1.10.1"), "Cassa contanti")
        mock_qs.assert_called_once_with()


class LinkedLabelsArticoloTests(SimpleTestCase):
    @patch("apps.articoli.lookups.descrizione_pdc")
    def test_linked_labels_include_contropartite(self, mock_pdc):
        from apps.articoli.lookups import linked_labels_for_articolo

        mock_pdc.side_effect = lambda codice: {
            "6.01.01": "Ricavi vendite",
            "6.02.01": "Acquisti merci",
        }.get((codice or "").strip(), "")

        art = MagicMock(
            cod_magazzino="",
            cat_omogenea="",
            cod_gruppo="",
            cod_fornitore="",
            cod_iva="",
            c_partita_vend="6.01.01",
            c_partita_acq="6.02.01",
        )
        labels = linked_labels_for_articolo(art)
        self.assertEqual(labels["c_partita_vend"], "Ricavi vendite")
        self.assertEqual(labels["c_partita_acq"], "Acquisti merci")


class SearchPdcTests(SimpleTestCase):
    def _mock_qs(self, mock_objects, ordered):
        qs = MagicMock()
        mock_objects.all.return_value = qs
        filtered = MagicMock()
        qs.filter.return_value = filtered
        filtered.only.return_value = filtered
        filtered.filter.return_value = filtered
        filtered.order_by.return_value = ordered
        return qs

    @patch("apps.pdc.hierarchy.PianoConti.objects")
    def test_search_filters_tipo_contropartita(self, mock_objects):
        row = MagicMock()
        row.codice = "1.10.1"
        row.descrizione = "ASSEGNI"
        qs = self._mock_qs(mock_objects, [row])

        rows = search_opzioni("pdc", "1.10", limit=10)

        qs.filter.assert_called_once_with(tipo=PDC_TIPO_CONTROPARTITA)
        self.assertEqual(rows, [{"codice": "1.10.1", "descrizione": "ASSEGNI"}])

    @patch("apps.pdc.hierarchy.PianoConti.objects")
    def test_search_pdc_allows_high_limit(self, mock_objects):
        """Il combo PDC non deve restare bloccato a 40/100 risultati."""
        ordered = _SliceCapture()
        self._mock_qs(mock_objects, ordered)

        search_opzioni("pdc", "", limit=400)

        self.assertEqual(ordered.captured, slice(None, 400))

    @patch("apps.pdc.hierarchy.PianoConti.objects")
    def test_search_pdc_clamps_above_500(self, mock_objects):
        ordered = _SliceCapture()
        self._mock_qs(mock_objects, ordered)

        search_opzioni("pdc", "", limit=999)

        self.assertEqual(ordered.captured, slice(None, 500))
