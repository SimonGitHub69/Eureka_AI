"""Test ordinamento movimenti magazzino su scheda articolo."""

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.movimenti_magazzino import MovimentoArticoloRiga
from apps.articoli.movimenti_sort import sort_movimenti_righe


def _riga(**kwargs) -> MovimentoArticoloRiga:
    base = dict(
        id_testa=1,
        num_registraz=100,
        data_registraz=date(2025, 1, 1),
        causale="01",
        causale_descrizione="CARICO",
        dep_entrata="02",
        dep_uscita="",
        cli_for_codice="",
        cli_for_ragione="",
        cli_for_kind="",
        num_doc="",
        data_doc=None,
        carico=10.0,
        scarico=0.0,
        valore=100.0,
        giacenza=10.0,
    )
    base.update(kwargs)
    return MovimentoArticoloRiga(**base)


class MovimentiSortTests(SimpleTestCase):
    def test_sort_by_carico_desc_keeps_special_rows(self):
        righe = [
            _riga(
                is_giacenza_precedente=True,
                id_testa=None,
                num_registraz=None,
                carico=0.0,
                giacenza=5.0,
            ),
            _riga(num_registraz=101, carico=5.0, giacenza=10.0),
            _riga(num_registraz=102, carico=20.0, giacenza=30.0),
            _riga(is_totale=True, id_testa=None, num_registraz=None, carico=25.0, giacenza=30.0),
        ]
        sorted_rows = sort_movimenti_righe(righe, "carico", "desc")
        self.assertTrue(sorted_rows[0].is_giacenza_precedente)
        self.assertTrue(sorted_rows[-1].is_totale)
        self.assertEqual([r.num_registraz for r in sorted_rows[1:-1]], [102, 101])

    def test_sort_by_data_registraz_asc(self):
        righe = [
            _riga(num_registraz=102, data_registraz=date(2025, 3, 1)),
            _riga(num_registraz=101, data_registraz=date(2025, 1, 1)),
        ]
        sorted_rows = sort_movimenti_righe(righe, "data_registraz", "asc")
        self.assertEqual([r.num_registraz for r in sorted_rows], [101, 102])

    def test_unknown_sort_leaves_order(self):
        righe = [_riga(num_registraz=101), _riga(num_registraz=102)]
        sorted_rows = sort_movimenti_righe(righe, "unknown", "asc")
        self.assertEqual([r.num_registraz for r in sorted_rows], [101, 102])


class UltimeDateMovimentiTests(SimpleTestCase):
    @patch("apps.articoli.movimenti_magazzino.connection")
    def test_ultime_date_da_movimenti(self, mock_connection):
        from datetime import datetime

        from apps.articoli.movimenti_magazzino import ultime_date_movimenti

        cursor = MagicMock()
        cursor.fetchone.return_value = (
            datetime(2025, 6, 15, 10, 0, 0),
            datetime(2025, 8, 20, 14, 30, 0),
        )
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        carico, scarico = ultime_date_movimenti("ZX4001")

        self.assertEqual(carico, date(2025, 6, 15))
        self.assertEqual(scarico, date(2025, 8, 20))
        sql = cursor.execute.call_args[0][0]
        self.assertIn("FILTER", sql)
        self.assertIn("Flag_CD", sql)
        self.assertEqual(cursor.execute.call_args[0][1], ["ZX4001"])

    @patch("apps.articoli.movimenti_magazzino.connection")
    def test_ultime_date_vuote(self, mock_connection):
        from apps.articoli.movimenti_magazzino import ultime_date_movimenti

        cursor = MagicMock()
        cursor.fetchone.return_value = (None, None)
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        carico, scarico = ultime_date_movimenti("NEW")

        self.assertIsNone(carico)
        self.assertIsNone(scarico)
