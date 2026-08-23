"""Lookup articolo per riga documento (descrizione + IVA da scheda)."""

from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.articoli.lookups import resolve_articolo, resolve_clifor
from apps.articoli.views import CodiceLookupView


class ResolveArticoloTests(SimpleTestCase):
    def test_empty_codice(self):
        info = resolve_articolo("")
        self.assertFalse(info["found"])
        self.assertEqual(info["descrizione"], "")
        self.assertEqual(info["iva"], "")

    @patch("apps.articoli.models.Articolo.objects")
    def test_found_fills_descrizione_iva_um_listino(self, mock_objects):
        art = MagicMock()
        art.codice = "VA22"
        art.descrizione = "Viti autoperforanti"
        art.cod_iva = "22"
        art.unita_misura = "PZ"
        art.listino1 = 12.5
        mock_objects.filter.return_value.only.return_value.first.return_value = art

        info = resolve_articolo("va22")
        self.assertTrue(info["found"])
        self.assertEqual(info["codice"], "VA22")
        self.assertEqual(info["descrizione"], "Viti autoperforanti")
        self.assertEqual(info["iva"], "22")
        self.assertEqual(info["unita_misura"], "PZ")
        self.assertEqual(info["prezzo_unitario"], 12.5)

    @patch("apps.articoli.models.Articolo.objects")
    def test_not_found(self, mock_objects):
        mock_objects.filter.return_value.only.return_value.first.return_value = None
        info = resolve_articolo("NOPE")
        self.assertFalse(info["found"])
        self.assertEqual(info["codice"], "NOPE")


class ArticoloLookupEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = CodiceLookupView.as_view()

    @patch("apps.articoli.views.resolve_articolo")
    def test_json_by_codice(self, mock_resolve):
        mock_resolve.return_value = {
            "found": True,
            "codice": "VA22",
            "descrizione": "Articolo prova",
            "iva": "22",
            "unita_misura": "NR",
            "prezzo_unitario": 3.0,
        }
        request = self.factory.get(
            "/articoli/lookup-codice/",
            {"tipo": "articolo", "codice": "VA22"},
        )
        request.user = MagicMock(is_authenticated=True)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertTrue(data["found"])
        self.assertEqual(data["descrizione"], "Articolo prova")
        self.assertEqual(data["iva"], "22")
        self.assertEqual(data["unita_misura"], "NR")
        self.assertEqual(data["prezzo_unitario"], 3.0)

    @patch("apps.articoli.views.search_opzioni")
    def test_json_search_by_q(self, mock_search):
        mock_search.return_value = [
            {
                "codice": "VA01",
                "descrizione": "Vaso",
                "iva": "22",
                "unita_misura": "PZ",
                "prezzo_unitario": 1.5,
                "found": True,
            }
        ]
        request = self.factory.get(
            "/articoli/lookup-codice/",
            {"tipo": "articolo", "q": "VA", "limit": "40"},
        )
        request.user = MagicMock(is_authenticated=True)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertEqual(data["q"], "VA")
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["codice"], "VA01")
        self.assertEqual(data["results"][0]["iva"], "22")
        mock_search.assert_called_once()
        args, kwargs = mock_search.call_args
        self.assertEqual(args[0], "articolo")
        self.assertEqual(args[1], "VA")

    @patch("apps.articoli.views.resolve_clifor")
    def test_json_cliente_includes_cond_paga(self, mock_resolve):
        mock_resolve.return_value = {
            "found": True,
            "codice": "C34719",
            "descrizione": "VIVAI KARMA",
            "cond_paga": "31",
            "cond_paga_descrizione": "ANTICIPATO",
            "agente": "A12",
            "agente_descrizione": "ROSSI MARIO",
            "destinatario": "VIVAI KARMA",
            "indirizzo": "STRADA RIVALTA, 220",
            "localita": "RIVOLI",
            "cap": "10098",
            "provincia": "TO",
            "nazione": "IT",
        }
        request = self.factory.get(
            "/articoli/lookup-codice/",
            {"tipo": "cliente", "codice": "C34719"},
        )
        request.user = MagicMock(is_authenticated=True)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertTrue(data["found"])
        self.assertEqual(data["cond_paga"], "31")
        self.assertEqual(data["cond_paga_descrizione"], "ANTICIPATO")
        self.assertEqual(data["agente"], "A12")
        self.assertEqual(data["agente_descrizione"], "ROSSI MARIO")
        self.assertEqual(data["destinatario"], "VIVAI KARMA")


