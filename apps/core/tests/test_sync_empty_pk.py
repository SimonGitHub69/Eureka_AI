"""Skip delle righe 4D senza PK/codice in sync_table (senza database)."""

from django.test import SimpleTestCase

from apps.core.sync_4d import (
    _format_empty_pk_skip_message,
    is_empty_pk_value,
    keep_rows_with_pk,
    pk_column_index,
)


class IsEmptyPkValueTests(SimpleTestCase):
    def test_none_and_blank_strings(self):
        self.assertTrue(is_empty_pk_value(None))
        self.assertTrue(is_empty_pk_value(""))
        self.assertTrue(is_empty_pk_value("   "))
        self.assertTrue(is_empty_pk_value("\t\n"))
        self.assertTrue(is_empty_pk_value(b""))
        self.assertTrue(is_empty_pk_value(b"  "))

    def test_valid_keys_are_kept(self):
        self.assertFalse(is_empty_pk_value("AA"))
        self.assertFalse(is_empty_pk_value("0"))
        self.assertFalse(is_empty_pk_value(0))
        self.assertFalse(is_empty_pk_value(12))
        self.assertFalse(is_empty_pk_value("  BA"))


class KeepRowsWithPkTests(SimpleTestCase):
    def test_skips_empty_codice_keeps_valid(self):
        columns = [{"name": "Codice"}, {"name": "Descrizione"}]
        pk_idx = pk_column_index(columns, "Codice", source="Magazzini")
        rows = [
            ("", "vuoto"),
            (None, "null"),
            ("   ", "spazi"),
            ("AA", "ACCESSORI"),
            ("AB", "ABBIGLIAMENTO"),
        ]
        kept, skipped = keep_rows_with_pk(rows, pk_idx)
        self.assertEqual(skipped, 3)
        self.assertEqual([row[0] for row in kept], ["AA", "AB"])

    def test_all_valid(self):
        kept, skipped = keep_rows_with_pk([("Z1", "ok"), (1, "id")], 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(len(kept), 2)

    def test_missing_pk_column_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            pk_column_index([{"name": "Descrizione"}], "Codice", source="Magazzini")
        self.assertIn("Codice", str(ctx.exception))
        self.assertIn("Magazzini", str(ctx.exception))


class EmptyPkSkipMessageTests(SimpleTestCase):
    def test_none_when_nothing_skipped(self):
        self.assertEqual(_format_empty_pk_skip_message(0, 0), "")

    def test_skipped_and_purged(self):
        self.assertIn("1 riga senza chiave/codice ignorata", _format_empty_pk_skip_message(1))
        self.assertIn("2 righe senza chiave/codice ignorate", _format_empty_pk_skip_message(2))
        msg = _format_empty_pk_skip_message(1, purged=1)
        self.assertIn("ignorata", msg)
        self.assertIn("rimossa da PostgreSQL", msg)
