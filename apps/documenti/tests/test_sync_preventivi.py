"""Import Preventivi: Alfa FF → tipo PRF (serie coerente)."""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO, DETAIL_SOURCES, HEADER_SOURCES
from apps.documenti.models import RigaDocumento, TestaDocumento, TipoDocumento
from apps.documenti.sync import (
    _drop_sibling_headers,
    _prune_headers_missing_from_4d,
    _selection_to_tipos,
    _serie_tipi_for_spec,
    build_alfa_where,
    import_slices_for_spec,
    resolve_alfa_column_name,
    sync_detail_source,
    sync_header_source,
)


class PreventiviSelectionTests(SimpleTestCase):
    def test_only_prv_include_prf(self):
        self.assertEqual(_selection_to_tipos(["PRV"]), frozenset({"PRV", "PRF"}))

    def test_only_preventivi_table_include_family(self):
        self.assertEqual(
            _selection_to_tipos(["Preventivi"]),
            frozenset({"PRV", "PRF"}),
        )

    def test_orv_unchanged(self):
        self.assertEqual(_selection_to_tipos(["ORV"]), frozenset({"ORV"}))


class AlfaWhereTests(SimpleTestCase):
    def test_resolve_alfa_column(self):
        self.assertEqual(
            resolve_alfa_column_name([{"name": "ID_Testa"}, {"name": "Alfa"}]),
            "Alfa",
        )
        self.assertEqual(
            resolve_alfa_column_name([{"name": "SerieDoc"}]),
            "SerieDoc",
        )
        self.assertIsNone(resolve_alfa_column_name([{"name": "Numero"}]))

    def test_where_serie_ff(self):
        where = build_alfa_where("Alfa", "FF", ["FF"])
        self.assertIn("[Alfa] = 'FF'", where)
        self.assertIn("[Alfa] = 'ff'", where)

    def test_where_residuo_esclude_ff(self):
        where = build_alfa_where("Alfa", "", ["FF"])
        self.assertIn("[Alfa] <> 'FF'", where)
        self.assertIn("[Alfa] <> 'ff'", where)
        self.assertIn("IS NULL", where)

    def test_import_slices_preventivi_due_letture(self):
        spec = next(s for s in HEADER_SOURCES if s.source == "Preventivi")
        with patch(
            "apps.documenti.sync._serie_by_tipo_for_spec",
            return_value={"PRV": "", "PRF": "FF"},
        ):
            slices = import_slices_for_spec(
                spec,
                enabled=("PRV", "PRF"),
                tipos_filter=None,
                alfa_column="Alfa",
            )
        self.assertEqual([s.tipo_doc for s in slices], ["PRF", "PRV"])
        self.assertIn("[Alfa] = 'FF'", slices[0].extra_where)
        self.assertIn("[Alfa] <> 'FF'", slices[1].extra_where)

    def test_import_slices_solo_prf(self):
        spec = next(s for s in HEADER_SOURCES if s.source == "Preventivi")
        with patch(
            "apps.documenti.sync._serie_by_tipo_for_spec",
            return_value={"PRV": "", "PRF": "FF"},
        ):
            slices = import_slices_for_spec(
                spec,
                enabled=("PRV", "PRF"),
                tipos_filter=frozenset({"PRF"}),
                alfa_column="Alfa",
            )
        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0].tipo_doc, "PRF")
        self.assertIn("[Alfa] = 'FF'", slices[0].extra_where)

    def test_fatture_senza_split_se_piu_residui(self):
        spec = next(s for s in HEADER_SOURCES if s.source == "Fatture")
        with patch(
            "apps.documenti.sync._serie_by_tipo_for_spec",
            return_value={"FAT": "FF", "NCR": "", "NDB": ""},
        ):
            slices = import_slices_for_spec(
                spec,
                enabled=("FAT", "NCR", "NDB"),
                tipos_filter=None,
                alfa_column="Alfa",
            )
        self.assertEqual(slices, [])


