"""Test conteggio risultati filtro liste."""

from django.test import RequestFactory, SimpleTestCase

from apps.core.pagination import (
    list_filters_active,
    resolve_list_filter_count,
)


class ListFiltersActiveTests(SimpleTestCase):
    def test_vuoto(self):
        request = RequestFactory().get("/movimenti/")
        self.assertFalse(list_filters_active(request))

    def test_ricerca_testo(self):
        request = RequestFactory().get("/movimenti/", {"q": "RAME10"})
        self.assertTrue(list_filters_active(request))

    def test_ignora_paginazione_e_sort(self):
        request = RequestFactory().get(
            "/articoli/",
            {"page": "2", "per_page": "50", "sort": "codice", "dir": "asc"},
        )
        self.assertFalse(list_filters_active(request))

    def test_filtro_ai(self):
        request = RequestFactory().get("/pdc/", {"ai": "1", "ai_token": "abc"})
        self.assertTrue(list_filters_active(request))


class ResolveListFilterCountTests(SimpleTestCase):
    def test_da_paginator(self):
        class Page:
            class Paginator:
                count = 42

            paginator = Paginator()

        class View:
            context_object_name = "movimenti"

        context = {"page_obj": Page()}
        self.assertEqual(resolve_list_filter_count(context, View()), 42)

    def test_da_lista(self):
        class View:
            context_object_name = "items"

        context = {"items": [1, 2, 3]}
        self.assertEqual(resolve_list_filter_count(context, View()), 3)
