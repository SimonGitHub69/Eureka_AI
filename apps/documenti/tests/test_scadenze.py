"""Calcolo scadenze documento da condizione di pagamento."""

from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.documenti.forms import TestaDocumentoForm
from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO
from apps.documenti.models import TestaDocumento, TipoDocumento
from apps.documenti.scadenze import (
    calcola_scadenze,
    ensure_scadenze,
    scadenze_for_documento,
)


class CalcolaScadenzeTests(SimpleTestCase):
    def test_anticipato_prima_rata_un_giorno(self):
        cond = SimpleNamespace(
            numero_rate=1,
            prima_rata=1,
            intervallo=0,
            giorno_fisso=0,
            mese_esclusione=None,
            mese_esclusione2=None,
            gg_mese_esclus=None,
            gg_mese_esclus2=None,
        )
        slots = calcola_scadenze(
            data_documento=date(2026, 7, 27),
            condizione=cond,
            totale=100,
        )
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["data"], date(2026, 7, 28))
        self.assertEqual(slots[0]["importo"], 100.0)

    def test_tre_rate_intervallo_30(self):
        cond = SimpleNamespace(
            numero_rate=3,
            prima_rata=30,
            intervallo=30,
            giorno_fisso=0,
            mese_esclusione=None,
            mese_esclusione2=None,
            gg_mese_esclus=None,
            gg_mese_esclus2=None,
        )
        slots = calcola_scadenze(
            data_documento=date(2026, 1, 1),
            condizione=cond,
            totale=100,
        )
        self.assertEqual(len(slots), 3)
        self.assertEqual(slots[0]["data"], date(2026, 1, 31))
        self.assertEqual(slots[1]["data"], date(2026, 3, 2))
        self.assertEqual(slots[2]["data"], date(2026, 4, 1))
        self.assertEqual(slots[0]["importo"], 33.33)
        self.assertEqual(slots[1]["importo"], 33.33)
        self.assertEqual(slots[2]["importo"], 33.34)

    def test_ventiquattro_rate(self):
        cond = SimpleNamespace(
            numero_rate=24,
            prima_rata=30,
            intervallo=30,
            giorno_fisso=0,
            mese_esclusione=None,
            mese_esclusione2=None,
            gg_mese_esclus=None,
            gg_mese_esclus2=None,
        )
        slots = calcola_scadenze(
            data_documento=date(2026, 1, 1),
            condizione=cond,
            totale=2400,
        )
        self.assertEqual(len(slots), 24)
        self.assertEqual(slots[0]["importo"], 100.0)
        self.assertEqual(slots[-1]["importo"], 100.0)
        self.assertTrue(all(s["data"] for s in slots))

    def test_senza_data_resta_vuota_con_n_rate(self):
        cond = SimpleNamespace(numero_rate=10, prima_rata=0, intervallo=30)
        slots = calcola_scadenze(data_documento=None, condizione=cond)
        self.assertEqual(len(slots), 10)
        self.assertTrue(all(s["data"] is None for s in slots))

    def test_fine_mese_usa_ultimo_giorno_mese(self):
        cond = SimpleNamespace(
            numero_rate=1,
            prima_rata=0,
            intervallo=0,
            giorno_fisso=31,
            fine_mese=True,
            mese_esclusione=None,
            mese_esclusione2=None,
            gg_mese_esclus=None,
            gg_mese_esclus2=None,
        )
        slots = calcola_scadenze(
            data_documento=date(2026, 2, 10),
            condizione=cond,
        )
        self.assertEqual(slots[0]["data"], date(2026, 2, 28))

    def test_giorno_31_senza_fine_mese_salta_a_mese_con_31(self):
        cond = SimpleNamespace(
            numero_rate=1,
            prima_rata=0,
            intervallo=0,
            giorno_fisso=31,
            fine_mese=False,
            mese_esclusione=None,
            mese_esclusione2=None,
            gg_mese_esclus=None,
            gg_mese_esclus2=None,
        )
        slots = calcola_scadenze(
            data_documento=date(2026, 2, 10),
            condizione=cond,
        )
        self.assertEqual(slots[0]["data"], date(2026, 3, 31))


class TestaDocumentoScadenzeFlagTests(SimpleTestCase):
    def test_obbligatorie_senza_date_non_valido(self):
        form = TestaDocumentoForm({"numero": "1"}, scadenze_obbligatorie=True)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_facoltative_senza_date_valido(self):
        form = TestaDocumentoForm({"numero": "1"}, scadenze_obbligatorie=False)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["scadenze"], [])

    def test_obbligatorie_con_data_valido(self):
        form = TestaDocumentoForm(
            {"numero": "1", "scadenza": ["2026-07-28", "2026-08-28"]},
            scadenze_obbligatorie=True,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["scadenze"], ["2026-07-28", "2026-08-28"])


class ScadenzeDocumentoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for spec in DEFAULT_TIPI_DOCUMENTO:
            TipoDocumento.objects.get_or_create(
                codice=spec["codice"],
                defaults={
                    "label": spec["label"],
                    "ordine": spec["ordine"],
                    "source_table_4d": spec["source_table_4d"],
                    "source_detail_4d": spec["source_detail_4d"],
                    "clifor_tipo": spec["clifor_tipo"],
                },
            )

    def test_usa_date_salvate(self):
        testa = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=1,
            totale=50,
            scadenze=["2026-07-28"],
        )
        slots = scadenze_for_documento(testa)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["data"], date(2026, 7, 28))
        self.assertEqual(slots[0]["importo"], 50.0)

    def test_ensure_senza_pagamento_non_scrive(self):
        testa = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=2,
            data_documento="2026-07-27",
        )
        ensure_scadenze(testa)
        self.assertEqual(testa.scadenze, [])
