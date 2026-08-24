"""Test stampa movimenti magazzino su articolo."""

from datetime import date
from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.articoli.movimenti_magazzino import MovimentiArticoloResult
from apps.articoli.movimenti_periodo import movimenti_print_filter_summary, movimenti_print_query
from apps.articoli.views import ArticoloMovimentiPrintView
from apps.core.print_list import build_print_rows
from apps.articoli.movimenti_magazzino import MOVIMENTI_ARTICOLO_PRINT_COLUMNS, MovimentoArticoloRiga


class ArticoloMovimentiPrintTests(SimpleTestCase):
    def test_print_url(self):
        url = reverse("articoli:movimenti_print", kwargs={"codice": "VA22"})
        self.assertTrue(url.endswith("/movimenti/stampa/"))

    def test_structured_row_aligns_numeric_columns(self):
        from apps.core.print_list import structured_print_row

        row = structured_print_row(
            ["16.000", "100", "10,000", "10%", "9,000", "13.726"],
            MOVIMENTI_ARTICOLO_PRINT_COLUMNS[9:],
        )
        for cell in row["cells"]:
            self.assertEqual(cell["align"], "end")

    def test_print_columns_build_rows(self):
        riga = MovimentoArticoloRiga(
            id_testa=None,
            num_registraz=None,
            data_registraz=None,
            causale="",
            causale_descrizione="",
            dep_entrata="",
            dep_uscita="",
            cli_for_codice="",
            cli_for_ragione="",
            cli_for_kind="",
            num_doc="",
            data_doc=None,
            carico=268050.0,
            scarico=254324.0,
            prezzo_unitario=0.0,
            prezzo_lordo=0.0,
            sconto="",
            valore=0.0,
            giacenza=13726.0,
            is_totale=True,
        )
        headers, rows = build_print_rows([riga], MOVIMENTI_ARTICOLO_PRINT_COLUMNS)
        self.assertIn("P. netto", headers)
        self.assertIn("P. lordo", headers)
        self.assertIn("Totali", rows[0][2])
        self.assertEqual(rows[0][-1], "13.726")

    def test_print_filter_summary(self):
        request = RequestFactory().get(
            "/articoli/VA22/movimenti/stampa/",
            {"mov_data_da": "2025-01-01", "mov_data_a": "2025-12-31"},
        )
        art = MagicMock(codice="VA22", unita_misura="PZ")
        result = MovimentiArticoloResult(
            codice="VA22",
            esistenza_attuale=13726.0,
            data_da=date(2025, 1, 1),
            data_a=date(2025, 12, 31),
            giacenza_precedente=16000.0,
            filtro_attivo=True,
        )
        summary = movimenti_print_filter_summary(request, result, art)
        self.assertIn("VA22", summary)
        self.assertIn("13.726", summary)
        self.assertIn("01/01/2025", summary)
        self.assertIn("16.000", summary)

    def test_print_query_preserves_period(self):
        request = RequestFactory().get(
            "/articoli/VA22/",
            {"mov_data_da": "2025-01-01", "mov_data_a": "2025-06-30"},
        )
        self.assertIn("mov_data_da=2025-01-01", movimenti_print_query(request))
        self.assertIn("mov_data_a=2025-06-30", movimenti_print_query(request))

    def test_print_requires_login(self):
        factory = RequestFactory()
        request = factory.get("/articoli/VA22/movimenti/stampa/")
        request.user = AnonymousUser()
        response = ArticoloMovimentiPrintView.as_view()(request, codice="VA22")
        self.assertEqual(response.status_code, 302)
