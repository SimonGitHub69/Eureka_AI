from django.test import SimpleTestCase
from django.urls import reverse

from apps.zone.models import Zona
from apps.zone.sync import TABLES


class ZoneSyncSpecTests(SimpleTestCase):
    def test_sync_uses_zone_and_codice_pk(self):
        spec = TABLES[0]
        self.assertEqual(spec["source"], "Zone")
        self.assertEqual(spec["target"], "zone")
        self.assertEqual(spec["pk"], "Codice")

    def test_model_is_unmanaged_mirror(self):
        self.assertFalse(Zona._meta.managed)
        self.assertEqual(Zona._meta.db_table, "zone")
        self.assertEqual(Zona._meta.get_field("codice").db_column, "Codice")
        self.assertEqual(Zona._meta.get_field("descrizione").db_column, "Descrizione")

    def test_urls_resolve(self):
        self.assertEqual(reverse("zone:list"), "/zone/")
        self.assertEqual(reverse("zone:create"), "/zone/nuova/")
        self.assertEqual(reverse("zone:detail", kwargs={"codice": "IT"}), "/zone/IT/")
        self.assertEqual(reverse("zone:edit", kwargs={"codice": "IT"}), "/zone/IT/modifica/")
        self.assertEqual(reverse("zone:sync"), "/parametri/4d/sync-zone/")

    def test_sync_4d_step_registered(self):
        from apps.core.views import MIRROR_4D_TABLES, SYNC_4D_STEPS

        step = next(s for s in SYNC_4D_STEPS if s["key"] == "zone")
        self.assertEqual(step["label"], "Zone")
        self.assertEqual(step["description"], "Zone")
        self.assertEqual(step["tables"], ("zone",))
        self.assertIn("zone", MIRROR_4D_TABLES)
