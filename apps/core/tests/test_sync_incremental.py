from datetime import date, datetime, time, timedelta

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.core.sync_incremental import (
    ModificaColumnSpec,
    _as_naive,
    build_incremental_where,
    detect_modifica_columns,
    ensure_modifica_columns_in_list,
    format_incremental_message,
    is_newer_than_watermark,
    max_modifica_from_rows,
    parse_4d_modifica,
)


class DetectModificaColumnsTests(SimpleTestCase):
    def test_split_data_ora(self):
        cols = [
            {"name": "Codice"},
            {"name": "DataModifica", "pg_type": "date"},
            {"name": "OraModifica", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "split")
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "date")

    def test_clienti_timestamp_data_with_ora(self):
        cols = [
            {"name": "Codice"},
            {"name": "DataModifica", "pg_type": "timestamp"},
            {"name": "OraModifica", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "split")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_single_column(self):
        cols = [{"name": "ID"}, {"name": "DataOraModifica"}]
        spec = detect_modifica_columns(cols)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "single")
        self.assertEqual(spec.single_col, "DataOraModifica")

    def test_data_e_ora_modifica_single(self):
        cols = [{"name": "Codice"}, {"name": "Data e Ora Modifica", "pg_type": "timestamp"}]
        spec = detect_modifica_columns(cols)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "single")
        self.assertEqual(spec.single_col, "Data e Ora Modifica")

    def test_missing_returns_none(self):
        self.assertIsNone(detect_modifica_columns([{"name": "Codice"}]))

    def test_gruppo_cli_for_odbc_introspection(self):
        cols = [
            {"name": "Codice", "pg_type": "text"},
            {"name": "Descrizione", "pg_type": "text"},
            {"name": "Escludi_Regola_NewCli", "pg_type": "boolean"},
            {"name": "DataModifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
            {"name": "OraModifica", "type_name": "INTERVAL", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols, source_table="Gruppo_Cli_For")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "split")
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_gruppo_cli_for_override_fallback(self):
        spec = detect_modifica_columns([{"name": "Codice"}], source_table="Gruppo_Cli_For")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_destclifor_override_fallback(self):
        spec = detect_modifica_columns(
            [{"name": "ID"}, {"name": "Codice"}],
            source_table="DestCliFor",
        )
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "split")
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_azienda_odbc_introspection(self):
        cols = [
            {"name": "ID", "pg_type": "integer"},
            {"name": "RagioneSociale", "pg_type": "text"},
            {"name": "DataModifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
            {"name": "OraModifica", "type_name": "INTERVAL", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols, source_table="Azienda")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "split")
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_azienda_override_fallback(self):
        spec = detect_modifica_columns([{"name": "ID"}], source_table="Azienda")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertIsNone(spec.data_pg_type)

    def test_clienti_override_fallback(self):
        spec = detect_modifica_columns([{"name": "Codice"}], source_table="Clienti")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_fornitori_override_fallback(self):
        spec = detect_modifica_columns([{"name": "Codice"}], source_table="Fornitori")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_primanota_override_fallback(self):
        spec = detect_modifica_columns([{"name": "ID"}], source_table="Primanota")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_primanota_dettaglio_override_fallback(self):
        spec = detect_modifica_columns(
            [{"name": "ID"}],
            source_table="Primanota_Dettaglio",
        )
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.data_col, "DataModifica")
        self.assertEqual(spec.ora_col, "OraModifica")
        self.assertEqual(spec.data_pg_type, "timestamp")

    def test_azienda_odbc_case_insensitive(self):
        cols = [
            {"name": "ID", "pg_type": "integer"},
            {"name": "datamodifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
            {"name": "ORAMODIFICA", "type_name": "INTERVAL", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols, source_table="Azienda")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.mode, "split")
        self.assertEqual(spec.data_col, "datamodifica")
        self.assertEqual(spec.ora_col, "ORAMODIFICA")
        self.assertEqual(spec.data_pg_type, "timestamp")


class Parse4dModificaTests(SimpleTestCase):
    def test_split_columns(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="date",
        )
        row = {
            "DataModifica": date(2024, 3, 15),
            "OraModifica": time(10, 30, 0),
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2024, 3, 15, 10, 30, 0))

    def test_timestamp_data_column(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        row = {
            "DataModifica": datetime(2024, 3, 15, 10, 30, 0),
            "OraModifica": time(8, 0, 0),
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2024, 3, 15, 10, 30, 0))

    def test_single_datetime(self):
        spec = ModificaColumnSpec(mode="single", single_col="DataOraModifica")
        row = {"DataOraModifica": datetime(2024, 3, 15, 10, 30, 0)}
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2024, 3, 15, 10, 30, 0))

    def test_azienda_split_date_and_ora_from_odbc(self):
        """DataModifica DATE + OraModifica TIME (caso reale tabella Azienda)."""
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="date",
        )
        row = {
            "DataModifica": date(2026, 8, 12),
            "OraModifica": time(16, 57, 56),
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2026, 8, 12, 16, 57, 56))

    def test_azienda_midnight_timestamp_with_ora(self):
        """ODBC TIMESTAMP a mezzanotte + OraModifica con l'ora effettiva."""
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        row = {
            "DataModifica": datetime(2026, 8, 12, 0, 0, 0),
            "OraModifica": time(16, 57, 56),
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2026, 8, 12, 16, 57, 56))

    def test_clienti_midnight_timestamp_with_ora(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        row = {
            "DataModifica": datetime(2026, 7, 27, 0, 0, 0),
            "OraModifica": time(14, 15, 30),
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2026, 7, 27, 14, 15, 30))

    def test_fornitori_midnight_timestamp_with_ora(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        row = {
            "DataModifica": datetime(2026, 1, 5, 0, 0, 0),
            "OraModifica": time(9, 45, 0),
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2026, 1, 5, 9, 45, 0))

    def test_gruppo_cli_for_interval_ora(self):
        """OraModifica ODBC INTERVAL arriva come timedelta."""
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        row = {
            "DataModifica": datetime(2026, 8, 12, 0, 0, 0),
            "OraModifica": timedelta(hours=16, minutes=57, seconds=56),
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2026, 8, 12, 16, 57, 56))

    def test_null_ora_uses_data_only(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        row = {
            "DataModifica": datetime(2026, 8, 12, 11, 22, 33),
            "OraModifica": None,
        }
        dt = parse_4d_modifica(row, spec=spec)
        self.assertEqual(dt, datetime(2026, 8, 12, 11, 22, 33))

    def test_is_newer_than_watermark_filters_equal_row(self):
        """DestCliFor: DataModifica date + OraModifica — non riprocessare watermark attuale."""
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        wm = datetime(2026, 8, 13, 19, 32, 36)
        same = {
            "DataModifica": date(2026, 8, 13),
            "OraModifica": time(19, 32, 36),
        }
        newer = {
            "DataModifica": date(2026, 8, 13),
            "OraModifica": time(19, 32, 37),
        }
        older = {
            "DataModifica": date(2026, 8, 13),
            "OraModifica": time(19, 32, 35),
        }
        self.assertFalse(is_newer_than_watermark(same, spec=spec, watermark=wm))
        self.assertTrue(is_newer_than_watermark(newer, spec=spec, watermark=wm))
        self.assertFalse(is_newer_than_watermark(older, spec=spec, watermark=wm))
        self.assertTrue(is_newer_than_watermark(same, spec=spec, watermark=None))


class BuildIncrementalWhereTests(SimpleTestCase):
    def test_split_where_date_and_time(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="date",
        )
        wm = datetime(2024, 3, 15, 10, 30, 0)
        clause = build_incremental_where(spec, wm)
        self.assertIn("[DataModifica]", clause)
        self.assertIn("[OraModifica]", clause)
        self.assertIn("{d '2024-03-15'}", clause)
        self.assertIn("{t '10:30:00'}", clause)

    def test_clienti_timestamp_data_with_ora(self):
        """Clienti: TIMESTAMP+INTERVAL — no {t} on OraModifica (ODBC 1108)."""
        cols = [
            {"name": "Codice", "pg_type": "text"},
            {"name": "DataModifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
            {"name": "OraModifica", "type_name": "INTERVAL", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols, source_table="Clienti")
        assert spec is not None
        wm = datetime(2026, 7, 27, 14, 15, 30)
        clause = build_incremental_where(spec, wm)
        self.assertEqual(clause, "[DataModifica] >= {ts '2026-07-27 00:00:00'}")
        self.assertNotIn("[OraModifica]", clause)
        self.assertNotIn("{t '", clause)
        self.assertNotIn("{d '", clause)

    def test_fornitori_timestamp_with_ora_no_t_literal(self):
        """Fornitori: same as Clienti — {ts} date-floor only, no {t} (ODBC 1108)."""
        cols = [
            {"name": "Codice", "pg_type": "text"},
            {"name": "DataModifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
            {"name": "OraModifica", "type_name": "INTERVAL", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols, source_table="Fornitori")
        assert spec is not None
        wm = datetime(2026, 1, 5, 9, 45, 0)
        clause = build_incremental_where(spec, wm)
        self.assertEqual(clause, "[DataModifica] >= {ts '2026-01-05 00:00:00'}")
        self.assertNotIn("[OraModifica]", clause)
        self.assertNotIn("{t '", clause)

    def test_fornitori_timestamp_only(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col=None,
            data_pg_type="timestamp",
        )
        clause = build_incremental_where(spec, datetime(2026, 7, 20, 0, 0, 0))
        self.assertEqual(
            clause,
            "[DataModifica] > {ts '2026-07-20 00:00:00'}",
        )

    def test_single_where(self):
        spec = ModificaColumnSpec(mode="single", single_col="DataOraModifica")
        clause = build_incremental_where(spec, datetime(2024, 1, 1, 8, 0, 0))
        self.assertIn("[DataOraModifica] > {ts '2024-01-01 08:00:00'}", clause)

    def test_gruppo_cli_for_timestamp_data_with_ora(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        wm = datetime(2026, 8, 12, 14, 30, 0)
        clause = build_incremental_where(spec, wm)
        self.assertEqual(clause, "[DataModifica] >= {ts '2026-08-12 00:00:00'}")
        self.assertNotIn("[OraModifica]", clause)
        self.assertNotIn("{t '", clause)
        self.assertNotIn("{d '", clause)

    def test_azienda_odbc_timestamp_uses_ts_not_date(self):
        """Azienda: TIMESTAMP + INTERVAL OraModifica → {ts} date-floor, no {t}/{d}."""
        cols = [
            {"name": "ID", "pg_type": "integer"},
            {"name": "DataModifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
            {"name": "OraModifica", "type_name": "INTERVAL", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols, source_table="Azienda")
        assert spec is not None
        wm = datetime(2026, 8, 12, 16, 57, 56)
        clause = build_incremental_where(spec, wm)
        self.assertEqual(clause, "[DataModifica] >= {ts '2026-08-12 00:00:00'}")
        self.assertNotIn("[OraModifica]", clause)
        self.assertNotIn("{t '", clause)
        self.assertNotIn("{d '", clause)

    def test_azienda_true_date_uses_split_where(self):
        """When ODBC reports DATE, split {d}/{t} WHERE is valid."""
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="date",
        )
        wm = datetime(2026, 8, 12, 14, 30, 0)
        clause = build_incremental_where(spec, wm)
        self.assertIn("[DataModifica]", clause)
        self.assertIn("[OraModifica]", clause)
        self.assertIn("{d '2026-08-12'}", clause)
        self.assertIn("{t '14:30:00'}", clause)
        self.assertNotIn("{ts '", clause)


class EnsureModificaColumnsTests(SimpleTestCase):
    def test_azienda_override_injects_missing_columns(self):
        cols = [{"name": "ID", "pg_type": "integer"}]
        spec = detect_modifica_columns(cols, source_table="Azienda")
        assert spec is not None
        merged = ensure_modifica_columns_in_list(cols, spec)
        names = {col["name"] for col in merged}
        self.assertEqual(names, {"ID", "DataModifica", "OraModifica"})


class WatermarkMessageTests(SimpleTestCase):
    def test_incremental_message_with_since(self):
        msg = format_incremental_message(
            142,
            since=datetime(2024, 3, 15, 10, 30, 0),
        )
        self.assertIn("142 righe aggiornate", msg)
        self.assertIn("2024-03-15 10:30:00", msg)

    def test_full_message(self):
        msg = format_incremental_message(10, since=None, full=True)
        self.assertIn("Sincronizzazione completa", msg)

    def test_fallback_full_message_legacy(self):
        msg = format_incremental_message(10, since=None, fallback_full=True)
        self.assertIn("colonne modifica assenti o primo import", msg)

    def test_fallback_first_import_message(self):
        msg = format_incremental_message(
            1,
            since=None,
            fallback_full=True,
            fallback_reason="first_import",
        )
        self.assertIn("primo import", msg)
        self.assertIn("watermark assente", msg)
        self.assertNotIn("colonne modifica assenti", msg)

    def test_fallback_no_modifica_columns_message(self):
        msg = format_incremental_message(
            1,
            since=None,
            fallback_full=True,
            fallback_reason="no_modifica_columns",
        )
        self.assertIn("colonne modifica assenti", msg)
        self.assertNotIn("primo import", msg)

    def test_fallback_modifica_values_empty_message(self):
        msg = format_incremental_message(
            1,
            since=None,
            fallback_full=True,
            fallback_reason="modifica_values_empty",
        )
        self.assertIn("colonne modifica senza valori utilizzabili", msg)
        self.assertNotIn("watermark assente", msg)

    def test_pk_incremental_message(self):
        msg = format_incremental_message(
            42,
            since=None,
            pk_incremental=True,
        )
        self.assertIn("incrementale per ID", msg)
        self.assertIn("42", msg)

    def test_azienda_first_import_not_missing_columns(self):
        """Con colonne rilevate ma senza watermark il messaggio non parla di colonne assenti."""
        cols = [
            {"name": "ID", "pg_type": "integer"},
            {"name": "DataModifica", "pg_type": "timestamp"},
            {"name": "OraModifica", "pg_type": "time"},
        ]
        spec = detect_modifica_columns(cols, source_table="Azienda")
        self.assertIsNotNone(spec)
        msg = format_incremental_message(
            1,
            since=None,
            fallback_full=True,
            fallback_reason="first_import" if spec is not None else "no_modifica_columns",
        )
        self.assertIn("primo import", msg)
        self.assertNotIn("colonne modifica assenti", msg)


class AziendaWatermarkUpdateTests(SimpleTestCase):
    def test_max_modifica_sets_watermark_for_split_date_ora(self):
        spec = detect_modifica_columns(
            [
                {"name": "ID", "pg_type": "integer"},
                {"name": "DataModifica", "type_name": "DATE", "pg_type": "date"},
                {"name": "OraModifica", "type_name": "TIME", "pg_type": "time"},
            ],
            source_table="Azienda",
        )
        assert spec is not None
        rows = [
            {
                "ID": 1,
                "DataModifica": date(2026, 8, 12),
                "OraModifica": time(16, 57, 56),
            }
        ]
        batch_max = max_modifica_from_rows(rows, spec=spec)
        self.assertEqual(batch_max, datetime(2026, 8, 12, 16, 57, 56))


class SplitTableWatermarkTests(SimpleTestCase):
    """Watermark con ora per tabelle split DataModifica + OraModifica."""

    def _timestamp_spec(self, source_table: str) -> ModificaColumnSpec:
        spec = detect_modifica_columns(
            [
                {"name": "Codice", "pg_type": "text"},
                {"name": "DataModifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
                {"name": "OraModifica", "type_name": "INTERVAL", "pg_type": "time"},
            ],
            source_table=source_table,
        )
        assert spec is not None
        return spec

    def test_clienti_watermark_includes_ora(self):
        spec = self._timestamp_spec("Clienti")
        batch_max = max_modifica_from_rows(
            [
                {
                    "DataModifica": datetime(2026, 7, 27, 0, 0, 0),
                    "OraModifica": time(14, 15, 30),
                }
            ],
            spec=spec,
        )
        self.assertEqual(batch_max, datetime(2026, 7, 27, 14, 15, 30))

    def test_fornitori_watermark_includes_ora(self):
        spec = self._timestamp_spec("Fornitori")
        batch_max = max_modifica_from_rows(
            [
                {
                    "DataModifica": datetime(2026, 1, 5, 0, 0, 0),
                    "OraModifica": time(9, 45, 0),
                }
            ],
            spec=spec,
        )
        self.assertEqual(batch_max, datetime(2026, 1, 5, 9, 45, 0))

    def test_gruppo_cli_for_watermark_includes_ora(self):
        spec = self._timestamp_spec("Gruppo_Cli_For")
        batch_max = max_modifica_from_rows(
            [
                {
                    "DataModifica": datetime(2026, 8, 12, 0, 0, 0),
                    "OraModifica": timedelta(hours=16, minutes=57, seconds=56),
                }
            ],
            spec=spec,
        )
        self.assertEqual(batch_max, datetime(2026, 8, 12, 16, 57, 56))

    def test_azienda_timestamp_watermark_includes_ora(self):
        spec = self._timestamp_spec("Azienda")
        batch_max = max_modifica_from_rows(
            [
                {
                    "DataModifica": datetime(2026, 8, 12, 0, 0, 0),
                    "OraModifica": time(16, 57, 56),
                }
            ],
            spec=spec,
        )
        self.assertEqual(batch_max, datetime(2026, 8, 12, 16, 57, 56))


class NaiveDatetimeNormalizationTests(SimpleTestCase):
    """USE_TZ may yield aware watermarks; ODBC modifica is naive local."""

    def test_as_naive_strips_aware(self):
        aware = timezone.make_aware(datetime(2024, 3, 15, 10, 30, 0))
        naive = _as_naive(aware)
        self.assertIsNotNone(naive)
        assert naive is not None
        self.assertIsNone(naive.tzinfo)
        self.assertEqual(naive, datetime(2024, 3, 15, 10, 30, 0))

    def test_as_naive_passthrough_naive(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, 123456)
        self.assertEqual(_as_naive(dt), datetime(2024, 3, 15, 10, 30, 0))

    def test_as_naive_none(self):
        self.assertIsNone(_as_naive(None))

    def test_compare_aware_watermark_with_naive_odbc_batch(self):
        """Mirrors sync_4d watermark update: must not raise TypeError."""
        aware_wm = timezone.make_aware(datetime(2026, 7, 1, 12, 0, 0))
        spec = detect_modifica_columns(
            [
                {"name": "Codice", "pg_type": "text"},
                {"name": "DataModifica", "type_name": "TIMESTAMP", "pg_type": "timestamp"},
                {"name": "OraModifica", "type_name": "INTERVAL", "pg_type": "time"},
            ],
            source_table="Clienti",
        )
        assert spec is not None
        batch_max = max_modifica_from_rows(
            [
                {
                    "DataModifica": datetime(2026, 7, 27, 0, 0, 0),
                    "OraModifica": time(14, 15, 30),
                }
            ],
            spec=spec,
        )
        wm = _as_naive(aware_wm)
        self.assertIsNotNone(batch_max)
        self.assertIsNotNone(wm)
        assert batch_max is not None and wm is not None
        # Must not raise TypeError: can't compare offset-naive and offset-aware
        self.assertTrue(batch_max > wm)

    def test_build_where_accepts_aware_watermark(self):
        spec = ModificaColumnSpec(
            mode="split",
            data_col="DataModifica",
            ora_col="OraModifica",
            data_pg_type="timestamp",
        )
        aware = timezone.make_aware(datetime(2026, 7, 27, 14, 15, 30))
        clause = build_incremental_where(spec, aware)
        self.assertEqual(clause, "[DataModifica] >= {ts '2026-07-27 00:00:00'}")

    @override_settings(USE_TZ=True)
    def test_format_message_with_aware_since(self):
        aware = timezone.make_aware(datetime(2024, 3, 15, 10, 30, 0))
        msg = format_incremental_message(5, since=aware)
        self.assertIn("2024-03-15 10:30:00", msg)
        self.assertNotIn("+", msg)

    def test_parse_4d_modifica_strips_aware_single(self):
        spec = ModificaColumnSpec(mode="single", single_col="DataOraModifica")
        aware = timezone.make_aware(datetime(2024, 5, 1, 8, 0, 0))
        dt = parse_4d_modifica({"DataOraModifica": aware}, spec=spec)
        self.assertEqual(dt, datetime(2024, 5, 1, 8, 0, 0))
        assert dt is not None
        self.assertIsNone(dt.tzinfo)
