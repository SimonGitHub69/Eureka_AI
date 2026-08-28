"""Test azzeramento tabelle mirror Sync 4D."""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from apps.core import views as core_views
from apps.core.views import (
    Sync4DClearView,
    _expire_stale_sync_4d_tasks_locked,
    _mark_sync_4d_task_stale_locked,
)


class Sync4DClearViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)
        core_views._SYNC_4D_TASKS.clear()

    def _post_clear(self):
        request = self.factory.post("/parametri/4d/sync-all/clear/")
        request.user = self.user
        return Sync4DClearView.as_view()(request)

    @staticmethod
    def _payload(response):
        return json.loads(response.content.decode())

    @patch.object(Sync4DClearView, "has_permission", return_value=True)
    @patch.object(core_views, "clear_all_watermarks", return_value=3)
    @patch.object(
        core_views,
        "_clear_mirror_4d_tables",
        return_value=(["clienti", "teste_documenti"], []),
    )
    @patch.object(core_views, "_pg_table_count", return_value=0)
    def test_clear_ok_drops_tables_and_watermarks(
        self, _count, _clear_tables, mock_wm, _perm
    ):
        response = self._post_clear()
        self.assertEqual(response.status_code, 200)
        payload = self._payload(response)
        self.assertTrue(payload["ok"])
        self.assertIn("Azzerate", payload["message"])
        self.assertEqual(payload["cleared"], ["clienti", "teste_documenti"])
        mock_wm.assert_called_once_with()

    @patch.object(Sync4DClearView, "has_permission", return_value=True)
    def test_clear_blocked_by_running_task(self, _perm):
        core_views._SYNC_4D_TASKS["live"] = {
            "id": "live",
            "status": "running",
            "started_at": timezone.now().isoformat(),
            "cancel_requested": False,
            "cancel_requested_at": "",
            "message": "in corso",
            "errors": [],
            "steps": [],
        }
        response = self._post_clear()
        self.assertEqual(response.status_code, 409)
        payload = self._payload(response)
        self.assertFalse(payload["ok"])
        self.assertIn("sincronizzazione in corso", payload["error"].lower())
        self.assertEqual(payload["task_id"], "live")

    @patch.object(Sync4DClearView, "has_permission", return_value=True)
    @patch.object(core_views, "clear_all_watermarks", return_value=0)
    @patch.object(core_views, "_clear_mirror_4d_tables", return_value=([], []))
    @patch.object(core_views, "_pg_table_count", return_value=0)
    def test_clear_allowed_after_stale_running_task_expired(
        self, _count, _clear_tables, _wm, _perm
    ):
        stale_start = (
            timezone.now() - core_views._SYNC_4D_STALE_AFTER - timedelta(minutes=1)
        ).isoformat()
        core_views._SYNC_4D_TASKS["stuck"] = {
            "id": "stuck",
            "status": "running",
            "started_at": stale_start,
            "cancel_requested": False,
            "cancel_requested_at": "",
            "message": "appeso",
            "errors": [],
            "steps": [{"key": "articoli", "status": "running", "message": ""}],
        }
        response = self._post_clear()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._payload(response)["ok"])
        self.assertEqual(core_views._SYNC_4D_TASKS["stuck"]["status"], "error")

    @patch.object(Sync4DClearView, "has_permission", return_value=True)
    @patch.object(core_views, "clear_all_watermarks", return_value=0)
    @patch.object(core_views, "_clear_mirror_4d_tables", return_value=([], []))
    @patch.object(core_views, "_pg_table_count", return_value=0)
    def test_clear_allowed_after_cancel_stale(
        self, _count, _clear_tables, _wm, _perm
    ):
        started = timezone.now().isoformat()
        cancel_at = (
            timezone.now()
            - core_views._SYNC_4D_CANCEL_STALE_AFTER
            - timedelta(seconds=30)
        ).isoformat()
        core_views._SYNC_4D_TASKS["cancelstuck"] = {
            "id": "cancelstuck",
            "status": "running",
            "started_at": started,
            "cancel_requested": True,
            "cancel_requested_at": cancel_at,
            "message": "Interruzione richiesta",
            "errors": [],
            "steps": [{"key": "documenti", "status": "running", "message": ""}],
        }
        response = self._post_clear()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._payload(response)["ok"])
        self.assertEqual(core_views._SYNC_4D_TASKS["cancelstuck"]["status"], "error")

    @patch.object(Sync4DClearView, "has_permission", return_value=True)
    @patch.object(core_views, "clear_all_watermarks", return_value=0)
    @patch.object(
        core_views,
        "_clear_mirror_4d_tables",
        return_value=(["clienti"], ["fornitori: permission denied"]),
    )
    @patch.object(core_views, "_pg_table_count", return_value=0)
    def test_clear_partial_drop_returns_500(self, _count, _clear, _wm, _perm):
        response = self._post_clear()
        self.assertEqual(response.status_code, 500)
        payload = self._payload(response)
        self.assertFalse(payload["ok"])
        self.assertIn("incompleto", payload["error"].lower())


