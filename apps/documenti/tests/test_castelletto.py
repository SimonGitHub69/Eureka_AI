"""Test castelletto IVA (merce / sconto / netto / IVA / totale documento).

La % IVA deve arrivare da Aliquota.percentuale (tabella AliquoteIva), non dal
solo parsing del codice riga.
"""

from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase

from apps.aliquote.models import Aliquota
from apps.documenti.castelletto import (
    AliquotaInfo,
    aliquote_map_for_js,
    apply_castelletto_to_testa,
    calcola_castelletto,
    parse_sconto_percent,
    resolve_aliquota,
)
from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO
from apps.documenti.models import RigaDocumento, TestaDocumento, TipoDocumento


def _aliq_cache(**pct_by_code: float) -> dict[str, AliquotaInfo]:
    """Simula anagrafica AliquoteIva (codice → percentuale)."""
    out: dict[str, AliquotaInfo] = {}
    for code, pct in pct_by_code.items():
        info = AliquotaInfo(
            codice=code,
            percentuale=Decimal(str(pct)).quantize(Decimal("0.01")),
            descrizione=f"IVA {code}",
        )
        out[code.upper()] = info
    return out


# Cache tipica usata nei test matematici (come record Aliquota noti)
_CACHE_STD = _aliq_cache(**{"22": 22, "10": 10})


