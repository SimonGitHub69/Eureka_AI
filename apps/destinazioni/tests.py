from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from apps.destinazioni.models import compact_codice, destinazioni_for_anagrafica, tipo_clifor
from apps.destinazioni.numerazione import (
    compute_next_codice_dest,
    next_codice_dest_for_anagrafica,
)
from apps.destinazioni.sync import TABLES
from apps.destinazioni.views import anagrafica_detail_url


class CodiceCliForHelpersTests(SimpleTestCase):
    def test_compact_codice(self):
        self.assertEqual(compact_codice("C3203"), "C3203")
        self.assertEqual(compact_codice(" c 3203 "), "C3203")
        self.assertEqual(compact_codice("F2082"), "F2082")

    def test_tipo_clifor(self):
        self.assertEqual(tipo_clifor("C3203"), "C")
        self.assertEqual(tipo_clifor("F2082"), "F")
        self.assertEqual(tipo_clifor(""), "")

    def test_destinazioni_for_anagrafica_query_compiles(self):
        """Replace su TextField non deve sollevare FieldError (mixed types)."""
        qs = destinazioni_for_anagrafica("C16294")
        # Compila SQL senza eseguire: fallisce se manca output_field=TextField().
        sql = str(qs.query)
        self.assertIn("REPLACE", sql.upper())
        self.assertEqual(destinazioni_for_anagrafica("").count(), 0)

    def test_anagrafica_detail_url_cliente_e_fornitore(self):
        self.assertIn("/clienti/C3203/", anagrafica_detail_url("C 3203"))
        self.assertIn("/fornitori/F2082/", anagrafica_detail_url("F2082"))
        self.assertEqual(anagrafica_detail_url(""), "")
        self.assertEqual(anagrafica_detail_url("X1"), "")


class CodiceDestNumerazioneTests(SimpleTestCase):
    def test_first_code_is_padded_five(self):
        self.assertEqual(compute_next_codice_dest([], "D"), "D00001")
        self.assertEqual(compute_next_codice_dest([], "E"), "E00001")

    def test_max_plus_one_clienti(self):
        codes = ["D00001", "D00230", "D00100", "X99", "DABC", None, ""]
        self.assertEqual(compute_next_codice_dest(codes, "D"), "D00231")

    def test_max_plus_one_fornitori(self):
        codes = ["E00001", "E00099", "D01209"]
        self.assertEqual(compute_next_codice_dest(codes, "E"), "E00100")

    def test_ignores_other_prefix(self):
        self.assertEqual(compute_next_codice_dest(["E00999", "D00005"], "D"), "D00006")
        self.assertEqual(compute_next_codice_dest(["D01209", "E00003"], "E"), "E00004")

    def test_preserves_wider_padding(self):
        self.assertEqual(compute_next_codice_dest(["D123456"], "D"), "D123457")

    @patch("apps.destinazioni.numerazione.next_codice_dest_cliente", return_value="D01210")
    @patch("apps.destinazioni.numerazione.next_codice_dest_fornitore", return_value="E00042")
    def test_for_anagrafica_maps_c_and_f(self, mock_e, mock_d):
        self.assertEqual(next_codice_dest_for_anagrafica("C3203"), "D01210")
        self.assertEqual(next_codice_dest_for_anagrafica(" c 3203 "), "D01210")
        self.assertEqual(next_codice_dest_for_anagrafica("F2082"), "E00042")
        self.assertEqual(next_codice_dest_for_anagrafica(""), "")
        self.assertEqual(next_codice_dest_for_anagrafica("X1"), "")
        mock_d.assert_called()
        mock_e.assert_called()

class DestCliForSyncSpecTests(SimpleTestCase):
    def test_sync_uses_destclifor_and_id_pk(self):
        spec = TABLES[0]
        self.assertEqual(spec["source"], "DestCliFor")
        self.assertEqual(spec["target"], "DestCliFor")
        self.assertEqual(spec["pk"], "ID")


