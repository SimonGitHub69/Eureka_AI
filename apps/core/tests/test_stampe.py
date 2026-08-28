from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class StampeMenuTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="stampeuser",
            password="testpass123",
        )
        self.client.login(username="stampeuser", password="testpass123")

    def test_hub_requires_login(self):
        self.client.logout()
        url = reverse("core:stampe")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_hub_lists_fatturazione_prints(self):
        response = self.client.get(reverse("core:stampe"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stampe")
        self.assertContains(response, reverse("articoli:print_list"))
        self.assertContains(response, reverse("core:stampe_inventario"))
        self.assertContains(response, reverse("distinte_base:print_list"))
        self.assertContains(response, reverse("movimenti:print_list"))
        self.assertContains(response, "Inventario")

    def test_sidebar_has_stampe_under_fatturazione(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-nav-section="fatturazione-stampe"')
        self.assertContains(response, reverse("core:stampe_inventario"))
        self.assertContains(response, "Inventario")
        self.assertNotContains(response, "Elenco stampe")

    def test_sidebar_has_stampe_under_primanota(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-nav-section="primanota-stampe"')
        self.assertContains(response, reverse("pdc:print_list"))
        self.assertContains(response, reverse("primanota:print_list"))
        self.assertContains(response, reverse("registri_iva:print_list"))
        self.assertContains(response, reverse("causali_contabili:print_list"))
