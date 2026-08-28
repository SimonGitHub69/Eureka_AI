"""Test filtro sync documenti per parametri programma."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.programma import (
    DOC_MENU_FIELDS,
    get_tipi_documento_abilitati,
    is_documento_menu_enabled,
    is_tipo_doc_enabled,
)
from apps.documenti.mapping import HEADER_SOURCES
from apps.documenti.sync import (
    _enabled_tipos_for_header_spec,
    _skip_message,
    sync_documenti,
    sync_header_source,
)


def _cfg(**flags):
    defaults = dict.fromkeys(DOC_MENU_FIELDS.values(), True)
    defaults.update(flags)
    return SimpleNamespace(**defaults)


class ProgrammaDocFlagsTests(SimpleTestCase):
    @patch("apps.core.programma.get_configurazione_programma")
    def test_all_enabled_by_default(self, mock_cfg):
        mock_cfg.return_value = _cfg()
        self.assertTrue(is_documento_menu_enabled("ORV"))
        self.assertTrue(is_tipo_doc_enabled("ORV"))
        self.assertEqual(
            set(get_tipi_documento_abilitati()),
            {"PRV", "ORV", "ORA", "DDT", "FAT", "NCR", "NDB"},
        )

    @patch("apps.core.programma.get_configurazione_programma")
    def test_disabled_tipo_not_enabled(self, mock_cfg):
        mock_cfg.return_value = _cfg(doc_orv=False)
        self.assertFalse(is_documento_menu_enabled("ORV"))
        self.assertNotIn("ORV", get_tipi_documento_abilitati())


class SyncSkipLogicTests(SimpleTestCase):
    @patch("apps.core.programma.get_configurazione_programma")
    def test_header_spec_reports_disabled_orv(self, mock_cfg):
        mock_cfg.return_value = _cfg(doc_orv=False)
        spec = next(s for s in HEADER_SOURCES if s.tipo_doc == "ORV")
        self.assertEqual(_enabled_tipos_for_header_spec(spec), ())

    def test_skip_message_format(self):
        msg = _skip_message("Ordini_Vendita", "teste_documenti", ("ORV",))
        self.assertIn("Tipo ORV disabilitato in parametri programma — ignorato", msg)

    @patch("apps.documenti.sync.ensure_documenti_tables")
    @patch("apps.core.programma.get_configurazione_programma")
    @patch("apps.documenti.sync.sync_header_source")
    @patch("apps.documenti.sync.sync_detail_source")
    def test_sync_only_disabled_tipo_skips_odbc(
        self, mock_detail, mock_header, mock_cfg, _mock_ensure
    ):
        mock_cfg.return_value = _cfg(doc_orv=False)
        result = sync_documenti(only="ORV")

        mock_header.assert_not_called()
        mock_detail.assert_not_called()
        self.assertTrue(result.ok)
        self.assertEqual(len(result.tables), 2)
        self.assertIn("ORV disabilitato", result.tables[0].message)
        self.assertEqual(result.teste_count, 0)

    @patch("apps.core.programma.get_configurazione_programma")
    @patch("apps.documenti.sync._fetch_all_rows")
    def test_sync_header_skips_disabled_without_odbc(self, mock_fetch, mock_cfg):
        mock_cfg.return_value = _cfg(doc_orv=False)
        spec = next(s for s in HEADER_SOURCES if s.tipo_doc == "ORV")

        result = sync_header_source(spec)

        mock_fetch.assert_not_called()
        self.assertTrue(result.ok)
        self.assertIn("ORV disabilitato", result.message)
        self.assertEqual(result.rows, 0)
