from django.test import SimpleTestCase
from django.urls import reverse

from apps.articoli.lookups import LOOKUP_TIPI
from apps.causali_magazzino.forms import (
    CausaleMagazzinoForm,
    norm_si_no,
    si_no_label,
)
from apps.causali_magazzino.models import CausaleMagazzino
from apps.causali_magazzino.sync import TABLES


class CausaliMagazzinoSyncSpecTests(SimpleTestCase):
    def test_sync_uses_causalimaga_and_codice_pk(self):
        spec = TABLES[0]
        self.assertEqual(spec["source"], "CausaliMaga")
        self.assertEqual(spec["target"], "causali_maga")
        self.assertEqual(spec["pk"], "Codice")

    def test_model_is_unmanaged_mirror(self):
        self.assertFalse(CausaleMagazzino._meta.managed)
        self.assertEqual(CausaleMagazzino._meta.db_table, "causali_maga")
        self.assertEqual(CausaleMagazzino._meta.get_field("codice").db_column, "Codice")
        self.assertEqual(
            CausaleMagazzino._meta.get_field("descrizione").db_column, "Descrizione"
        )
        self.assertEqual(
            CausaleMagazzino._meta.get_field("tipo_causale").db_column, "Tipo_Causale"
        )
        self.assertEqual(
            CausaleMagazzino._meta.get_field("deposito_entrata").db_column,
            "DepositoEntrata",
        )
        self.assertEqual(
            CausaleMagazzino._meta.get_field("deposito_uscita").db_column,
            "DepositoUscita",
        )
        self.assertEqual(CausaleMagazzino._meta.get_field("scar_db").db_column, "Scar_DB")
        self.assertEqual(
            CausaleMagazzino._meta.get_field("update_listino").db_column,
            "Update_Listino",
        )
        self.assertEqual(
            CausaleMagazzino._meta.get_field("update_prezzo_medio").db_column,
            "Update_Prezzo_Medio",
        )
        self.assertEqual(
            CausaleMagazzino._meta.get_field("cod_market").db_column, "CodMarket"
        )

    def test_urls_resolve(self):
        self.assertEqual(reverse("causali_magazzino:list"), "/causali-magazzino/")
        self.assertEqual(
            reverse("causali_magazzino:create"), "/causali-magazzino/nuova/"
        )
        self.assertEqual(
            reverse("causali_magazzino:detail", kwargs={"codice": "01"}),
            "/causali-magazzino/01/",
        )
        self.assertEqual(
            reverse("causali_magazzino:edit", kwargs={"codice": "01"}),
            "/causali-magazzino/01/modifica/",
        )
        self.assertEqual(
            reverse("causali_magazzino:sync"),
            "/parametri/4d/sync-causali-magazzino/",
        )

    def test_sync_4d_step_registered(self):
        from apps.core.views import MIRROR_4D_TABLES, SYNC_4D_STEPS

        step = next(s for s in SYNC_4D_STEPS if s["key"] == "causali_magazzino")
        self.assertEqual(step["label"], "Causali magazzino")
        self.assertEqual(step["description"], "CausaliMaga")
        self.assertEqual(step["tables"], ("causali_maga",))
        self.assertIn("causali_maga", MIRROR_4D_TABLES)


class CausaliMagazzinoFormTests(SimpleTestCase):
    def test_si_no_fields(self):
        form = CausaleMagazzinoForm()
        self.assertEqual(form.fields["update_listino"].label, "Aggiorna ultimo prezzo")
        self.assertEqual(
            form.fields["update_prezzo_medio"].label, "Aggiorna prezzo medio"
        )
        self.assertEqual(form.fields["scar_db"].label, "Scarico distinta base")
        for name in ("scar_db", "update_listino", "update_prezzo_medio"):
            self.assertEqual(
                list(form.fields[name].choices),
                [("", "No"), ("Si", "Sì")],
            )

    def test_norm_si_no(self):
        self.assertEqual(norm_si_no("Si"), "Si")
        self.assertEqual(norm_si_no("SI"), "Si")
        self.assertEqual(norm_si_no(""), "")
        self.assertEqual(norm_si_no("No"), "")
        self.assertEqual(si_no_label("Si"), "Sì")
        self.assertEqual(si_no_label(""), "No")

    def test_lookup_deposito_registered(self):
        self.assertIn("deposito", LOOKUP_TIPI)
