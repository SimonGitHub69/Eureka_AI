from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.pdc.bilancio_verifica import (
    BilancioRiga,
    BilancioVerificaResult,
    inserisci_riepiloghi,
)
from apps.pdc.views_bilancio_verifica import BilancioVerificaPrintView


class BilancioVerificaUrlTests(SimpleTestCase):
    def test_url_resolves(self):
        url = reverse("pdc:bilancio_verifica")
        self.assertEqual(url, "/pdc/bilancio-verifica/")

    def test_requires_login(self):
        request = RequestFactory().get("/pdc/bilancio-verifica/")
        request.user = AnonymousUser()
        response = BilancioVerificaPrintView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


class BilancioRigaTests(SimpleTestCase):
    def test_saldo_periodo_unico(self):
        dare = BilancioRiga(
            codice="1.10.1",
            descrizione="Cassa",
            dare_periodo=100.0,
            avere_periodo=40.0,
        )
        self.assertEqual(dare.saldo_periodo, 60.0)
        self.assertEqual(dare.saldo_finale, 60.0)

        avere = BilancioRiga(
            codice="2.01.1",
            descrizione="Fornitori",
            dare_periodo=10.0,
            avere_periodo=90.0,
        )
        self.assertEqual(avere.saldo_periodo, -80.0)
        self.assertEqual(avere.saldo_finale, -80.0)

    def test_include_precedente_in_saldo(self):
        riga = BilancioRiga(
            codice="1.10.1",
            descrizione="Cassa",
            dare_precedente=50.0,
            avere_precedente=20.0,
            dare_periodo=10.0,
            avere_periodo=5.0,
        )
        self.assertEqual(riga.saldo_precedente, 30.0)
        self.assertEqual(riga.saldo_finale, 35.0)

    def test_solo_movimenti_periodo_ignora_saldo_storico(self):
        solo_saldo = BilancioRiga(
            codice="1.10.4",
            descrizione="CAMBIALI ESTERE",
            dare_precedente=10733.24,
            avere_precedente=13416.55,
        )
        self.assertTrue(solo_saldo.ha_saldo)
        self.assertFalse(solo_saldo.ha_movimento_periodo)


class BilancioPrintColumnsTests(SimpleTestCase):
    def test_saldo_periodo_e_dare_meno_avere(self):
        riga = BilancioRiga(
            codice="1.10.9",
            descrizione="AMAZON",
            dare_periodo=1_201_987.30,
            avere_periodo=797_827.52,
        )
        self.assertEqual(riga.saldo_periodo, 404_159.78)
        self.assertEqual(
            round(riga.dare_periodo - riga.avere_periodo, 2), riga.saldo_periodo
        )

    def test_totale_saldo_e_differenza_somme(self):
        result = BilancioVerificaResult(
            data_da=date(2026, 1, 1),
            data_a=date(2026, 12, 31),
            totale_dare_periodo=100.0,
            totale_avere_periodo=40.0,
        )
        result.totale_saldo_periodo = round(
            result.totale_dare_periodo - result.totale_avere_periodo, 2
        )
        self.assertEqual(result.totale_saldo_periodo, 60.0)


class BilancioSoloPdcTests(SimpleTestCase):
    def test_partite_clienti_non_sono_contropartite(self):
        from apps.pdc.hierarchy import pdc_is_contropartita

        self.assertTrue(pdc_is_contropartita("1.10.9"))
        self.assertFalse(pdc_is_contropartita("C0005"))
        self.assertFalse(pdc_is_contropartita("1.10"))
        self.assertFalse(pdc_is_contropartita("1"))


class BilancioAllegatoRollupTests(SimpleTestCase):
    def test_partite_clifor_riconosciute(self):
        from apps.pdc.bilancio_verifica import _is_partita_clifor

        self.assertTrue(_is_partita_clifor("C0005"))
        self.assertTrue(_is_partita_clifor("F12"))
        self.assertFalse(_is_partita_clifor("1.13.1"))
        self.assertFalse(_is_partita_clifor("1.10.9"))

    def test_conto_allegato_default_e_mappa(self):
        from apps.pdc.bilancio_verifica import (
            DEFAULT_CONTO_CLIENTI,
            DEFAULT_CONTO_FORNITORI,
            _conto_allegato,
        )

        self.assertEqual(_conto_allegato("C999", {}), DEFAULT_CONTO_CLIENTI)
        self.assertEqual(_conto_allegato("F999", {}), DEFAULT_CONTO_FORNITORI)
        self.assertEqual(
            _conto_allegato("C1", {"C1": "1.13.9"}),
            "1.13.9",
        )


