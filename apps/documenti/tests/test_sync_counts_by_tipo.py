"""Conteggi teste/righe per tipologia nel messaggio sync documenti."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.programma import DOC_MENU_FIELDS
from apps.documenti.sync import (
    DocTableSyncResult,
    format_counts_by_tipo,
    sync_documenti,
)


def _cfg(**flags):
    defaults = dict.fromkeys(DOC_MENU_FIELDS.values(), True)
    defaults.update(flags)
    return SimpleNamespace(**defaults)


class FormatCountsByTipoTests(SimpleTestCase):
    def test_empty(self):
        self.assertEqual(format_counts_by_tipo({}, {}), "")

    def test_sorted_lines_with_missing_side(self):
        text = format_counts_by_tipo({"ORV": 10, "DDT": 2}, {"ORV": 40})
        self.assertEqual(
            text,
            "DDT: 2 teste / 0 righe\nORV: 10 teste / 40 righe",
        )


class SyncDocumentiCountsByTipoTests(SimpleTestCase):
    @patch("apps.documenti.sync._append_porto_lookup")
    @patch("apps.documenti.sync.ensure_documenti_tables")
    @patch("apps.core.programma.get_configurazione_programma")
    @patch("apps.documenti.sync.sync_detail_source")
    @patch("apps.documenti.sync.sync_header_source")
    def test_summary_message_lists_per_tipo(
        self, mock_header, mock_detail, mock_cfg, _mock_ensure, _mock_porto
    ):
        mock_cfg.return_value = _cfg()
        mock_header.side_effect = [
            DocTableSyncResult(
                source="Ordini_Vendita",
                target="teste_documenti",
                rows=3,
                rows_by_tipo={"ORV": 3},
                message="hdr ORV",
            ),
            DocTableSyncResult(
                source="Bolle",
                target="teste_documenti",
                rows=1,
                rows_by_tipo={"DDT": 1},
                message="hdr DDT",
            ),
        ]
        mock_detail.side_effect = [
            DocTableSyncResult(
                source="Ordini_Vendita_Dettaglio",
                target="righe_documenti",
                rows=9,
                rows_by_tipo={"ORV": 9},
                message="det ORV",
            ),
            DocTableSyncResult(
                source="Bolle_Dettaglio",
                target="righe_documenti",
                rows=4,
                rows_by_tipo={"DDT": 4},
                message="det DDT",
            ),
        ]

        result = sync_documenti(only=["ORV", "DDT"], full=True)

        self.assertTrue(result.ok)
        self.assertEqual(result.teste_count, 4)
        self.assertEqual(result.righe_count, 13)
        self.assertEqual(result.teste_by_tipo, {"ORV": 3, "DDT": 1})
        self.assertEqual(result.righe_by_tipo, {"ORV": 9, "DDT": 4})
        self.assertIn("4 testate, 13 righe", result.message)
        self.assertIn("DDT: 1 teste / 4 righe", result.message)
        self.assertIn("ORV: 3 teste / 9 righe", result.message)
