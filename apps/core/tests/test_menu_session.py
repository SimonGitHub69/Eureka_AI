"""
Dopo il login, tutte le voci di menu devono restare accessibili senza
re-autenticazione (salvo chiusura reale dell'applicazione).

Copre anche le Stampe aperte in target=_blank, dove un bug di
logout-on-close poteva invalidare la sessione.
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import NoReverseMatch, reverse


# Allineato a templates/base/sidebar.html (+ stampe target=_blank).
MENU_URL_NAMES = (
    "dashboard:index",
    "agenda:calendario",
    "anagrafiche:clienti_list",
    "anagrafiche:fornitori_list",
    "anagrafiche:agenti_list",
    "pdc:list",
    "primanota:list",
    "causali_contabili:list",
    "raggruppamento_conti:list",
    "raggruppamento_clifor:list",
    "pdc:print_list",
    "primanota:print_list",
    "anagrafiche:partitario_print",
    "registri_iva:print_list",
    "registri_iva:liquidazione",
    "causali_contabili:print_list",
    "raggruppamento_conti:print_list",
    "raggruppamento_clifor:print_list",
    "articoli:list",
    "set_articoli:list",
    "distinte_base:list",
    "movimenti:list",
    "articoli:print_list",
    "core:stampe_inventario",
    "set_articoli:print_list",
    "distinte_base:print_list",
    "movimenti:print_list",
    "fatture:analisi",
    "fatture:classifica",
    "fatture:analisi_regioni",
    "movimenti:statistiche",
    "categorie:list",
    "gruppi_articoli:list",
    "gruppi_magazzini:list",
    "magazzini:list",
    "depositi:list",
    "causali_magazzino:list",
    "aliquote:list",
    "registri_iva:list",
    "banche:list",
    "sconti:list",
    "valute:list",
    "condizioni:list",
    "aziende:list",
    "zone:list",
    "destinazioni:list",
    "documenti:porto_list",
    "vettori:list",
    "causali_trasp:list",
    "geografia:regioni_list",
    "geografia:province_list",
    "geografia:citta_list",
    "operatori:list",
    "timbrature:list",
    "core:offline",
    "documenti:parametri_list",
    "documenti:contatori_list",
    "core:parametri_contabili",
    "dashboard:sistema",
)

DOC_MENU_URLS = (
    ("documenti:list", {"tipo_doc": "PRV"}),
    ("documenti:list", {"tipo_doc": "ORV"}),
    ("documenti:list", {"tipo_doc": "ORA"}),
    ("documenti:list", {"tipo_doc": "DDT"}),
    ("documenti:list", {"tipo_doc": "NCR"}),
    ("documenti:list", {"tipo_doc": "NDB"}),
    ("fatture:list", None),
)

STAFF_PARAM_URLS = (
    "core:parametri_mail",
    "core:parametri_programma",
    "core:configurazione_pc_list",
    "core:parametri_4d",
    "core:comandi_vocali_list",
)


def _is_login_redirect(response) -> bool:
    if response.status_code not in (301, 302, 303, 307, 308):
        return False
    location = response.get("Location") or ""
    return "/login" in location


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
)
class MenuKeepsSessionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("menuuser", password="secret123")
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="menuuser", password="secret123"))

    def _assert_stays_authenticated(self, url: str, label: str):
        before = self.client.session.get("_auth_user_id")
        self.assertTrue(before, msg="Sessione non autenticata prima della richiesta")
        response = self.client.get(url)
        self.assertFalse(
            _is_login_redirect(response),
            msg=f"{label} ({url}) ha richiesto di nuovo il login: {response.get('Location')}",
        )
        after = self.client.session.get("_auth_user_id")
        self.assertEqual(
            str(before),
            str(after),
            msg=f"{label} ({url}) ha invalidato la sessione autenticata",
        )
        self.assertNotIn(
            response.status_code,
            (401, 403),
            msg=f"{label} ({url}) ha risposto {response.status_code}",
        )

    def test_all_sidebar_menu_urls_keep_session(self):
        for name in MENU_URL_NAMES:
            with self.subTest(url_name=name):
                try:
                    url = reverse(name)
                except NoReverseMatch as exc:
                    self.fail(f"URL menu non risolvibile: {name} ({exc})")
                self._assert_stays_authenticated(url, name)

    def test_documenti_menu_urls_keep_session(self):
        for name, kwargs in DOC_MENU_URLS:
            with self.subTest(url_name=name, kwargs=kwargs):
                url = reverse(name, kwargs=kwargs or None)
                self._assert_stays_authenticated(url, name)

    def test_parametri_staff_urls_keep_session(self):
        for name in STAFF_PARAM_URLS:
            with self.subTest(url_name=name):
                url = reverse(name)
                self._assert_stays_authenticated(url, name)

    def test_print_urls_then_regular_menu_still_authenticated(self):
        """Simula: apri stampe (come target=_blank) poi torna al menu principale."""
        print_names = (
            "pdc:print_list",
            "primanota:print_list",
            "anagrafiche:partitario_print",
            "registri_iva:print_list",
            "registri_iva:liquidazione",
            "articoli:print_list",
            "core:stampe_inventario",
            "movimenti:print_list",
        )
        for name in print_names:
            self._assert_stays_authenticated(reverse(name), name)

        self._assert_stays_authenticated(reverse("dashboard:index"), "dashboard:index")
        self._assert_stays_authenticated(
            reverse("anagrafiche:clienti_list"), "anagrafiche:clienti_list"
        )
        self._assert_stays_authenticated(reverse("articoli:list"), "articoli:list")


class LogoutOnCloseScriptGuardsTests(SimpleTestCase):
    """Regressione sul JS che invalidava la sessione aprendo le Stampe."""

    def test_script_guards_target_blank_and_skips_unload(self):
        root = Path(__file__).resolve().parents[3]
        script = (root / "static" / "eureka" / "js" / "logout-on-close.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("registerChildPlaceholder", script)
        self.assertIn('anchor.target', script)
        self.assertIn("__eurekaMarkNavigating", script)
        self.assertIn("suppressLogoutUntil", script)
        self.assertIn('CHILD_GRACE_MS', script)
        # unload era troppo aggressivo e contribuiva ai logout spurii.
        self.assertNotIn('addEventListener("unload"', script)
        self.assertNotIn("addEventListener('unload'", script)
