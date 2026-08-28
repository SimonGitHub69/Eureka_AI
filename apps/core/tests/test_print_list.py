from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.core.print_list import (
    PRINT_PREVIEW_PARAM,
    build_print_rows,
    print_preview_requested,
    resolve_column_value,
)
from apps.magazzini.views import MagazzinoPrintListView


class PrintListHelperTests(SimpleTestCase):
    def test_resolve_column_value_empty(self):
        self.assertEqual(resolve_column_value({}, {"field": "x", "label": "X"}), "—")

    def test_resolve_bool_column(self):
        self.assertEqual(
            resolve_column_value({"ok": True}, {"field": "ok", "label": "OK", "bool": True}),
            "Sì",
        )

    def test_build_print_rows(self):
        headers, rows = build_print_rows(
            [{"codice": "A1", "nome": "Alpha"}],
            (
                {"field": "codice", "label": "Codice"},
                {"field": "nome", "label": "Nome"},
            ),
        )
        self.assertEqual(headers, ["Codice", "Nome"])
        self.assertEqual(rows, [["A1", "Alpha"]])


class PrintPreviewGateTests(SimpleTestCase):
    def test_preview_not_requested_by_default(self):
        request = RequestFactory().get("/magazzini/stampa/")
        self.assertFalse(print_preview_requested(request))

    def test_preview_requested_with_param(self):
        request = RequestFactory().get("/magazzini/stampa/", {PRINT_PREVIEW_PARAM: "1"})
        self.assertTrue(print_preview_requested(request))

    def test_print_view_skips_query_without_preview(self):
        request = RequestFactory().get("/magazzini/stampa/")
        view = MagazzinoPrintListView()
        view.request = request
        self.assertEqual(view.get_queryset(), [])

    def test_print_view_context_without_preview(self):
        request = RequestFactory().get("/magazzini/stampa/")
        view = MagazzinoPrintListView()
        view.request = request
        from unittest.mock import patch

        with patch(
            "apps.core.print_list.resolve_print_azienda_context",
            return_value={},
        ):
            context = view.get_context_data()
        self.assertFalse(context["print_preview_ready"])
        self.assertEqual(context["print_count"], 0)
        self.assertTrue(context["print_filters_gate"])


class PrintListUrlTests(SimpleTestCase):
    PRINT_URLS = (
        "articoli:print_list",
        "core:stampe_inventario",
        "distinte_base:print_list",
        "movimenti:print_list",
        "magazzini:print_list",
        "categorie:print_list",
        "gruppi_articoli:print_list",
        "gruppi_magazzini:print_list",
        "causali_magazzino:print_list",
        "aliquote:print_list",
        "registri_iva:print_list",
        "banche:print_list",
        "condizioni:print_list",
        "aziende:print_list",
        "zone:print_list",
        "destinazioni:print_list",
        "documenti:porto_print_list",
        "vettori:print_list",
        "causali_trasp:print_list",
        "geografia:regioni_print_list",
        "geografia:province_print_list",
        "geografia:citta_print_list",
        "operatori:print_list",
        "timbrature:print_list",
        "carbon:reparti_print_list",
    )

    def test_print_urls_resolve(self):
        for name in self.PRINT_URLS:
            with self.subTest(url=name):
                url = reverse(name)
                path = url.rstrip("/")
                self.assertTrue(
                    path.endswith("/stampa") or path.endswith("/inventario"),
                    msg=url,
                )

    def test_print_requires_login(self):
        request = RequestFactory().get("/magazzini/stampa/")
        request.user = AnonymousUser()
        response = MagazzinoPrintListView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
