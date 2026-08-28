from unittest.mock import MagicMock, patch

from django.db.utils import ProgrammingError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.sync_incremental import detect_modifica_columns
from apps.primanota.lookups import (
    attach_causali_contabili,
    attach_line_lookups,
    attach_registri_iva,
    resolve_causale_contabile,
    resolve_partita_clifor,
    resolve_registro_iva,
)
from apps.primanota.forms import PrimanotaForm, PrimanotaRigaForm, save_primanota_with_righe, riga_formset_for
from apps.primanota.models import Primanota, PrimanotaDettaglio
from apps.primanota.sync import TABLES
from apps.primanota.views import _primanota_print_filter_summary, load_primanota_righe


class PrimanotaPrintFilterSummaryTests(SimpleTestCase):
    def test_summary_periodo_e_tipo(self):
        from django.test import RequestFactory

        request = RequestFactory().get(
            "/primanota/stampa/",
            {"data_da": "2025-01-01", "data_a": "2025-01-31", "tipo": "2"},
        )
        summary = _primanota_print_filter_summary(request)
        self.assertIn("01/01/2025", summary)
        self.assertIn("31/01/2025", summary)
        self.assertIn("Tipo: IVA", summary)

    def test_summary_vuota_senza_filtri(self):
        from django.test import RequestFactory

        request = RequestFactory().get("/primanota/stampa/")
        self.assertEqual(_primanota_print_filter_summary(request), "")


