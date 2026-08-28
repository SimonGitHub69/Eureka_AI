"""Test filtro elenco documenti (q = numero/serie)."""

from datetime import datetime

from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO
from apps.documenti.models import TestaDocumento, TipoDocumento
from apps.documenti.views import _filter_documenti_queryset, list_tipo_codes_for


class DocumentoListFilterTests(TestCase):
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
        TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=100,
            numero=6,
            alfa="FF",
            codice_clifor="C001",
            destinatario="Acme",
        )
        TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=101,
            numero=6,
            alfa="T",
            codice_clifor="C002",
            destinatario="Other",
        )
        TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=102,
            numero=12,
            alfa="FF",
            codice_clifor="C003",
            destinatario="Serie FF",
            codice_agente="A12",
        )
        TipoDocumento.objects.update_or_create(
            codice="PRF",
            defaults={
                "label": "PREVENTIVO FF",
                "categoria": TipoDocumento.CATEGORIA_PREVENTIVI,
                "serie": "FF",
                "attivo": True,
                "source_table_4d": "Preventivi",
                "source_detail_4d": "Preventivi_Dettaglio",
                "clifor_tipo": "C",
            },
        )
        TestaDocumento.objects.create(
            tipo_doc_id="PRF",
            id_4d=200,
            numero=99,
            alfa="FF",
            codice_clifor="C099",
            destinatario="Offerta FF",
        )

    def _qs(self, q: str = "", **extra):
        params = {"q": q} if q else {}
        params.update(extra)
        request = RequestFactory().get("/documenti/PRV/", params)
        return _filter_documenti_queryset(request, "PRV")

    def test_q_numero_slash_serie(self):
        qs = self._qs("6/FF")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().id_4d, 100)
        self.assertEqual(qs.first().numero_documento, "6/FF")

    def test_q_numero_slash_serie_spaces(self):
        self.assertEqual(self._qs("6 / FF").count(), 1)

    def test_q_serie_alone(self):
        self.assertEqual(self._qs("FF").count(), 3)

    def test_q_numero_alone(self):
        self.assertEqual(self._qs("6").count(), 2)

    def test_q_codice_agente(self):
        qs = self._qs("A12")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().id_4d, 102)

    def test_q_preventivo_ff_numero_serie(self):
        qs = self._qs("99/FF")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().tipo_doc_id, "PRF")
        self.assertEqual(qs.first().id_4d, 200)

    def test_q_preventivo_ff_destinatario(self):
        qs = self._qs("Offerta FF")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().tipo_doc_id, "PRF")

    def test_elenco_prv_include_prf(self):
        request = RequestFactory().get("/documenti/PRV/")
        qs = _filter_documenti_queryset(request, "PRV")
        self.assertEqual(set(qs.values_list("tipo_doc_id", flat=True)), {"PRV", "PRF"})
        self.assertEqual(list_tipo_codes_for("PRV"), ("PRV", "PRF"))
        self.assertEqual(list_tipo_codes_for("FAT"), ("FAT",))

    def test_elenco_prv_include_serie_t(self):
        TipoDocumento.objects.update_or_create(
            codice="PRT",
            defaults={
                "label": "Preventivi T",
                "categoria": TipoDocumento.CATEGORIA_PREVENTIVI,
                "serie": "T",
                "attivo": True,
                "source_table_4d": "Preventivi",
                "source_detail_4d": "Preventivi_Dettaglio",
                "clifor_tipo": "C",
            },
        )
        codes = list_tipo_codes_for("PRV")
        self.assertIn("PRF", codes)
        self.assertIn("PRT", codes)

    def test_filtro_serie_ff(self):
        qs = self._qs(serie="FF")
        self.assertEqual(qs.count(), 3)
        self.assertTrue(all((d.alfa or "").upper() == "FF" for d in qs))

    def test_filtro_serie_case_insensitive(self):
        self.assertEqual(self._qs(serie="ff").count(), 3)

    def test_filtro_serie_t(self):
        qs = self._qs(serie="T")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().id_4d, 101)

    def test_filtro_serie_e_numero(self):
        qs = self._qs("6", serie="FF")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().id_4d, 100)

    def test_ordine_data_desc_poi_numero_alfa(self):
        day = timezone.make_aware(datetime(2026, 1, 15, 12, 0, 0))
        earlier = timezone.make_aware(datetime(2026, 1, 14, 12, 0, 0))
        TestaDocumento.objects.create(
            tipo_doc_id="PRV", id_4d=301, numero=10, alfa="T", data_documento=day
        )
        TestaDocumento.objects.create(
            tipo_doc_id="PRV", id_4d=302, numero=20, alfa="A", data_documento=day
        )
        TestaDocumento.objects.create(
            tipo_doc_id="PRV", id_4d=303, numero=20, alfa="FF", data_documento=day
        )
        TestaDocumento.objects.create(
            tipo_doc_id="PRV", id_4d=304, numero=99, alfa="Z", data_documento=earlier
        )
        qs = _filter_documenti_queryset(RequestFactory().get("/documenti/PRV/"), "PRV")
        ids = list(qs.filter(id_4d__in=[301, 302, 303, 304]).values_list("id_4d", flat=True))
        self.assertEqual(ids, [302, 303, 301, 304])
