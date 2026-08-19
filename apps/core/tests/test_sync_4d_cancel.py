"""Test interruzione sync 4D completo (wizard parametri/4d)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.core import views as core_views
from apps.core.views import Sync4DCancelView, _run_sync_4d_task, _sync_4d_cancel_requested


class Sync4DCancelViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)
        core_views._SYNC_4D_TASKS.clear()

    @patch.object(Sync4DCancelView, "has_permission", return_value=True)
    def test_cancel_sets_flag_on_running_task(self, _mock_perm):
        core_views._SYNC_4D_TASKS["abc123"] = {
            "id": "abc123",
            "status": "running",
            "cancel_requested": False,
            "message": "",
        }

        request = self.factory.post(
            "/parametri/4d/sync-all/cancel/",
            {"task_id": "abc123"},
        )
        request.user = self.user

        response = Sync4DCancelView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        task = core_views._SYNC_4D_TASKS["abc123"]
        self.assertTrue(task["cancel_requested"])
        self.assertTrue(task.get("cancel_requested_at"))
        self.assertIn("Interruzione richiesta", task["message"])

    @patch.object(Sync4DCancelView, "has_permission", return_value=True)
    def test_cancel_not_found_when_task_missing(self, _mock_perm):
        request = self.factory.post(
            "/parametri/4d/sync-all/cancel/",
            {"task_id": "missing"},
        )
        request.user = self.user

        response = Sync4DCancelView.as_view()(request)

        self.assertEqual(response.status_code, 404)

    @patch.object(Sync4DCancelView, "has_permission", return_value=True)
    def test_cancel_not_found_when_task_not_running(self, _mock_perm):
        core_views._SYNC_4D_TASKS["done123"] = {
            "id": "done123",
            "status": "done",
            "cancel_requested": False,
            "message": "",
        }

        request = self.factory.post(
            "/parametri/4d/sync-all/cancel/",
            {"task_id": "done123"},
        )
        request.user = self.user

        response = Sync4DCancelView.as_view()(request)

        self.assertEqual(response.status_code, 404)


    def test_run_task_exception_marks_error_not_stuck_running(self):
        task_id = "boom"
        core_views._SYNC_4D_TASKS[task_id] = {
            "id": task_id,
            "status": "pending",
            "progress_pct": 0,
            "current_step": "",
            "started_at": "",
            "finished_at": "",
            "message": "",
            "cancel_requested": False,
            "selected_steps": ["a"],
            "documenti_tipos": [],
            "documenti_from_mirror": False,
            "sync_full": False,
            "steps": [
                {
                    "key": "a",
                    "label": "A",
                    "description": "",
                    "status": "pending",
                    "message": "",
                    "rows": {},
                }
            ],
            "counts_before": {},
            "counts_after": {},
            "errors": [],
        }

        def boom_runner(**kwargs):
            raise RuntimeError("ODBC dead")

        steps = (
            {
                "key": "a",
                "label": "A",
                "description": "",
                "runner": boom_runner,
                "tables": (),
            },
        )
        with patch.object(core_views, "SYNC_4D_STEPS", steps):
            with patch.object(core_views, "_sync_4d_counts", return_value={}):
                _run_sync_4d_task(task_id)

        task = core_views._SYNC_4D_TASKS[task_id]
        self.assertEqual(task["status"], "error")
        self.assertIn("ODBC dead", task["message"])
        self.assertTrue(task["finished_at"])


class Sync4DTaskCancelLoopTests(SimpleTestCase):
    def setUp(self):
        core_views._SYNC_4D_TASKS.clear()

    def test_cancel_requested_helper(self):
        core_views._SYNC_4D_TASKS["t1"] = {"cancel_requested": True}
        self.assertTrue(_sync_4d_cancel_requested("t1"))
        self.assertFalse(_sync_4d_cancel_requested("missing"))

    @patch("apps.core.views._sync_4d_counts", return_value={})
    @patch("apps.core.views.timezone")
    def test_run_task_stops_before_next_step_when_cancelled(
        self, mock_timezone, _mock_counts
    ):
        mock_timezone.now.return_value.isoformat.return_value = "2026-01-01T00:00:00"

        runner_one = MagicMock()
        runner_two = MagicMock()
        steps = (
            {
                "key": "step1",
                "label": "Step 1",
                "description": "",
                "runner": runner_one,
                "tables": ("t1",),
            },
            {
                "key": "step2",
                "label": "Step 2",
                "description": "",
                "runner": runner_two,
                "tables": ("t2",),
            },
        )

        task_id = "cancel-me"
        core_views._SYNC_4D_TASKS[task_id] = {
            "id": task_id,
            "status": "pending",
            "progress_pct": 0,
            "current_step": "",
            "message": "",
            "cancel_requested": False,
            "selected_steps": ["step1", "step2"],
            "documenti_tipos": [],
            "documenti_from_mirror": False,
            "steps": [
                {
                    "key": "step1",
                    "label": "Step 1",
                    "description": "",
                    "status": "pending",
                    "message": "",
                    "rows": {},
                },
                {
                    "key": "step2",
                    "label": "Step 2",
                    "description": "",
                    "status": "pending",
                    "message": "",
                    "rows": {},
                },
            ],
            "counts_before": {},
            "counts_after": {},
            "errors": [],
        }

        with patch.object(core_views, "SYNC_4D_STEPS", steps):
            runner_one.return_value = MagicMock(
                ok=True,
                tables=[],
                message="step1 ok",
            )
            core_views._SYNC_4D_TASKS[task_id]["cancel_requested"] = True
            _run_sync_4d_task(task_id)

        runner_one.assert_not_called()
        runner_two.assert_not_called()
        task = core_views._SYNC_4D_TASKS[task_id]
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(task["steps"][0]["status"], "error")
        self.assertEqual(task["steps"][1]["status"], "pending")