class PrimanotaSyncSpecTests(SimpleTestCase):
    def test_sync_uses_primanota_tables_and_id_pk(self):
        testa, dettaglio = TABLES
        self.assertEqual(testa["source"], "Primanota")
        self.assertEqual(testa["target"], "primanota")
        self.assertEqual(testa["pk"], "ID")
        self.assertTrue(testa["page_by_pk"])
        self.assertTrue(testa.get("incremental_by_pk"))
        self.assertEqual(testa.get("batch_size"), 5000)
        self.assertEqual(testa.get("page_size"), 50000)
        self.assertEqual(dettaglio["source"], "Primanota_Dettaglio")
        self.assertEqual(dettaglio["target"], "primanota_dettaglio")
        self.assertEqual(dettaglio["pk"], "ID")
        self.assertTrue(dettaglio["page_by_pk"])
        self.assertTrue(dettaglio.get("incremental_by_pk"))

    def test_sync_detects_modifica_columns_for_both_tables(self):
        testa_spec = detect_modifica_columns([{"name": "ID"}], source_table="Primanota")
        dettaglio_spec = detect_modifica_columns(
            [{"name": "ID"}],
            source_table="Primanota_Dettaglio",
        )
        self.assertIsNotNone(testa_spec)
        self.assertIsNotNone(dettaglio_spec)
        assert testa_spec is not None
        assert dettaglio_spec is not None
        self.assertEqual(testa_spec.data_col, "DataModifica")
        self.assertEqual(testa_spec.ora_col, "OraModifica")
        self.assertEqual(testa_spec.data_pg_type, "timestamp")
        self.assertEqual(dettaglio_spec.data_col, "DataModifica")
        self.assertEqual(dettaglio_spec.ora_col, "OraModifica")
        self.assertEqual(dettaglio_spec.data_pg_type, "timestamp")

    def test_models_are_unmanaged_mirrors(self):
        self.assertFalse(Primanota._meta.managed)
        self.assertEqual(Primanota._meta.db_table, "primanota")
        self.assertEqual(Primanota._meta.get_field("id").db_column, "ID")
        self.assertEqual(Primanota._meta.get_field("numero_reg").db_column, "NumeroReg")
        self.assertEqual(Primanota._meta.get_field("fornitore_cee").db_column, "FornitoreCEE")
        self.assertEqual(Primanota._meta.get_field("data_modifica").db_column, "DataModifica")
        self.assertEqual(Primanota._meta.get_field("ora_modifica").db_column, "OraModifica")
        self.assertFalse(PrimanotaDettaglio._meta.managed)
        self.assertEqual(PrimanotaDettaglio._meta.db_table, "primanota_dettaglio")
        self.assertEqual(PrimanotaDettaglio._meta.get_field("id").db_column, "ID")
        self.assertEqual(
            PrimanotaDettaglio._meta.get_field("id_testa").db_column,
            "id_added_by_converter",
        )
        self.assertEqual(PrimanotaDettaglio._meta.get_field("imp_val").db_column, "Imp_Val")
        self.assertEqual(
            PrimanotaDettaglio._meta.get_field("data_modifica").db_column,
            "DataModifica",
        )
        self.assertEqual(
            PrimanotaDettaglio._meta.get_field("ora_modifica").db_column,
            "OraModifica",
        )

    def test_tipo_label(self):
        row = Primanota(id=1, tipo=1)
        self.assertEqual(row.tipo_label, "Generico")
        self.assertEqual(Primanota(id=2, tipo=2).tipo_label, "IVA")
        self.assertEqual(Primanota(id=3, tipo=3).tipo_label, "Corrispettivi")
        self.assertEqual(Primanota(id=4, tipo=4).tipo_label, "Iva con Autofattura")
        self.assertEqual(Primanota(id=5, tipo=None).tipo_label, "—")
        self.assertEqual(Primanota(id=6, tipo=9).tipo_label, "9")
        self.assertTrue(Primanota(id=7, tipo=2).is_iva)
        self.assertTrue(Primanota(id=70, tipo=4).is_iva)
        self.assertFalse(Primanota(id=8, tipo=1).is_iva)
        self.assertTrue(Primanota(id=9, tipo=1).is_generico)
        self.assertFalse(Primanota(id=10, tipo=2).is_generico)
        self.assertFalse(Primanota(id=11, tipo=3).is_generico)
        self.assertTrue(Primanota(id=12, tipo=3).is_corrispettivi)
        self.assertFalse(Primanota(id=13, tipo=2).is_corrispettivi)
        self.assertFalse(Primanota(id=14, tipo=1).is_corrispettivi)
        self.assertTrue(Primanota(id=15, tipo=4).is_iva_autofattura)
        self.assertFalse(Primanota(id=16, tipo=2).is_iva_autofattura)
        self.assertFalse(Primanota(id=17, tipo=1).is_iva_autofattura)

    def test_generico_detail_hides_scadenze_ins(self):
        from apps.primanota.views import SCADENZE_CAMPI_EXCLUDE

        self.assertIn("ScadenzeIns", SCADENZE_CAMPI_EXCLUDE)

    def test_iva_line_uses_conto_partita_and_imponibile(self):
        vendita = PrimanotaDettaglio(
            id=1, conto_avere="3.71.1", avere=27424.32, conto_dare="", dare=0
        )
        self.assertEqual(vendita.conto_partita, "3.71.1")
        self.assertEqual(vendita.imponibile, 27424.32)
        acquisto = PrimanotaDettaglio(
            id=2, conto_dare="1.10.1", dare=100.0, conto_avere="", avere=0
        )
        self.assertEqual(acquisto.conto_partita, "1.10.1")
        self.assertEqual(acquisto.imponibile, 100.0)
        euro = PrimanotaDettaglio(id=3, conto_avere="3.71.1", avere=34.9, imp_val=None)
        self.assertEqual(euro.imponibile_valuta, 34.9)
        usd = PrimanotaDettaglio(id=4, conto_avere="3.71.1", avere=100.0, imp_val=110.0)
        self.assertEqual(usd.imponibile_valuta, 110.0)

    def test_attach_line_lookups_decodes_pdc(self):
        pdc = MagicMock()
        pdc.codice = "3.71.1"
        pdc.descrizione = "Ricavi vendite"
        filtered = [pdc]
        qs = MagicMock()
        qs.annotate.return_value.filter.return_value = filtered
        riga = PrimanotaDettaglio(id=1, conto_avere="3.71.1", conto_dare="")
        with (
            patch("apps.pdc.models.PianoConti") as mock_model,
            patch("apps.primanota.lookups.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            attach_line_lookups([riga], iva=True)
        self.assertIs(riga.pdc, pdc)
        self.assertIn("/pdc/", riga.pdc_url)

    def test_attach_line_lookups_decodes_clifor_on_dare_avere(self):
        riga = PrimanotaDettaglio(id=1, conto_dare="C7310", conto_avere="F2082")
        qs = MagicMock()
        qs.annotate.return_value.filter.return_value = []
        with (
            patch("apps.pdc.models.PianoConti") as mock_model,
            patch("apps.primanota.lookups.transaction.atomic") as mock_atomic,
            patch("apps.primanota.lookups.resolve_partita_clifor") as mock_clifor,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            mock_clifor.side_effect = lambda code: {
                "C7310": {
                    "codice": "C7310",
                    "label": "VIVAI",
                    "url": "/clienti/C7310/",
                },
                "F2082": {
                    "codice": "F2082",
                    "label": "ACME",
                    "url": "/fornitori/F2082/",
                },
            }.get((code or "").strip(), {"label": "", "url": ""})
            attach_line_lookups([riga])
        self.assertEqual(riga.pdc_dare.label, "VIVAI")
        self.assertIn("/clienti/", riga.pdc_dare_url)
        self.assertEqual(riga.pdc_avere.label, "ACME")
        self.assertIn("/fornitori/", riga.pdc_avere_url)

    def test_attach_line_lookups_decodes_clifor_on_conto_partita(self):
        riga = PrimanotaDettaglio(id=1, conto_avere="C3567", conto_dare="")
        qs = MagicMock()
        qs.annotate.return_value.filter.return_value = []
        with (
            patch("apps.pdc.models.PianoConti") as mock_model,
            patch("apps.primanota.lookups.transaction.atomic") as mock_atomic,
            patch("apps.primanota.lookups.resolve_partita_clifor") as mock_clifor,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            mock_clifor.side_effect = lambda code: {
                "C3567": {
                    "codice": "C3567",
                    "label": "CLIENTE GENERICO U.E.",
                    "url": "/clienti/C3567/",
                },
            }.get((code or "").strip(), {"label": "", "url": ""})
            attach_line_lookups([riga], iva=True)
        self.assertEqual(riga.pdc.label, "CLIENTE GENERICO U.E.")
        self.assertIn("/clienti/", riga.pdc_url)

    def test_scadenze_righe_from_header_slots(self):
        from datetime import datetime

        row = Primanota(
            id=1,
            tipo=2,
            scad1=datetime(2024, 3, 31),
            imp_scad1=16731.99,
            scad2=datetime(2024, 4, 30),
            imp_scad2=16731.98,
            flag_ra01=False,
            scadenze_ins=False,
            acconto=0,
        )
        slots = row.scadenze_righe
        self.assertEqual(len(slots), 10)
        self.assertEqual(slots[0]["n"], 1)
        self.assertEqual(slots[0]["importo"], 16731.99)
        self.assertEqual(slots[1]["importo"], 16731.98)
        self.assertFalse(slots[0]["rit_acc"])
        self.assertIsNone(slots[2]["data"])
        self.assertAlmostEqual(row.totale_scadenze, 33463.97)
        empty = Primanota(id=2, scad1=datetime(1, 1, 1), imp_scad1=0)
        self.assertIsNone(empty.scadenze_righe[0]["data"])

    def test_scadenze_righe_fills_dates_when_4d_left_scad_null(self):
        """4D con ScadenzeIns=No spesso ha ImpScad valorizzato e Scad NULL."""
        from datetime import date, datetime
        from types import SimpleNamespace
        from unittest.mock import patch

        row = Primanota(
            id=435956,
            tipo=2,
            scadenze_ins=False,
            codice_paga="141",
            data_doc=datetime(2026, 7, 13),
            data_reg=datetime(2026, 7, 13),
            scad1=None,
            imp_scad1=42.0,
        )
        cond = SimpleNamespace(
            numero_rate=1,
            prima_rata=0,
            intervallo=0,
            giorno_fisso=0,
            fine_mese=False,
            mese_esclusione=None,
            mese_esclusione2=None,
            gg_mese_esclus=None,
            gg_mese_esclus2=None,
        )
        with patch("apps.primanota.scadenze.load_condizione", return_value=cond):
            slots = row.scadenze_righe
        self.assertEqual(slots[0]["data"], date(2026, 7, 13))
        self.assertEqual(slots[0]["importo"], 42.0)
        self.assertIsNone(slots[1]["data"])

    def test_causali_choices_generico_excludes_registro_iva(self):
        from apps.primanota.lookups import causali_contabili_choices

        catalog = [
            {"code": "PN", "label": "PN — Prima nota", "has_registro": False},
            {"code": "FT", "label": "FT — Fattura", "has_registro": True},
            {"code": "GI", "label": "GI — Giroconto", "has_registro": False},
        ]
        all_codes = [c[0] for c in causali_contabili_choices(catalog=catalog)]
        gen_codes = [
            c[0]
            for c in causali_contabili_choices(
                senza_registro_iva=True, catalog=catalog
            )
        ]
        self.assertIn("FT", all_codes)
        self.assertIn("PN", all_codes)
        self.assertNotIn("FT", gen_codes)
        self.assertEqual(gen_codes, ["", "PN", "GI"])
        iva_codes = [
            c[0]
            for c in causali_contabili_choices(
                con_registro_iva=True, catalog=catalog
            )
        ]
        self.assertEqual(iva_codes, ["", "FT"])
        self.assertNotIn("PN", iva_codes)

    def test_causali_choices_corrispettivi_only_corrispettivi_register(self):
        from apps.primanota.lookups import causali_contabili_choices

        catalog = [
            {"code": "PN", "label": "PN", "has_registro": False, "tipo_registro": ""},
            {"code": "FT", "label": "FT", "has_registro": True, "tipo_registro": "Vendita"},
            {"code": "24", "label": "24", "has_registro": True, "tipo_registro": "Corrispettivi"},
            {"code": "AQ", "label": "AQ", "has_registro": True, "tipo_registro": "Acquisto"},
        ]
        corr_codes = [
            c[0]
            for c in causali_contabili_choices(
                registro_corrispettivi=True, catalog=catalog
            )
        ]
        self.assertEqual(corr_codes, ["", "24"])
        self.assertNotIn("FT", corr_codes)
        self.assertNotIn("PN", corr_codes)

    def test_causali_choices_autofattura_only_flagged_causali(self):
        from apps.primanota.lookups import causali_contabili_choices

        catalog = [
            {"code": "FT", "label": "FT", "has_registro": True, "is_autofattura": False},
            {"code": "XX", "label": "XX", "has_registro": True, "is_autofattura": True},
            {"code": "PN", "label": "PN", "has_registro": False, "is_autofattura": True},
        ]
        codes = [
            c[0]
            for c in causali_contabili_choices(iva_autofattura=True, catalog=catalog)
        ]
        self.assertEqual(codes, ["", "XX"])
        self.assertNotIn("FT", codes)
        self.assertNotIn("PN", codes)

    def test_causale_is_registro_corrispettivi(self):
        from apps.primanota.lookups import causale_is_registro_corrispettivi

        causale = MagicMock()
        causale.registro_iva = "9"
        registro = MagicMock()
        registro.tipo_registro = "Corrispettivi"
        with patch("apps.primanota.lookups.resolve_registro_iva", return_value=registro):
            self.assertTrue(causale_is_registro_corrispettivi(causale))
        registro.tipo_registro = "Vendita"
        with patch("apps.primanota.lookups.resolve_registro_iva", return_value=registro):
            self.assertFalse(causale_is_registro_corrispettivi(causale))
        self.assertFalse(causale_is_registro_corrispettivi(None))

    def test_causale_is_iva_autofattura(self):
        from apps.primanota.lookups import causale_is_iva_autofattura

        causale = MagicMock()
        causale.registro_iva = "AF"
        causale.iva_con_autofattura = True
        causale.autofattura = False
        self.assertTrue(causale_is_iva_autofattura(causale))
        causale.iva_con_autofattura = False
        causale.autofattura = True
        self.assertTrue(causale_is_iva_autofattura(causale))
        causale.autofattura = False
        self.assertFalse(causale_is_iva_autofattura(causale))
        causale.registro_iva = ""
        causale.iva_con_autofattura = True
        self.assertFalse(causale_is_iva_autofattura(causale))
        self.assertFalse(causale_is_iva_autofattura(None))

    def test_causale_is_autofattura_automatica(self):
        from apps.primanota.lookups import causale_is_autofattura_automatica

        causale = MagicMock()
        causale.autofattura = True
        self.assertTrue(causale_is_autofattura_automatica(causale))
        causale.autofattura = False
        self.assertFalse(causale_is_autofattura_automatica(causale))
        causale.autofattura = None
        self.assertFalse(causale_is_autofattura_automatica(causale))
        self.assertFalse(causale_is_autofattura_automatica(None))

    def test_form_iva_rejects_causale_without_registro_iva(self):
        causale = MagicMock()
        causale.codice = "PN"
        causale.registro_iva = ""
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("PN", "PN — Prima nota")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            form = PrimanotaForm(data={"tipo": "2", "causale": "PN"}, is_create=True)
            self.assertFalse(form.is_valid())
            self.assertIn("causale", form.errors)

    def test_form_corrispettivi_rejects_causale_without_corrispettivi_register(self):
        causale = MagicMock()
        causale.codice = "FT"
        causale.registro_iva = "1"
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("FT", "FT — Fattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.causale_is_registro_corrispettivi", return_value=False),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=None),
        ):
            form = PrimanotaForm(data={"tipo": "3", "causale": "FT"}, is_create=True)
            self.assertFalse(form.is_valid())
            self.assertIn("causale", form.errors)

    def test_form_autofattura_rejects_causale_without_autofattura_flag(self):
        causale = MagicMock()
        causale.codice = "FT"
        causale.registro_iva = "1"
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("FT", "FT — Fattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.causale_is_iva_autofattura", return_value=False),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=None),
        ):
            form = PrimanotaForm(data={"tipo": "4", "causale": "FT"}, is_create=True)
            self.assertFalse(form.is_valid())
            self.assertIn("causale", form.errors)

    def test_form_autofattura_keeps_and_uppercases_fornitore(self):
        causale = MagicMock()
        causale.codice = "XX"
        causale.registro_iva = "15"
        causale.autofattura = True
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("XX", "XX — Autofattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("15", "15")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.causale_is_iva_autofattura", return_value=True),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=None),
        ):
            form = PrimanotaForm(
                data={"tipo": "4", "causale": "XX", "fornitore_cee": "f1871", "data_reg": "2026-08-18"},
                is_create=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["fornitore_cee"], "F1871")

    def test_form_autofattura_non_automatica_clears_fornitore(self):
        causale = MagicMock()
        causale.codice = "XX"
        causale.registro_iva = "15"
        causale.autofattura = False
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("XX", "XX — Autofattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("15", "15")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.causale_is_iva_autofattura", return_value=True),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=None),
        ):
            form = PrimanotaForm(
                data={"tipo": "4", "causale": "XX", "fornitore_cee": "F1871", "data_reg": "2026-08-18"},
                is_create=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertIsNone(form.cleaned_data["fornitore_cee"])

    def test_form_iva_clears_fornitore_cee(self):
        causale = MagicMock()
        causale.codice = "FT"
        causale.registro_iva = "1"
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("FT", "FT — Fattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=None),
        ):
            form = PrimanotaForm(
                data={"tipo": "2", "causale": "FT", "fornitore_cee": "F1871", "data_reg": "2026-08-18"},
                is_create=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertIsNone(form.cleaned_data["fornitore_cee"])

    def test_form_generico_rejects_causale_with_registro_iva(self):
        causale = MagicMock()
        causale.codice = "FT"
        causale.registro_iva = "1"
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("FT", "FT — Fattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            form = PrimanotaForm(data={"tipo": "1", "causale": "FT"}, is_create=True)
            self.assertFalse(form.is_valid())
            self.assertIn("causale", form.errors)

    def test_attach_causale_contabile_by_trimmed_code(self):
        causale = MagicMock()
        causale.codice = "FT  "
        causale.descrizione = "Fattura vendita"
        filtered = [causale]
        qs = MagicMock()
        qs.annotate.return_value.filter.return_value = filtered
        with (
            patch("apps.primanota.lookups.CausaleContabile") as mock_model,
            patch("apps.primanota.lookups.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            rows = [Primanota(id=1, causale="ft")]
            attach_causali_contabili(rows)
        self.assertIs(rows[0].causale_contabile, causale)
        self.assertEqual(resolve_causale_contabile(""), None)

    def test_attach_registro_iva_by_trimmed_code(self):
        registro = MagicMock()
        registro.codice = "1"
        registro.descrizione = "VENDITE ITALIA"
        filtered = [registro]
        qs = MagicMock()
        qs.annotate.return_value.filter.return_value = filtered
        with (
            patch("apps.registri_iva.lookups.RegistroIva") as mock_model,
            patch("apps.registri_iva.lookups.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            rows = [Primanota(id=1, registro=" 1 ")]
            attach_registri_iva(rows)
        self.assertIs(rows[0].registro_iva, registro)
        self.assertEqual(resolve_registro_iva(""), None)

    def test_resolve_registro_iva_ok_if_table_missing(self):
        qs = MagicMock()
        qs.annotate.side_effect = ProgrammingError("missing")
        with (
            patch("apps.registri_iva.lookups.RegistroIva") as mock_model,
            patch("apps.registri_iva.lookups.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            self.assertIsNone(resolve_registro_iva("1"))

    def test_form_causale_prefills_registro_from_causale(self):
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = "1"
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—"), ("01", "01 — Fattura")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            form = PrimanotaForm(
                data={
                    "tipo": "2",
                    "causale": "01",
                    "registro": "",
                    "data_reg": "2026-08-18",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["causale"], "01")
            self.assertEqual(form.cleaned_data["registro"], "1")
            self.assertTrue(form.fields["registro"].disabled)

    def test_form_causale_overrides_posted_registro(self):
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = "1"
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—"), ("01", "01 — Fattura")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite"), ("9", "9")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=12),
        ):
            form = PrimanotaForm(
                data={"tipo": "2", "causale": "01", "registro": "9", "data_reg": "2026-08-18"},
                is_create=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["registro"], "1")
            self.assertEqual(form.initial.get("numero_prot"), 12)
            self.assertTrue(form.fields["numero_prot"].widget.attrs.get("readonly"))

    def test_form_generico_clears_registro_and_protocollo(self):
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = ""
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—"), ("01", "01 — Fattura")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—"), ("Euro", "Euro")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=12),
        ):
            form = PrimanotaForm(
                data={
                    "tipo": "1",
                    "causale": "01",
                    "registro": "1",
                    "numero_prot": "12",
                    "alfa_prot": "A",
                    "codice_partita": "C7310",
                    "fornitore_cee": "F1871",
                    "codice_paga": "31",
                    "valuta": "Euro",
                    "acconto": "10",
                    "data_reg": "2026-08-18",
                },
                is_create=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertIsNone(form.cleaned_data["registro"])
            self.assertIsNone(form.cleaned_data["numero_prot"])
            self.assertIsNone(form.cleaned_data["alfa_prot"])
            self.assertIsNone(form.cleaned_data["codice_partita"])
            self.assertIsNone(form.cleaned_data["fornitore_cee"])
            self.assertIsNone(form.cleaned_data["codice_paga"])
            self.assertIsNone(form.cleaned_data["valuta"])
            self.assertIsNone(form.cleaned_data["acconto"])
            self.assertFalse(form.cleaned_data["scadenze_ins"])
            self.assertFalse(form.fields["numero_prot"].widget.attrs.get("readonly"))

    def test_form_generico_edit_clears_existing_registro(self):
        row = Primanota(id=1, tipo=1, registro="1", numero_prot=5, alfa_prot="A", codice_partita="C7310", codice_paga="31", valuta="Euro", acconto=10)
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = ""
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—"), ("01", "01 — Fattura")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            form = PrimanotaForm(
                data={"tipo": "1", "causale": "01", "data_reg": "2026-08-18"},
                instance=row,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertIsNone(form.cleaned_data["registro"])
            self.assertIsNone(form.cleaned_data["numero_prot"])
            self.assertIsNone(form.cleaned_data["alfa_prot"])
            self.assertIsNone(form.cleaned_data["codice_partita"])
            self.assertIsNone(form.cleaned_data["codice_paga"])
            self.assertIsNone(form.cleaned_data["valuta"])
            self.assertIsNone(form.cleaned_data["acconto"])

    def test_form_corrispettivi_keeps_registro_from_causale(self):
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = "1"
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—"), ("01", "01 — Fattura")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.causale_is_registro_corrispettivi", return_value=True),
            patch("apps.primanota.forms.peek_next_protocollo", return_value=7),
        ):
            form = PrimanotaForm(
                data={"tipo": "3", "causale": "01", "data_reg": "2026-08-18"},
                is_create=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["registro"], "1")
            self.assertEqual(form.initial.get("numero_prot"), 7)

    def test_corrispettivi_extra_from_causale_maps_incasso_and_cassa(self):
        from apps.primanota.lookups import corrispettivi_extra_from_causale

        causale = MagicMock()
        causale.causale_colleg_auto_f = "23"
        causale.c_dare_1 = "C4425"
        causale.cassa_corrispettivi = "1.10.1"
        incasso = MagicMock()
        incasso.label = "Incasso Corrispettivi"
        with (
            patch(
                "apps.primanota.lookups.resolve_causale_contabile",
                return_value=incasso,
            ),
            patch("apps.articoli.lookups.resolve_descrizione", return_value="ASSEGNI E/O CONTANTI"),
        ):
            extra = corrispettivi_extra_from_causale(causale)
        self.assertEqual(extra["incasso_code"], "23")
        self.assertEqual(extra["incasso_label"], "Incasso Corrispettivi")
        self.assertEqual(extra["cassa_code"], "1.10.1")
        self.assertEqual(extra["cassa_label"], "ASSEGNI E/O CONTANTI")

        conto = MagicMock()
        conto.causale_colleg_auto_f = ""
        conto.c_dare_1 = "C4425"
        conto.cassa_corrispettivi = ""
        self.assertEqual(corrispettivi_extra_from_causale(conto)["incasso_code"], "")
        self.assertEqual(corrispettivi_extra_from_causale(None)["cassa_code"], "")

    def test_form_template_corrispettivi_layout(self):
        from pathlib import Path

        form_html = Path("apps/primanota/templates/primanota/primanota_form.html").read_text(
            encoding="utf-8"
        )
        row_html = Path(
            "apps/primanota/templates/primanota/partials/riga_form_row.html"
        ).read_text(encoding="utf-8")
        detail_html = Path(
            "apps/primanota/templates/primanota/primanota_detail.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-corr-kpis", form_html)
        self.assertIn("data-corr-extra", form_html)
        self.assertIn("data-doc-block", form_html)
        self.assertIn("field=form.causale_incasso", form_html)
        self.assertIn('tipo="causale_contabile"', form_html)
        self.assertIn("fillCorrIncasso", form_html)
        self.assertIn("data-corr-cassa-code", form_html)
        self.assertNotIn("Descrizione contropartita", form_html)
        self.assertNotIn("data-corr-col", form_html)
        self.assertIn("data-iva-importo-col", form_html)
        self.assertIn("data-iva-doc-totale", form_html)
        self.assertIn("data-anno-col", form_html)
        self.assertIn("const corr = tipo && tipo.value === \"3\"", form_html)
        self.assertNotIn("data-corr-col", row_html)
        self.assertIn("Causale di incasso dei corrispettivi di vendita", detail_html)
        self.assertIn(
            "Causale di incasso dei corrispettivi di vendita",
            Path("apps/primanota/forms.py").read_text(encoding="utf-8"),
        )
        self.assertNotIn("Descrizione contropartita", detail_html)
        self.assertIn("{% if is_iva_layout %}", detail_html)

    def test_save_generico_skips_protocol_allocation(self):
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = ""
        formset_data = {
            "righe-TOTAL_FORMS": "3",
            "righe-INITIAL_FORMS": "0",
            "righe-MIN_NUM_FORMS": "0",
            "righe-MAX_NUM_FORMS": "1000",
        }
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—"), ("01", "01 — Fattura")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
            patch("apps.primanota.forms.next_primanota_id", return_value=100),
            patch("apps.primanota.forms.next_dettaglio_id", return_value=1000),
            patch("apps.primanota.forms.allocate_next_numero_reg", return_value=42),
            patch("apps.primanota.forms.allocate_next_protocollo") as mock_allocate,
            patch("apps.primanota.forms.stamp_modifica"),
            patch("apps.primanota.forms.maybe_apply_scadenze"),
            patch("apps.primanota.forms.transaction.atomic") as mock_atomic,
            patch.object(Primanota, "save", return_value=None),
        ):
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            data = {"tipo": "1", "causale": "01", "data_reg": "2026-08-18", **formset_data}
            form = PrimanotaForm(data=data, is_create=True)
            formset = riga_formset_for(data)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertTrue(formset.is_valid(), formset.errors)
            obj = save_primanota_with_righe(form, formset)
        mock_allocate.assert_not_called()
        self.assertIsNone(obj.registro)
        self.assertIsNone(obj.numero_prot)
        self.assertIsNone(obj.alfa_prot)

    def test_form_create_copies_data_valuta_from_data_reg_when_empty(self):
        from datetime import date

        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = "1"
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("01", "01 — Fattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            form = PrimanotaForm(
                data={"tipo": "2", "causale": "01", "data_reg": "2026-08-18"},
                is_create=True,
            )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["data_valuta"].date(), date(2026, 8, 18))

    def test_form_edit_keeps_posted_data_valuta(self):
        from datetime import date, datetime

        row = Primanota(
            id=1,
            data_reg=datetime(2026, 8, 18),
            data_valuta=datetime(2026, 1, 5),
        )
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = "1"
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("01", "01 — Fattura")],
            ),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            form = PrimanotaForm(
                data={
                    "tipo": "2",
                    "causale": "01",
                    "data_reg": "2026-08-18",
                    "data_valuta": "2026-01-05",
                },
                instance=row,
            )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["data_valuta"].date(), date(2026, 1, 5))
        self.assertFalse(form.fields["numero_prot"].widget.attrs.get("readonly"))

    def test_numero_reg_preview_has_no_help_text(self):
        from apps.primanota.views import _apply_numero_reg_preview

        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
        ):
            form = PrimanotaForm(is_create=True)
            _apply_numero_reg_preview(form, is_create=True)
        self.assertTrue(form.fields["numero_reg"].widget.attrs.get("readonly"))
        self.assertEqual(form.fields["numero_reg"].help_text, "")
        self.assertEqual(form.fields["registro"].help_text, "")
        self.assertEqual(form.fields["numero_prot"].help_text, "")
        self.assertEqual(form.fields["data_valuta"].help_text, "")

    def test_tipo_field_only_has_four_selectable_options(self):
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=None),
        ):
            form = PrimanotaForm(is_create=True)
            empty = PrimanotaForm(data={"causale": "01"})
        values = [choice[0] for choice in form.fields["tipo"].choices]
        self.assertEqual(values, [1, 2, 3, 4])
        html = str(form["tipo"])
        self.assertNotIn("---------", html)
        self.assertIn("Generico", html)
        self.assertIn("IVA", html)
        self.assertIn("Corrispettivi", html)
        self.assertIn("Iva con Autofattura", html)
        self.assertFalse(empty.is_valid())
        self.assertIn("tipo", empty.errors)
        self.assertFalse(form.fields["tipo"].disabled)

    def test_tipo_locked_when_editing(self):
        row = Primanota(id=1, tipo=2, causale="01")
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = "1"
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—"), ("01", "01 — Fattura")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—"), ("1", "1 — Vendite")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            shown = PrimanotaForm(instance=row)
            posted = PrimanotaForm(
                data={"tipo": "1", "causale": "01", "data_reg": "2026-08-18"},
                instance=row,
            )
            self.assertTrue(shown.fields["tipo"].disabled)
            self.assertIn("disabled", str(shown["tipo"]))
            self.assertTrue(posted.fields["tipo"].disabled)
            self.assertTrue(posted.is_valid(), posted.errors)
            self.assertEqual(posted.cleaned_data["tipo"], 2)

    def test_resolve_causale_ok_if_table_missing(self):
        qs = MagicMock()
        qs.annotate.side_effect = ProgrammingError("missing")
        with (
            patch("apps.primanota.lookups.CausaleContabile") as mock_model,
            patch("apps.primanota.lookups.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            self.assertIsNone(resolve_causale_contabile("FT"))

    def test_resolve_partita_cliente(self):
        cliente = MagicMock()
        cliente.codice = "C7310"
        cliente.ragione_sociale = "VIVAI DE LAURENTIIS"
        with patch("apps.anagrafiche.models.get_by_codice", return_value=cliente):
            info = resolve_partita_clifor("C7310")
        self.assertEqual(info["tipo"], "Cliente")
        self.assertEqual(info["label"], "VIVAI DE LAURENTIIS")
        self.assertEqual(info["url"], reverse("anagrafiche:cliente_detail", kwargs={"codice": "C7310"}))

    def test_resolve_partita_fornitore(self):
        fornitore = MagicMock()
        fornitore.codice = "F2082"
        fornitore.ragione_sociale = "ACME SRL"
        with patch("apps.anagrafiche.models.get_by_codice", return_value=fornitore):
            info = resolve_partita_clifor("F2082")
        self.assertEqual(info["tipo"], "Fornitore")
        self.assertEqual(info["label"], "ACME SRL")
        self.assertEqual(
            info["url"],
            reverse("anagrafiche:fornitore_detail", kwargs={"codice": "F2082"}),
        )

    def test_resolve_partita_empty(self):
        info = resolve_partita_clifor("")
        self.assertEqual(info["tipo"], "Cliente / Fornitore")
        self.assertEqual(info["label"], "")
        self.assertEqual(info["url"], "")

    def test_urls_resolve(self):
        self.assertEqual(reverse("primanota:list"), "/primanota/")
        self.assertEqual(reverse("primanota:create"), "/primanota/nuova/")
        self.assertEqual(
            reverse("primanota:prossimo_numero"),
            "/primanota/prossimo-numero/",
        )
        self.assertEqual(reverse("primanota:da_causale"), "/primanota/da-causale/")
        self.assertEqual(
            reverse("primanota:create") + "?causale=01",
            "/primanota/nuova/?causale=01",
        )
        self.assertEqual(reverse("primanota:detail", kwargs={"pk": 12}), "/primanota/12/")
        self.assertEqual(reverse("primanota:edit", kwargs={"pk": 12}), "/primanota/12/modifica/")
        self.assertEqual(reverse("primanota:delete", kwargs={"pk": 12}), "/primanota/12/elimina/")
        self.assertEqual(reverse("primanota:sync"), "/parametri/4d/sync-primanota/")
        self.assertEqual(
            reverse("primanota:riga_create", kwargs={"pk": 12}),
            "/primanota/12/righe/nuova/",
        )
        self.assertEqual(
            reverse("primanota:riga_edit", kwargs={"pk": 12, "riga_pk": 99}),
            "/primanota/12/righe/99/modifica/",
        )
        self.assertEqual(
            reverse("primanota:riga_delete", kwargs={"pk": 12, "riga_pk": 99}),
            "/primanota/12/righe/99/elimina/",
        )

    def test_list_shows_totale_documento_for_iva(self):
        from pathlib import Path

        from apps.primanota.views import PrimanotaListView

        html = Path("apps/primanota/templates/primanota/primanota_list.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("totale_documento_list", html)
        self.assertIn("r.totale_documento_list != None", html)
        self.assertNotIn("totale_doc_controllo", html)
        self.assertIn("totale_documento_list", PrimanotaListView.sortable_fields)

    def test_sync_4d_step_registered(self):
        from apps.core.views import MIRROR_4D_TABLES, SYNC_4D_STEPS

        step = next(s for s in SYNC_4D_STEPS if s["key"] == "primanota")
        self.assertEqual(step["label"], "Primanota")
        self.assertEqual(step["description"], "Primanota e Primanota_Dettaglio")
        self.assertEqual(step["tables"], ("primanota", "primanota_dettaglio"))
        self.assertIn("primanota", MIRROR_4D_TABLES)
        self.assertIn("primanota_dettaglio", MIRROR_4D_TABLES)

    def test_load_righe_ok_if_dettaglio_table_missing(self):
        ordered = MagicMock()
        ordered.__iter__.side_effect = ProgrammingError("missing")
        qs = MagicMock()
        qs.filter.return_value.exclude.return_value.order_by.return_value = ordered
        with (
            patch("apps.primanota.views.PrimanotaDettaglio") as mock_model,
            patch("apps.primanota.views.transaction.atomic") as mock_atomic,
        ):
            mock_model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            righe, missing = load_primanota_righe(147140)
        self.assertEqual(righe, [])
        self.assertTrue(missing)

    def test_form_scadenze_locked_when_flag_off(self):
        row = Primanota(id=1, scadenze_ins=False)
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
        ):
            form = PrimanotaForm(instance=row)
        self.assertFalse(form.scadenze_editable())
        self.assertTrue(form.fields["scad1"].disabled)

    def test_form_scadenze_editable_when_flag_on(self):
        row = Primanota(id=1, scadenze_ins=True)
        with (
            patch("apps.primanota.forms.causali_contabili_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.registro_iva_choices", return_value=[("", "—")]),
            patch("apps.primanota.forms.valuta_choices", return_value=[("", "—")]),
        ):
            form = PrimanotaForm(instance=row)
        self.assertTrue(form.scadenze_editable())
        self.assertFalse(form.fields["scad1"].disabled)

    def test_calc_importo_iva_from_aliquota(self):
        from apps.documenti.castelletto import AliquotaInfo
        from apps.primanota.iva import calc_importo_iva

        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(codice="22", percentuale=22, descrizione="IVA 22%"),
        ):
            self.assertEqual(calc_importo_iva(100, "22"), 22.0)
            self.assertEqual(calc_importo_iva(5475.6, "22"), 1204.63)

    def test_riga_form_uppercases_clifor_dare_avere(self):
        form = PrimanotaRigaForm(
            data={
                "conto_dare": "c7310",
                "dare": "10.00",
                "conto_avere": "f2082",
                "avere": "10.00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["conto_dare"], "C7310")
        self.assertEqual(form.cleaned_data["conto_avere"], "F2082")

    def test_riga_form_uppercases_clifor_conto_partita(self):
        form = PrimanotaRigaForm(
            data={
                "conto_partita": "c3567",
                "imponibile": "34.90",
            },
            is_iva=True,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["conto_partita"], "C3567")
        self.assertEqual(form.cleaned_data["conto_avere"], "C3567")

    def test_riga_form_leaves_pdc_codes_unchanged(self):
        form = PrimanotaRigaForm(
            data={
                "conto_dare": "1.10.1",
                "dare": "10.00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["conto_dare"], "1.10.1")

    def test_parse_importo_italian_thousands(self):
        from apps.primanota.forms import format_importo, parse_importo, ImportoNumberInput

        self.assertEqual(parse_importo("20.696,90"), 20696.9)
        self.assertEqual(parse_importo("20696,90"), 20696.9)
        self.assertEqual(parse_importo("20696.90"), 20696.9)
        self.assertEqual(parse_importo("20.696"), 20696.0)
        self.assertEqual(parse_importo(20696.9), 20696.9)
        self.assertEqual(format_importo(20696.9), "20.696,90")
        self.assertEqual(format_importo(7259.2), "7.259,20")
        self.assertEqual(format_importo(0), "0,00")
        widget = ImportoNumberInput()
        self.assertEqual(widget.format_value(20696.9), "20.696,90")
        self.assertEqual(widget.format_value(7259.2), "7.259,20")
        self.assertEqual(widget.format_value(None), "0,00")

    def test_riga_form_accepts_italian_thousands(self):
        form = PrimanotaRigaForm(
            data={
                "conto_dare": "1.11.1",
                "dare": "20.696,90",
                "conto_avere": "",
                "avere": "0,00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["dare"], 20696.9)
        self.assertEqual(form.cleaned_data["avere"], 0.0)

    def test_riga_form_imponibile_iva_accepts_italian_thousands(self):
        from apps.documenti.castelletto import AliquotaInfo

        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(codice="22", percentuale=22, descrizione="IVA 22%"),
        ):
            form = PrimanotaRigaForm(
                data={
                    "conto_partita": "3.71.1",
                    "imponibile": "5.475,60",
                    "importo_iva": "1.204,63",
                    "codice_iva": "22",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["imponibile"], 5475.6)
            self.assertEqual(form.cleaned_data["importo_iva"], 1204.63)

    def test_riga_form_maps_iva_partita_to_avere(self):
        from apps.documenti.castelletto import AliquotaInfo

        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(codice="22", percentuale=22, descrizione="IVA 22%"),
        ):
            form = PrimanotaRigaForm(
                data={
                    "conto_partita": "3.71.1",
                    "imponibile": "10.50",
                    "codice_iva": "22",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["conto_avere"], "3.71.1")
            self.assertEqual(form.cleaned_data["avere"], 10.5)
            self.assertEqual(form.cleaned_data["importo_iva"], 2.31)
            self.assertEqual(form.cleaned_data["imp_val"], 10.5)

    def test_riga_form_copies_imp_val_to_imponibile_when_empty(self):
        from apps.documenti.castelletto import AliquotaInfo

        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(codice="22", percentuale=22, descrizione="IVA 22%"),
        ):
            form = PrimanotaRigaForm(
                data={
                    "conto_partita": "3.71.1",
                    "imp_val": "110,00",
                    "imponibile": "0,00",
                    "codice_iva": "22",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["imp_val"], 110.0)
            self.assertEqual(form.cleaned_data["imponibile"], 110.0)
            self.assertEqual(form.cleaned_data["avere"], 110.0)
        self.assertEqual(
            Primanota(id=9).get_absolute_url(),
            reverse("primanota:detail", kwargs={"pk": 9}),
        )

    def test_riga_form_computes_iva_from_imponibile_without_is_iva_flag(self):
        """Formset create historically omitted is_iva; imponibile must still drive IVA."""
        from apps.documenti.castelletto import AliquotaInfo

        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(codice="22", percentuale=22, descrizione="IVA 22%"),
        ):
            form = PrimanotaRigaForm(
                data={
                    "imponibile": "10.50",
                    "codice_iva": "22",
                    "importo_iva": "",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["importo_iva"], 2.31)

    def test_riga_form_computes_iva_on_iva_layout(self):
        from apps.documenti.castelletto import AliquotaInfo

        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(codice="22", percentuale=22, descrizione="IVA 22%"),
        ):
            form = PrimanotaRigaForm(
                data={
                    "conto_partita": "3.71.1",
                    "imponibile": "5475.6",
                    "codice_iva": "22",
                },
                is_iva=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["importo_iva"], 1204.63)

    def test_riga_formset_prefix_computes_importo_iva(self):
        from apps.documenti.castelletto import AliquotaInfo

        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(codice="22", percentuale=22, descrizione="IVA 22%"),
        ):
            form = PrimanotaRigaForm(
                data={
                    "righe-0-conto_partita": "3.71.1",
                    "righe-0-imponibile": "100",
                    "righe-0-codice_iva": "22",
                },
                prefix="righe-0",
                is_iva=True,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["importo_iva"], 22.0)

    def _riga_formset_data(self, rows, **extra):
        data = {
            "righe-TOTAL_FORMS": str(len(rows)),
            "righe-INITIAL_FORMS": "0",
            "righe-MIN_NUM_FORMS": "0",
            "righe-MAX_NUM_FORMS": "1000",
        }
        for i, row in enumerate(rows):
            for key, value in row.items():
                data[f"righe-{i}-{key}"] = value
        data.update(extra)
        return data

    def test_formset_generico_rejects_sbilancio(self):
        formset = riga_formset_for(
            self._riga_formset_data(
                [
                    {"conto_dare": "1.10.1", "dare": "100", "conto_avere": "", "avere": ""},
                    {"conto_dare": "", "dare": "", "conto_avere": "2.10.1", "avere": "40"},
                ]
            ),
            is_iva=False,
        )
        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())
        self.assertIn("sbilanciata", str(formset.non_form_errors()))

    def test_formset_generico_accepts_balanced_righe(self):
        formset = riga_formset_for(
            self._riga_formset_data(
                [
                    {"conto_dare": "1.10.1", "dare": "100", "conto_avere": "", "avere": ""},
                    {"conto_dare": "", "dare": "", "conto_avere": "2.10.1", "avere": "100"},
                ]
            ),
            is_iva=False,
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        self.assertFalse(formset.non_form_errors())

    def test_formset_iva_does_not_require_dare_avere_balance(self):
        formset = riga_formset_for(
            self._riga_formset_data(
                [
                    {
                        "conto_partita": "3.71.1",
                        "imponibile": "100",
                        "codice_iva": "22",
                    }
                ]
            ),
            is_iva=True,
        )
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_primanota_iva_js_writes_dot_decimal_for_number_input(self):
        from pathlib import Path

        js = Path("static/eureka/js/primanota-righe.js").read_text(encoding="utf-8")
        self.assertIn("formatEuro(iva)", js)
        self.assertNotIn('replace(".", ",")', js)
        disable = Path("static/eureka/js/disable-autocomplete.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("#primanotaForm", disable)
        self.assertIn("data-primanota-riga-form", disable)
        self.assertIn("updateRigheCount", js)
        self.assertIn("countVisibleRows", js)
        self.assertIn("data-righe-count", js)
        self.assertIn("data-totale-documento", js)
        self.assertIn("data-sbilancio", js)
        self.assertIn("isCorrispettiviMode", js)
        self.assertIn("isIvaLayoutMode", js)
        self.assertIn("getTotals", js)
        self.assertIn("sbilancio: round2(totDare - totAvere)", js)
        self.assertIn("data-add-riga", js)
        self.assertIn("TOTAL_FORMS", js)
        self.assertIn("EurekaLinkedLookups", js)
        self.assertIn("data-sbilancio-banner", js)
        self.assertIn("needsBalance", js)
        self.assertIn("syncBalanceGate", js)
        self.assertIn("[data-save-primanota]", js)
        self.assertIn("data-confirm-elimina", js)
        self.assertIn("confermaEliminaRigaModal", js)
        self.assertIn("is-open", js)
        self.assertNotIn("window.confirm", js)
        self.assertIn("formatImportoInput", js)
        self.assertIn('["dare", "avere", "imp_val", "imponibile", "importo_iva"]', js)
        self.assertIn("syncFromCambio", js)
        self.assertIn("headerCambio", js)
        self.assertIn("EurekaPrimanotaCambio", js)
        self.assertIn(r"\B(?=(\d{3})+(?!\d))", js)
        self.assertNotIn('toLocaleString("it-IT"', js)
        scad = Path("static/eureka/js/primanota-scadenze.js").read_text(encoding="utf-8")
        self.assertIn("max_n=10", scad)
        self.assertIn("id_codice_paga", scad)
        self.assertIn("id_scadenze_ins", scad)
        self.assertIn("isGenerico", scad)

    def test_form_template_shows_iva_totals_and_pagamento_lookup(self):
        from pathlib import Path

        html = Path("apps/primanota/templates/primanota/primanota_form.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("Totale imponibile", html)
        self.assertIn("Totale IVA", html)
        self.assertIn("Totale documento", html)
        self.assertIn("data-totale-imponibile", html)
        self.assertIn("data-iva-kpis", html)
        self.assertIn("data-corr-kpis", html)
        self.assertIn("data-gen-kpis", html)
        self.assertIn("data-sbilancio", html)
        self.assertIn("Sbilancio", html)
        self.assertIn("data-sbilancio-banner", html)
        self.assertIn("mask_linked_code.html", html)
        self.assertIn('tipo="condizione"', html)
        self.assertIn("field=form.codice_paga", html)
        self.assertIn("data-calc-scadenze-url", html)
        self.assertIn("primanota-scadenze.js", html)
        self.assertIn("eureka-mask-card--primanota-scadenze", html)
        self.assertNotIn(
            'eureka-mask-card--primanota-scadenze mb-3" data-iva-block', html
        )
        self.assertIn("data-scadenze-block", html)
        self.assertIn('tipo="clifor"', html)
        self.assertIn("field=form.codice_partita", html)
        self.assertIn("field=form.valuta", html)
        self.assertIn("field=form.data_cambio", html)
        self.assertIn("field=form.cambio", html)
        self.assertIn("{% if is_generico %} d-none{% endif %}\" data-valuta-col", html)
        self.assertIn("data-cambio-col", html)
        self.assertIn("{% if is_generico or not show_cambio %} d-none{% endif %}\" data-cambio-col", html)
        self.assertIn("field=form.alfa_prot", html)
        self.assertIn("d-none\" data-serie-prot-col", html)
        self.assertNotIn("mask_field.html\" with field=form.codice_partita", html)
        self.assertIn("data-add-riga", html)
        self.assertIn("rigaEmptyFormTemplate", html)
        self.assertIn('id="righeBody"', html)
        self.assertIn("formset.empty_form", html)
        self.assertIn("data-righe-count", html)
        self.assertIn("data-save-primanota", html)
        self.assertIn("data-eureka-mask-collapse", html)
        self.assertIn("data-mask-toggle", html)
        self.assertIn('data-mask-section="documento"', html)
        self.assertIn('data-mask-empty="collapsed"', html)
        self.assertIn("data-mask-empty-from", html)
        self.assertIn('data-summary-kind="linked-label"', html)
        self.assertIn('data-summary-kind="select-extra"', html)
        self.assertIn("data-summary-from=\"id_codice_partita\"", html)
        self.assertIn('data-mask-section="dettaglio"', html)
        self.assertIn('data-mask-section="scadenze"', html)
        self.assertIn("confermaEliminaRigaModal", html)
        self.assertIn("eureka-confirm", html)
        self.assertIn("data-elimina-riga-ok", html)

    def test_templates_hide_iva_when_tipo_generico(self):
        from pathlib import Path

        form_html = Path("apps/primanota/templates/primanota/primanota_form.html").read_text(
            encoding="utf-8"
        )
        row_html = Path(
            "apps/primanota/templates/primanota/partials/riga_form_row.html"
        ).read_text(encoding="utf-8")
        self.assertIn('data-iva-col{% if not is_iva_layout %} class="d-none"{% endif %}>C. IVA</th>', form_html)
        self.assertIn("data-iva-importo-col>Importo IVA</th>", form_html)
        self.assertIn("data-iva-importo-col data-totale-iva", form_html)
        self.assertIn("[data-iva-block], [data-iva-kpis], [data-iva-importo-col], [data-iva-doc-totale]", form_html)
        self.assertIn('el.classList.toggle("d-none", !iva)', form_html)
        self.assertIn('data-partita-col', form_html)
        self.assertIn('data-paga-col', form_html)
        self.assertIn("[data-registro-col], [data-partita-col], [data-paga-col], [data-valuta-col]", form_html)
        self.assertIn("{% if is_generico %} d-none{% endif %}\" data-registro-col", form_html)
        self.assertIn("{% if is_generico %} d-none{% endif %}\" data-partita-col", form_html)
        self.assertIn("{% if is_generico or is_iva or is_corrispettivi %} d-none{% endif %}\" data-acconto-col", form_html)
        self.assertIn('el.classList.toggle("d-none", generico || iva || corr)', form_html)
        self.assertIn("resetExclusive", form_html)
        self.assertIn("clearGenericoExclusiveFields", form_html)
        self.assertIn("if (current && !keep)", form_html)
        self.assertIn("data-scadenze-block", form_html)
        self.assertIn('id_codice_partita', form_html)
        self.assertIn('id_codice_paga', form_html)
        self.assertIn('id_valuta', form_html)
        self.assertIn("EUREKA_CAUSALI", form_html)
        self.assertIn("EUREKA_VALUTE_CAMBI", form_html)
        self.assertIn("fillCambioFromValuta", form_html)
        self.assertIn("pickCambioFromCatalog", form_html)
        self.assertIn("syncCambioCols", form_html)
        self.assertIn("valutaAbbrevIsEur", form_html)
        self.assertIn("fillCambioFromValuta();", form_html)
        self.assertIn('field=f.conto_partita label=labels.conto_partita tipo="pdc_clifor"', row_html)
        self.assertIn("field=f.conto_dare", row_html)
        self.assertNotIn("f.initial.pos", row_html)
        self.assertIn("btn-elimina-riga", row_html)
        self.assertIn("data-confirm-elimina", row_html)
        self.assertNotIn("primanota:riga_delete", row_html)
        self.assertNotIn('<form method="post"', row_html)
        self.assertIn("has_registro", form_html)
        self.assertIn("tipo_registro", form_html)
        self.assertIn("fillCausaleOptions(generico, iva && !autoF, corr, autoF)", form_html)
        self.assertIn("is_autofattura", form_html)
        self.assertIn("is_autofattura_automatica", form_html)
        self.assertIn("show_fornitore_cee", form_html)
        self.assertIn("syncFornitoreCee", form_html)
        self.assertIn("Boolean(autoF) && causaleIsAutofatturaAutomatica()", form_html)
        self.assertIn("data-autofattura-col", form_html)
        self.assertIn('tipo="fornitore"', form_html)
        self.assertIn("field=form.fornitore_cee", form_html)
        self.assertIn("[data-autofattura-col]", form_html)
        self.assertIn("isCorrReg", form_html)
        self.assertIn("data-sbilancio", form_html)
        self.assertIn("Sbilancio", form_html)
        self.assertIn('data-gen-importo="dare"', form_html)
        self.assertIn('data-gen-importo="avere"', form_html)
        self.assertIn('data-iva-importo="imponibile"', row_html)
        self.assertIn('data-iva-importo="imp_val"', row_html)
        self.assertIn("data-imp-val-col", row_html)
        self.assertIn("{{ f.imp_val }}", row_html)
        self.assertIn("Imponibile Valuta", form_html)
        self.assertIn("data-totale-impon-valuta", form_html)
        self.assertIn("data-imp-val-col", form_html)
        self.assertIn("[data-imp-val-col]", form_html)
        self.assertIn("EurekaPrimanotaCambio", form_html)
        self.assertIn('data-iva-importo="iva"', row_html)
        self.assertIn('data-gen-sezione="dare"', form_html)
        self.assertIn('data-gen-sezione="avere"', form_html)
        self.assertNotIn("align-middle", row_html)
        css_html = Path("static/eureka/css/table-mask.css").read_text(encoding="utf-8")
        self.assertIn(".eureka-primanota-righe-table.table-vcenter tbody td", css_html)
        self.assertIn("vertical-align: top", css_html)
        self.assertIn("[data-iva-importo] .form-control", css_html)

        riga_html = Path("apps/primanota/templates/primanota/riga_form.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('class="d-none" aria-hidden="true">{{ form.codice_iva }}', riga_html)
        self.assertIn('field=form.conto_partita label=labels.conto_partita tipo="pdc_clifor"', riga_html)
        self.assertIn("field=form.imp_val", riga_html)
        self.assertIn("{% if show_cambio %}", riga_html)
        self.assertIn('field=form.importo_iva col="col-sm-2"', riga_html)

        detail_html = Path(
            "apps/primanota/templates/primanota/primanota_detail.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("<th>IVA</th>", detail_html)
        self.assertIn("<th>C. IVA</th>", detail_html)
        self.assertIn("Imponibile Valuta", detail_html)
        self.assertIn("riga.imponibile_valuta", detail_html)
        self.assertIn("{% if show_cambio %}<th class=\"text-end\">Imponibile Valuta</th>{% endif %}", detail_html)
        self.assertIn("eureka-mask--primanota", detail_html)
        self.assertIn("{% if is_iva or is_generico or is_corrispettivi %}", detail_html)
        self.assertIn("eureka-mask-card--primanota-movimenti", detail_html)
        self.assertIn("data-eureka-mask-collapse", detail_html)
        self.assertIn('data-mask-section="dettaglio"', detail_html)
        self.assertIn('data-mask-section="registrazione"', detail_html)
        self.assertIn("{% if is_iva %}", detail_html)
        self.assertIn("Protocollo numero", detail_html)
        self.assertIn("eureka-mask-grid--compact", detail_html)
        js_src = Path("static/eureka/js/mask-collapse.js").read_text(encoding="utf-8")
        self.assertIn("data-mask-empty", js_src)
        self.assertIn("isCardEmpty", js_src)
        self.assertIn("clifor.label", detail_html)
        self.assertIn("{% if show_fornitore_cee %}", detail_html)
        self.assertIn("registrazione.fornitore_cee", detail_html)
        self.assertIn("fornitore.label", detail_html)
        self.assertIn("registrazione.valuta", detail_html)
        self.assertIn("cambio_info.data", detail_html)
        self.assertIn("cambio_info.cambio", detail_html)
        self.assertIn("{% if show_cambio %}", detail_html)
        self.assertIn("Data cambio", detail_html)
        self.assertIn("causale_contabile.label", detail_html)
        self.assertIn("eureka-mask-collapse__chip--name", detail_html)
        self.assertIn("{% if not is_generico %}", detail_html)
        self.assertIn("Sbilancio", detail_html)
        self.assertNotIn("Aggiungi riga", detail_html)
        self.assertNotIn("Acconto", detail_html)
        scad_html = Path(
            "apps/primanota/templates/primanota/partials/scadenze_iva.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Acconto", scad_html)

    def test_empty_form_row_renders_without_pos_in_initial(self):
        from django.template.loader import render_to_string

        formset = riga_formset_for()
        self.assertEqual(formset.empty_form.initial, {})
        html = render_to_string(
            "primanota/partials/riga_form_row.html",
            {
                "f": formset.empty_form,
                "is_empty_tpl": True,
                "is_create": True,
            },
        )
        self.assertIn("data-riga-row", html)
        self.assertIn("data-riga-pos", html)

    def test_formset_totals_sum_imponibile_iva_as_documento(self):
        from apps.primanota.views import _formset_totals

        class Bound:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class FakeForm:
            def __init__(self, amounts):
                self._amounts = amounts
                self.initial = {}
                self.instance = MagicMock(pk=None)

            def __getitem__(self, name):
                if name == "DELETE":
                    raise KeyError(name)
                return Bound(self._amounts.get(name))

        formset = MagicMock()
        formset.forms = [
            FakeForm(
                {"imponibile": "100", "importo_iva": "22", "dare": "", "avere": ""}
            ),
            FakeForm(
                {
                    "imponibile": "50,50",
                    "importo_iva": "11,11",
                    "dare": "",
                    "avere": "",
                }
            ),
        ]
        totals = _formset_totals(formset)
        self.assertAlmostEqual(totals["totale_imponibile"], 150.5)
        self.assertAlmostEqual(totals["totale_imponibile_valuta"], 150.5)
        self.assertAlmostEqual(totals["totale_iva"], 33.11)
        self.assertAlmostEqual(totals["totale_documento"], 183.61)
        self.assertAlmostEqual(totals["sbilancio"], 0)

    def test_formset_totals_sbilancio_dare_minus_avere(self):
        from apps.primanota.views import _formset_totals

        class Bound:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class FakeForm:
            def __init__(self, amounts):
                self._amounts = amounts
                self.initial = {}
                self.instance = MagicMock(pk=None)

            def __getitem__(self, name):
                if name == "DELETE":
                    raise KeyError(name)
                return Bound(self._amounts.get(name))

        formset = MagicMock()
        formset.forms = [
            FakeForm({"imponibile": "", "importo_iva": "", "dare": "200", "avere": "50"}),
            FakeForm({"imponibile": "", "importo_iva": "", "dare": "10", "avere": "30"}),
        ]
        totals = _formset_totals(formset)
        self.assertAlmostEqual(totals["totale_dare"], 210)
        self.assertAlmostEqual(totals["totale_avere"], 80)
        self.assertAlmostEqual(totals["sbilancio"], 130)

    def test_form_context_iva_tipo_4_totals_and_pagamento_label(self):
        from apps.primanota.views import _primanota_form_context

        form = MagicMock()
        form.is_bound = False
        form.initial = {"tipo": 4}
        form.data = {}
        form.instance = MagicMock(pk=1, codice_paga="31", codice_partita="")
        form.scadenza_slots.return_value = []
        form.scadenze_editable.return_value = False
        formset = MagicMock()
        formset.forms = []
        reg = Primanota(id=1, tipo=4, causale="FT", registro="1", codice_paga="31")
        riga = MagicMock()
        riga.imponibile = 100.0
        riga.imponibile_valuta = 100.0
        riga.importo_iva = 22.0
        riga.dare = 0
        riga.avere = 100.0
        with (
            patch("apps.primanota.views._righe_queryset", return_value=[riga]),
            patch("apps.primanota.views.resolve_causale_contabile", return_value=None),
            patch("apps.primanota.views.resolve_registro_iva", return_value=None),
            patch("apps.primanota.views._lookup_context", return_value={}),
            patch(
                "apps.primanota.views.resolve_descrizione",
                return_value="30 GG DFFM",
            ),
        ):
            ctx = _primanota_form_context(
                form, formset, is_create=False, registrazione=reg
            )
        self.assertTrue(ctx["is_iva_autofattura"])
        self.assertFalse(ctx["show_fornitore_cee"])
        self.assertEqual(ctx["fornitore_label"], "")
        self.assertEqual(ctx["fornitore_url"], "")
        self.assertEqual(ctx["totale_imponibile"], 100.0)
        self.assertEqual(ctx["totale_iva"], 22.0)
        self.assertEqual(ctx["totale_documento"], 122.0)
        self.assertEqual(ctx["pagamento_label"], "30 GG DFFM")
        self.assertEqual(ctx["partita_label"], "")
        self.assertEqual(ctx["partita_url"], "")
        self.assertEqual(ctx["righe_count"], 1)

    def test_form_context_show_cambio_depends_on_valuta_abbrev(self):
        from apps.primanota.views import _primanota_form_context

        form = MagicMock()
        form.is_bound = False
        form.initial = {"tipo": 4}
        form.data = {}
        form.instance = MagicMock(pk=1, valuta="USD")
        form.scadenza_slots.return_value = []
        form.scadenze_editable.return_value = False
        formset = MagicMock()
        formset.forms = []
        with (
            patch("apps.primanota.views._lookup_context", return_value={}),
            patch("apps.primanota.views.is_cambio_visible", return_value=True) as mock_vis,
        ):
            ctx = _primanota_form_context(form, formset, is_create=False)
        mock_vis.assert_called()
        self.assertTrue(ctx["show_cambio"])

        form.instance.valuta = "Euro"
        with (
            patch("apps.primanota.views._lookup_context", return_value={}),
            patch("apps.primanota.views.is_cambio_visible", return_value=False),
        ):
            ctx = _primanota_form_context(form, formset, is_create=False)
        self.assertFalse(ctx["show_cambio"])

    def test_form_context_shows_fornitore_when_autofattura_automatica(self):
        from apps.primanota.views import _primanota_form_context

        form = MagicMock()
        form.is_bound = False
        form.initial = {"tipo": 4}
        form.data = {}
        form.instance = MagicMock(pk=1, codice_paga="", codice_partita="", causale="XX")
        form.scadenza_slots.return_value = []
        form.scadenze_editable.return_value = False
        formset = MagicMock()
        formset.forms = []
        causale = MagicMock()
        causale.autofattura = True
        with (
            patch("apps.primanota.views._lookup_context", return_value={}),
            patch("apps.primanota.views.resolve_causale_contabile", return_value=causale),
        ):
            ctx = _primanota_form_context(form, formset, is_create=True)
        self.assertTrue(ctx["is_iva_autofattura"])
        self.assertTrue(ctx["show_fornitore_cee"])

    def test_form_context_partita_label_from_clifor(self):
        from apps.primanota.views import _primanota_form_context

        form = MagicMock()
        form.is_bound = False
        form.initial = {"tipo": 4}
        form.data = {}
        form.instance = MagicMock(pk=1, codice_paga="", codice_partita="C7310")
        form.scadenza_slots.return_value = []
        form.scadenze_editable.return_value = False
        formset = MagicMock()
        formset.forms = []
        with (
            patch("apps.primanota.views._lookup_context", return_value={}),
            patch(
                "apps.primanota.views.resolve_partita_clifor",
                return_value={
                    "codice": "C7310",
                    "tipo": "Cliente",
                    "label": "VIVAI DE LAURENTIIS",
                    "url": "/clienti/C7310/",
                },
            ) as mock_partita,
        ):
            ctx = _primanota_form_context(form, formset, is_create=True)
        mock_partita.assert_any_call("C7310")
        self.assertEqual(ctx["partita_label"], "VIVAI DE LAURENTIIS")
        self.assertEqual(ctx["partita_url"], "/clienti/C7310/")

    def test_form_codice_paga_label_and_valuta_is_choice(self):
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—")],
            ),
            patch(
                "apps.primanota.forms.registro_iva_choices",
                return_value=[("", "—")],
            ),
            patch(
                "apps.primanota.forms.valuta_choices",
                return_value=[
                    ("", "—"),
                    ("Euro", "Euro"),
                    ("USD", "USD — Dollaro"),
                ],
            ),
        ):
            form = PrimanotaForm()
        self.assertEqual(form.fields["codice_paga"].label, "Condizione di pagamento")
        self.assertEqual(form.fields["codice_partita"].label, "Codice Partita")
        self.assertEqual(form.fields["fornitore_cee"].label, "Fornitore")
        self.assertEqual(form.fields["data_cambio"].label, "Data cambio")
        self.assertEqual(form.fields["cambio"].label, "Cambio")
        self.assertTrue(form.fields["data_cambio"].disabled)
        self.assertTrue(form.fields["cambio"].disabled)
        self.assertEqual(form.fields["valuta"].__class__.__name__, "ChoiceField")
        self.assertEqual(
            list(form.fields["valuta"].choices),
            [("", "—"), ("Euro", "Euro"), ("USD", "USD — Dollaro")],
        )

    def test_form_cambio_uses_rate_as_of_data_reg(self):
        from datetime import date, datetime

        row = Primanota(
            id=1,
            valuta="USD",
            data_reg=datetime(2019, 11, 30),
        )
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—")],
            ),
            patch(
                "apps.primanota.forms.registro_iva_choices",
                return_value=[("", "—")],
            ),
            patch(
                "apps.primanota.forms.valuta_choices",
                return_value=[("", "—"), ("USD", "USD — Dollaro")],
            ),
            patch("apps.primanota.forms.cambio_info") as mock_info,
        ):
            mock_info.return_value = {
                "cambio": 0.9084,
                "data": date(2019, 11, 13),
            }
            form = PrimanotaForm(instance=row)
        mock_info.assert_called_once()
        args, kwargs = mock_info.call_args
        self.assertEqual(args[0], "USD")
        self.assertEqual(kwargs.get("alla_data"), date(2019, 11, 30))
        self.assertEqual(form.initial.get("cambio"), 0.9084)
        self.assertEqual(form.initial.get("data_cambio"), date(2019, 11, 13))

    def test_form_valuta_must_exist_in_choices(self):
        choices = [("", "—"), ("Euro", "Euro")]
        causale = MagicMock()
        causale.codice = "01"
        causale.registro_iva = "1"
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—"), ("01", "01 — Fattura")],
            ),
            patch(
                "apps.primanota.forms.registro_iva_choices",
                return_value=[("", "—")],
            ),
            patch("apps.primanota.forms.valuta_choices", return_value=choices),
            patch("apps.primanota.forms.resolve_causale_contabile", return_value=causale),
        ):
            invalid = PrimanotaForm(
                data={
                    "tipo": "2",
                    "causale": "01",
                    "data_reg": "2026-08-18",
                    "valuta": "XXX",
                }
            )
            valid = PrimanotaForm(
                data={
                    "tipo": "2",
                    "causale": "01",
                    "data_reg": "2026-08-18",
                    "valuta": "Euro",
                }
            )
        self.assertFalse(invalid.is_valid())
        self.assertIn("valuta", invalid.errors)
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.cleaned_data["valuta"], "Euro")

    def test_form_valuta_choices_keep_instance_orphan(self):
        row = Primanota(id=1, valuta="VECCIA")
        with (
            patch(
                "apps.primanota.forms.causali_contabili_choices",
                return_value=[("", "—")],
            ),
            patch(
                "apps.primanota.forms.registro_iva_choices",
                return_value=[("", "—")],
            ),
            patch("apps.primanota.forms.valuta_choices") as mock_choices,
        ):
            mock_choices.return_value = [("", "—"), ("VECCIA", "VECCIA")]
            PrimanotaForm(instance=row)
        mock_choices.assert_called_once_with("VECCIA")


class PrimanotaContatoreNumerazioneTests(TestCase):
    def setUp(self):
        from apps.documenti.models import ContatoreDocumento

        self.ContatoreDocumento = ContatoreDocumento
        self.pn26 = ContatoreDocumento.objects.create(
            codice="PN26",
            label="Primanota 2026",
            tipo_contatore=ContatoreDocumento.TIPO_PRIMANOTA,
            esercizio=2026,
            ultimo_numero=10,
        )
        self.pn25 = ContatoreDocumento.objects.create(
            codice="PN25",
            label="Primanota 2025",
            tipo_contatore=ContatoreDocumento.TIPO_PRIMANOTA,
            esercizio=2025,
            ultimo_numero=99,
        )
        ContatoreDocumento.objects.create(
            codice="FAT26",
            label="Fatture 2026",
            tipo_contatore=ContatoreDocumento.TIPO_DOCUMENTI,
            esercizio=2026,
            ultimo_numero=500,
        )

    def test_peek_uses_primanota_counter_for_registration_year(self):
        from datetime import date

        from apps.primanota.numerazione import peek_next_numero_reg

        self.assertEqual(peek_next_numero_reg(date(2026, 3, 15)), 11)
        self.assertEqual(peek_next_numero_reg(date(2025, 12, 31)), 100)

    def test_allocate_increments_only_matching_year(self):
        from datetime import date

        from apps.primanota.numerazione import allocate_next_numero_reg

        n = allocate_next_numero_reg(date(2026, 8, 18))
        self.assertEqual(n, 11)
        self.pn26.refresh_from_db()
        self.pn25.refresh_from_db()
        self.assertEqual(self.pn26.ultimo_numero, 11)
        self.assertEqual(self.pn25.ultimo_numero, 99)

    def test_documents_counter_is_ignored(self):
        from datetime import date

        from apps.primanota.numerazione import resolve_contatore_primanota

        c = resolve_contatore_primanota(date(2026, 1, 1))
        self.assertEqual(c.codice, "PN26")


class PrimanotaProtocolloTests(SimpleTestCase):
    def test_peek_acquisto_uses_upa(self):
        from apps.primanota.protocollo import peek_next_protocollo

        reg = MagicMock()
        reg.tipo_registro = "Acquisto"
        reg.upa = 10
        reg.ups = 99
        with patch("apps.primanota.protocollo.resolve_registro_iva", return_value=reg):
            self.assertEqual(peek_next_protocollo("A"), 11)

    def test_peek_vendita_uses_ups(self):
        from apps.primanota.protocollo import peek_next_protocollo

        reg = MagicMock()
        reg.tipo_registro = "Vendita"
        reg.upa = 1
        reg.ups = 40
        with patch("apps.primanota.protocollo.resolve_registro_iva", return_value=reg):
            self.assertEqual(peek_next_protocollo("V"), 41)

    def test_peek_corrispettivi_uses_ups(self):
        from apps.primanota.protocollo import peek_next_protocollo

        reg = MagicMock()
        reg.tipo_registro = "Corrispettivi"
        reg.ups = 3
        with patch("apps.primanota.protocollo.resolve_registro_iva", return_value=reg):
            self.assertEqual(peek_next_protocollo("C"), 4)

    def test_allocate_increments_ups_for_vendita(self):
        from apps.primanota.protocollo import allocate_next_protocollo

        locked = MagicMock()
        locked.pk = "1"
        locked.tipo_registro = "Vendita"
        locked.ups = 5
        locked.upa = 1
        qs = MagicMock()
        qs.select_for_update.return_value.get.return_value = locked
        with (
            patch("apps.primanota.protocollo.resolve_registro_iva", return_value=locked),
            patch("apps.primanota.protocollo.RegistroIva") as model,
            patch("apps.primanota.protocollo.transaction.atomic") as mock_atomic,
        ):
            model.objects = qs
            mock_atomic.return_value.__enter__ = MagicMock()
            mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
            n = allocate_next_protocollo("1")
        self.assertEqual(n, 6)
        self.assertEqual(locked.ups, 6)
        locked.save.assert_called_once()

    def test_protocollo_from_causale_reads_linked_register(self):
        from apps.primanota.protocollo import protocollo_from_causale

        causale = MagicMock()
        causale.registro_iva = "1"
        registro = MagicMock()
        registro.codice = "1"
        registro.label = "Vendite"
        registro.tipo_registro = "Vendita"
        registro.ups = 7
        with patch("apps.primanota.protocollo.resolve_registro_iva", return_value=registro):
            info = protocollo_from_causale(causale)
        self.assertEqual(info["registro"], "1")
        self.assertEqual(info["registro_label"], "1 — Vendite")
        self.assertEqual(info["numero_prot"], 8)
        self.assertEqual(info["tipo_registro"], "Vendita")

    def test_protocollo_from_causale_without_register(self):
        from apps.primanota.protocollo import protocollo_from_causale

        causale = MagicMock()
        causale.registro_iva = ""
        info = protocollo_from_causale(causale)
        self.assertIsNone(info["registro"])
        self.assertIsNone(info["numero_prot"])


class PrimanotaScadenzeAlgoritmoTests(SimpleTestCase):
    def _cond(self, n=3, prima=30, intervallo=30):
        from types import SimpleNamespace

        return SimpleNamespace(
            numero_rate=n,
            prima_rata=prima,
            intervallo=intervallo,
            giorno_fisso=0,
            mese_esclusione=None,
            mese_esclusione2=None,
            gg_mese_esclus=None,
            gg_mese_esclus2=None,
        )

    def test_condition_n_rate_fills_n_dates_and_amounts(self):
        from datetime import date

        from apps.documenti.scadenze import calcola_scadenze
        from apps.primanota.scadenze import compute_scadenze

        cond = self._cond(n=3)
        expected = calcola_scadenze(
            data_documento=date(2026, 1, 1),
            condizione=cond,
            totale=122,
            max_n=10,
        )
        with patch("apps.primanota.scadenze.load_condizione", return_value=cond):
            slots = compute_scadenze(
                codice_paga="31",
                data_doc=date(2026, 1, 1),
                data_reg=None,
                tipo=2,
                totale_imponibile=100,
                totale_iva=22,
            )
        filled = [s for s in slots if s["data"]]
        self.assertEqual(len(filled), 3)
        self.assertEqual([s["data"] for s in slots[:3]], [s["data"] for s in expected])
        self.assertEqual(
            [s["importo"] for s in slots[:3]], [s["importo"] for s in expected]
        )
        self.assertAlmostEqual(sum(s["importo"] for s in filled), 122.0)
        self.assertEqual(slots[0]["data"], date(2026, 1, 31))
        self.assertEqual(slots[1]["data"], date(2026, 3, 2))
        self.assertEqual(slots[2]["data"], date(2026, 4, 1))

    def test_scadenze_ins_preserves_user_values(self):
        from datetime import datetime

        from apps.primanota.scadenze import maybe_apply_scadenze

        row = Primanota(
            id=1,
            tipo=2,
            codice_paga="31",
            data_doc=datetime(2026, 1, 1),
            scadenze_ins=True,
            scad1=datetime(2026, 6, 15),
            imp_scad1=99.0,
            scad2=datetime(2026, 7, 15),
            imp_scad2=1.0,
        )
        with patch(
            "apps.primanota.scadenze.load_condizione", return_value=self._cond()
        ):
            applied = maybe_apply_scadenze(
                row,
                totals={
                    "totale_imponibile": 100,
                    "totale_iva": 22,
                    "totale_dare": 0,
                    "totale_avere": 0,
                },
            )
        self.assertFalse(applied)
        self.assertEqual(row.scad1, datetime(2026, 6, 15))
        self.assertEqual(row.imp_scad1, 99.0)
        self.assertEqual(row.scad2, datetime(2026, 7, 15))
        self.assertEqual(row.imp_scad2, 1.0)

    def test_missing_pagamento_leaves_empty(self):
        from datetime import date, datetime

        from apps.primanota.scadenze import compute_scadenze, maybe_apply_scadenze

        slots = compute_scadenze(
            codice_paga="",
            data_doc=date(2026, 1, 1),
            tipo=2,
            totale_imponibile=100,
            totale_iva=22,
        )
        self.assertEqual(len(slots), 10)
        self.assertTrue(all(s["data"] is None for s in slots))
        self.assertTrue(all(s["importo"] is None for s in slots))

        row = Primanota(
            id=2,
            tipo=2,
            codice_paga="",
            data_doc=datetime(2026, 1, 1),
            scadenze_ins=False,
            scad1=datetime(2026, 3, 1),
            imp_scad1=50,
        )
        maybe_apply_scadenze(
            row,
            totals={
                "totale_imponibile": 100,
                "totale_iva": 22,
                "totale_dare": 0,
                "totale_avere": 0,
            },
        )
        self.assertIsNone(row.scad1)
        self.assertIsNone(row.imp_scad1)

    def test_uses_data_reg_when_data_doc_missing(self):
        from datetime import date, datetime

        from apps.primanota.scadenze import maybe_apply_scadenze

        row = Primanota(
            id=3,
            tipo=2,
            codice_paga="31",
            data_doc=None,
            data_reg=datetime(2026, 1, 1),
            scadenze_ins=False,
        )
        with patch(
            "apps.primanota.scadenze.load_condizione", return_value=self._cond(n=1, prima=30)
        ):
            maybe_apply_scadenze(
                row,
                totals={
                    "totale_imponibile": 80,
                    "totale_iva": 20,
                    "totale_dare": 0,
                    "totale_avere": 0,
                },
            )
        self.assertEqual(row.scad1.date(), date(2026, 1, 31))
        self.assertEqual(row.imp_scad1, 100.0)
        self.assertIsNone(row.scad2)

    def test_generico_splits_dare(self):
        from datetime import date, datetime

        from apps.primanota.scadenze import maybe_apply_scadenze

        row = Primanota(
            id=4,
            tipo=1,
            codice_paga="31",
            data_doc=datetime(2026, 1, 1),
            scadenze_ins=False,
        )
        with patch(
            "apps.primanota.scadenze.load_condizione", return_value=self._cond(n=2, prima=0, intervallo=30)
        ):
            maybe_apply_scadenze(
                row,
                totals={
                    "totale_imponibile": 0,
                    "totale_iva": 0,
                    "totale_dare": 200,
                    "totale_avere": 50,
                },
            )
        self.assertEqual(row.scad1.date(), date(2026, 1, 1))
        self.assertEqual(row.imp_scad1, 100.0)
        self.assertEqual(row.imp_scad2, 100.0)


