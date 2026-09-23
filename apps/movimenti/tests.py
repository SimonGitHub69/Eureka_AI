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


class StatisticheMagazzinoWiringTests(SimpleTestCase):
    def test_urls(self):
        self.assertEqual(
            reverse("movimenti:statistiche"),
            "/elaborazioni/statistiche-magazzino/",
        )
        self.assertEqual(
            reverse("movimenti:statistiche_print"),
            "/elaborazioni/statistiche-magazzino/stampa/",
        )
        self.assertEqual(
            reverse("movimenti:statistiche_export"),
            "/elaborazioni/statistiche-magazzino/export/",
        )
        self.assertEqual(
            reverse("movimenti:statistiche_articoli_set"),
            "/elaborazioni/statistiche-magazzino/articoli-set/",
        )

    def test_parse_period_anno_preset(self):
        from apps.movimenti.statistiche import parse_period

        da, a = parse_period({"anno": "2025"})
        self.assertEqual(da.isoformat(), "2025-01-01")
        self.assertEqual(a.isoformat(), "2025-12-31")

    def test_selected_causali(self):
        from apps.movimenti.statistiche import selected_causali

        class FakeGet(dict):
            def getlist(self, key):
                return ["05", "07", "05", ""]

        self.assertEqual(selected_causali(FakeGet()), ["05", "07"])

    def test_selected_set_ids(self):
        from apps.movimenti.statistiche import selected_set_ids

        class FakeGet(dict):
            def getlist(self, key):
                return ["10", "20", "10", "x", ""]

        self.assertEqual(selected_set_ids(FakeGet()), [10, 20])

    def test_selected_articoli(self):
        from apps.movimenti.statistiche import selected_articoli

        class FakeGet(dict):
            def getlist(self, key):
                return ["AAA", "bbb", "AAA", ""]

        self.assertEqual(selected_articoli(FakeGet()), ["AAA", "bbb"])

    def test_finalize_righe_articoli(self):
        from apps.movimenti.statistiche import StatisticaRiga, finalize_righe_articoli

        rows = finalize_righe_articoli(
            [
                StatisticaRiga("A", "Uno", 10.0, 100.0),
                StatisticaRiga("B", "Due", 5.0, 50.0),
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0].valore_un, 10.0)
        self.assertAlmostEqual(rows[0].incidenza, 100 * 100 / 150)
        self.assertAlmostEqual(rows[1].incidenza, 100 * 50 / 150)
        self.assertAlmostEqual(sum(r.incidenza for r in rows), 100.0)

    def test_layout_cliente_articolo_testata_dettaglio(self):
        from apps.movimenti.statistiche import (
            LAYOUT_TESTATA_DETTAGLIO,
            _RawStatRow,
            _layout_testata_dettaglio,
            finalize_righe_articoli,
            is_data_riga,
            resolve_statistica_tipo,
        )

        spec = resolve_statistica_tipo("cliente_articolo")
        self.assertEqual(spec.get("layout"), LAYOUT_TESTATA_DETTAGLIO)

        raw = [
            _RawStatRow(dims=(("C1", "Cliente Uno"), ("A1", "Art A")), quantita=2.0, valore=20.0),
            _RawStatRow(dims=(("C1", "Cliente Uno"), ("A2", "Art B")), quantita=3.0, valore=30.0),
            _RawStatRow(dims=(("C2", "Cliente Due"), ("A1", "Art A")), quantita=1.0, valore=10.0),
        ]
        rows = finalize_righe_articoli(
            _layout_testata_dettaglio(
                raw, dim_keys=("cliente", "articolo"), detail_link="articolo"
            )
        )
        self.assertEqual([r.kind for r in rows], ["header", "detail", "detail", "header", "detail"])
        self.assertEqual(rows[0].codice, "C1")
        self.assertEqual(rows[0].descrizione, "Cliente Uno")
        self.assertAlmostEqual(rows[0].quantita, 5.0)
        self.assertAlmostEqual(rows[0].valore, 50.0)
        self.assertEqual(rows[0].link_kind, "cliente")
        self.assertEqual(rows[1].codice, "A1")
        self.assertEqual(rows[1].link_kind, "articolo")
        self.assertEqual(rows[2].codice, "A2")
        data = [r for r in rows if is_data_riga(r)]
        self.assertEqual(len(data), 3)
        self.assertAlmostEqual(sum(r.valore for r in data), 60.0)
        self.assertAlmostEqual(sum(r.incidenza for r in data), 100.0)
        # La testata riporta la % del gruppo sul totale.
        self.assertAlmostEqual(rows[0].incidenza, 100 * 50 / 60)

    def test_all_slash_articoli_use_testata_dettaglio(self):
        from apps.movimenti.statistiche import LAYOUT_TESTATA_DETTAGLIO, STATISTICHE_TIPI

        multi = []
        for spec in STATISTICHE_TIPI:
            dims = tuple(spec.get("dims") or ())
            if len(dims) < 2:
                continue
            multi.append(str(spec["key"]))
            self.assertEqual(spec.get("layout"), LAYOUT_TESTATA_DETTAGLIO, spec["key"])
            last = str(dims[-1])
            self.assertEqual(
                spec.get("detail_link"),
                {"articolo": "articolo", "cliente": "cliente", "fornitore": "fornitore", "categoria": "categoria"}.get(
                    last, last
                ),
                spec["key"],
            )
        self.assertIn("agenti_clienti", multi)
        self.assertIn("zone_clienti", multi)
        self.assertIn("articoli_cliente", multi)
        self.assertIn("cliente_articolo", multi)

    def test_layout_agenti_clienti_testata_dettaglio(self):
        from apps.movimenti.statistiche import (
            LAYOUT_TESTATA_DETTAGLIO,
            _RawStatRow,
            _layout_testata_dettaglio,
            finalize_righe_articoli,
            resolve_statistica_tipo,
        )

        spec = resolve_statistica_tipo("agenti_clienti")
        self.assertEqual(spec.get("layout"), LAYOUT_TESTATA_DETTAGLIO)
        self.assertEqual(spec.get("header_link"), "agente")
        self.assertEqual(spec.get("detail_link"), "cliente")
        self.assertEqual(spec.get("dims"), ("agente", "cliente"))

        rows = finalize_righe_articoli(
            _layout_testata_dettaglio(
                [
                    _RawStatRow(
                        dims=(("AG1", "Agente Uno"), ("C1", "Cliente A")),
                        quantita=2.0,
                        valore=20.0,
                    ),
                    _RawStatRow(
                        dims=(("AG1", "Agente Uno"), ("C2", "Cliente B")),
                        quantita=3.0,
                        valore=30.0,
                    ),
                ],
                dim_keys=("agente", "cliente"),
                detail_link="cliente",
            )
        )
        self.assertEqual([r.kind for r in rows], ["header", "detail", "detail"])
        self.assertEqual(rows[0].codice, "AG1")
        self.assertEqual(rows[0].link_kind, "agente")
        self.assertAlmostEqual(rows[0].quantita, 5.0)
        self.assertEqual(rows[1].codice, "C1")
        self.assertEqual(rows[1].link_kind, "cliente")

    def test_layout_articoli_cliente_testata_dettaglio(self):
        from apps.movimenti.statistiche import (
            LAYOUT_TESTATA_DETTAGLIO,
            _RawStatRow,
            _layout_testata_dettaglio,
            finalize_righe_articoli,
            resolve_statistica_tipo,
        )

        spec = resolve_statistica_tipo("articoli_cliente")
        self.assertEqual(spec.get("layout"), LAYOUT_TESTATA_DETTAGLIO)
        self.assertEqual(spec.get("header_link"), "articolo")
        self.assertEqual(spec.get("detail_link"), "cliente")
        self.assertEqual(spec.get("dims"), ("articolo", "cliente"))

        rows = finalize_righe_articoli(
            _layout_testata_dettaglio(
                [
                    _RawStatRow(
                        dims=(("A1", "Art Uno"), ("C1", "Cliente A")),
                        quantita=2.0,
                        valore=20.0,
                    ),
                    _RawStatRow(
                        dims=(("A1", "Art Uno"), ("C2", "Cliente B")),
                        quantita=3.0,
                        valore=30.0,
                    ),
                    _RawStatRow(
                        dims=(("A2", "Art Due"), ("C1", "Cliente A")),
                        quantita=1.0,
                        valore=10.0,
                    ),
                ],
                dim_keys=("articolo", "cliente"),
                detail_link="cliente",
            )
        )
        self.assertEqual(
            [r.kind for r in rows],
            ["header", "detail", "detail", "header", "detail"],
        )
        self.assertEqual(rows[0].codice, "A1")
        self.assertEqual(rows[0].link_kind, "articolo")
        self.assertAlmostEqual(rows[0].quantita, 5.0)
        self.assertEqual(rows[1].codice, "C1")
        self.assertEqual(rows[1].descrizione, "Cliente A")
        self.assertEqual(rows[1].link_kind, "cliente")
        self.assertEqual(rows[3].codice, "A2")
        self.assertEqual(rows[4].link_kind, "cliente")

    def test_layout_nested_zone_clienti_articoli(self):
        from apps.movimenti.statistiche import (
            _RawStatRow,
            _layout_testata_dettaglio,
            finalize_righe_articoli,
        )

        rows = finalize_righe_articoli(
            _layout_testata_dettaglio(
                [
                    _RawStatRow(
                        dims=(("Z1", "Nord"), ("C1", "Cli A"), ("A1", "Art 1")),
                        quantita=2.0,
                        valore=20.0,
                    ),
                    _RawStatRow(
                        dims=(("Z1", "Nord"), ("C1", "Cli A"), ("A2", "Art 2")),
                        quantita=3.0,
                        valore=30.0,
                    ),
                    _RawStatRow(
                        dims=(("Z1", "Nord"), ("C2", "Cli B"), ("A1", "Art 1")),
                        quantita=1.0,
                        valore=10.0,
                    ),
                ],
                dim_keys=("zona", "cliente", "articolo"),
            )
        )
        kinds = [r.kind for r in rows]
        self.assertEqual(
            kinds,
            ["header", "header", "detail", "detail", "header", "detail"],
        )
        self.assertEqual(rows[0].codice, "Z1")
        self.assertEqual(rows[0].level, 0)
        self.assertEqual(rows[0].link_kind, "zona")
        self.assertAlmostEqual(rows[0].valore, 60.0)
        self.assertEqual(rows[1].codice, "C1")
        self.assertEqual(rows[1].level, 1)
        self.assertEqual(rows[1].link_kind, "cliente")
        self.assertAlmostEqual(rows[1].valore, 50.0)
        self.assertEqual(rows[2].kind, "detail")
        self.assertEqual(rows[2].codice, "A1")
        self.assertEqual(rows[2].level, 2)

    def test_layout_agenti_zone_articoli(self):
        from apps.movimenti.statistiche import (
            LAYOUT_TESTATA_DETTAGLIO,
            _RawStatRow,
            _layout_testata_dettaglio,
            finalize_righe_articoli,
            resolve_statistica_tipo,
        )

        spec = resolve_statistica_tipo("agenti_zone_articoli")
        self.assertEqual(spec.get("layout"), LAYOUT_TESTATA_DETTAGLIO)
        self.assertEqual(spec.get("dims"), ("agente", "zona", "articolo"))
        self.assertEqual(spec.get("detail_link"), "articolo")
        self.assertEqual(spec.get("header_link"), "agente")

        rows = finalize_righe_articoli(
            _layout_testata_dettaglio(
                [
                    _RawStatRow(
                        dims=(("AG1", "Agente 1"), ("Z1", "Nord"), ("A1", "Art A")),
                        quantita=2.0,
                        valore=20.0,
                    ),
                    _RawStatRow(
                        dims=(("AG1", "Agente 1"), ("Z1", ""), ("A2", "Art B")),
                        quantita=1.0,
                        valore=10.0,
                    ),
                    _RawStatRow(
                        dims=(("AG1", "Agente 1"), ("Z2", "Sud"), ("A1", "Art A")),
                        quantita=4.0,
                        valore=40.0,
                    ),
                    _RawStatRow(
                        dims=(("AG2", "Agente 2"), ("Z1", "Nord"), ("A1", "Art A")),
                        quantita=3.0,
                        valore=30.0,
                    ),
                ],
                dim_keys=("agente", "zona", "articolo"),
                detail_link="articolo",
            )
        )
        # Stessa zona Z1 con label diverse resta un solo gruppo (groupby su codice).
        self.assertEqual(
            [r.kind for r in rows],
            ["header", "header", "detail", "detail", "header", "detail", "header", "header", "detail"],
        )
        self.assertEqual(rows[0].codice, "AG1")
        self.assertEqual(rows[0].link_kind, "agente")
        self.assertAlmostEqual(rows[0].valore, 70.0)
        self.assertEqual(rows[1].codice, "Z1")
        self.assertEqual(rows[1].link_kind, "zona")
        self.assertEqual(rows[1].level, 1)
        self.assertEqual(rows[1].descrizione, "Nord")
        self.assertAlmostEqual(rows[1].valore, 30.0)
        self.assertEqual(rows[2].codice, "A1")
        self.assertEqual(rows[2].link_kind, "articolo")
        self.assertEqual(rows[2].level, 2)
        self.assertEqual(rows[4].codice, "Z2")
        self.assertEqual(rows[6].codice, "AG2")

    def test_gruppo_clienti_uses_raggruppamento_descrizione(self):
        from apps.movimenti.statistiche import _DIM_SQL, _join_sql, resolve_statistica_tipo

        spec = resolve_statistica_tipo("gruppo_clienti")
        self.assertEqual(spec.get("dims"), ("gruppo_cli",))
        dim = _DIM_SQL["gruppo_cli"]
        self.assertIn("gcf.\"Descrizione\"", str(dim["label"]))
        self.assertIn("gruppi_clifor", dim["joins"])
        sql = _join_sql({"articoli", "clienti", "gruppi_clifor"})
        self.assertIn("raggruppamento_clifor", sql)
        self.assertIn('gcf."Codice"', sql)

    def test_layout_zone_articoli_testata_dettaglio(self):
        from apps.movimenti.statistiche import (
            LAYOUT_TESTATA_DETTAGLIO,
            _RawStatRow,
            _layout_testata_dettaglio,
            finalize_righe_articoli,
            resolve_statistica_tipo,
        )

        spec = resolve_statistica_tipo("zone_articoli")
        self.assertEqual(spec.get("layout"), LAYOUT_TESTATA_DETTAGLIO)
        self.assertEqual(spec.get("header_link"), "zona")
        self.assertEqual(spec.get("detail_link"), "articolo")
        self.assertEqual(spec.get("dims"), ("zona", "articolo"))

        rows = finalize_righe_articoli(
            _layout_testata_dettaglio(
                [
                    _RawStatRow(
                        dims=(("Z1", "Nord"), ("A1", "Art A")), quantita=4.0, valore=40.0
                    ),
                    _RawStatRow(
                        dims=(("Z1", "Nord"), ("A2", "Art B")), quantita=1.0, valore=10.0
                    ),
                ],
                dim_keys=("zona", "articolo"),
                detail_link="articolo",
            )
        )
        self.assertEqual(rows[0].kind, "header")
        self.assertEqual(rows[0].codice, "Z1")
        self.assertEqual(rows[0].descrizione, "Nord")
        self.assertEqual(rows[0].link_kind, "zona")
        self.assertAlmostEqual(rows[0].quantita, 5.0)
        self.assertEqual(rows[1].kind, "detail")
        self.assertEqual(rows[1].codice, "A1")
        self.assertEqual(rows[1].link_kind, "articolo")

    def test_layout_agenti_articoli_testata_dettaglio(self):
        from apps.movimenti.statistiche import (
            LAYOUT_TESTATA_DETTAGLIO,
            resolve_statistica_tipo,
        )

        spec = resolve_statistica_tipo("agenti_articoli")
        self.assertEqual(spec.get("layout"), LAYOUT_TESTATA_DETTAGLIO)
        self.assertEqual(spec.get("header_link"), "agente")
        self.assertEqual(spec.get("detail_link"), "articolo")
        self.assertEqual(spec.get("dims"), ("agente", "articolo"))

    def test_filter_summary(self):
        from datetime import date

        from apps.movimenti.statistiche import filter_summary

        text = filter_summary(
            titolo="Statistiche di Vendita",
            data_da=date(2026, 1, 1),
            data_a=date(2026, 12, 31),
            causali=["05", "07"],
            set_label="Set A, Set B",
            n_articoli=12,
        )
        self.assertIn("Statistiche di Vendita", text)
        self.assertIn("05", text)
        self.assertIn("07", text)
        self.assertIn("Set A, Set B", text)
        self.assertIn("12 articoli", text)

    def test_export_csv_and_xlsx_for_tipologiche(self):
        from datetime import date
        from unittest.mock import patch

        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from apps.core.export import XLSX_CONTENT_TYPE
        from apps.movimenti.statistiche import STATISTICHE_TIPI, StatisticaRiga
        from apps.movimenti.views import StatisticheMagazzinoExportView

        sample = [
            StatisticaRiga("A01", "Articolo uno", 2.0, 20.0, valore_un=10.0, incidenza=100.0)
        ]
        rf = RequestFactory()
        tipologiche = [str(t["key"]) for t in STATISTICHE_TIPI]

        for tipo in tipologiche:
            for fmt in ("csv", "xlsx"):
                with self.subTest(tipo=tipo, fmt=fmt):
                    request = rf.get(
                        "/elaborazioni/statistiche-magazzino/export/",
                        {
                            "elabora": "1",
                            "tipo": tipo,
                            "fmt": fmt,
                            "data_da": "2026-01-01",
                            "data_a": "2026-12-31",
                            "causale": "05",
                        },
                    )
                    request.user = AnonymousUser()
                    with patch(
                        "apps.movimenti.views.elabora_statistiche",
                        return_value=sample,
                    ):
                        # Bypass LoginRequiredMixin redirect.
                        response = StatisticheMagazzinoExportView().get(request)
                    self.assertEqual(response.status_code, 200)
                    cd = response["Content-Disposition"]
                    self.assertIn(f"statistiche_{tipo}_{date.today():%Y-%m-%d}", cd)
                    if fmt == "csv":
                        self.assertTrue(cd.endswith('.csv"') or '.csv"' in cd)
                        body = response.content.decode("utf-8-sig")
                        self.assertIn("Codice", body)
                        self.assertIn("A01", body)
                    else:
                        self.assertEqual(response["Content-Type"], XLSX_CONTENT_TYPE)
                        self.assertTrue(cd.endswith('.xlsx"') or '.xlsx"' in cd)
                        self.assertGreater(len(response.content), 100)