class DestinazioneLookupTests(SimpleTestCase):
    def _dest(self, **kwargs):
        d = MagicMock()
        d.id = kwargs.get("id", 1)
        d.codice = kwargs.get("codice", "C3203")
        d.codice_dest = kwargs.get("codice_dest", "01")
        d.ragione_sociale = kwargs.get("ragione_sociale", "MAGAZZINO NORD")
        d.indirizzo = kwargs.get("indirizzo", "VIA ROMA 1")
        d.cap = kwargs.get("cap", "10100")
        d.citta = kwargs.get("citta", "TORINO")
        d.provincia = kwargs.get("provincia", "TO")
        d.cod_nazione = kwargs.get("cod_nazione", "IT")
        d.desc_nazione = kwargs.get("desc_nazione", "ITALIA")
        d.telefono = kwargs.get("telefono", "0932 123456")
        return d

    @patch("apps.destinazioni.lookups.destinazioni_for_anagrafica")
    def test_search_requires_codice_clifor(self, mock_qs):
        from apps.destinazioni.lookups import search_destinazioni

        self.assertEqual(search_destinazioni("", "nord"), [])
        self.assertEqual(search_destinazioni(None, "nord"), [])
        mock_qs.assert_not_called()

    @patch("apps.destinazioni.lookups.destinazioni_for_anagrafica")
    def test_search_filters_and_maps_fields(self, mock_for):
        from apps.destinazioni.lookups import search_destinazioni

        dest = self._dest()
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.order_by.return_value = qs
        qs.__getitem__ = lambda _self, _sl: [dest]
        mock_for.return_value = qs

        rows = search_destinazioni("C 3203", "nord", limit=10)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["found"])
        self.assertEqual(row["codice"], "01")
        self.assertEqual(row["destinatario"], "MAGAZZINO NORD")
        self.assertEqual(row["localita"], "TORINO")
        self.assertEqual(row["nazione"], "ITALIA")
        self.assertEqual(row["telefono"], "0932 123456")
        self.assertEqual(row["codice_clifor"], "C3203")
        mock_for.assert_called_once_with("C 3203")

    @patch("apps.destinazioni.lookups.destinazioni_for_anagrafica")
    def test_resolve_by_codice_dest(self, mock_for):
        from apps.destinazioni.lookups import resolve_destinazione

        dest = self._dest(codice_dest="D02", ragione_sociale="SEDE SUD")
        qs = MagicMock()
        filtered = MagicMock()
        filtered.order_by.return_value.first.return_value = dest
        qs.filter.return_value = filtered
        mock_for.return_value = qs

        info = resolve_destinazione("d02", codice_clifor="C3203")
        self.assertTrue(info["found"])
        self.assertEqual(info["codice"], "D02")
        self.assertEqual(info["descrizione"], "SEDE SUD")
        self.assertEqual(info["indirizzo"], "VIA ROMA 1")
        self.assertEqual(info["nazione"], "ITALIA")
        self.assertEqual(info["telefono"], "0932 123456")

    def test_resolve_empty(self):
        from apps.destinazioni.lookups import resolve_destinazione

        info = resolve_destinazione("", codice_clifor="C3203")
        self.assertFalse(info["found"])
        self.assertEqual(info["destinatario"], "")
        self.assertEqual(info["telefono"], "")

    @patch("apps.destinazioni.lookups.search_destinazioni")
    def test_search_opzioni_destinazione_passes_clifor(self, mock_search):
        from apps.articoli.lookups import search_opzioni

        mock_search.return_value = [{"codice": "01", "descrizione": "A"}]
        rows = search_opzioni("destinazione", "a", limit=20, codice_clifor="C3203")
        self.assertEqual(rows[0]["codice"], "01")
        mock_search.assert_called_once_with("C3203", "a", limit=20)


class DestinazioneLookupEndpointTests(SimpleTestCase):
    def setUp(self):
        from django.test import RequestFactory

        from apps.articoli.views import CodiceLookupView

        self.factory = RequestFactory()
        self.view = CodiceLookupView.as_view()

    @patch("apps.articoli.views.search_opzioni")
    def test_json_search_destinazione(self, mock_search):
        mock_search.return_value = [
            {
                "codice": "01",
                "descrizione": "MAGAZZINO",
                "destinatario": "MAGAZZINO",
                "localita": "TORINO",
                "found": True,
            }
        ]
        request = self.factory.get(
            "/articoli/lookup-codice/",
            {
                "tipo": "destinazione",
                "q": "",
                "codice_clifor": "C3203",
                "limit": "40",
            },
        )
        request.user = MagicMock(is_authenticated=True)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertEqual(data["tipo"], "destinazione")
        self.assertEqual(data["codice_clifor"], "C3203")
        self.assertEqual(len(data["results"]), 1)
        mock_search.assert_called_once()
        _args, kwargs = mock_search.call_args
        self.assertEqual(kwargs.get("codice_clifor"), "C3203")

    @patch("apps.destinazioni.lookups.resolve_destinazione")
    def test_json_resolve_destinazione(self, mock_resolve):
        mock_resolve.return_value = {
            "found": True,
            "codice": "01",
            "descrizione": "MAGAZZINO NORD",
            "destinatario": "MAGAZZINO NORD",
            "indirizzo": "VIA ROMA 1",
            "localita": "TORINO",
            "cap": "10100",
            "provincia": "TO",
            "telefono": "0932 123456",
            "nazione": "ITALIA",
        }
        request = self.factory.get(
            "/articoli/lookup-codice/",
            {"tipo": "destinazione", "codice": "01", "codice_clifor": "C3203"},
        )
        request.user = MagicMock(is_authenticated=True)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertTrue(data["found"])
        self.assertEqual(data["localita"], "TORINO")
        self.assertEqual(data["nazione"], "ITALIA")
        self.assertEqual(data["telefono"], "0932 123456")
        mock_resolve.assert_called_once_with("01", codice_clifor="C3203")