class PreventiviSplitFetchTests(SimpleTestCase):
    def test_sync_header_due_fetch_alfa(self):
        spec = next(s for s in HEADER_SOURCES if s.source == "Preventivi")
        empty = ([], [{"name": "Alfa"}, {"name": "ID_Testa"}], "0 righe", [])
        with (
            patch("apps.documenti.sync.is_documento_menu_enabled", return_value=True),
            patch("apps.documenti.sync._max_header_id_4d", return_value=None),
            patch(
                "apps.documenti.sync._serie_by_tipo_for_spec",
                return_value={"PRV": "", "PRF": "FF"},
            ),
            patch(
                "apps.documenti.sync._peek_columns",
                return_value=[{"name": "Alfa"}, {"name": "ID_Testa"}],
            ),
            patch("apps.documenti.sync._run_fetch", return_value=empty) as mock_fetch,
            patch("apps.documenti.sync._upsert_teste", return_value=0),
            patch("apps.documenti.sync._drop_sibling_headers"),
            patch("apps.documenti.sync._load_cambio_by_valuta", return_value={}),
            patch("apps.documenti.sync._commit_watermark"),
        ):
            result = sync_header_source(spec)

        self.assertTrue(result.ok)
        self.assertEqual(mock_fetch.call_count, 2)
        wheres = [call.kwargs.get("extra_where") or "" for call in mock_fetch.call_args_list]
        self.assertTrue(any("[Alfa] = 'FF'" in w for w in wheres))
        self.assertTrue(any("[Alfa] <> 'FF'" in w for w in wheres))
        self.assertTrue(all(call.kwargs.get("update_watermark") is False for call in mock_fetch.call_args_list))
        self.assertTrue(all(call.kwargs.get("full") is False for call in mock_fetch.call_args_list))

    def test_sync_detail_due_fetch_se_ha_alfa(self):
        spec = next(s for s in DETAIL_SOURCES if s.source == "Preventivi_Dettaglio")
        empty = ([], [{"name": "Alfa"}, {"name": "ID_Testa"}], "0 righe", [])
        with (
            patch("apps.documenti.sync.is_documento_menu_enabled", return_value=True),
            patch("apps.documenti.sync._max_line_id_4d", return_value=None),
            patch(
                "apps.documenti.sync._serie_by_tipo_for_spec",
                return_value={"PRV": "", "PRF": "FF"},
            ),
            patch(
                "apps.documenti.sync._peek_columns",
                return_value=[{"name": "Alfa"}, {"name": "ID_Riga"}],
            ),
            patch("apps.documenti.sync._run_fetch", return_value=empty) as mock_fetch,
            patch(
                "apps.documenti.sync.TestaDocumento.objects.filter",
                return_value=type("QS", (), {"values_list": lambda *a, **k: []})(),
            ),
            patch("apps.documenti.sync._upsert_righe", return_value=0),
            patch("apps.documenti.sync._commit_watermark"),
        ):
            result = sync_detail_source(spec, header_tipo_by_id_4d={})

        self.assertTrue(result.ok)
        self.assertEqual(mock_fetch.call_count, 2)
        wheres = [call.kwargs.get("extra_where") or "" for call in mock_fetch.call_args_list]
        self.assertTrue(any("[Alfa] = 'FF'" in w for w in wheres))

    def test_sync_detail_una_fetch_senza_alfa(self):
        spec = next(s for s in DETAIL_SOURCES if s.source == "Preventivi_Dettaglio")
        empty = ([], [{"name": "ID_Riga"}, {"name": "ID_Testa"}], "0 righe", [])
        with (
            patch("apps.documenti.sync.is_documento_menu_enabled", return_value=True),
            patch("apps.documenti.sync._max_line_id_4d", return_value=None),
            patch(
                "apps.documenti.sync._serie_by_tipo_for_spec",
                return_value={"PRV": "", "PRF": "FF"},
            ),
            patch(
                "apps.documenti.sync._peek_columns",
                return_value=[{"name": "ID_Riga"}, {"name": "ID_Testa"}],
            ),
            patch("apps.documenti.sync._run_fetch", return_value=empty) as mock_fetch,
            patch(
                "apps.documenti.sync.TestaDocumento.objects.filter",
                return_value=type("QS", (), {"values_list": lambda *a, **k: []})(),
            ),
            patch("apps.documenti.sync._upsert_righe", return_value=0),
        ):
            result = sync_detail_source(spec, header_tipo_by_id_4d={})

        self.assertTrue(result.ok)
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertIsNone(mock_fetch.call_args.kwargs.get("extra_where"))
        self.assertFalse(mock_fetch.call_args.kwargs.get("full"))


class PreventiviSerieReclassTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for spec in DEFAULT_TIPI_DOCUMENTO:
            TipoDocumento.objects.get_or_create(
                codice=spec["codice"],
                defaults={
                    "label": spec["label"],
                    "ordine": spec["ordine"],
                    "source_table_4d": spec["source_table_4d"],
                    "source_detail_4d": spec["source_detail_4d"],
                    "clifor_tipo": spec["clifor_tipo"],
                    "categoria": spec.get("categoria", "ALTRO"),
                },
            )
        TipoDocumento.objects.update_or_create(
            codice="PRF",
            defaults={
                "label": "PREVENTIVO FF",
                "categoria": TipoDocumento.CATEGORIA_PREVENTIVI,
                "serie": "FF",
                "attivo": True,
                "ordine": 0,
                "clifor_tipo": "C",
                "source_table_4d": "Preventivi",
                "source_detail_4d": "Preventivi_Dettaglio",
            },
        )

    def test_serie_tipi_maps_ff_to_prf(self):
        from apps.documenti.mapping import HEADER_SOURCES

        spec = next(s for s in HEADER_SOURCES if s.source == "Preventivi")
        lookup = _serie_tipi_for_spec(spec)
        self.assertEqual(lookup.get("FF"), "PRF")

    def test_import_slices_da_parametri_documento(self):
        spec = next(s for s in HEADER_SOURCES if s.source == "Preventivi")
        slices = import_slices_for_spec(
            spec,
            enabled=("PRV", "PRF"),
            tipos_filter=None,
            alfa_column="Alfa",
        )
        self.assertEqual([s.tipo_doc for s in slices], ["PRF", "PRV"])
        self.assertEqual(slices[0].serie, "FF")
        self.assertIn("[Alfa] = 'FF'", slices[0].extra_where)

    def test_import_slices_ff_e_t(self):
        from apps.documenti.mapping import HEADER_SOURCES

        TipoDocumento.objects.update_or_create(
            codice="PRT",
            defaults={
                "label": "Preventivi T",
                "categoria": TipoDocumento.CATEGORIA_PREVENTIVI,
                "serie": "T",
                "attivo": True,
                "source_table_4d": "Preventivi",
                "source_detail_4d": "Preventivi_Dettaglio",
                "clifor_tipo": "C",
            },
        )
        spec = next(s for s in HEADER_SOURCES if s.source == "Preventivi")
        slices = import_slices_for_spec(
            spec,
            enabled=("PRV", "PRF", "PRT"),
            tipos_filter=None,
            alfa_column="Alfa",
        )
        by_tipo = {s.tipo_doc: s for s in slices}
        self.assertEqual(set(by_tipo), {"PRF", "PRT", "PRV"})
        self.assertIn("[Alfa] = 'T'", by_tipo["PRT"].extra_where)
        self.assertIn("[Alfa] <> 'T'", by_tipo["PRV"].extra_where)
        self.assertIn("[Alfa] <> 'FF'", by_tipo["PRV"].extra_where)

    def test_drop_old_prv_when_moved_to_prf(self):
        old = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=501,
            numero=1,
            alfa="FF",
        )
        RigaDocumento.objects.create(testa=old, id_4d=1, numero_riga=10)
        moved = TestaDocumento.objects.create(
            tipo_doc_id="PRF",
            id_4d=501,
            numero=1,
            alfa="FF",
        )
        _drop_sibling_headers([moved], ("PRV", "PRF"))
        self.assertFalse(
            TestaDocumento.objects.filter(tipo_doc_id="PRV", id_4d=501).exists()
        )
        self.assertTrue(
            TestaDocumento.objects.filter(tipo_doc_id="PRF", id_4d=501).exists()
        )
        self.assertFalse(RigaDocumento.objects.filter(testa=old).exists())

    def test_prune_id_testa_eliminato_in_4d(self):
        stale = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=4119,
            numero=4,
            alfa="",
        )
        RigaDocumento.objects.create(testa=stale, id_4d=1, numero_riga=10)
        keep = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=100,
            numero=1,
            alfa="",
        )
        removed = _prune_headers_missing_from_4d("PRV", {100})
        self.assertEqual(removed, 1)
        self.assertFalse(TestaDocumento.objects.filter(id_4d=4119).exists())
        self.assertTrue(TestaDocumento.objects.filter(pk=keep.pk).exists())
        self.assertFalse(RigaDocumento.objects.filter(testa=stale).exists())

    def test_prune_non_svuota_se_keep_vuoto(self):
        TestaDocumento.objects.create(tipo_doc_id="PRV", id_4d=4119, numero=4)
        self.assertEqual(_prune_headers_missing_from_4d("PRV", set()), 0)
        self.assertTrue(TestaDocumento.objects.filter(id_4d=4119).exists())

    def test_serie_ordini_vendita_da_parametri(self):
        from apps.documenti.mapping import HEADER_SOURCES
        from apps.documenti.sync import _tipos_for_header_spec

        TipoDocumento.objects.update_or_create(
            codice="ORF",
            defaults={
                "label": "Ordini FF",
                "categoria": TipoDocumento.CATEGORIA_ORDINI,
                "serie": "FF",
                "attivo": True,
                "clifor_tipo": "C",
                "source_table_4d": "Ordini_Vendita",
                "source_detail_4d": "Ordini_Vendita_Dettaglio",
            },
        )
        spec = next(s for s in HEADER_SOURCES if s.source == "Ordini_Vendita")
        lookup = _serie_tipi_for_spec(spec)
        self.assertEqual(lookup.get("FF"), "ORF")
        self.assertIn("ORF", _tipos_for_header_spec(spec))