class BilancioModalitaTests(SimpleTestCase):
    def test_normalize_modalita(self):
        from apps.pdc.bilancio_verifica import (
            MODALITA_BILANCIO,
            MODALITA_CLIENTI,
            MODALITA_FORNITORI,
            modalita_label,
            normalize_modalita,
        )

        self.assertEqual(normalize_modalita(None), MODALITA_BILANCIO)
        self.assertEqual(normalize_modalita("clienti"), MODALITA_CLIENTI)
        self.assertEqual(normalize_modalita("fornitori"), MODALITA_FORNITORI)
        self.assertEqual(normalize_modalita("xyz"), MODALITA_BILANCIO)
        self.assertEqual(
            modalita_label("clienti"), "Situazione analitica clienti"
        )
        self.assertEqual(
            modalita_label("fornitori"), "Situazione analitica fornitori"
        )

    def test_analitica_sql_usa_codice_partita_come_partitario(self):
        from apps.pdc.bilancio_verifica import _ANALITICA_CLIFOR_SQL

        self.assertIn('p."CodicePartita"', _ANALITICA_CLIFOR_SQL)
        self.assertIn("(avere + importo_iva) AS dare_cli", _ANALITICA_CLIFOR_SQL)
        self.assertIn("tipo IN (1, 3)", _ANALITICA_CLIFOR_SQL)
        # NC: niente split pos→Dare / neg→Avere (resta firmato in Dare clienti).
        self.assertNotIn("WHEN (avere + importo_iva) < 0", _ANALITICA_CLIFOR_SQL)


class BilancioIvaFlipTests(SimpleTestCase):
    def test_sql_inverte_lati_per_tipo_2_e_4(self):
        from apps.pdc.bilancio_verifica import _AGG_SQL

        self.assertIn("WHEN tipo IN (2, 4) THEN avere_amt ELSE 0 END AS dare", _AGG_SQL)
        self.assertIn("WHEN tipo IN (2, 4) THEN dare_amt ELSE 0 END AS avere", _AGG_SQL)


class BilancioRiepiloghiTests(SimpleTestCase):
    def test_inserisce_conto_e_mastro_al_cambio_gruppo(self):
        dettaglio = [
            BilancioRiga(codice="1.10.1", descrizione="Assegni", dare_periodo=100.0),
            BilancioRiga(codice="1.10.8", descrizione="Paypal", avere_periodo=10.0),
            BilancioRiga(codice="1.11.1", descrizione="Banca", dare_periodo=50.0),
            BilancioRiga(codice="2.30.1", descrizione="Fornitori", avere_periodo=20.0),
        ]
        desc = {
            "1.10": "CASSA",
            "1.11": "BANCA C/C",
            "1": "ATTIVO PATRIMONIALE",
            "2.30": "FORNITORI",
            "2": "PASSIVO PATRIMONIALE",
        }
        righe = inserisci_riepiloghi(dettaglio, descrizioni=desc)
        codes = [r.codice for r in righe]
        self.assertEqual(
            codes,
            [
                "1.10.1",
                "1.10.8",
                "1.10",
                "1.11.1",
                "1.11",
                "1",
                "2.30.1",
                "2.30",
                "2",
            ],
        )
        cassa = next(r for r in righe if r.codice == "1.10")
        self.assertTrue(cassa.is_riepilogo)
        self.assertEqual(cassa.descrizione, "CASSA")
        self.assertEqual(cassa.dare_periodo, 100.0)
        self.assertEqual(cassa.avere_periodo, 10.0)
        attivo = next(r for r in righe if r.codice == "1")
        self.assertTrue(attivo.is_riepilogo)
        self.assertEqual(attivo.dare_periodo, 150.0)
        self.assertEqual(attivo.avere_periodo, 10.0)


