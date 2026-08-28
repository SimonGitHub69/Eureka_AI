from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.registri_iva.libro_registro import (
    LibroRegistroIvaDati,
    _periodo_label,
    build_libro_registro_iva,
)
from apps.registri_iva.views import (
    RegistroIvaElencoPrintView,
    RegistroIvaLibroPrintView,
    _is_registri_iva_elenco_stampa,
    _registri_iva_print_filter_summary,
)


class RegistriIvaUrlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="registri_iva",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def test_list_url(self):
        response = self.client.get(reverse("registri_iva:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registri IVA")

    def test_print_and_export_urls(self):
        for name in ("registri_iva:print_list", "registri_iva:export_list"):
            with self.subTest(url=name):
                url = reverse(name)
                self.assertTrue(url.endswith("/stampa/") or url.endswith("/export/"))


class RegistriIvaPrintFilterTests(SimpleTestCase):
    def test_elenco_mode_detected(self):
        request = RequestFactory().get("/registri-iva/stampa/", {"elenco": "1"})
        self.assertTrue(_is_registri_iva_elenco_stampa(request))

    def test_elenco_filter_summary_includes_dates(self):
        request = RequestFactory().get(
            "/registri-iva/stampa/",
            {"elenco": "1", "data_da": "2024-01-01", "data_a": "2024-01-31"},
        )
        summary = _registri_iva_print_filter_summary(request)
        self.assertIn("01/01/2024", summary)
        self.assertIn("31/01/2024", summary)

    def test_elenco_mode_has_date_filters(self):
        request = RequestFactory().get("/registri-iva/stampa/", {"elenco": "1"})
        view = RegistroIvaElencoPrintView()
        view.request = request
        with patch(
            "apps.core.print_list.resolve_print_azienda_context",
            return_value={},
        ):
            context = view.get_context_data(object_list=[])
        self.assertTrue(context["print_registri_iva_filters"])
        self.assertIn("data_da", context)
        self.assertIn("data_a", context)

    def test_libro_periodo_aprile(self):
        from datetime import date

        self.assertEqual(_periodo_label(date(2026, 4, 1), date(2026, 4, 30)), "Aprile 2026")

    def test_libro_build_without_registro(self):
        request = RequestFactory().get("/registri-iva/stampa/", {"anteprima": "1"})
        try:
            libro = build_libro_registro_iva(request)
        except Exception as exc:
            if exc.__class__.__name__ in {"ProgrammingError", "OperationalError"}:
                self.skipTest("DB mirror non disponibile")
            raise
        self.assertEqual(libro.documenti_count, 0)

    def test_libro_view_filter_form(self):
        from unittest.mock import Mock

        from django.http import HttpResponse

        request = RequestFactory().get("/registri-iva/stampa/")
        request.user = Mock(is_authenticated=True)
        with patch(
            "apps.registri_iva.views.registro_iva_choices",
            return_value=[("", "—"), ("1", "1 — Vendite")],
        ), patch(
            "apps.registri_iva.views.resolve_print_azienda_context",
            return_value={},
        ), patch(
            "apps.registri_iva.views._resolve_azienda_header",
            return_value={"ragione_sociale": "", "indirizzo": "", "codice_fiscale": "", "partita_iva": ""},
        ), patch(
            "apps.registri_iva.views.render",
            return_value=HttpResponse("ok"),
        ) as mock_render:
            response = RegistroIvaLibroPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args[0][2]
        self.assertFalse(context["print_preview_ready"])
        self.assertIn("registri_choices", context)
