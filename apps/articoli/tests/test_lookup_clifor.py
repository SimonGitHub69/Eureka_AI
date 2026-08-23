"""Lookup combinato cliente+fornitore (tipo=clifor) per Primanota."""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.articoli.lookups import LOOKUP_TIPI, descrizione_clifor, resolve_clifor, search_opzioni
from apps.articoli.views import CodiceLookupView


def _anagrafica(codice: str, ragione: str) -> MagicMock:
    obj = MagicMock()
    obj.codice = codice
    obj.ragione_sociale = ragione
    obj.cond_paga = ""
    obj.agente = ""
    obj.indirizzo = ""
    obj.localita = ""
    obj.cap = ""
    obj.provincia = ""
    obj.cod_nazione = ""
    return obj


class CliforLookupTests(SimpleTestCase):
    def test_tipo_in_lookup_tipi(self):
        self.assertIn("clifor", LOOKUP_TIPI)

    def test_empty_codice(self):
        info = resolve_clifor("clifor", "")
        self.assertFalse(info["found"])
        self.assertEqual(info["descrizione"], "")

    @patch("apps.articoli.lookups.resolve_clifor")
    def test_descrizione_uses_resolve(self, mock_resolve):
        mock_resolve.return_value = {"descrizione": "VIVAI DE LAURENTIIS"}
        self.assertEqual(descrizione_clifor("C7310"), "VIVAI DE LAURENTIIS")
        mock_resolve.assert_called_once_with("clifor", "C7310")

    @patch("apps.anagrafiche.models.get_by_codice")
    def test_resolve_c_prefix_cliente(self, mock_get):
        mock_get.return_value = _anagrafica("C7310", "VIVAI DE LAURENTIIS")
        info = resolve_clifor("clifor", "C7310")
        self.assertTrue(info["found"])
        self.assertEqual(info["descrizione"], "VIVAI DE LAURENTIIS")
        self.assertEqual(info["kind"], "cliente")
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[0][0].__name__, "Cliente")

    @patch("apps.anagrafiche.models.get_by_codice")
    def test_resolve_f_prefix_fornitore(self, mock_get):
        mock_get.return_value = _anagrafica("F2082", "ACME SRL")
        info = resolve_clifor("clifor", "F2082")
        self.assertTrue(info["found"])
        self.assertEqual(info["descrizione"], "ACME SRL")
        self.assertEqual(info["kind"], "fornitore")
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[0][0].__name__, "Fornitore")

    def test_search_merges_clienti_and_fornitori_sorted(self):
        original = search_opzioni

        def fake(tipo, q=None, *, limit=40, codice_clifor=None):
            if tipo == "clifor":
                return original(tipo, q, limit=limit, codice_clifor=codice_clifor)
            if tipo == "cliente":
                return [{"codice": "C1", "descrizione": "Zeta Spa"}]
            if tipo == "fornitore":
                return [{"codice": "F1", "descrizione": "Alfa Srl"}]
            return []

        with patch("apps.articoli.lookups.search_opzioni", side_effect=fake):
            rows = original("clifor", "")
        self.assertEqual([r["codice"] for r in rows], ["F1", "C1"])
        self.assertEqual(rows[0]["kind"], "fornitore")
        self.assertEqual(rows[1]["kind"], "cliente")


class CliforLookupEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = CodiceLookupView.as_view()

    @patch("apps.articoli.views.resolve_clifor")
    def test_json_by_codice(self, mock_resolve):
        mock_resolve.return_value = {
            "found": True,
            "codice": "C7310",
            "descrizione": "VIVAI DE LAURENTIIS",
            "kind": "cliente",
            "cond_paga": "31",
        }
        request = self.factory.get(
            "/articoli/lookup-codice/",
            {"tipo": "clifor", "codice": "C7310"},
        )
        request.user = MagicMock(is_authenticated=True)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["found"])
        self.assertEqual(data["descrizione"], "VIVAI DE LAURENTIIS")
        self.assertEqual(data["kind"], "cliente")
        mock_resolve.assert_called_once_with("clifor", "C7310")

    @patch("apps.articoli.views.search_opzioni")
    def test_json_search_by_q(self, mock_search):
        mock_search.return_value = [
            {"codice": "C1", "descrizione": "Cliente", "kind": "cliente"},
            {"codice": "F1", "descrizione": "Fornitore", "kind": "fornitore"},
        ]
        request = self.factory.get(
            "/articoli/lookup-codice/",
            {"tipo": "clifor", "q": "1", "limit": "40"},
        )
        request.user = MagicMock(is_authenticated=True)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["q"], "1")
        self.assertEqual(len(data["results"]), 2)
        mock_search.assert_called_once()
        self.assertEqual(mock_search.call_args[0][0], "clifor")
