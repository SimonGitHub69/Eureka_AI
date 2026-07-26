from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.anagrafiche.models import Cliente, Fornitore


class AnagraficheViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@example.com", "secret")
        self.client.login(username="testuser", password="secret")

    def test_clienti_list_returns_200(self):
        response = self.client.get(reverse("anagrafiche:clienti_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clienti")

    def test_fornitori_list_returns_200(self):
        response = self.client.get(reverse("anagrafiche:fornitori_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fornitori")

    def test_cliente_detail_when_data_exists(self):
        cliente = Cliente.objects.first()
        if not cliente:
            self.skipTest("Nessun cliente nel database")
        url = reverse("anagrafiche:cliente_detail", kwargs={"codice": cliente.codice})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cliente.codice)

    def test_fornitore_detail_when_data_exists(self):
        fornitore = Fornitore.objects.first()
        if not fornitore:
            self.skipTest("Nessun fornitore nel database")
        url = reverse("anagrafiche:fornitore_detail", kwargs={"codice": fornitore.codice})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, fornitore.codice)

    def test_search_filter(self):
        cliente = Cliente.objects.exclude(ragione_sociale1__isnull=True).exclude(ragione_sociale1="").first()
        if not cliente:
            self.skipTest("Nessun cliente con ragione sociale")
        term = (cliente.ragione_sociale1 or "")[:8]
        response = self.client.get(reverse("anagrafiche:clienti_list"), {"q": term})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cliente.codice)

    def test_orm_counts(self):
        self.assertGreater(Cliente.objects.count(), 0)
        self.assertGreater(Fornitore.objects.count(), 0)

    def test_urls_resolve(self):
        self.assertEqual(reverse("anagrafiche:clienti_list"), "/clienti/")
        self.assertEqual(reverse("anagrafiche:fornitori_list"), "/fornitori/")
