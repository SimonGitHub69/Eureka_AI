from django.test import RequestFactory, SimpleTestCase

from apps.core.navigation import list_back_label, related_back


class NavigationBackTests(SimpleTestCase):
    def test_filtered_list_back(self):
        request = RequestFactory().get(
            "/articoli/VA22/",
            {"next": "/articoli/?q=rame&page=2"},
        )
        back_url, back_label = related_back(request)
        self.assertEqual(back_url, "/articoli/?q=rame&page=2")
        self.assertEqual(back_label, "Torna alla selezione")

    def test_unfiltered_list_back(self):
        request = RequestFactory().get(
            "/movimenti/100/",
            {"next": "/movimenti/"},
        )
        back_url, back_label = related_back(request)
        self.assertEqual(back_url, "/movimenti/")
        self.assertEqual(back_label, "Torna all'elenco")

    def test_list_back_query_param(self):
        request = RequestFactory().get(
            "/distinte-base/1/",
            {"list_back": "/distinte-base/?q=10"},
        )
        back_url, back_label = related_back(request)
        self.assertEqual(back_url, "/distinte-base/?q=10")
        self.assertEqual(back_label, "Torna alla selezione")

    def test_articolo_movimenti_has_priority(self):
        request = RequestFactory().get(
            "/movimenti/100/",
            {"next": "/articoli/VA22/?mov_data_da=2025-01-01"},
        )
        back_url, back_label = related_back(request)
        self.assertEqual(
            back_url,
            "/articoli/VA22/?mov_data_da=2025-01-01#articolo-movimenti",
        )
        self.assertEqual(back_label, "Torna ai movimenti")

    def test_list_back_label_only_pagination(self):
        self.assertEqual(list_back_label("/clienti/?page=2&sort=codice"), "Torna all'elenco")

    def test_partitario_back(self):
        request = RequestFactory().get(
            "/primanota/1/",
            {"next": "/anagrafiche/clienti/001/partitario/?anno=2025"},
        )
        back_url, back_label = related_back(request)
        self.assertIn("/partitario", back_url)
        self.assertEqual(back_label, "Torna al partitario")

    def test_primanota_list_filtered(self):
        request = RequestFactory().get(
            "/primanota/1/",
            {"next": "/primanota/?q=test"},
        )
        back_url, back_label = related_back(request)
        self.assertEqual(back_url, "/primanota/?q=test")
        self.assertEqual(back_label, "Torna alla selezione")

    def test_set_articoli_list_is_not_movimenti_articolo(self):
        request = RequestFactory().get(
            "/set-articoli/75/",
            {"next": "/set-articoli/?q=tubolare"},
        )
        back_url, back_label = related_back(request)
        self.assertEqual(back_url, "/set-articoli/?q=tubolare")
        self.assertEqual(back_label, "Torna alla selezione")

    def test_redirect_with_back_preserves_next(self):
        from apps.core.navigation import redirect_with_back

        request = RequestFactory().get("/set-articoli/1/modifica/", {"next": "/set-articoli/?q=x"})
        response = redirect_with_back(request, "/set-articoli/1/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/set-articoli/1/", response.url)
        self.assertIn("next=", response.url)

    def test_redirect_with_back_exits_to_list(self):
        from apps.core.navigation import redirect_with_back

        request = RequestFactory().post("/set-articoli/1/elimina/", {"next": "/set-articoli/?q=x"})
        response = redirect_with_back(
            request, "/set-articoli/", preserve_on_fallback=False
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/set-articoli/?q=x")
