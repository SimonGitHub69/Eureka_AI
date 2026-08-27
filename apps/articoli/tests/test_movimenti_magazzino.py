"""Test lista movimenti magazzino su articolo."""

from datetime import date
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.articoli.movimenti_magazzino import (
    _prezzo_lordo_da_netto,
    movimenti_articolo,
)
from apps.articoli.movimenti_periodo import movimenti_periodo_context, parse_movimenti_periodo


class MovimentiArticoloTests(SimpleTestCase):
    def test_prezzo_lordo_da_netto_con_sconto(self):
        self.assertAlmostEqual(_prezzo_lordo_da_netto(90.0, "10"), 100.0, places=4)
        self.assertAlmostEqual(_prezzo_lordo_da_netto(85.5, "10+5"), 100.0, places=4)
        self.assertEqual(_prezzo_lordo_da_netto(12.5, ""), 12.5)

    @patch("apps.articoli.movimenti_magazzino._sconti_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.depositi_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=15900.0)
    @patch("apps.articoli.movimenti_magazzino.fornitori_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.clienti_ragione_sociale_by_codes", return_value={"C1": "Cliente uno"})
    @patch("apps.articoli.movimenti_magazzino.causali_magazzino_by_codes", return_value={"01": "CARICO", "05": "SCARICO"})
    @patch(
        "apps.articoli.movimenti_magazzino.prezzi_periodo_articolo",
        return_value={"ultimo": 9.85, "medio": 9.7},
    )
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
                "ValoreUnNetto": 0.00625,
                "ValoreTotale": 100.0,
                "Sconto_CodArtCliFor": "",
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
                "ValoreUnNetto": 0.294,
                "ValoreTotale": 29.4,
                "Sconto_CodArtCliFor": "",
            },
        ]

        result = movimenti_articolo("VA22")

        self.assertEqual(result.esistenza_attuale, 15900.0)
        self.assertEqual(result.totale_carico, 16000.0)
        self.assertEqual(result.totale_scarico, 100.0)
        self.assertEqual(result.prezzo_ultimo_acquisto, 9.85)
        self.assertEqual(result.prezzo_medio, 9.7)
        self.assertEqual(result.giacenza_finale, 15900.0)
        self.assertEqual(len(result.righe), 3)

        r1, r2, tot = result.righe
        self.assertEqual(r1.carico, 16000.0)
        self.assertEqual(r1.giacenza, 16000.0)
        self.assertEqual(r1.prezzo_unitario, 0.00625)
        self.assertEqual(r1.causale_descrizione, "CARICO")
        self.assertEqual(r2.scarico, 100.0)
        self.assertEqual(r2.giacenza, 15900.0)
        self.assertEqual(r2.prezzo_unitario, 0.294)
        self.assertEqual(r2.cli_for_codice, "C1")
        self.assertEqual(r2.cli_for_ragione, "Cliente uno")
        self.assertTrue(tot.is_totale)
        self.assertEqual(tot.carico, 16000.0)
        self.assertEqual(tot.scarico, 100.0)
        self.assertEqual(tot.giacenza, 15900.0)

    @patch("apps.articoli.movimenti_magazzino._sconti_by_codes", return_value={"10": "10"})
    @patch("apps.articoli.movimenti_magazzino.depositi_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=10.0)
    @patch("apps.articoli.movimenti_magazzino.fornitori_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.clienti_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.causali_magazzino_by_codes", return_value={"02": "CARICO"})
    @patch(
        "apps.articoli.movimenti_magazzino.prezzi_periodo_articolo",
        return_value={"ultimo": 90.0, "medio": 90.0},
    )
    @patch("apps.articoli.movimenti_magazzino._fetch_rows")
    def test_movimenti_con_prezzo_lordo_sconto_netto(self, mock_fetch, *_mocks):
        mock_fetch.return_value = [
            {
                "ID_Testa": 3,
                "NumRegistraz": 200,
                "DataRegistraz": date(2025, 2, 3),
                "Causale": "02",
                "dep_ent": "02",
                "dep_usc": "",
                "Cliente": "",
                "Fornitore": "F1",
                "NumDoc": "100",
                "DataDoc": date(2025, 2, 3),
                "Quantita": 10.0,
                "Flag_CD": 2,
                "ValoreUnNetto": 90.0,
                "ValoreTotale": 900.0,
                "Sconto_CodArtCliFor": "10",
            },
        ]
        result = movimenti_articolo("ART1")
        riga = result.righe[0]
        self.assertEqual(riga.prezzo_unitario, 90.0)
        self.assertAlmostEqual(riga.prezzo_lordo, 100.0, places=4)
        self.assertEqual(riga.sconto, "10%")

    @patch("apps.articoli.movimenti_magazzino._sconti_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.depositi_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=810.0)
    @patch("apps.articoli.movimenti_magazzino.fornitori_ragione_sociale_by_codes", return_value={"F1776": "FORN"})
    @patch("apps.articoli.movimenti_magazzino.clienti_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.causali_magazzino_by_codes", return_value={"02": "CARICO"})
    @patch(
        "apps.articoli.movimenti_magazzino.prezzi_periodo_articolo",
        return_value={"ultimo": 3.9035, "medio": 3.9035},
    )
    @patch("apps.articoli.movimenti_magazzino._fetch_rows")
    def test_movimenti_sconto_percentuale_diretta_4d(self, mock_fetch, *_mocks):
        """4D: Sconto_CodArtCliFor può essere la % (es. 7,5) senza codice tabella Sconti."""
        mock_fetch.return_value = [
            {
                "ID_Testa": 603352,
                "NumRegistraz": 309251,
                "DataRegistraz": date(2025, 2, 3),
                "Causale": "02",
                "dep_ent": "02",
                "dep_usc": "",
                "Cliente": "",
                "Fornitore": "F1776",
                "NumDoc": "1/176",
                "DataDoc": date(2025, 1, 23),
                "Quantita": 1500.0,
                "Flag_CD": 2,
                "ValoreUnNetto": 3.9035,
                "ValoreTotale": 5855.25,
                "Sconto_CodArtCliFor": "7,5",
            },
        ]
        result = movimenti_articolo("RAME10")
        riga = result.righe[0]
        self.assertEqual(riga.prezzo_unitario, 3.9035)
        self.assertAlmostEqual(riga.prezzo_lordo, 4.22, places=2)
        self.assertEqual(riga.sconto, "7,5%")

    @patch("apps.articoli.movimenti_magazzino.prezzi_periodo_articolo", return_value={"ultimo": None, "medio": None})
    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=0.0)
    @patch("apps.articoli.movimenti_magazzino._fetch_rows", return_value=[])
    def test_senza_movimenti(self, _mock_fetch, _mock_giac, _mock_prezzi):
        result = movimenti_articolo("NEW")
        self.assertEqual(result.esistenza_attuale, 0.0)
        self.assertEqual(result.righe, [])
        self.assertIsNone(result.prezzo_ultimo_acquisto)
        self.assertIsNone(result.prezzo_medio)

    @patch("apps.articoli.movimenti_magazzino._sconti_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.depositi_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.giacenza_articolo", return_value=15900.0)
    @patch("apps.articoli.movimenti_magazzino.fornitori_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.clienti_ragione_sociale_by_codes", return_value={})
    @patch("apps.articoli.movimenti_magazzino.causali_magazzino_by_codes", return_value={"05": "SCARICO"})
    @patch(
        "apps.articoli.movimenti_magazzino.prezzi_periodo_articolo",
        return_value={"ultimo": 1.1, "medio": 1.05},
    )
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
                "ValoreUnNetto": 0.294,
                "ValoreTotale": 29.4,
                "Sconto_CodArtCliFor": "",
            }
        ]

        result = movimenti_articolo(
            "VA22",
            data_da=date(2025, 1, 3),
            data_a=date(2025, 1, 31),
        )

        self.assertTrue(result.filtro_attivo)
        self.assertEqual(result.giacenza_precedente, 16000.0)
        self.assertEqual(result.prezzo_ultimo_acquisto, 1.1)
        self.assertEqual(result.prezzo_medio, 1.05)
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

    @patch("apps.anagrafiche.partitario.timezone")
    def test_context_include_anno_precedente(self, mock_tz):
        mock_tz.localdate.return_value = date(2026, 8, 24)
        request = self.factory.get("/articoli/VA22/")
        ctx = movimenti_periodo_context(request)
        self.assertEqual(ctx["mov_data_da_prev"], "2025-01-01")
        self.assertEqual(ctx["mov_data_a_prev"], "2025-12-31")
        self.assertEqual(ctx["mov_data_da_default"], "2026-01-01")
        self.assertEqual(ctx["mov_data_a_default"], "2026-08-24")
