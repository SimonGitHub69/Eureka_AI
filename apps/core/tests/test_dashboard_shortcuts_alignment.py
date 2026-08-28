"""Allineamento catalogo scorciatoie Parametri PC ↔ menu laterale."""

from django.test import SimpleTestCase

from apps.core.dashboard_shortcuts import (
    DOC_SHORTCUT_BY_CODICE,
    NAVBAR_SHORTCUT_CATALOG,
    catalog_by_section,
    resolve_shortcut_configs,
)
from apps.core.programma import DOC_MENU_FIELDS, DOC_MENU_ICONS
from apps.core.stampe import STAMPE_FATTURAZIONE


class DashboardShortcutSidebarAlignmentTests(SimpleTestCase):
    def test_section_names_match_sidebar_hierarchy(self):
        sections = [name for name, _ in catalog_by_section()]
        self.assertIn("Fatturazione Magazzino · Magazzino", sections)
        self.assertIn("Fatturazione Magazzino · Documenti", sections)
        self.assertIn("Fatturazione Magazzino · Stampe", sections)
        self.assertIn("Primanota · Gestione", sections)
        self.assertIn("Primanota · Stampe", sections)
        self.assertNotIn("Magazzino", sections)
        self.assertNotIn("Documenti", sections)
        self.assertNotIn("Contabilità", sections)
        self.assertNotIn("Tabelle · Contabilità", sections)

    def test_stampe_match_sidebar_items(self):
        by_key = {item["key"]: item for item in NAVBAR_SHORTCUT_CATALOG}
        expected = {
            "articoli": "stampa_articoli",
            "inventario": "stampa_inventario",
            "distinte_base": "stampa_distinte_base",
            "movimenti": "stampa_movimenti",
        }
        for spec in STAMPE_FATTURAZIONE:
            key = expected[spec["key"]]
            self.assertIn(key, by_key)
            self.assertEqual(by_key[key]["label"], spec["label"])
            self.assertEqual(by_key[key]["url_name"], spec["url_name"])
            self.assertEqual(by_key[key]["section"], "Fatturazione Magazzino · Stampe")

    def test_stampe_primanota_match_sidebar_items(self):
        from apps.core.stampe import STAMPE_PRIMANOTA

        by_key = {item["key"]: item for item in NAVBAR_SHORTCUT_CATALOG}
        expected = {
            "pdc": "stampa_pdc",
            "primanota": "stampa_primanota",
            "registri_iva": "stampa_registri_iva",
            "causali_contabili": "stampa_causali_contabili",
            "raggruppamento_conti": "stampa_raggruppamento_conti",
            "raggruppamento_clifor": "stampa_raggruppamento_clifor",
        }
        for spec in STAMPE_PRIMANOTA:
            key = expected[spec["key"]]
            self.assertIn(key, by_key)
            self.assertEqual(by_key[key]["label"], spec["label"])
            self.assertEqual(by_key[key]["url_name"], spec["url_name"])
            self.assertEqual(by_key[key]["section"], "Primanota · Stampe")

    def test_parametri_include_pc_and_sync(self):
        by_key = {item["key"]: item for item in NAVBAR_SHORTCUT_CATALOG}
        self.assertEqual(by_key["parametri_pc"]["url_name"], "core:configurazione_pc_list")
        self.assertEqual(by_key["parametri_pc"]["label"], "Parametri PC")
        self.assertEqual(by_key["sync_4d"]["label"], "Sync 4D")
        self.assertEqual(by_key["sync_4d"]["url_name"], "core:parametri_4d")

    def test_documenti_icons_match_menu(self):
        by_key = {item["key"]: item for item in NAVBAR_SHORTCUT_CATALOG}
        for codice, field in DOC_MENU_FIELDS.items():
            shortcut_key = DOC_SHORTCUT_BY_CODICE[codice]
            self.assertEqual(shortcut_key, field)
            self.assertEqual(
                by_key[shortcut_key]["icon"],
                DOC_MENU_ICONS[codice],
            )

    def test_legacy_stampe_migrates_to_four_items(self):
        configs = resolve_shortcut_configs({"stampe": "both"})
        for key in (
            "stampa_articoli",
            "stampa_inventario",
            "stampa_distinte_base",
            "stampa_movimenti",
        ):
            self.assertEqual(configs[key]["mode"], "both")
