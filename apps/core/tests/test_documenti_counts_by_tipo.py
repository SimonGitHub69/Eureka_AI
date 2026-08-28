"""Conteggi teste/righe documenti per tipologia nella card Sync 4D."""

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core import views as core_views


class DocumentiCountsByTipoTests(SimpleTestCase):
    @patch("apps.documenti.models.RigaDocumento.objects")
    @patch("apps.documenti.models.TestaDocumento.objects")
    def test_aggregates_teste_and_righe(self, mock_teste, mock_righe):
        mock_teste.values.return_value.annotate.return_value = [
            {"tipo_doc_id": "ORV", "c": 10},
            {"tipo_doc_id": "DDT", "c": 3},
        ]
        mock_righe.values.return_value.annotate.return_value = [
            {"testa__tipo_doc_id": "ORV", "c": 40},
            {"testa__tipo_doc_id": "FAT", "c": 7},
        ]

        result = core_views._documenti_counts_by_tipo()

        self.assertEqual(result["ORV"], {"teste": 10, "righe": 40})
        self.assertEqual(result["DDT"], {"teste": 3, "righe": 0})
        self.assertEqual(result["FAT"], {"teste": 0, "righe": 7})

    def test_set_task_counts_updates_both(self):
        task = {}
        with (
            patch.object(core_views, "_sync_4d_counts", return_value={"teste_documenti": 1}),
            patch.object(
                core_views,
                "_documenti_counts_by_tipo",
                return_value={"ORV": {"teste": 2, "righe": 5}},
            ),
        ):
            core_views._set_task_counts(task)

        self.assertEqual(task["counts_after"], {"teste_documenti": 1})
        self.assertEqual(task["documenti_counts_by_tipo"]["ORV"]["righe"], 5)
