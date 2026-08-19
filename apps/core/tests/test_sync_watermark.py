from datetime import date, datetime, time

from django.test import TestCase
from django.utils import timezone

from apps.core.models import SyncWatermark
from apps.core.sync_incremental import (
    detect_modifica_columns,
    get_watermark,
    max_modifica_from_rows,
    set_watermark,
)


class SyncWatermarkModelTests(TestCase):
    def test_get_set_watermark(self):
        self.assertIsNone(get_watermark("Clienti"))
        dt = datetime(2024, 3, 15, 10, 30, 0)
        set_watermark("Clienti", dt)
        stored = get_watermark("Clienti")
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored, dt)
        self.assertIsNone(stored.tzinfo)

    def test_set_watermark_updates_existing(self):
        set_watermark("Fornitori", datetime(2024, 1, 1, 8, 0, 0))
        set_watermark("Fornitori", datetime(2024, 6, 1, 12, 0, 0))
        self.assertEqual(SyncWatermark.objects.count(), 1)
        wm = get_watermark("Fornitori")
        assert wm is not None
        self.assertEqual(wm.month, 6)

    def test_aware_datetime_normalized(self):
        aware = timezone.make_aware(datetime(2024, 3, 15, 10, 30, 0))
        set_watermark("Agenti", aware)
        wm = get_watermark("Agenti")
        assert wm is not None
        self.assertIsNone(wm.tzinfo)
        self.assertEqual(wm, datetime(2024, 3, 15, 10, 30, 0))

    def test_get_watermark_returns_naive_under_use_tz(self):
        """Django DateTimeField + USE_TZ returns aware; get_watermark must strip."""
        set_watermark("Clienti", datetime(2026, 7, 27, 14, 15, 30))
        raw = SyncWatermark.objects.get(source_table="Clienti").last_modifica
        # ORM value may be aware when USE_TZ=True
        wm = get_watermark("Clienti")
        assert wm is not None
        self.assertIsNone(wm.tzinfo)
        self.assertEqual(wm, datetime(2026, 7, 27, 14, 15, 30))
        # Compare naive ODBC batch_max with watermark (sync_4d path)
        batch_max = datetime(2026, 7, 28, 9, 0, 0)
        self.assertTrue(batch_max > wm)
        if timezone.is_aware(raw):
            # Without _as_naive this comparison would raise TypeError
            with self.assertRaises(TypeError):
                _ = batch_max > raw

    def test_azienda_watermark_from_split_date_ora_rows(self):
        """Dopo import Azienda il watermark deve includere DataModifica + OraModifica."""
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
        assert batch_max is not None
        set_watermark("Azienda", batch_max)
        stored = get_watermark("Azienda")
        assert stored is not None
        self.assertEqual(stored, datetime(2026, 8, 12, 16, 57, 56))
        self.assertIsNone(stored.tzinfo)
        self.assertEqual(SyncWatermark.objects.filter(source_table="Azienda").count(), 1)
