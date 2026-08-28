"""Test selezione multipla sync documenti (CLI, sync, view)."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from apps.core.programma import DOC_MENU_FIELDS
from django.core.management import call_command

from apps.documenti.sync import (
    DocTableSyncResult,
    parse_only_selection,
    sync_documenti,
)
from apps.documenti.views import SyncDocumentiView


def _cfg(**flags):
    defaults = dict.fromkeys(DOC_MENU_FIELDS.values(), True)
    defaults.update(flags)
    return SimpleNamespace(**defaults)


class ParseOnlySelectionTests(SimpleTestCase):
    def test_none_means_all(self):
        self.assertIsNone(parse_only_selection(None))
        self.assertIsNone(parse_only_selection([]))
        self.assertIsNone(parse_only_selection(""))

    def test_single_string(self):
        self.assertEqual(parse_only_selection("ORV"), ["ORV"])

    def test_comma_separated(self):
        self.assertEqual(parse_only_selection("ORV,PRV,DDT"), ["ORV", "PRV", "DDT"])

    def test_multiple_args(self):
        self.assertEqual(parse_only_selection(["ORV", "PRV"]), ["ORV", "PRV"])

    def test_mixed_comma_and_list(self):
        self.assertEqual(parse_only_selection(["ORV,PRV", "DDT"]), ["ORV", "PRV", "DDT"])


class SyncMultipleOnlyTests(SimpleTestCase):
    @patch("apps.documenti.sync.sync_tab_porto")
    @patch("apps.documenti.sync.ensure_documenti_tables")
    @patch("apps.core.programma.get_configurazione_programma")
    @patch("apps.documenti.sync.sync_header_source")
    @patch("apps.documenti.sync.sync_detail_source")
    def test_sync_only_subset_calls_matching_sources(
        self, mock_detail, mock_header, mock_cfg, _mock_ensure, mock_porto
    ):
        mock_cfg.return_value = _cfg()
        ok_result = DocTableSyncResult(source="x", target="y", ok=True, message="ok")
        mock_header.return_value = ok_result
        mock_detail.return_value = ok_result
        mock_porto.return_value = SimpleNamespace(ok=True, tables=[])

        sync_documenti(only=["ORV", "PRV"])

        header_sources = {call.args[0].source for call in mock_header.call_args_list}
        self.assertEqual(header_sources, {"Ordini_Vendita", "Preventivi"})
        detail_sources = {call.args[0].source for call in mock_detail.call_args_list}
        self.assertEqual(detail_sources, {"Ordini_Vendita_Dettaglio", "Preventivi_Dettaglio"})
        _mock_ensure.assert_called_once()


class SyncDocumentiCommandTests(SimpleTestCase):
    @patch("apps.documenti.management.commands.sync_documenti_4d.sync_documenti")
    @patch("apps.documenti.management.commands.sync_documenti_4d.SyncDocumentiLog")
    @patch("apps.core.programma.get_tipi_documento_abilitati")
    def test_command_multiple_only_flags(self, mock_abilitati, mock_log, mock_sync):
        mock_abilitati.return_value = ("ORV", "PRV")
        mock_log.objects.create.return_value = SimpleNamespace(
            save=lambda: None,
            ok=True,
            teste_count=0,
            righe_count=0,
            message="",
            finished_at=None,
        )
        mock_sync.return_value = SimpleNamespace(
            ok=True,
            teste_count=0,
            righe_count=0,
            tables=[],
            message="ok",
        )

        out = StringIO()
        call_command(
            "sync_documenti_4d",
            "--only",
            "ORV",
            "--only",
            "PRV",
            stdout=out,
        )

        mock_sync.assert_called_once_with(batch_size=5000, only=["ORV", "PRV"], full=False)

    @patch("apps.documenti.management.commands.sync_documenti_4d.sync_documenti")
    @patch("apps.documenti.management.commands.sync_documenti_4d.SyncDocumentiLog")
    @patch("apps.core.programma.get_tipi_documento_abilitati")
    def test_command_comma_only(self, mock_abilitati, mock_log, mock_sync):
        mock_abilitati.return_value = ("ORV",)
        mock_log.objects.create.return_value = SimpleNamespace(
            save=lambda: None,
        )
        mock_sync.return_value = SimpleNamespace(
            ok=True,
            teste_count=0,
            righe_count=0,
            tables=[],
            message="ok",
        )

        call_command("sync_documenti_4d", "--only", "ORV,PRV,DDT", stdout=StringIO())

        mock_sync.assert_called_once_with(batch_size=5000, only=["ORV", "PRV", "DDT"], full=False)


class SyncDocumentiViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.documenti.views.threading.Thread")
    @patch("apps.documenti.views.is_documento_menu_enabled", return_value=True)
    @patch("apps.documenti.views.SyncDocumentiLog")
    def test_post_subset_starts_background_sync(
        self, mock_log_model, _mock_enabled, mock_thread
    ):
        mock_log = SimpleNamespace(pk=99, save=lambda: None)
        mock_log_model.objects.create.return_value = mock_log
        mock_log_model.objects.filter.return_value.first.return_value = None

        request = self.factory.post(
            "/parametri/4d/sync-documenti/",
            {"tipos": ["ORV", "PRV"]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user = AnonymousUser()

        view = SyncDocumentiView()
        response = view.post(request)

        self.assertEqual(response.status_code, 200)
        import json

        payload = json.loads(response.content)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["log_id"], 99)
        mock_thread.assert_called_once()

    @patch("apps.documenti.views.messages")
    @patch("apps.documenti.views.SyncDocumentiLog")
    def test_post_empty_shows_validation(self, mock_log_model, _mock_messages):
        request = self.factory.post("/parametri/4d/sync-documenti/", {})
        request.user = AnonymousUser()

        view = SyncDocumentiView()
        with patch("apps.documenti.views.render") as mock_render:
            mock_render.return_value = SimpleNamespace(status_code=200)
            with patch.object(SyncDocumentiView, "get_context", return_value={}):
                view.post(request)

        mock_render.assert_called_once()
        mock_log_model.objects.create.assert_not_called()
