"""Test selezione step sync 4D globale (parametri/4d)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.core import views as core_views
from apps.core.programma import DOC_MENU_FIELDS
from apps.core.views import (
    Sync4DStartView,
    _parse_sync_4d_selection,
    _run_sync_4d_task,
    _sync_4d_documenti_step,
)
from apps.documenti.bridge import FattureMirrorUnavailable


def _cfg(**flags):
    defaults = dict.fromkeys(DOC_MENU_FIELDS.values(), True)
    defaults.update(flags)
    return SimpleNamespace(**defaults)


class ParseSync4DSelectionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_requires_at_least_one_step(self):
        request = self.factory.post("/parametri/4d/sync-all/start/", {})
        steps, tipos, mirror, error = _parse_sync_4d_selection(request)
        self.assertEqual(steps, [])
        self.assertIsNotNone(error)

    def test_accepts_valid_steps(self):
        request = self.factory.post(
            "/parametri/4d/sync-all/start/",
            {"steps": ["anagrafiche", "articoli", "invalid"]},
        )
        steps, tipos, mirror, error = _parse_sync_4d_selection(request)
        self.assertIsNone(error)
        self.assertEqual(steps, ["anagrafiche", "articoli"])

    @patch("apps.core.views.is_documento_menu_enabled", return_value=True)
    def test_documenti_requires_tipo_or_mirror(self, _mock_enabled):
        request = self.factory.post(
            "/parametri/4d/sync-all/start/",
            {"steps": ["documenti"]},
        )
        _, _, _, error = _parse_sync_4d_selection(request)
        self.assertIsNotNone(error)

    @patch("apps.core.views.is_documento_menu_enabled", return_value=True)
    def test_documenti_with_tipos(self, _mock_enabled):
        request = self.factory.post(
            "/parametri/4d/sync-all/start/",
            {"steps": ["documenti"], "tipos": ["ORV", "PRV"]},
        )
        steps, tipos, mirror, error = _parse_sync_4d_selection(request)
        self.assertIsNone(error)
        self.assertEqual(steps, ["documenti"])
        self.assertEqual(tipos, ["ORV", "PRV"])
        self.assertFalse(mirror)

    @patch("apps.core.views.is_documento_menu_enabled", return_value=True)
    def test_documenti_with_prv_only(self, _mock_enabled):
        request = self.factory.post(
            "/parametri/4d/sync-all/start/",
            {"steps": ["documenti"], "tipos": ["PRV"]},
        )
        steps, tipos, mirror, error = _parse_sync_4d_selection(request)
        self.assertIsNone(error)
        self.assertEqual(steps, ["documenti"])
        self.assertEqual(tipos, ["PRV"])
        self.assertFalse(mirror)

    @patch("apps.core.views.is_documento_menu_enabled", return_value=False)
    def test_documenti_mirror_only(self, _mock_enabled):
        request = self.factory.post(
            "/parametri/4d/sync-all/start/",
            {"steps": ["documenti"], "from_fatture_mirror": "on"},
        )
        _, _, mirror, error = _parse_sync_4d_selection(request)
        self.assertIsNone(error)
        self.assertTrue(mirror)


class Sync4DStartViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, username="tester")
        core_views._SYNC_4D_TASKS.clear()

    @patch.object(Sync4DStartView, "has_permission", return_value=True)
    def test_start_rejects_empty_selection(self, _mock_perm):
        request = self.factory.post("/parametri/4d/sync-all/start/", {})
        request.user = self.user
        response = Sync4DStartView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    @patch("apps.core.views.threading.Thread")
    @patch.object(Sync4DStartView, "has_permission", return_value=True)
    def test_start_accepts_selected_steps(self, _mock_perm, mock_thread):
        mock_thread.return_value.start = MagicMock()
        request = self.factory.post(
            "/parametri/4d/sync-all/start/",
            {"steps": ["anagrafiche", "fatture"]},
        )
        request.user = self.user
        response = Sync4DStartView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        task = next(iter(core_views._SYNC_4D_TASKS.values()))
        self.assertEqual(set(task["selected_steps"]), {"anagrafiche", "fatture"})

    @patch("apps.core.views.is_documento_menu_enabled", return_value=True)
    @patch("apps.core.views.threading.Thread")
    @patch.object(Sync4DStartView, "has_permission", return_value=True)
    def test_start_accepts_documenti_prv_only(self, _mock_perm, mock_thread, _mock_enabled):
        mock_thread.return_value.start = MagicMock()
        request = self.factory.post(
            "/parametri/4d/sync-all/start/",
            {"steps": ["documenti"], "tipos": ["PRV"]},
        )
        request.user = self.user
        response = Sync4DStartView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        task = next(iter(core_views._SYNC_4D_TASKS.values()))
        self.assertEqual(task["selected_steps"], ["documenti"])
        self.assertEqual(task["documenti_tipos"], ["PRV"])
        self.assertFalse(task["documenti_from_mirror"])

class Sync4DTaskStepFilterTests(SimpleTestCase):
    def setUp(self):
        core_views._SYNC_4D_TASKS.clear()

    @patch("apps.core.views._sync_4d_counts", return_value={})
    @patch("apps.core.views.timezone")
    def test_run_task_only_selected_steps(self, mock_timezone, _mock_counts):
        mock_timezone.now.return_value.isoformat.return_value = "2026-01-01T00:00:00"

        runner_one = MagicMock(
            return_value=MagicMock(ok=True, tables=[], message="step1 ok")
        )
        runner_two = MagicMock(
            return_value=MagicMock(ok=True, tables=[], message="step2 ok")
        )
        runner_three = MagicMock(
            return_value=MagicMock(ok=True, tables=[], message="step3 ok")
        )
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
            {
                "key": "step3",
                "label": "Step 3",
                "description": "",
                "runner": runner_three,
                "tables": ("t3",),
            },
        )

        task_id = "filter-me"
        core_views._SYNC_4D_TASKS[task_id] = {
            "id": task_id,
            "status": "pending",
            "progress_pct": 0,
            "current_step": "",
            "message": "",
            "cancel_requested": False,
            "selected_steps": ["step1", "step3"],
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
                    "status": "skipped",
                    "message": "Non selezionato.",
                    "rows": {},
                },
                {
                    "key": "step3",
                    "label": "Step 3",
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
            _run_sync_4d_task(task_id)

        runner_one.assert_called_once()
        runner_two.assert_not_called()
        runner_three.assert_called_once()
        task = core_views._SYNC_4D_TASKS[task_id]
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["steps"][1]["status"], "skipped")


class Sync4DDocumentiStepMirrorTests(SimpleTestCase):
    @patch("apps.core.views.ensure_documenti_tables")
    @patch("apps.core.views.fatture_mirror_available", return_value=False)
    @patch("apps.core.views.is_documento_menu_enabled", return_value=True)
    @patch("apps.core.views._sync_4d_cancel_requested", return_value=False)
    @patch("apps.core.views.sync_documenti_as_sync_result")
    @patch("apps.core.views.sync_fatture_mirror_to_unified")
    def test_odbc_succeeds_when_mirror_missing(
        self, mock_bridge, mock_odbc, _cancel, _enabled, _mirror_avail, _ensure
    ):
        mock_odbc.return_value = MagicMock(
            ok=True,
            tables=[],
            message="ODBC ok",
        )
        mock_bridge.side_effect = FattureMirrorUnavailable(
            'Bridge mirror fatture saltato: tabelle "fatture" assenti'
        )

        result = _sync_4d_documenti_step(
            "task-1",
            tipos=["FAT", "ORV"],
            from_mirror=True,
            full=False,
        )

        self.assertTrue(result.ok)
        _ensure.assert_called_once()
        mock_odbc.assert_called_once()
        mock_bridge.assert_called_once()
        self.assertIn("Bridge mirror fatture saltato", result.message)
        self.assertIn("ODBC ok", result.message)

    @patch("apps.core.views.ensure_documenti_tables")
    @patch("apps.core.views.fatture_mirror_available", return_value=False)
    @patch("apps.core.views.is_documento_menu_enabled", return_value=True)
    @patch("apps.core.views._sync_4d_cancel_requested", return_value=False)
    @patch("apps.core.views.sync_documenti_as_sync_result")
    @patch("apps.core.views.sync_fatture_mirror_to_unified")
    def test_mirror_only_falls_back_to_odbc_when_missing(
        self, mock_bridge, mock_odbc, _cancel, _enabled, _mirror_avail, _ensure
    ):
        mock_odbc.return_value = MagicMock(
            ok=True,
            tables=[],
            message="ODBC full ok",
        )
        mock_bridge.side_effect = FattureMirrorUnavailable(
            'Bridge mirror fatture saltato: tabelle "fatture" assenti'
        )

        result = _sync_4d_documenti_step(
            "task-2",
            tipos=[],
            from_mirror=True,
            full=False,
        )

        self.assertTrue(result.ok)
        mock_odbc.assert_called_once()
        self.assertIsNone(mock_odbc.call_args.kwargs.get("only"))
        mock_bridge.assert_called_once()
        self.assertIn("Bridge mirror fatture saltato", result.message)
        self.assertIn("ODBC full ok", result.message)

    @patch("apps.core.views.ensure_documenti_tables")
    @patch("apps.core.views.fatture_mirror_available", return_value=True)
    @patch("apps.core.views.is_documento_menu_enabled", return_value=True)
    @patch("apps.core.views._sync_4d_cancel_requested", return_value=False)
    @patch("apps.core.views.sync_documenti_as_sync_result")
    @patch("apps.core.views.sync_fatture_mirror_to_unified")
    def test_mirror_only_skips_odbc_when_mirror_present(
        self, mock_bridge, mock_odbc, _cancel, _enabled, _mirror_avail, _ensure
    ):
        mock_bridge.return_value = (3, 10)

        result = _sync_4d_documenti_step(
            "task-3",
            tipos=[],
            from_mirror=True,
            full=False,
        )

        self.assertTrue(result.ok)
        mock_odbc.assert_not_called()
        mock_bridge.assert_called_once()
        self.assertIn("Bridge mirror fatture", result.message)