class CastellettoMathTests(SimpleTestCase):
    def test_parse_sconto_percent(self):
        self.assertEqual(parse_sconto_percent("10"), Decimal("10.00"))
        self.assertEqual(parse_sconto_percent("10%"), Decimal("10.00"))
        # Cascata ERP IT: 100×(1−0.9×0.95) = 14,50
        self.assertEqual(parse_sconto_percent("10+5"), Decimal("14.50"))
        self.assertEqual(parse_sconto_percent("10-5"), Decimal("14.50"))
        self.assertEqual(parse_sconto_percent(""), Decimal("0"))

    def test_riepilogo_22_percent_come_screenshot(self):
        """280,38 merce → IVA 61,68 → totale 342,06 (22% da Aliquota)."""
        result = calcola_castelletto(
            [
                {
                    "codice": "ART1",
                    "descrizione": "Prova",
                    "quantita": 1,
                    "prezzo_unitario": 280.38,
                    "sconto": "",
                    "iva": "22",
                }
            ],
            spese={},
            include_spese_zero_row=True,
            aliquote_cache=_CACHE_STD,
        )
        self.assertEqual(len(result.righe), 2)  # merce + SPESE 0
        merce = result.righe[0]
        self.assertFalse(merce.is_spese)
        self.assertEqual(merce.merce, Decimal("280.38"))
        self.assertEqual(merce.sconto, Decimal("0.00"))
        self.assertEqual(merce.netto, Decimal("280.38"))
        self.assertEqual(merce.percentuale, Decimal("22.00"))
        self.assertEqual(merce.iva, Decimal("61.68"))
        self.assertEqual(merce.imponibile_iva, Decimal("342.06"))
        self.assertEqual(merce.label, "IVA 22")

        spese = result.righe[1]
        self.assertTrue(spese.is_spese)
        self.assertEqual(spese.netto, Decimal("0.00"))
        self.assertEqual(spese.percentuale, Decimal("22.00"))
        self.assertEqual(spese.label, "IVA 22 SPESE")

        self.assertEqual(result.totale_netto, Decimal("280.38"))
        self.assertEqual(result.totale_iva, Decimal("61.68"))
        self.assertEqual(result.totale_documento, Decimal("342.06"))
        self.assertEqual(result.totale_quantita, Decimal("1.00"))

    def test_totale_quantita_somma_righe(self):
        result = calcola_castelletto(
            [
                {
                    "quantita": 2,
                    "prezzo_unitario": 10,
                    "iva": "22",
                    "codice": "A",
                },
                {
                    "quantita": 3.5,
                    "prezzo_unitario": 4,
                    "iva": "22",
                    "codice": "B",
                },
            ],
            spese={},
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
        )
        self.assertEqual(result.totale_quantita, Decimal("5.50"))

    def test_sconto_percentuale_su_riga(self):
        # merce = 2×100=200; sconto 10% = 20; netto 180; IVA 22% = 39.60
        result = calcola_castelletto(
            [
                {
                    "quantita": 2,
                    "prezzo_unitario": 100,
                    "sconto": "10",
                    "iva": "22",
                    "codice": "X",
                }
            ],
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("200.00"))
        self.assertEqual(row.sconto, Decimal("20.00"))
        self.assertEqual(row.netto, Decimal("180.00"))
        self.assertEqual(row.iva, Decimal("39.60"))
        self.assertEqual(result.totale_documento, Decimal("219.60"))

    @patch(
        "apps.documenti.sconto.resolve_sconto_percentuale",
        side_effect=lambda x: {"50A": "50+10"}.get((x or "").strip(), x or ""),
    )
    def test_sconto_codice_sconti_risolto_in_calcolo(self, _mock):
        # 50A → 50+10: merce 200; fattore 0.5×0.9=0.45 → sconto 110; netto 90
        result = calcola_castelletto(
            [
                {
                    "quantita": 2,
                    "prezzo_unitario": 100,
                    "sconto": "50A",
                    "iva": "22",
                    "codice": "X",
                }
            ],
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("200.00"))
        self.assertEqual(row.sconto, Decimal("110.00"))
        self.assertEqual(row.netto, Decimal("90.00"))

    def test_sconto_testata_in_calcolo_senza_scrivere_riga(self):
        # Riga senza sconto: usa header_sconto solo nel calcolo
        result = calcola_castelletto(
            [
                {
                    "quantita": 2,
                    "prezzo_unitario": 100,
                    "sconto": "",
                    "iva": "22",
                    "codice": "X",
                }
            ],
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
            header_sconto="10",
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("200.00"))
        self.assertEqual(row.sconto, Decimal("20.00"))
        self.assertEqual(row.netto, Decimal("180.00"))

    def test_sconto_riga_e_testata_in_cascata(self):
        # merce 200; riga 2% + testata 10% → fattore 0.98×0.90=0.882 → sconto 23.60
        result = calcola_castelletto(
            [
                {
                    "quantita": 2,
                    "prezzo_unitario": 100,
                    "sconto": "2",
                    "iva": "22",
                    "codice": "X",
                }
            ],
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
            header_sconto="10",
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("200.00"))
        self.assertEqual(row.sconto, Decimal("23.60"))
        self.assertEqual(row.netto, Decimal("176.40"))

    def test_sconto_composto_cascata_10_piu_5(self):
        # merce 200; 10+5 → fattore 0.855 → sconto 29; netto 171; IVA 22% = 37.62
        result = calcola_castelletto(
            [
                {
                    "quantita": 2,
                    "prezzo_unitario": 100,
                    "sconto": "10+5",
                    "iva": "22",
                    "codice": "X",
                }
            ],
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("200.00"))
        self.assertEqual(row.sconto, Decimal("29.00"))
        self.assertEqual(row.netto, Decimal("171.00"))
        self.assertEqual(row.iva, Decimal("37.62"))
        self.assertEqual(result.totale_documento, Decimal("208.62"))

    def test_prezzo_unitario_tre_decimali(self):
        # 4 × 12,505 = 50,02 merce (prezzo a 3 decimali, merce a 2)
        result = calcola_castelletto(
            [
                {
                    "quantita": 4,
                    "prezzo_unitario": "12,505",
                    "sconto": "",
                    "iva": "22",
                    "codice": "P3",
                }
            ],
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("50.02"))
        self.assertEqual(row.netto, Decimal("50.02"))
        self.assertEqual(row.iva, Decimal("11.00"))
        self.assertEqual(result.totale_documento, Decimal("61.02"))

    def test_spese_testata_su_riga_spese(self):
        result = calcola_castelletto(
            [
                {
                    "quantita": 1,
                    "prezzo_unitario": 100,
                    "sconto": "",
                    "iva": "22",
                    "codice": "A",
                }
            ],
            spese={"spese_trasporto": 10},
            include_spese_zero_row=True,
            aliquote_cache=_CACHE_STD,
        )
        self.assertEqual(len(result.righe), 2)
        spese = result.righe[1]
        self.assertTrue(spese.is_spese)
        self.assertEqual(spese.merce, Decimal("10.00"))
        self.assertEqual(spese.netto, Decimal("10.00"))
        self.assertEqual(spese.iva, Decimal("2.20"))
        self.assertEqual(result.totale_netto, Decimal("110.00"))
        self.assertEqual(result.totale_iva, Decimal("24.20"))
        self.assertEqual(result.totale_documento, Decimal("134.20"))

    def test_due_aliquote(self):
        result = calcola_castelletto(
            [
                {"quantita": 1, "prezzo_unitario": 100, "iva": "22", "codice": "A"},
                {"quantita": 1, "prezzo_unitario": 50, "iva": "10", "codice": "B"},
            ],
            include_spese_zero_row=False,
            aliquote_cache=_CACHE_STD,
        )
        self.assertEqual(len(result.righe), 2)
        by_code = {r.codice_iva.upper(): r for r in result.righe}
        self.assertEqual(by_code["22"].iva, Decimal("22.00"))
        self.assertEqual(by_code["10"].iva, Decimal("5.00"))
        self.assertEqual(result.totale_documento, Decimal("177.00"))

    def test_percentuale_da_cache_non_dal_codice(self):
        """Codice non numerico: la % deve venire dall'anagrafica, non dal parsing."""
        cache = _aliq_cache(**{"XYZ": 7.5})
        result = calcola_castelletto(
            [
                {
                    "quantita": 4,
                    "prezzo_unitario": 25,  # merce 100
                    "sconto": "",
                    "iva": "XYZ",
                    "codice": "ART",
                }
            ],
            include_spese_zero_row=False,
            aliquote_cache=cache,
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("100.00"))
        self.assertEqual(row.percentuale, Decimal("7.50"))
        self.assertEqual(row.iva, Decimal("7.50"))


