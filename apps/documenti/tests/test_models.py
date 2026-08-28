"""Test modelli documenti (DB Django)."""

from django.test import SimpleTestCase, TestCase

from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO
from apps.documenti.models import RigaDocumento, TestaDocumento, TipoDocumento
from apps.documenti.numerazione import format_numero_documento


class FormatNumeroDocumentoTests(SimpleTestCase):
    def test_con_serie(self):
        self.assertEqual(format_numero_documento(1, "FF"), "1/FF")
        self.assertEqual(format_numero_documento(47, "A"), "47/A")

    def test_senza_serie_niente_slash(self):
        self.assertEqual(format_numero_documento(1, ""), "1")
        self.assertEqual(format_numero_documento(1, None), "1")
        self.assertEqual(format_numero_documento(1, "  "), "1")
        self.assertFalse(format_numero_documento(1, "").endswith("/"))

    def test_solo_serie(self):
        self.assertEqual(format_numero_documento(None, "FF"), "FF")
        self.assertEqual(format_numero_documento("", "FF"), "FF")

    def test_vuoto(self):
        self.assertEqual(format_numero_documento(None, ""), "")
        self.assertEqual(format_numero_documento(None, "", empty="—"), "—")

    def test_proprieta_modello(self):
        self.assertEqual(TestaDocumento(numero=1, alfa="FF").numero_documento, "1/FF")
        self.assertEqual(TestaDocumento(numero=1, alfa="").numero_documento, "1")
        self.assertEqual(TestaDocumento(numero=1, alfa="  ").numero_documento, "1")
        self.assertEqual(TestaDocumento(numero=None, alfa="").numero_documento, "—")

    def test_totale_spese_zero_se_add_spese_no(self):
        doc = TestaDocumento(
            add_spese=False,
            spese_trasporto=10,
            spese_imballo=5,
            spese_incasso=2,
        )
        self.assertEqual(doc.totale_spese, 0.0)
        doc.add_spese = True
        self.assertEqual(doc.totale_spese, 17.0)


class DocumentiModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for spec in DEFAULT_TIPI_DOCUMENTO:
            TipoDocumento.objects.create(
                codice=spec["codice"],
                label=spec["label"],
                ordine=spec["ordine"],
                source_table_4d=spec["source_table_4d"],
                source_detail_4d=spec["source_detail_4d"],
                clifor_tipo=spec["clifor_tipo"],
            )

    def test_numero_documento_con_serie(self):
        testa = TestaDocumento.objects.create(
            tipo_doc_id="ORV",
            id_4d=1,
            numero=47,
            alfa="A",
        )
        self.assertEqual(testa.numero_documento, "47/A")

    def test_numero_documento_senza_serie(self):
        testa = TestaDocumento.objects.create(
            tipo_doc_id="ORV",
            id_4d=2,
            numero=1,
            alfa="",
        )
        self.assertEqual(testa.numero_documento, "1")

    def test_numero_documento_serie_solo_spazi(self):
        testa = TestaDocumento.objects.create(
            tipo_doc_id="ORV",
            id_4d=3,
            numero=1,
            alfa="  ",
        )
        self.assertEqual(testa.numero_documento, "1")

    def test_unique_tipo_id4d(self):
        TestaDocumento.objects.create(tipo_doc_id="ORV", id_4d=99, numero=1)
        with self.assertRaises(Exception):
            TestaDocumento.objects.create(tipo_doc_id="ORV", id_4d=99, numero=2)

    def test_righe_cascade(self):
        testa = TestaDocumento.objects.create(tipo_doc_id="DDT", id_4d=10, numero=1)
        RigaDocumento.objects.create(testa=testa, id_4d=1, codice="X")
        self.assertEqual(testa.righe.count(), 1)
        testa.delete()
        self.assertEqual(RigaDocumento.objects.count(), 0)

    def test_is_nota_credito_by_tipo(self):
        testa = TestaDocumento.objects.create(tipo_doc_id="NCR", id_4d=5)
        self.assertTrue(testa.is_nota_credito)