class BilancioVerificaViewGateTests(SimpleTestCase):
    def _auth_request(self, path="/pdc/bilancio-verifica/", data=None):
        from django.contrib.auth import get_user_model
        from django.http import HttpResponse

        request = RequestFactory().get(path, data or {})
        request.user = get_user_model()(username="t", is_staff=True)
        return request, HttpResponse("ok")

    def test_without_preview_skips_query(self):
        request, fake_resp = self._auth_request()
        with patch(
            "apps.pdc.views_bilancio_verifica.build_bilancio_verifica"
        ) as mocked_build:
            with patch(
                "apps.pdc.views_bilancio_verifica.render",
                return_value=fake_resp,
            ) as mocked_render:
                with patch(
                    "apps.pdc.views_bilancio_verifica.resolve_print_azienda_context",
                    return_value={},
                ):
                    with patch(
                        "apps.pdc.views_bilancio_verifica._resolve_azienda_header",
                        return_value={},
                    ):
                        response = BilancioVerificaPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        mocked_build.assert_not_called()
        ctx = mocked_render.call_args.args[2]
        self.assertFalse(ctx["print_preview_ready"])
        self.assertEqual(ctx["pagina_da"], 1)

    def test_with_preview_calls_builder(self):
        request, fake_resp = self._auth_request(
            data={
                "anteprima": "1",
                "data_da": "2026-01-01",
                "data_a": "2026-03-31",
                "solo_movimenti": "1",
                "mostra_prec": "1",
            }
        )
        fake = BilancioVerificaResult(
            data_da=date(2026, 1, 1),
            data_a=date(2026, 3, 31),
            righe=[
                BilancioRiga(
                    codice="1.10.1",
                    descrizione="Cassa",
                    dare_periodo=100.0,
                )
            ],
            totale_dare_periodo=100.0,
            totale_saldo_periodo=100.0,
        )
        with patch(
            "apps.pdc.views_bilancio_verifica.build_bilancio_verifica",
            return_value=fake,
        ) as mocked_build:
            with patch(
                "apps.pdc.views_bilancio_verifica.render",
                return_value=fake_resp,
            ) as mocked_render:
                with patch(
                    "apps.pdc.views_bilancio_verifica.resolve_print_azienda_context",
                    return_value={},
                ):
                    with patch(
                        "apps.pdc.views_bilancio_verifica._resolve_azienda_header",
                        return_value={},
                    ):
                        response = BilancioVerificaPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        mocked_build.assert_called_once()
        self.assertEqual(mocked_build.call_args.kwargs["modalita"], "bilancio")
        ctx = mocked_render.call_args.args[2]
        self.assertTrue(ctx["print_preview_ready"])
        self.assertEqual(ctx["bilancio"].righe[0].codice, "1.10.1")
        self.assertEqual(ctx["modalita"], "bilancio")

    def test_analitica_clienti_passa_modalita(self):
        request, fake_resp = self._auth_request(
            data={
                "anteprima": "1",
                "data_da": "2026-01-01",
                "data_a": "2026-03-31",
                "modalita": "clienti",
                "solo_movimenti": "1",
            }
        )
        fake = BilancioVerificaResult(
            data_da=date(2026, 1, 1),
            data_a=date(2026, 3, 31),
            righe=[
                BilancioRiga(
                    codice="C0005",
                    descrizione="ACME",
                    dare_periodo=50.0,
                )
            ],
            totale_dare_periodo=50.0,
            totale_saldo_periodo=50.0,
        )
        with patch(
            "apps.pdc.views_bilancio_verifica.build_bilancio_verifica",
            return_value=fake,
        ) as mocked_build:
            with patch(
                "apps.pdc.views_bilancio_verifica.render",
                return_value=fake_resp,
            ) as mocked_render:
                with patch(
                    "apps.pdc.views_bilancio_verifica.resolve_print_azienda_context",
                    return_value={},
                ):
                    with patch(
                        "apps.pdc.views_bilancio_verifica._resolve_azienda_header",
                        return_value={},
                    ):
                        response = BilancioVerificaPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_build.call_args.kwargs["modalita"], "clienti")
        ctx = mocked_render.call_args.args[2]
        self.assertEqual(ctx["titolo_stampa"], "Situazione analitica clienti")
        self.assertEqual(ctx["count_label"], "clienti")