class CastellettoAliquotaDbTests(TestCase):
    """Usa record Aliquota reali (campo percentuale) quando la tabella esiste."""

    @classmethod
    def setUpClass(cls):
        cls._created_aliquote_table = False
        table = Aliquota._meta.db_table
        if table not in connection.introspection.table_names():
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(Aliquota)
            cls._created_aliquote_table = True
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if getattr(cls, "_created_aliquote_table", False):
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(Aliquota)

    def setUp(self):
        Aliquota.objects.filter(codice__in=["22", "10", "MIO", "VA22"]).delete()
        Aliquota.objects.create(
            codice="22",
            descrizione="Aliquota 22%",
            percentuale=22.0,
        )
        Aliquota.objects.create(
            codice="10",
            descrizione="Aliquota 10%",
            percentuale=10.0,
        )
        Aliquota.objects.create(
            codice="MIO",
            descrizione="Aliquota custom",
            percentuale=12.5,
        )
        Aliquota.objects.create(
            codice="VA22",
            descrizione="IVA Ordinaria 22%",
            percentuale=22.0,
        )

    def test_resolve_usa_percentuale_tabella(self):
        info = resolve_aliquota("22")
        self.assertEqual(info.percentuale, Decimal("22.00"))
        info_mio = resolve_aliquota("MIO")
        self.assertEqual(info_mio.percentuale, Decimal("12.50"))
        # Parsing del codice darebbe 0; la tabella vince
        self.assertEqual(info_mio.descrizione, "Aliquota custom")

    def test_label_usa_descrizione_non_inventata(self):
        """Codice VA22 → Tipo Aliquota Iva = Aliquota.descrizione."""
        info = resolve_aliquota("VA22")
        self.assertEqual(info.percentuale, Decimal("22.00"))
        self.assertEqual(info.descrizione, "IVA Ordinaria 22%")
        self.assertEqual(info.label, "IVA Ordinaria 22%")
        self.assertEqual(info.label_spese, "IVA Ordinaria 22% SPESE")

        result = calcola_castelletto(
            [
                {
                    "quantita": 1,
                    "prezzo_unitario": 100,
                    "sconto": "",
                    "iva": "VA22",
                    "codice": "A",
                }
            ],
            include_spese_zero_row=True,
        )
        merce = result.righe[0]
        self.assertFalse(merce.is_spese)
        self.assertEqual(merce.label, "IVA Ordinaria 22%")
        spese = result.righe[1]
        self.assertTrue(spese.is_spese)
        self.assertEqual(spese.label, "IVA Ordinaria 22% SPESE")

    def test_label_fallback_codice_se_descrizione_vuota(self):
        Aliquota.objects.filter(codice="EMPTY").delete()
        Aliquota.objects.create(codice="EMPTY", descrizione="", percentuale=4.0)
        info = resolve_aliquota("EMPTY")
        self.assertEqual(info.label, "EMPTY")
        self.assertEqual(info.label_spese, "EMPTY SPESE")

    def test_aliquote_map_for_js_include_descrizione(self):
        js_map = aliquote_map_for_js()
        entry = js_map.get("VA22") or js_map.get("va22")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["pct"], 22.0)
        self.assertEqual(entry["descrizione"], "IVA Ordinaria 22%")
        self.assertEqual(entry["label"], "IVA Ordinaria 22%")

    def test_calcola_con_aliquota_db(self):
        result = calcola_castelletto(
            [
                {
                    "quantita": 2,
                    "prezzo_unitario": 50,  # merce 100
                    "sconto": "",
                    "iva": "MIO",
                    "codice": "A",
                }
            ],
            include_spese_zero_row=False,
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("100.00"))
        self.assertEqual(row.percentuale, Decimal("12.50"))
        self.assertEqual(row.iva, Decimal("12.50"))
        self.assertEqual(row.label, "Aliquota custom")
        self.assertEqual(result.totale_documento, Decimal("112.50"))

    def test_qty_x_prezzo_imponibile_poi_iva_22(self):
        result = calcola_castelletto(
            [
                {
                    "quantita": 1,
                    "prezzo_unitario": 280.38,
                    "iva": "22",
                    "codice": "ART",
                }
            ],
            include_spese_zero_row=False,
        )
        row = result.righe[0]
        self.assertEqual(row.merce, Decimal("280.38"))
        self.assertEqual(row.netto, Decimal("280.38"))
        self.assertEqual(row.percentuale, Decimal("22.00"))
        self.assertEqual(row.iva, Decimal("61.68"))


class CastellettoPersistTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._created_aliquote_table = False
        table = Aliquota._meta.db_table
        if table not in connection.introspection.table_names():
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(Aliquota)
            cls._created_aliquote_table = True
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if getattr(cls, "_created_aliquote_table", False):
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(Aliquota)

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
        Aliquota.objects.update_or_create(
            codice="22",
            defaults={"descrizione": "Aliquota 22%", "percentuale": 22.0},
        )

    def test_apply_updates_imponibile_e_totale(self):
        testa = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=1,
            numero=1,
            spese_trasporto=0,
        )
        RigaDocumento.objects.create(
            testa=testa,
            id_4d=1,
            numero_riga=10,
            codice="ART",
            quantita=1,
            prezzo_unitario=280.38,
            iva="22",
        )
        result = apply_castelletto_to_testa(testa)
        testa.save(update_fields=["imponibile", "totale"])
        testa.refresh_from_db()
        self.assertAlmostEqual(testa.imponibile, 280.38, places=2)
        self.assertAlmostEqual(testa.totale, 342.06, places=2)
        self.assertEqual(result.totale_iva, Decimal("61.68"))
        self.assertEqual(result.righe[0].percentuale, Decimal("22.00"))

    def test_modifica_prv_mostra_castelletto_e_campi_riga(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        from apps.core.models import ConfigurazioneProgramma

        user = get_user_model().objects.create_user(
            username="castelletto_edit",
            password="testpass123",
        )
        self.client.login(username="castelletto_edit", password="testpass123")
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_prv = True
        cfg.save()

        testa = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=88001,
            numero=88,
        )
        RigaDocumento.objects.create(
            testa=testa,
            id_4d=88001,
            numero_riga=10,
            codice="ART1",
            descrizione="Prova",
            quantita=2,
            prezzo_unitario=100,
            iva="22",
            sconto="",
        )
        url = reverse(
            "documenti:edit",
            kwargs={"tipo_doc": "PRV", "pk": testa.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="documentoForm"')
        self.assertContains(response, 'id="castellettoIva"')
        self.assertContains(response, "documento-castelletto.js")
        self.assertContains(response, 'name="righe-0-quantita"')
        self.assertContains(response, 'name="righe-0-prezzo_unitario"')
        self.assertContains(response, 'name="righe-0-sconto"')
        self.assertContains(response, 'name="righe-0-iva"')
        # 2×100 = 200 netto; IVA 22% = 44; totale 244
        castelletto = response.context["castelletto"]
        self.assertEqual(float(castelletto.totale_netto), 200.0)
        self.assertEqual(float(castelletto.totale_iva), 44.0)
        self.assertEqual(float(castelletto.totale_documento), 244.0)
        self.assertContains(response, "200,00")
        self.assertContains(response, "44,00")
        self.assertContains(response, "244,00")

    def test_static_castelletto_js_usa_original_name(self):
        from pathlib import Path

        js = Path("static/eureka/js/documento-castelletto.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("data-original-name", js)
        self.assertIn("fieldNameKey", js)
        self.assertIn("addSpeseEnabled", js)
        self.assertIn("add_spese", js)
        disable = Path("static/eureka/js/disable-autocomplete.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("#documentoForm", disable)
