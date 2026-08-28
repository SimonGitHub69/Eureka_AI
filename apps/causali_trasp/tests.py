from django.test import SimpleTestCase
from django.urls import reverse

from apps.causali_trasp.models import CausaleTrasporto
from apps.causali_trasp.sync import TABLES


class CausaliTraspSyncSpecTests(SimpleTestCase):
    def test_sync_uses_causalitasp_and_codice_pk(self):
        spec = TABLES[0]
        self.assertEqual(spec["source"], "CausaliTrasp")
        self.assertEqual(spec["target"], "causali_trasp")
        self.assertEqual(spec["pk"], "Codice")

    def test_model_is_unmanaged_mirror(self):
        self.assertFalse(CausaleTrasporto._meta.managed)
        self.assertEqual(CausaleTrasporto._meta.db_table, "causali_trasp")
        self.assertEqual(CausaleTrasporto._meta.get_field("codice").db_column, "Codice")
        self.assertEqual(CausaleTrasporto._meta.get_field("descrizione").db_column, "Desc")
        self.assertEqual(CausaleTrasporto._meta.get_field("fatturabile").db_column, "Fatturabile")
        self.assertEqual(CausaleTrasporto._meta.get_field("causale_maga").db_column, "CausaleMaga")
        self.assertEqual(CausaleTrasporto._meta.get_field("reparto_ecr").db_column, "RepartoECR")
        self.assertEqual(CausaleTrasporto._meta.get_field("c_partita_vend").db_column, "CPartitaVend")

    def test_urls_resolve(self):
        self.assertEqual(reverse("causali_trasp:list"), "/causali-trasp/")
        self.assertEqual(reverse("causali_trasp:create"), "/causali-trasp/nuova/")
        self.assertEqual(
            reverse("causali_trasp:detail", kwargs={"codice": "01"}),
            "/causali-trasp/01/",
        )
        self.assertEqual(
            reverse("causali_trasp:edit", kwargs={"codice": "01"}),
            "/causali-trasp/01/modifica/",
        )
        self.assertEqual(reverse("causali_trasp:sync"), "/parametri/4d/sync-causali-trasp/")

    def test_sync_4d_step_registered(self):
        from apps.core.views import MIRROR_4D_TABLES, SYNC_4D_STEPS

        step = next(s for s in SYNC_4D_STEPS if s["key"] == "causali_trasp")
        self.assertEqual(step["label"], "Causali trasporto")
        self.assertEqual(step["description"], "CausaliTrasp")
        self.assertEqual(step["tables"], ("causali_trasp",))
        self.assertIn("causali_trasp", MIRROR_4D_TABLES)