class Sync4DStaleHelpersTests(SimpleTestCase):
    def setUp(self):
        core_views._SYNC_4D_TASKS.clear()

    def test_expire_marks_old_running_task(self):
        started = (timezone.now() - timedelta(hours=3)).isoformat()
        core_views._SYNC_4D_TASKS["t"] = {
            "id": "t",
            "status": "running",
            "started_at": started,
            "cancel_requested": False,
            "errors": [],
            "steps": [{"key": "x", "status": "running", "message": ""}],
        }
        with core_views._SYNC_4D_LOCK:
            expired = _expire_stale_sync_4d_tasks_locked()
        self.assertEqual(expired, ["t"])
        self.assertEqual(core_views._SYNC_4D_TASKS["t"]["status"], "error")

    def test_mark_stale_ignores_finished(self):
        task = {"id": "d", "status": "done", "steps": []}
        _mark_sync_4d_task_stale_locked(task, "x")
        self.assertEqual(task["status"], "done")

    def test_mirror_tables_include_documenti(self):
        self.assertIn("teste_documenti", core_views.MIRROR_4D_TABLES)
        self.assertIn("righe_documenti", core_views.MIRROR_4D_TABLES)
        self.assertIn("clienti", core_views.MIRROR_4D_TABLES)
        self.assertIn("DestCliFor", core_views.MIRROR_4D_TABLES)
        self.assertIn("tab_porto", core_views.MIRROR_4D_TABLES)
        self.assertIn("movimentit", core_views.MIRROR_4D_TABLES)
        self.assertIn("depositi", core_views.MIRROR_4D_TABLES)

    def test_depositi_is_standalone_sync_step(self):
        keys = {step["key"] for step in core_views.SYNC_4D_STEPS}
        self.assertIn("depositi", keys)
        step = next(s for s in core_views.SYNC_4D_STEPS if s["key"] == "depositi")
        self.assertEqual(step["tables"], ("depositi",))
        self.assertEqual(step["description"], "Depositi")
        keys = {step["key"] for step in core_views.SYNC_4D_STEPS}
        self.assertIn("porto", keys)
        porto = next(s for s in core_views.SYNC_4D_STEPS if s["key"] == "porto")
        self.assertEqual(porto["tables"], ("tab_porto",))
        self.assertEqual(porto["description"], "TabPorto")

    def test_movimenti_is_standalone_sync_step(self):
        keys = {step["key"] for step in core_views.SYNC_4D_STEPS}
        self.assertIn("movimenti", keys)
        step = next(s for s in core_views.SYNC_4D_STEPS if s["key"] == "movimenti")
        self.assertEqual(step["tables"], ("movimentit", "movimentit_dettaglio"))
        self.assertEqual(step["description"], "MovimentiT e MovimentiT_Dettaglio")
