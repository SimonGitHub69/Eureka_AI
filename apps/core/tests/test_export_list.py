from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.magazzini.views import MagazzinoExportListView


class ExportListUrlTests(SimpleTestCase):
    EXPORT_URLS = (
        "magazzini:export_list",
        "categorie:export_list",
        "gruppi_articoli:export_list",
        "gruppi_magazzini:export_list",
        "causali_magazzino:export_list",
        "aliquote:export_list",
        "registri_iva:export_list",
        "banche:export_list",
        "condizioni:export_list",
        "aziende:export_list",
        "zone:export_list",
        "destinazioni:export_list",
        "documenti:porto_export_list",
        "vettori:export_list",
        "causali_trasp:export_list",
        "geografia:regioni_export_list",
        "geografia:province_export_list",
        "geografia:citta_export_list",
        "operatori:export_list",
        "timbrature:export_list",
        "carbon:reparti_export_list",
    )

    def test_export_urls_resolve(self):
        for name in self.EXPORT_URLS:
            with self.subTest(url=name):
                url = reverse(name)
                self.assertTrue(url.endswith("/export/") or url.endswith("/export"))

    def test_export_requires_login(self):
        request = RequestFactory().get("/magazzini/export/")
        request.user = AnonymousUser()
        response = MagazzinoExportListView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
