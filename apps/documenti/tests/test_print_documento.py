"""Stampa documento: spese di testata nel piede."""

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from apps.documenti.models import TestaDocumento


def _foot_html(documento, *, with_values: bool) -> str:
    return render_to_string(
        "documenti/partials/documento_print_foot.html",
        {
            "documento": documento,
            "castelletto": None,
            "with_values": with_values,
        },
    )


class DocumentoPrintFootSpeseTests(SimpleTestCase):
    def test_spese_in_stampa_come_in_maschera(self):
        doc = TestaDocumento(
            add_spese=True,
            spese_imballo=5,
            spese_trasporto=15,
            spese_incasso=25.80,
            spese_varie=12,
            spese_bolli=0,
        )
        html = _foot_html(doc, with_values=True)
        self.assertIn("Spese imballo", html)
        self.assertIn("Spese trasporto", html)
        self.assertIn("Spese incasso", html)
        self.assertIn("Spese varie", html)
        self.assertIn("Spese bolli", html)
        self.assertIn("Totale spese", html)
        self.assertIn("5,00", html)
        self.assertIn("15,00", html)
        self.assertIn("25,80", html)
        self.assertIn("12,00", html)
        self.assertIn("0,00", html)
        self.assertIn("57,80", html)

    def test_pagine_intermedie_senza_importi(self):
        doc = TestaDocumento(
            add_spese=True,
            spese_imballo=5,
            spese_trasporto=15,
            spese_incasso=25.80,
            spese_varie=12,
            spese_bolli=0,
        )
        html = _foot_html(doc, with_values=False)
        self.assertIn("Spese imballo", html)
        self.assertIn("Totale spese", html)
        self.assertNotIn("5,00", html)
        self.assertNotIn("25,80", html)
        self.assertNotIn("57,80", html)

    def test_totale_spese_zero_se_non_addebitate(self):
        doc = TestaDocumento(
            add_spese=False,
            spese_imballo=5,
            spese_trasporto=15,
        )
        html = _foot_html(doc, with_values=True)
        self.assertIn("Totale spese", html)
        self.assertIn("0,00", html)
        self.assertNotIn("20,00", html)
