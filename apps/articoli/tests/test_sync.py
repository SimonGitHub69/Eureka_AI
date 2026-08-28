"""Config sync Articoli 4D → mirror PostgreSQL."""

from django.test import SimpleTestCase

from apps.articoli.sync import DEFAULT_SYNC_BATCH_SIZE, DEFAULT_SYNC_PAGE_SIZE, TABLES


class ArticoliSyncConfigTests(SimpleTestCase):
    def test_table_spec_has_paging_and_incremental(self):
        spec = TABLES[0]
        self.assertEqual(spec["source"], "Articoli")
        self.assertEqual(spec["target"], "articoli")
        self.assertEqual(spec["pk"], "Codice")
        self.assertTrue(spec["page_by_pk"])
        self.assertTrue(spec["incremental_by_pk"])
        self.assertEqual(spec["batch_size"], DEFAULT_SYNC_BATCH_SIZE)
        self.assertEqual(spec["page_size"], DEFAULT_SYNC_PAGE_SIZE)
        self.assertIsNotNone(spec.get("post_create"))
