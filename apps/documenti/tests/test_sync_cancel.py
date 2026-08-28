"""Test interruzione sync documenti."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.documenti.sync import (
    CANCELLED_MESSAGE,
    DocTableSyncResult,
    request_cancel_sync,
    should_cancel_sync,
    sync_documenti,
)
from apps.documenti.views import (
    SyncDocumentiCancelView,
    SyncDocumentiStatusView,
    _sync_documenti_log_snapshot,
)


class SyncCancelFlagTests(SimpleTestCase):
    @patch("apps.documenti.models.SyncDocumentiLog")
    def test_request_cancel_sets_flag_on_running_log(self, mock_log_model):
        mock_qs = MagicMock()
        mock_qs.update.return_value = 1
        mock_log_model.objects.filter.return_value = mock_qs

        self.assertTrue(request_cancel_sync(7))

        mock_log_model.objects.filter.assert_called_once_with(
            pk=7,
            finished_at__isnull=True,
        )
        mock_qs.update.assert_called_once_with(cancel_requested=True)

    @patch("apps.documenti.models.SyncDocumentiLog")
    def test_request_cancel_ignores_finished_log(self, mock_log_model):
        mock_qs = MagicMock()
        mock_qs.update.return_value = 0
        mock_log_model.objects.filter.return_value = mock_qs

        self.assertFalse(request_cancel_sync(7))

    @patch("apps.documenti.models.SyncDocumentiLog")
    def test_should_cancel_sync_reads_flag(self, mock_log_model):
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_log_model.objects.filter.return_value = mock_qs

        self.assertTrue(should_cancel_sync(7))

        mock_log_model.objects.filter.assert_called_once_with(
            pk=7,
            cancel_requested=True,
        )


class SyncDocumentiCancelLoopTests(SimpleTestCase):
    @patch("apps.documenti.sync.sync_tab_porto")
    @patch("apps.documenti.sync.ensure_documenti_tables")
    @patch("apps.core.programma.get_configurazione_programma")
    @patch("apps.documenti.sync.sync_header_source")
    @patch("apps.documenti.sync.sync_detail_source")
    @patch("apps.documenti.sync._is_cancelled")
    def test_sync_stops_when_cancel_flag_set(
        self, mock_is_cancelled, mock_detail, mock_header, mock_cfg, _mock_ensure, mock_porto
    ):
        mock_cfg.return_value = SimpleNamespace(**{f"doc_menu_{k}": True for k in ("ORV", "PRV")})
        mock_is_cancelled.side_effect = [False, True]
        ok_result = DocTableSyncResult(source="x", target="y", ok=True, message="ok")
        mock_header.return_value = ok_result
        mock_porto.return_value = SimpleNamespace(ok=True, tables=[])

        result = sync_documenti(only=["ORV", "PRV"], log_id=42)

        self.assertTrue(result.cancelled)
        self.assertFalse(result.ok)
        self.assertEqual(result.message, CANCELLED_MESSAGE)
        mock_header.assert_called_once()
        mock_detail.assert_not_called()


class SyncDocumentiLogSnapshotTests(SimpleTestCase):
    def test_running_log_status(self):
        log = SimpleNamespace(
            pk=1,
            finished_at=None,
            ok=False,
            cancel_requested=False,
            teste_count=0,
            righe_count=0,
            message="Sync in corso...",
            started_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        )
        snapshot = _sync_documenti_log_snapshot(log)
        self.assertEqual(snapshot["status"], "running")
        self.assertTrue(snapshot["running"])

    def test_cancelled_log_status(self):
        log = SimpleNamespace(
            pk=2,
            finished_at=SimpleNamespace(isoformat=lambda: "2026-01-01T01:00:00"),
            ok=False,
            cancel_requested=True,
            teste_count=3,
            righe_count=5,
            message="Sincronizzazione interrotta dall'utente.",
            started_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        )
        snapshot = _sync_documenti_log_snapshot(log)
        self.assertEqual(snapshot["status"], "cancelled")
        self.assertFalse(snapshot["running"])


class SyncDocumentiStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch.object(SyncDocumentiStatusView, "has_permission", return_value=True)
    @patch("apps.documenti.views.get_object_or_404")
    def test_status_returns_log_snapshot(self, mock_get_log, _mock_perm):
        log = SimpleNamespace(
            pk=9,
            finished_at=None,
            ok=False,
            cancel_requested=True,
            teste_count=1,
            righe_count=2,
            message="Sync in corso...",
            started_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        )
        mock_get_log.return_value = log

        request = self.factory.get("/parametri/4d/sync-documenti/status/9/")
        request.user = SimpleNamespace(is_authenticated=True)

        response = SyncDocumentiStatusView.as_view()(request, log_id=9)

        self.assertEqual(response.status_code, 200)
        import json

        payload = json.loads(response.content)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["log"]["status"], "running")
        self.assertTrue(payload["log"]["cancel_requested"])


class SyncDocumentiCancelViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.documenti.views.request_cancel_sync", return_value=True)
    @patch.object(SyncDocumentiCancelView, "has_permission", return_value=True)
    def test_cancel_endpoint_sets_flag(self, _mock_perm, mock_request_cancel):
        request = self.factory.post(
            "/parametri/4d/sync-documenti/cancel/",
            {"log_id": "7"},
        )
        request.user = self.user

        response = SyncDocumentiCancelView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_request_cancel.assert_called_once_with(7)

    @patch("apps.documenti.views.request_cancel_sync", return_value=False)
    @patch.object(SyncDocumentiCancelView, "has_permission", return_value=True)
    def test_cancel_endpoint_not_found_when_not_running(
        self, _mock_perm, _mock_request_cancel
    ):
        request = self.factory.post(
            "/parametri/4d/sync-documenti/cancel/",
            {"log_id": "7"},
        )
        request.user = self.user

        response = SyncDocumentiCancelView.as_view()(request)

        self.assertEqual(response.status_code, 404)
