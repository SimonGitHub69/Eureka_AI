"""Test lista movimenti magazzino su articolo."""

from datetime import date
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.articoli.movimenti_magazzino import movimenti_articolo
from apps.articoli.movimenti_periodo import parse_movimenti_periodo


class MovimentiArticoloTests(SimpleTestCase):
    @patch("apps.articoli.movimenti_magazzino.depositi_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=15900.0)
    @patch("apps.articoli.movimenti_magazzino.fornitori_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.clienti_ragione_sociale_by_codes", return_value={"C1": "Cliente uno"})
    @patch("apps.articoli.movimenti_magazzino.causali_magazzino_by_codes", return_value={"01": "CARICO", "05": "SCARICO"})
    @patch("apps.articoli.movimenti_magazzino._fetch_rows")
    def test_movimenti_con_giacenza_progressiva(self, mock_fetch, *_mocks):
        mock_fetch.return_value = [
            {
                "ID_Testa": 1,
                "NumRegistraz": 100,
                "DataRegistraz": date(2025, 1, 1),
                "Causale": "01",
                "dep_ent": "02",
                "dep_usc": "",
                "Cliente": "",
                "Fornitore": "",
                "NumDoc": "",
                "DataDoc": date(2025, 1, 1),
                "Quantita": 16000.0,
                "Flag_CD": 1,
                "ValoreTotale": 100.0,
            },
            {
                "ID_Testa": 2,
                "NumRegistraz": 101,
                "DataRegistraz": date(2025, 1, 3),
                "Causale": "05",
                "dep_ent": "",
                "dep_usc": "02",
                "Cliente": "C1",
                "Fornitore": "",
                "NumDoc": "54",
                "DataDoc": date(2025, 1, 3),
                "Quantita": 100.0,
                "Flag_CD": 4,
                "ValoreTotale": 29.4,
            },
        ]

        result = movimenti_articolo("VA22")

        self.assertEqual(result.esistenza_attuale, 15900.0)
        self.assertEqual(result.totale_carico, 16000.0)
        self.assertEqual(result.totale_scarico, 100.0)
        self.assertEqual(len(result.righe), 3)

        r1, r2, tot = result.righe
        self.assertEqual(r1.carico, 16000.0)
        self.assertEqual(r1.giacenza, 16000.0)
        self.assertEqual(r1.causale_descrizione, "CARICO")
        self.assertEqual(r2.scarico, 100.0)
        self.assertEqual(r2.giacenza, 15900.0)
        self.assertEqual(r2.cli_for_codice, "C1")
        self.assertEqual(r2.cli_for_ragione, "Cliente uno")
        self.assertTrue(tot.is_totale)
        self.assertEqual(tot.carico, 16000.0)
        self.assertEqual(tot.scarico, 100.0)
        self.assertEqual(tot.giacenza, 15900.0)

    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=0.0)
    @patch("apps.articoli.movimenti_magazzino._fetch_rows", return_value=[])
    def test_senza_movimenti(self, _mock_fetch, _mock_giac):
        result = movimenti_articolo("NEW")
        self.assertEqual(result.esistenza_attuale, 0.0)
        self.assertEqual(result.righe, [])

    @patch("apps.articoli.movimenti_magazzino.depositi_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=15900.0)
    @patch("apps.articoli.movimenti_magazzino.fornitori_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.clienti_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.causali_magazzino_by_codes", return_value={"05": "SCARICO"})
    @patch("apps.articoli.movimenti_magazzino._giacenza_precedente", return_value=16000.0)
    @patch("apps.articoli.movimenti_magazzino._fetch_rows")
    def test_filtro_periodo_con_giacenza_precedente(self, mock_fetch, *_mocks):
        mock_fetch.return_value = [
            {
                "ID_Testa": 2,
                "NumRegistraz": 101,
                "DataRegistraz": date(2025, 1, 3),
                "Causale": "05",
                "dep_ent": "",
                "dep_usc": "02",
                "Cliente": "C1",
                "Fornitore": "",
                "NumDoc": "54",
                "DataDoc": date(2025, 1, 3),
                "Quantita": 100.0,
                "Flag_CD": 4,
                "ValoreTotale": 29.4,
            }
        ]

        result = movimenti_articolo(
            "VA22",
            data_da=date(2025, 1, 3),
            data_a=date(2025, 1, 31),
        )

        self.assertTrue(result.filtro_attivo)
        self.assertEqual(result.giacenza_precedente, 16000.0)
        self.assertEqual(len(result.righe), 3)
        prec, move, tot = result.righe
        self.assertTrue(prec.is_giacenza_precedente)
        self.assertEqual(prec.giacenza, 16000.0)
        self.assertEqual(move.giacenza, 15900.0)
        mock_fetch.assert_called_once_with(
            "VA22",
            data_da=date(2025, 1, 3),
            data_a=date(2025, 1, 31),
        )


class MovimentiPeriodoTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_senza_parametri_nessun_filtro(self):
        request = self.factory.get("/articoli/VA22/")
        data_da, data_a, attivo = parse_movimenti_periodo(request)
        self.assertFalse(attivo)
        self.assertIsNone(data_da)
        self.assertIsNone(data_a)

    def test_mov_tutti_nessun_filtro(self):
        request = self.factory.get("/articoli/VA22/", {"mov_tutti": "1"})
        data_da, data_a, attivo = parse_movimenti_periodo(request)
        self.assertFalse(attivo)

    def test_date_parametri_attivano_filtro(self):
        request = self.factory.get(
            "/articoli/VA22/",
            {"mov_data_da": "2025-01-01", "mov_data_a": "2025-12-31"},
        )
        data_da, data_a, attivo = parse_movimenti_periodo(request)
        self.assertTrue(attivo)
        self.assertEqual(data_da, date(2025, 1, 1))
        self.assertEqual(data_a, date(2025, 12, 31))
