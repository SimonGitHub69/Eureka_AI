from django.test import SimpleTestCase
from django.urls import reverse

from apps.vettori.models import Vettore
from apps.vettori.sync import TABLES


class VettoriSyncSpecTests(SimpleTestCase):
    def test_sync_uses_vettori_and_codicevet_pk(self):
        spec = TABLES[0]
        self.assertEqual(spec["source"], "Vettori")
        self.assertEqual(spec["target"], "vettori")
        self.assertEqual(spec["pk"], "CodiceVet")

    def test_model_is_unmanaged_mirror(self):
        self.assertFalse(Vettore._meta.managed)
        self.assertEqual(Vettore._meta.db_table, "vettori")
        self.assertEqual(Vettore._meta.get_field("codice").db_column, "CodiceVet")
        self.assertEqual(Vettore._meta.get_field("denominazione").db_column, "Denominazione")

    def test_urls_resolve(self):
        self.assertEqual(reverse("vettori:list"), "/vettori/")
        self.assertEqual(reverse("vettori:create"), "/vettori/nuovo/")
        self.assertEqual(reverse("vettori:detail", kwargs={"codice": "01"}), "/vettori/01/")
        self.assertEqual(reverse("vettori:edit", kwargs={"codice": "01"}), "/vettori/01/modifica/")
        self.assertEqual(reverse("vettori:sync"), "/parametri/4d/sync-vettori/")

    def test_sync_4d_step_registered(self):
        from apps.core.views import MIRROR_4D_TABLES, SYNC_4D_STEPS

        step = next(s for s in SYNC_4D_STEPS if s["key"] == "vettori")
        self.assertEqual(step["label"], "Spedizionieri")
        self.assertEqual(step["description"], "Spedizionieri (Vettori 4D)")
        self.assertEqual(step["tables"], ("vettori",))
        self.assertIn("vettori", MIRROR_4D_TABLES)
