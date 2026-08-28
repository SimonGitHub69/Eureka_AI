"""Test bridge mirror fatture → documenti unificati."""

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.documenti.bridge import (
    FattureMirrorUnavailable,
    sync_fatture_mirror_to_unified,
)


class SyncFattureMirrorToUnifiedTests(SimpleTestCase):
    @patch("apps.documenti.bridge.is_documento_menu_enabled", return_value=True)
    @patch("apps.documenti.bridge.fatture_mirror_available", return_value=False)
    def test_raises_when_mirror_tables_missing(self, _avail, _enabled):
        with self.assertRaises(FattureMirrorUnavailable) as ctx:
            sync_fatture_mirror_to_unified()
        self.assertIn("fatture", str(ctx.exception))

    @patch("apps.documenti.bridge.is_documento_menu_enabled", return_value=False)
    def test_no_enabled_tipos_returns_zero(self, _enabled):
        self.assertEqual(sync_fatture_mirror_to_unified(), (0, 0))
