"""Lookup combinato PDC + cliente/fornitore (tipo=pdc_clifor) per Primanota Generico."""

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.articoli.lookups import (
    LOOKUP_TIPI,
    descrizione_pdc_clifor,
    search_opzioni,
)


class PdcCliforLookupTests(SimpleTestCase):
    def test_tipo_in_lookup_tipi(self):
        self.assertIn("pdc_clifor", LOOKUP_TIPI)

    def test_descrizione_prefers_pdc_then_clifor(self):
        with (
            patch("apps.articoli.lookups.descrizione_pdc", return_value="Cassa"),
            patch("apps.articoli.lookups.descrizione_clifor", return_value="VIVAI"),
        ):
            self.assertEqual(descrizione_pdc_clifor("1.10.1"), "Cassa")
        with (
            patch("apps.articoli.lookups.descrizione_pdc", return_value=""),
            patch("apps.articoli.lookups.descrizione_clifor", return_value="VIVAI"),
        ):
            self.assertEqual(descrizione_pdc_clifor("C7310"), "VIVAI")
        with (
            patch("apps.articoli.lookups.descrizione_pdc", return_value=""),
            patch("apps.articoli.lookups.descrizione_clifor", return_value=""),
        ):
            self.assertEqual(descrizione_pdc_clifor("X"), "")

    def test_search_merges_pdc_and_clifor(self):
        original = search_opzioni

        def fake(tipo, q=None, *, limit=40, codice_clifor=None):
            if tipo == "pdc_clifor":
                return original(tipo, q, limit=limit, codice_clifor=codice_clifor)
            if tipo == "pdc":
                return [{"codice": "1.10.1", "descrizione": "Cassa"}]
            if tipo == "clifor":
                return [
                    {"codice": "C1", "descrizione": "Zeta Spa", "kind": "cliente"},
                    {"codice": "F1", "descrizione": "Alfa Srl", "kind": "fornitore"},
                ]
            return []

        with patch("apps.articoli.lookups.search_opzioni", side_effect=fake):
            rows = original("pdc_clifor", "")
        self.assertEqual([r["codice"] for r in rows], ["F1", "1.10.1", "C1"])
        kinds = {r["codice"]: r["kind"] for r in rows}
        self.assertEqual(kinds["1.10.1"], "pdc")
        self.assertEqual(kinds["C1"], "cliente")
        self.assertEqual(kinds["F1"], "fornitore")