class SearchArticoloRankingTests(SimpleTestCase):
    @patch("apps.articoli.models.Articolo.objects")
    def test_prefix_codice_ranks_before_descrizione_contains(self, mock_objects):
        """'VA' must surface VA* codes, not STI*VA*LETTO via descrizione."""
        from apps.articoli.lookups import search_opzioni

        va = MagicMock()
        va.codice = "VA22"
        va.descrizione = "VASO VIVAIO"
        va.cod_iva = "22"
        va.unita_misura = "N."
        va.listino1 = 0.76

        stivale = MagicMock()
        stivale.codice = "1010"
        stivale.descrizione = "STIVALETTO 1010"
        stivale.cod_iva = "22"
        stivale.unita_misura = "N."
        stivale.listino1 = 0.0

        chain = mock_objects.all.return_value.only.return_value
        filtered = chain.filter.return_value
        annotated = filtered.annotate.return_value
        annotated.order_by.return_value.__getitem__.return_value = [va, stivale]

        rows = search_opzioni("articolo", "VA", limit=40)
        self.assertEqual(rows[0]["codice"], "VA22")
        filtered.annotate.assert_called_once()
        annotated.order_by.assert_called_once_with("_rank", "codice", "descrizione")


class ResolveCliforTests(SimpleTestCase):
    @patch("apps.articoli.lookups.descrizione_agente", return_value="ROSSI MARIO")
    @patch("apps.articoli.lookups.descrizione_condizione", return_value="ANTICIPATO")
    @patch("apps.anagrafiche.models.get_by_codice")
    def test_cliente_fills_cond_paga_and_sede(self, mock_get, _mock_desc, _mock_agente):
        cli = MagicMock()
        cli.codice = "C34719"
        cli.ragione_sociale = "VIVAI KARMA S.S.A. DI ANDRE GULLI"
        cli.cond_paga = "31"
        cli.agente = "A12"
        cli.indirizzo = "STRADA RIVALTA, 220"
        cli.localita = "RIVOLI"
        cli.cap = "10098"
        cli.provincia = "TO"
        cli.cod_nazione = "IT"
        cli.telefono = "011 123456"
        cli.cellulare = "333 9876543"
        mock_get.return_value = cli

        info = resolve_clifor("cliente", "C34719")
        self.assertTrue(info["found"])
        self.assertEqual(info["cond_paga"], "31")
        self.assertEqual(info["cond_paga_descrizione"], "ANTICIPATO")
        self.assertEqual(info["agente"], "A12")
        self.assertEqual(info["agente_descrizione"], "ROSSI MARIO")
        self.assertEqual(info["destinatario"], "VIVAI KARMA S.S.A. DI ANDRE GULLI")
        self.assertEqual(info["indirizzo"], "STRADA RIVALTA, 220")
        self.assertEqual(info["localita"], "RIVOLI")
        self.assertEqual(info["nazione"], "IT")
        self.assertEqual(info["telefono"], "333 9876543")
        mock_get.assert_called_once()

    @patch("apps.anagrafiche.models.get_by_codice")
    def test_cliente_telefono_fallback_without_cellulare(self, mock_get):
        cli = MagicMock()
        cli.codice = "C1"
        cli.ragione_sociale = "ACME"
        cli.cond_paga = ""
        cli.agente = ""
        cli.indirizzo = "VIA 1"
        cli.localita = "ROMA"
        cli.cap = "00100"
        cli.provincia = "RM"
        cli.cod_nazione = "IT"
        cli.telefono = "06 111"
        cli.cellulare = ""
        mock_get.return_value = cli

        info = resolve_clifor("cliente", "C1")
        self.assertEqual(info["telefono"], "06 111")

    @patch("apps.anagrafiche.models.get_by_codice")
    def test_cliente_matches_padded_codice(self, mock_get):
        cli = MagicMock()
        cli.codice = "C33945     "
        cli.ragione_sociale = "UNIVERSITA' DI PISA"
        cli.cond_paga = ""
        cli.agente = ""
        cli.indirizzo = "VIA LUCA GHINI 13"
        cli.localita = "PISA"
        cli.cap = "56126"
        cli.provincia = "PI"
        cli.cod_nazione = "IT"
        mock_get.return_value = cli

        info = resolve_clifor("cliente", "C33945")
        self.assertTrue(info["found"])
        self.assertEqual(info["codice"], "C33945")
        self.assertEqual(info["destinatario"], "UNIVERSITA' DI PISA")
        self.assertEqual(info["indirizzo"], "VIA LUCA GHINI 13")

    def test_empty_codice(self):
        info = resolve_clifor("cliente", "")
        self.assertFalse(info["found"])
        self.assertEqual(info["descrizione"], "")
        self.assertEqual(info["cond_paga"], "")
        self.assertEqual(info["agente"], "")
        self.assertEqual(info["telefono"], "")
