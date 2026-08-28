from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ConfigurazioneProgramma


class FattureMenuAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="fatuser",
            password="testpass123",
        )
        self.client.login(username="fatuser", password="testpass123")
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_fat = False
        cfg.save()

    def test_fatture_list_blocked_when_disabled(self):
        url = reverse("fatture:list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_fatture_list_allowed_when_enabled(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_fat = True
        cfg.save()
        url = reverse("fatture:list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
