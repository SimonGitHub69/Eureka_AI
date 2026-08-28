from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ConfigurazioneProgramma
from apps.documenti.models import TipoDocumento


class DocumentiMenuAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="docuser",
            password="testpass123",
        )
        self.client.login(username="docuser", password="testpass123")
        TipoDocumento.objects.get_or_create(
            codice="ORV",
            defaults={"label": "Ordini vendita", "attivo": True},
        )
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_orv = False
        cfg.save()

    def test_disabled_tipo_returns_403(self):
        url = reverse("documenti:list", kwargs={"tipo_doc": "ORV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_disabled_create_returns_403(self):
        url = reverse("documenti:create", kwargs={"tipo_doc": "ORV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_enabled_tipo_is_accessible(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_orv = True
        cfg.save()
        url = reverse("documenti:list", kwargs={"tipo_doc": "ORV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_enabled_create_is_accessible(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_orv = True
        cfg.save()
        url = reverse("documenti:create", kwargs={"tipo_doc": "ORV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_extra_altro_attivo_is_accessible(self):
        TipoDocumento.objects.create(
            codice="XTR",
            label="Extra trasporto",
            categoria=TipoDocumento.CATEGORIA_ALTRO,
            attivo=True,
        )
        url = reverse("documenti:list", kwargs={"tipo_doc": "XTR"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Extra trasporto")

    def test_extra_altro_non_attivo_returns_403(self):
        TipoDocumento.objects.create(
            codice="XTR",
            label="Extra trasporto",
            categoria=TipoDocumento.CATEGORIA_ALTRO,
            attivo=False,
        )
        url = reverse("documenti:list", kwargs={"tipo_doc": "XTR"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
