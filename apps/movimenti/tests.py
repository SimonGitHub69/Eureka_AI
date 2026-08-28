from django.db.models import Q
from django.test import SimpleTestCase
from django.urls import reverse

from apps.core.sync_incremental import detect_modifica_columns
from apps.movimenti.models import MovimentoT, MovimentoTDettaglio
from apps.movimenti.sync import TABLES


class MovimentiSyncSpecTests(SimpleTestCase):
    def test_sync_uses_movimentit_tables_and_pks(self):
        testa, dettaglio = TABLES
        self.assertEqual(testa["source"], "MovimentiT")
        self.assertEqual(testa["target"], "movimentit")
        self.assertEqual(testa["pk"], "ID_Testa")
        self.assertTrue(testa["page_by_pk"])
        self.assertEqual(dettaglio["source"], "MovimentiT_Dettaglio")
        self.assertEqual(dettaglio["target"], "movimentit_dettaglio")
        self.assertEqual(dettaglio["pk"], "ID")
        self.assertTrue(dettaglio["page_by_pk"])

    def test_dettaglio_detects_datamodifica(self):
        spec = detect_modifica_columns(
            [
                {"name": "ID"},
                {"name": "DataModifica", "pg_type": "timestamp"},
                {"name": "DataMov", "pg_type": "timestamp"},
            ],
            source_table="MovimentiT_Dettaglio",
        )
        self.assertIsNotNone(spec)
        assert spec is not None
        # DataModifica esiste ma non è valorizzata in 4D → watermark su DataMov.
        self.assertEqual(spec.data_col, "DataMov")
        self.assertIsNone(spec.ora_col)
        self.assertTrue(spec.force_columns)

    def test_testa_uses_dataregistraz_for_incremental(self):
        spec = detect_modifica_columns(
            [
                {"name": "ID_Testa"},
                {"name": "DataModifica", "pg_type": "timestamp"},
                {"name": "OraModifica", "pg_type": "time"},
                {"name": "DataRegistraz", "pg_type": "timestamp"},
                {"name": "OraRegistraz", "pg_type": "time"},
            ],
            source_table="MovimentiT",
        )
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataRegistraz")
        self.assertEqual(spec.ora_col, "OraRegistraz")
        self.assertTrue(spec.force_columns)

    def test_testa_override_without_introspected_registraz_still_resolves(self):
        spec = detect_modifica_columns(
            [{"name": "ID_Testa"}, {"name": "Utente_Modifica"}],
            source_table="MovimentiT",
        )
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataRegistraz")
        self.assertEqual(spec.ora_col, "OraRegistraz")

    def test_models_are_unmanaged_mirrors(self):
        self.assertFalse(MovimentoT._meta.managed)
        self.assertEqual(MovimentoT._meta.db_table, "movimentit")
        self.assertEqual(MovimentoT._meta.get_field("id_testa").db_column, "ID_Testa")
        self.assertFalse(MovimentoTDettaglio._meta.managed)
        self.assertEqual(MovimentoTDettaglio._meta.db_table, "movimentit_dettaglio")
        self.assertEqual(MovimentoTDettaglio._meta.get_field("id").db_column, "ID")
        self.assertEqual(
            MovimentoTDettaglio._meta.get_field("id_testa").db_column,
            "id_added_by_converter",
        )

    def test_list_and_detail_urls_resolve(self):
        self.assertEqual(reverse("movimenti:list"), "/movimenti/")
        self.assertEqual(reverse("movimenti:detail", kwargs={"pk": 1}), "/movimenti/1/")
        self.assertEqual(reverse("movimenti:sync"), "/parametri/4d/sync-movimenti/")

class MovimentiLabelsTests(SimpleTestCase):
    def test_attach_movimento_labels_sets_descriptions(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.movimenti.lookups import attach_movimento_labels

        rows = [
            SimpleNamespace(causale="05", cliente="C5737", fornitore=""),
            SimpleNamespace(causale="12", cliente="", fornitore="F100"),
        ]
        with (
            patch(
                "apps.movimenti.lookups.causali_magazzino_by_codes",
                return_value={"05": "VENDITA", "12": "CARICO"},
            ),
            patch(
                "apps.movimenti.lookups.clienti_ragione_sociale_by_codes",
                return_value={"C5737": "ACME SRL"},
            ),
            patch(
                "apps.movimenti.lookups.fornitori_ragione_sociale_by_codes",
                return_value={"F100": "BETA SPA"},
            ),
        ):
            attach_movimento_labels(rows)

        self.assertEqual(rows[0].causale_descrizione, "VENDITA")
        self.assertEqual(rows[0].cliente_ragione_sociale, "ACME SRL")
        self.assertEqual(rows[0].fornitore_ragione_sociale, "")
        self.assertEqual(rows[1].causale_descrizione, "CARICO")
        self.assertEqual(rows[1].fornitore_ragione_sociale, "BETA SPA")

    def test_format_helpers(self):
        from types import SimpleNamespace

        from apps.movimenti.lookups import (
            format_anagrafica_display,
            format_causale_display,
        )

        self.assertEqual(
            format_causale_display(
                SimpleNamespace(causale="05", causale_descrizione="VENDITA")
            ),
            "05 - VENDITA",
        )
        self.assertEqual(
            format_anagrafica_display("C1", "ACME SRL"),
            "ACME SRL (C1)",
        )


class MovimentiFilterTests(SimpleTestCase):
    def test_movimenti_articolo_filter_vuoto(self):
        from apps.movimenti.views import _movimenti_articolo_filter

        self.assertEqual(_movimenti_articolo_filter(""), Q())
        self.assertEqual(_movimenti_articolo_filter("   "), Q())

    def test_movimenti_articolo_filter_costruisce_exists(self):
        from apps.movimenti.views import _movimenti_articolo_filter

        filt = _movimenti_articolo_filter("RAME10")
        self.assertIsInstance(filt, Q)
        sql = str(MovimentoT.objects.filter(filt).query)
        self.assertIn("movimentit_dettaglio", sql.lower())
        self.assertIn("exists", sql.lower())


class MovimentoDetailBackTests(SimpleTestCase):
    def test_related_back_from_articolo_movimenti(self):
        from django.test import RequestFactory

        from apps.core.navigation import related_back

        request = RequestFactory().get(
            "/movimenti/100/",
            {"next": "/articoli/VA22/?mov_data_da=2025-01-01"},
        )
        back_url, back_label = related_back(request)
        self.assertEqual(
            back_url,
            "/articoli/VA22/?mov_data_da=2025-01-01#articolo-movimenti",
        )
        self.assertEqual(back_label, "Torna ai movimenti")


class MovimentoRighePrezziTests(SimpleTestCase):
    def test_attach_prezzi_movimento_righe(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.articoli.movimenti_magazzino import attach_prezzi_movimento_righe

        riga = SimpleNamespace(
            sconto_cod_art_cli_for="7,5",
            valore_un_netto=3.9035,
        )
        with patch(
            "apps.articoli.movimenti_magazzino._sconti_by_codes",
            return_value={},
        ):
            attach_prezzi_movimento_righe([riga])
        self.assertAlmostEqual(riga.prezzo_lordo, 4.22, places=2)
        self.assertEqual(riga.sconto, "7,5%")
        self.assertAlmostEqual(riga.prezzo_netto, 3.9035, places=4)

