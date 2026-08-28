from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.dashboard_shortcuts import (
    SHORTCUT_BAR,
    SHORTCUT_BOTH,
    SHORTCUT_DASH,
    SHORTCUT_OFF,
    build_navbar_shortcut_groups,
    build_navbar_shortcuts,
    default_shortcut_configs,
    default_shortcut_modes,
    normalize_shortcut_mode,
    resolve_shortcut_configs,
    resolve_shortcut_modes,
    shows_on_dashboard,
    shows_on_navbar,
)
from apps.core.models import ConfigurazionePC, ConfigurazioneProgramma
from apps.core.pc import COOKIE_NAME, SESSION_KEY
from apps.dashboard.views import TABELLE_IMPORTATE


class DashboardIndexTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dash",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def test_mostra_documenti_e_nuovi_moduli(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        for label in (
            "Preventivi",
            "Ordini vendita",
            "Ordini acquisto",
            "DDT / Bolle",
            "Fatture",
            "Note di credito",
            "Clienti",
            "Agenda",
            "Piano dei Conti",
            "Primanota",
            "CARBON",
            "Schede di lavorazione",
        ):
            self.assertContains(response, label)

    def test_nasconde_tipo_documento_disabilitato(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_ora = False
        cfg.save()
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Ordini acquisto")
        self.assertContains(response, "Preventivi")

    def test_nasconde_carbon_se_personalizzazione_disattivata(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.extra_carbon = False
        cfg.save()
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-nav-section="carbon"')
        self.assertNotContains(response, "Schede di lavorazione")
        self.assertContains(response, "Preventivi")
        self.assertFalse(response.context["eureka_extra_carbon"])

    def test_parametri_pc_tre_stati_dashboard_e_barra(self):
        defaults = default_shortcut_configs()
        pc = ConfigurazionePC.objects.create(
            nome_pc="DESKTOP-TEST",
            dashboard_shortcuts={
                **defaults,
                "clienti": {
                    **defaults["clienti"],
                    "mode": SHORTCUT_BOTH,
                    "gruppo": 1,
                    "posizione": 10,
                },
                "fornitori": {
                    **defaults["fornitori"],
                    "mode": SHORTCUT_DASH,
                },
                "agenti": {**defaults["agenti"], "mode": SHORTCUT_OFF},
                "articoli": {**defaults["articoli"], "mode": SHORTCUT_OFF},
            },
        )
        session = self.client.session
        session[SESSION_KEY] = pc.nome_pc
        session.save()
        self.client.cookies[COOKIE_NAME] = pc.nome_pc

        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        labels = [
            card["label"]
            for section in response.context["dashboard_sections"]
            for card in section["cards"]
        ]
        self.assertIn("Clienti", labels)
        self.assertIn("Fornitori", labels)
        self.assertNotIn("Articoli", labels)
        shortcuts = response.context["eureka_navbar_shortcuts"]
        keys = [s["key"] for s in shortcuts]
        self.assertIn("clienti", keys)
        self.assertNotIn("fornitori", keys)
        self.assertContains(response, 'class="eureka-navbar__shortcuts"')
        self.assertContains(response, 'title="Clienti"')


class NavbarShortcutModesTests(SimpleTestCase):
    def test_normalize_bool_legacy(self):
        self.assertEqual(normalize_shortcut_mode(True), SHORTCUT_BOTH)
        self.assertEqual(normalize_shortcut_mode(False), SHORTCUT_OFF)

    def test_resolve_merges_defaults(self):
        modes = resolve_shortcut_modes(
            {"clienti": SHORTCUT_BOTH, "articoli": SHORTCUT_BAR}
        )
        self.assertEqual(modes["clienti"], SHORTCUT_BOTH)
        self.assertEqual(modes["fornitori"], SHORTCUT_DASH)
        self.assertEqual(modes["agenti"], SHORTCUT_OFF)
        self.assertEqual(modes["articoli"], SHORTCUT_BAR)
        self.assertTrue(shows_on_dashboard(modes["fornitori"]))
        self.assertFalse(shows_on_navbar(modes["fornitori"]))
        self.assertTrue(shows_on_navbar(modes["clienti"]))
        self.assertFalse(shows_on_dashboard(modes["articoli"]))
        self.assertTrue(shows_on_navbar(modes["articoli"]))

    def test_resolve_configs_gruppo_posizione(self):
        configs = resolve_shortcut_configs(
            {
                "clienti": {
                    "mode": SHORTCUT_BAR,
                    "gruppo": 2,
                    "posizione": 5,
                },
                "fornitori": SHORTCUT_BOTH,
            }
        )
        self.assertEqual(configs["clienti"]["mode"], SHORTCUT_BAR)
        self.assertEqual(configs["clienti"]["gruppo"], 2)
        self.assertEqual(configs["clienti"]["posizione"], 5)
        self.assertEqual(configs["clienti"]["etichetta"], "Clienti")
        self.assertEqual(configs["fornitori"]["mode"], SHORTCUT_BOTH)
        self.assertEqual(configs["fornitori"]["gruppo"], 1)
        self.assertEqual(configs["fornitori"]["etichetta"], "Fornitori")

        with_label = resolve_shortcut_configs(
            {"clienti": {"mode": SHORTCUT_BAR, "etichetta": "Cli"}}
        )
        self.assertEqual(with_label["clienti"]["etichetta"], "Cli")

    def test_build_navbar_shortcut_groups_order(self):
        request = RequestFactory().get("/")
        request.user = type(
            "U",
            (),
            {
                "is_authenticated": True,
                "is_superuser": True,
                "has_perm": lambda *a: True,
            },
        )()
        configs = default_shortcut_configs()
        configs["clienti"] = {
            "mode": SHORTCUT_BAR,
            "gruppo": 2,
            "posizione": 20,
        }
        configs["fornitori"] = {
            "mode": SHORTCUT_BOTH,
            "gruppo": 1,
            "posizione": 30,
        }
        configs["articoli"] = {
            "mode": SHORTCUT_BAR,
            "gruppo": 1,
            "posizione": 10,
        }
        configs["primanota"] = {
            "mode": SHORTCUT_DASH,
            "gruppo": 1,
            "posizione": 1,
        }
        groups = build_navbar_shortcut_groups(request, configs=configs)
        self.assertEqual([g["gruppo"] for g in groups], [1, 2])
        self.assertEqual([g["tone"] for g in groups], [0, 1])
        self.assertEqual(
            [i["key"] for i in groups[0]["items"]],
            ["articoli", "fornitori"],
        )
        self.assertEqual([i["key"] for i in groups[1]["items"]], ["clienti"])

        flat = build_navbar_shortcuts(request, configs=configs)
        self.assertEqual([i["key"] for i in flat], ["articoli", "fornitori", "clienti"])


class SistemaTabelleTests(TestCase):
    def test_tabelle_importate_includono_moduli_nuovi(self):
        labels = {spec["label"] for spec in TABELLE_IMPORTATE}
        self.assertIn("Teste documenti", labels)
        self.assertIn("Piano dei Conti", labels)
        self.assertIn("Primanota", labels)
        self.assertIn("Causali contabili", labels)
        self.assertIn("Registri IVA", labels)
        self.assertIn("Causali magazzino", labels)
        self.assertIn("Causali trasporto", labels)
        self.assertIn("Spedizionieri", labels)
        self.assertIn("Porto", labels)
        self.assertIn("Destinazioni diverse", labels)
