from django.test import SimpleTestCase
from django.urls import reverse

from apps.depositi.sync import TABLES


class DepositiSyncSpecTests(SimpleTestCase):
    def test_sync_uses_depositi_table(self):
        spec = TABLES[0]
        self.assertEqual(spec["source"], "Depositi")
        self.assertEqual(spec["target"], "depositi")
        self.assertEqual(spec["pk"], "Numero")

    def test_detail_url(self):
        self.assertEqual(reverse("depositi:list"), "/depositi/")
        self.assertEqual(reverse("depositi:detail", kwargs={"codice": "02"}), "/depositi/02/")

    def test_sync_url(self):
        self.assertEqual(reverse("depositi:sync"), "/parametri/4d/sync-depositi/")
