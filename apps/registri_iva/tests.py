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
        for name, suffix in (
            ("registri_iva:print_list", "/stampa/"),
            ("registri_iva:export_list", "/export/"),
            ("registri_iva:liquidazione", "/liquidazione/"),
        ):
            with self.subTest(url=name):
                url = reverse(name)
                self.assertTrue(url.endswith(suffix))


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

    def test_is_registro_acquisto(self):
        from apps.registri_iva.libro_registro import _is_registro_acquisto
        from apps.registri_iva.models import RegistroIva

        acq = RegistroIva(codice="9", tipo_registro="Acquisto")
        ven = RegistroIva(codice="1", tipo_registro="Vendita")
        self.assertTrue(_is_registro_acquisto(acq))
        self.assertFalse(_is_registro_acquisto(ven))
        self.assertFalse(_is_registro_acquisto(None))

    def test_is_registro_corrispettivi(self):
        from apps.registri_iva.libro_registro import _is_registro_corrispettivi
        from apps.registri_iva.models import RegistroIva

        corr = RegistroIva(codice="C", tipo_registro="Corrispettivi")
        self.assertTrue(_is_registro_corrispettivi(corr))
        ven = RegistroIva(codice="1", tipo_registro="Vendita")
        self.assertFalse(_is_registro_corrispettivi(ven))
        self.assertFalse(_is_registro_corrispettivi(None))

    def test_libro_template_definitiva_senza_righe(self):
        """Definitiva abilitata anche a registro vuoto (barra obliqua)."""
        from pathlib import Path

        html = Path(
            "apps/registri_iva/templates/registri_iva/libro_registro_print.html"
        ).read_text(encoding="utf-8")
        self.assertIn('id="btnStampaDefinitiva"', html)
        btn_snip = html.split('id="btnStampaDefinitiva"')[1][:220]
        self.assertNotIn("libro.righe", btn_snip)
        self.assertNotIn("not data_a", btn_snip)
        self.assertIn("eureka-print-libro-vuoto", html)
        self.assertIn("eureka-print-libro-vuoto__slash", html)

    def test_importi_riga_libro_scorpora_corrispettivi(self):
        from unittest.mock import MagicMock, patch

        from apps.documenti.castelletto import AliquotaInfo
        from apps.registri_iva.libro_registro import _importi_riga_libro

        riga = MagicMock()
        riga.imponibile = 122.0  # lordo IVA inclusa
        riga.importo_iva = 26.84  # valore errato in DB (ignorato in scorporo)
        riga.codice_iva = "22"
        with patch(
            "apps.primanota.iva.resolve_aliquota",
            return_value=AliquotaInfo(
                codice="22", percentuale=22, descrizione="IVA 22%"
            ),
        ):
            imp, iva, tot = _importi_riga_libro(
                riga, iva_inclusa=True, aliquota_cache={}
            )
        self.assertEqual(imp, 100.0)
        self.assertEqual(iva, 22.0)
        self.assertEqual(tot, 122.0)

        riga.imponibile = 100.0
        riga.importo_iva = 22.0
        imp2, iva2, tot2 = _importi_riga_libro(
            riga, iva_inclusa=False, aliquota_cache={}
        )
        self.assertEqual(imp2, 100.0)
        self.assertEqual(iva2, 22.0)
        self.assertEqual(tot2, 122.0)

    def test_libro_col_count_with_competenza(self):
        base = LibroRegistroIvaDati(
            registro=None,
            registro_label="",
            periodo_label="",
            anno=None,
            mostra_competenza=False,
        )
        self.assertEqual(base.col_count, 10)
        self.assertEqual(base.label_colspan, 6)
        acq = LibroRegistroIvaDati(
            registro=None,
            registro_label="",
            periodo_label="",
            anno=None,
            mostra_competenza=True,
        )
        self.assertEqual(acq.col_count, 11)
        self.assertEqual(acq.label_colspan, 7)

    def test_split_iva_by_percentuale_ind(self):
        from apps.registri_iva.libro_registro import _split_iva

        self.assertEqual(_split_iva(100.0, 0), (100.0, 0.0))
        self.assertEqual(_split_iva(100.0, 100), (0.0, 100.0))
        self.assertEqual(_split_iva(100.0, 40), (60.0, 40.0))
        self.assertEqual(_split_iva(22.0, 50), (11.0, 11.0))

    def test_date_in_period_for_competenza(self):
        from datetime import date

        from apps.registri_iva.libro_registro import _date_in_period

        da = date(2026, 2, 1)
        a = date(2026, 2, 28)
        self.assertTrue(_date_in_period(date(2026, 2, 15), da, a))
        self.assertFalse(_date_in_period(date(2026, 1, 31), da, a))
        self.assertFalse(_date_in_period(date(2026, 3, 1), da, a))
        self.assertFalse(_date_in_period(None, da, a))
        # Gennaio: stessa regola
        self.assertTrue(
            _date_in_period(date(2026, 1, 10), date(2026, 1, 1), date(2026, 1, 31))
        )
        self.assertFalse(
            _date_in_period(date(2025, 12, 31), date(2026, 1, 1), date(2026, 1, 31))
        )

    def test_iva_altra_competenza_delta(self):
        libro = LibroRegistroIvaDati(
            registro=None,
            registro_label="Acquisti",
            periodo_label="Gennaio 2026",
            anno=2026,
            totale_iva=1114.0,
            totale_iva_competenza=588.0,
            totale_iva_competenza_mese=1702.0,
            mostra_riepilogo_competenza=True,
            mese_iva_label="Gennaio 2026",
            mese_successivo_label="Febbraio 2026",
        )
        self.assertEqual(libro.totale_iva_competenza_mese, 1702.0)
        self.assertEqual(libro.mese_iva_label, "Gennaio 2026")

    def test_month_bounds_and_next(self):
        from datetime import date

        from apps.registri_iva.libro_registro import (
            _mese_label,
            _month_bounds,
            _next_mese_label,
            _next_month_end,
            _prev_mese_label,
        )

        start, end = _month_bounds(date(2026, 1, 15))
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 1, 31))
        self.assertEqual(_next_month_end(start), date(2026, 2, 28))
        self.assertEqual(_mese_label(start), "Gennaio 2026")
        self.assertEqual(_next_mese_label(start), "Febbraio 2026")
        self.assertEqual(_prev_mese_label(date(2026, 2, 1)), "Gennaio 2026")
        self.assertEqual(_prev_mese_label(date(2026, 1, 1)), "Dicembre 2025")

    def test_dicembre_senza_riepilogo_2(self):
        """A dicembre non si estende a gennaio: niente R2, resta da detrarre nov."""
        from unittest.mock import MagicMock, patch

        request = RequestFactory().get(
            "/registri-iva/stampa/",
            {
                "registro": "9",
                "data_da": "2025-12-01",
                "data_a": "2025-12-31",
                "anteprima": "1",
            },
        )
        registro = MagicMock()
        registro.codice = "9"
        registro.descrizione = "Acquisti"
        registro.tipo_registro = "Acquisto"
        with patch(
            "apps.registri_iva.libro_registro.RegistroIva.objects.filter"
        ) as mock_reg, patch(
            "apps.registri_iva.libro_registro._filter_registrazioni_libro",
            return_value=[],
        ):
            mock_reg.return_value.first.return_value = registro
            libro = build_libro_registro_iva(request)
        self.assertTrue(libro.mostra_riepilogo_competenza)
        self.assertFalse(libro.mostra_riepilogo_2)
        self.assertEqual(libro.mese_iva_label, "Dicembre 2025")
        self.assertEqual(libro.mese_precedente_label, "Novembre 2025")
        self.assertEqual(libro.mese_successivo_label, "")

    def test_parse_includi_reg_successive(self):
        from apps.registri_iva.libro_registro import parse_includi_reg_successive

        self.assertFalse(parse_includi_reg_successive({}))
        self.assertTrue(parse_includi_reg_successive({"incl_reg_succ": "1"}))
        self.assertTrue(parse_includi_reg_successive({"incl_reg_succ": "on"}))
        self.assertFalse(parse_includi_reg_successive({"incl_reg_succ": "0"}))
        self.assertFalse(parse_includi_reg_successive({"incl_reg_succ": "false"}))
        # QueryDict: hidden 0 + checkbox 1 → last wins
        from django.http import QueryDict

        qd = QueryDict("incl_reg_succ=0&incl_reg_succ=1")
        self.assertTrue(parse_includi_reg_successive(qd))
        qd_off = QueryDict("incl_reg_succ=0")
        self.assertFalse(parse_includi_reg_successive(qd_off))

    def test_libro_view_passes_includi_reg_succ(self):
        from unittest.mock import Mock

        from django.http import HttpResponse

        request = RequestFactory().get(
            "/registri-iva/stampa/", {"incl_reg_succ": "0"}
        )
        request.user = Mock(is_authenticated=True)
        with patch(
            "apps.registri_iva.views.registro_iva_choices",
            return_value=[("", "—"), ("1", "1 — Vendite")],
        ), patch(
            "apps.registri_iva.views.resolve_print_azienda_context",
            return_value={},
        ), patch(
            "apps.registri_iva.views._resolve_azienda_header",
            return_value={
                "ragione_sociale": "",
                "indirizzo": "",
                "codice_fiscale": "",
                "partita_iva": "",
            },
        ), patch(
            "apps.registri_iva.views.render",
            return_value=HttpResponse("ok"),
        ) as mock_render:
            response = RegistroIvaLibroPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args[0][2]
        self.assertFalse(context["includi_reg_succ"])

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
        self.assertFalse(context["includi_reg_succ"])


class RegistriIvaStampaDefinitivaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="stampa_def",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def test_save_and_get_stampa_stato(self):
        from datetime import date

        from apps.registri_iva.stampa_stato import get_stampa_stato, save_stampa_stato

        save_stampa_stato(
            registro_codice="9",
            data_finale=date(2026, 1, 31),
            ultimo_protocollo=42,
            ultima_pagina=7,
        )
        info = get_stampa_stato("9")
        self.assertEqual(info.data_finale, date(2026, 1, 31))
        self.assertEqual(info.ultimo_protocollo, 42)
        self.assertEqual(info.ultima_pagina, 7)
        self.assertEqual(info.data_da_suggerita.isoformat(), "2026-02-01")
        self.assertEqual(info.data_a_suggerita.isoformat(), "2026-02-28")
        self.assertEqual(info.pagina_da_suggerita, 8)

    def test_conferma_definitiva_endpoint(self):
        url = reverse("registri_iva:conferma_definitiva")
        response = self.client.post(
            url,
            {
                "registro": "ACQ",
                "data_finale": "2026-03-31",
                "ultimo_protocollo": "15",
                "ultima_pagina": "3",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["ultima_pagina"], 3)
        from apps.registri_iva.models import RegistroIvaStampaStato

        row = RegistroIvaStampaStato.objects.get(registro_codice="ACQ")
        self.assertEqual(row.ultimo_protocollo, 15)

    def test_libro_prefill_data_da_from_stato(self):
        from datetime import date
        from unittest.mock import Mock

        from django.http import HttpResponse

        from apps.registri_iva.stampa_stato import save_stampa_stato

        save_stampa_stato(
            registro_codice="1",
            data_finale=date(2026, 1, 31),
            ultimo_protocollo=10,
            ultima_pagina=5,
        )
        request = RequestFactory().get(
            "/registri-iva/stampa/", {"registro": "1"}
        )
        request.user = Mock(is_authenticated=True)
        with patch(
            "apps.registri_iva.views.registro_iva_choices",
            return_value=[("", "—"), ("1", "1")],
        ), patch(
            "apps.registri_iva.views.resolve_print_azienda_context",
            return_value={},
        ), patch(
            "apps.registri_iva.views._resolve_azienda_header",
            return_value={
                "ragione_sociale": "",
                "indirizzo": "",
                "codice_fiscale": "",
                "partita_iva": "",
            },
        ), patch(
            "apps.registri_iva.views.render",
            return_value=HttpResponse("ok"),
        ) as mock_render:
            RegistroIvaLibroPrintView.as_view()(request)
        context = mock_render.call_args[0][2]
        self.assertEqual(context["data_da"], "2026-02-01")
        self.assertEqual(context["data_a"], "2026-02-28")
        self.assertEqual(context["pagina_da"], 6)

    def test_stampa_stato_suggerimenti_endpoint(self):
        from datetime import date
        from unittest.mock import Mock, patch

        from django.http import JsonResponse

        from apps.registri_iva.stampa_stato import StampaDefinitivaInfo
        from apps.registri_iva.views import stampa_stato_suggerimenti

        request = RequestFactory().get(
            "/registri-iva/stampa/stato-suggerimenti/", {"registro": "4"}
        )
        request.user = Mock(is_authenticated=True)
        with patch(
            "apps.registri_iva.views.get_stampa_stato",
            return_value=StampaDefinitivaInfo(
                registro_codice="4",
                data_finale=date(2026, 1, 31),
                ultimo_protocollo=9,
                ultima_pagina=12,
            ),
        ):
            response = stampa_stato_suggerimenti(request)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content.decode())
        self.assertTrue(data["ok"])
        self.assertEqual(data["data_da"], "2026-02-01")
        self.assertEqual(data["data_a"], "2026-02-28")
        self.assertEqual(data["pagina_da"], 13)
        self.assertEqual(data["data_finale"], "2026-01-31")

    def test_periodo_sovrappone(self):
        from datetime import date

        from apps.registri_iva.stampa_stato import (
            StampaDefinitivaInfo,
            periodo_sovrappone_definitiva,
        )

        stato = StampaDefinitivaInfo(
            registro_codice="1", data_finale=date(2026, 1, 31), ultima_pagina=2
        )
        self.assertTrue(
            periodo_sovrappone_definitiva(date(2026, 1, 1), date(2026, 1, 15), stato)
        )
        self.assertFalse(
            periodo_sovrappone_definitiva(date(2026, 2, 1), date(2026, 2, 28), stato)
        )

    def test_stima_num_pagine(self):
        from apps.registri_iva.stampa_stato import stima_num_pagine

        self.assertEqual(stima_num_pagine(0), 1)
        self.assertGreaterEqual(stima_num_pagine(90), 2)
        # Riepilogo = sempre +1 foglio rispetto alle sole pagine movimenti.
        self.assertEqual(stima_num_pagine(0, con_riepilogo=True), 2)
        senza = stima_num_pagine(90)
        self.assertEqual(stima_num_pagine(90, con_riepilogo=True), senza + 1)


class LiquidazionePeriodicaTests(SimpleTestCase):
    def test_resolve_periodo_anno_mese(self):
        from datetime import date

        from apps.registri_iva.liquidazione import resolve_periodo_liquidazione

        da, a, label = resolve_periodo_liquidazione({"anno": "2026", "mese": "2"})
        self.assertEqual(da, date(2026, 2, 1))
        self.assertEqual(a, date(2026, 2, 28))
        self.assertEqual(label, "Febbraio 2026")

    def test_parse_credito_precedente(self):
        from apps.registri_iva.liquidazione import _parse_credito_precedente

        self.assertEqual(_parse_credito_precedente("1.234,56"), 1234.56)
        self.assertEqual(_parse_credito_precedente("12,5"), 12.5)
        self.assertEqual(_parse_credito_precedente(""), 0.0)

    def test_liquidazione_stampa_codice_constant(self):
        from apps.registri_iva.stampa_stato import LIQUIDAZIONE_STAMPA_CODICE

        self.assertEqual(LIQUIDAZIONE_STAMPA_CODICE, "LIQUIDAZIONE")

    def test_liquidazione_view_filter_form(self):
        from unittest.mock import Mock

        from django.http import HttpResponse

        from apps.registri_iva.stampa_stato import StampaDefinitivaInfo
        from apps.registri_iva.views import LiquidazionePeriodicaIvaPrintView

        request = RequestFactory().get("/registri-iva/liquidazione/")
        request.user = Mock(is_authenticated=True)

        def _stato(code):
            return StampaDefinitivaInfo(registro_codice=code or "LIQUIDAZIONE")

        with patch(
            "apps.registri_iva.views.get_stampa_stato",
            side_effect=_stato,
        ), patch(
            "apps.registri_iva.views._default_registro_liquidazione",
            return_value="4",
        ), patch(
            "apps.registri_iva.views.registro_iva_choices",
            return_value=[("4", "4 — ACQUISTI")],
        ), patch(
            "apps.registri_iva.views.resolve_print_azienda_context",
            return_value={},
        ), patch(
            "apps.registri_iva.views.resolve_azienda_header_liquidazione",
            return_value={
                "ragione_sociale": "",
                "indirizzo": "",
                "codice_fiscale": "",
                "partita_iva": "",
            },
        ), patch(
            "apps.registri_iva.views.render",
            return_value=HttpResponse("ok"),
        ) as mock_render:
            response = LiquidazionePeriodicaIvaPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args[0][2]
        self.assertFalse(context["print_preview_ready"])
        self.assertIn("mese_choices", context)
        self.assertIn("Liquidazione Periodica IVA", context["libro"].registro_label)
        self.assertEqual(context["pagina_da"], 1)
        self.assertEqual(context["registro"], "4")
        self.assertEqual(context["liquidazione_codice"], "4")
        self.assertIn("stampa_stato", context)
        self.assertIn("stampa_stato_registro", context)
        self.assertIn("conferma_url", context)

    def test_liquidazione_prefill_pagina_from_registro_collegato(self):
        from datetime import date
        from unittest.mock import Mock

        from django.http import HttpResponse

        from apps.registri_iva.stampa_stato import (
            LIQUIDAZIONE_STAMPA_CODICE,
            StampaDefinitivaInfo,
        )
        from apps.registri_iva.views import LiquidazionePeriodicaIvaPrintView

        request = RequestFactory().get(
            "/registri-iva/liquidazione/", {"registro": "4"}
        )
        request.user = Mock(is_authenticated=True)

        def _stato(code):
            if code == LIQUIDAZIONE_STAMPA_CODICE:
                return StampaDefinitivaInfo(
                    registro_codice=LIQUIDAZIONE_STAMPA_CODICE,
                    data_finale=date(2026, 1, 31),
                    ultima_pagina=0,
                )
            return StampaDefinitivaInfo(
                registro_codice="4",
                data_finale=date(2026, 1, 31),
                ultimo_protocollo=48,
                ultima_pagina=2,
            )

        with patch(
            "apps.registri_iva.views.get_stampa_stato",
            side_effect=_stato,
        ), patch(
            "apps.registri_iva.views.registro_iva_choices",
            return_value=[("4", "4 — ACQUISTI")],
        ), patch(
            "apps.registri_iva.views.resolve_print_azienda_context",
            return_value={},
        ), patch(
            "apps.registri_iva.views.resolve_azienda_header_liquidazione",
            return_value={
                "ragione_sociale": "",
                "indirizzo": "",
                "codice_fiscale": "",
                "partita_iva": "",
            },
        ), patch(
            "apps.registri_iva.views.render",
            return_value=HttpResponse("ok"),
        ) as mock_render:
            response = LiquidazionePeriodicaIvaPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args[0][2]
        self.assertEqual(context["anno"], 2026)
        self.assertEqual(context["mese"], 2)
        self.assertEqual(context["registro"], "4")
        self.assertEqual(context["pagina_da"], 3)

    def test_conferma_definitiva_sync_periodo_liquidazione(self):
        from datetime import date
        from unittest.mock import Mock, patch

        from apps.registri_iva.stampa_stato import (
            LIQUIDAZIONE_STAMPA_CODICE,
            StampaDefinitivaInfo,
        )
        from apps.registri_iva.views import conferma_stampa_definitiva

        request = RequestFactory().post(
            "/registri-iva/stampa/conferma-definitiva/",
            {
                "registro": "4",
                "data_finale": "2026-01-31",
                "ultima_pagina": "5",
                "sync_periodo_liquidazione": "1",
            },
        )
        request.user = Mock(is_authenticated=True)
        saved = []

        def _save(**kwargs):
            saved.append(kwargs)
            return Mock(
                registro_codice=kwargs["registro_codice"],
                data_finale=kwargs["data_finale"],
                ultimo_protocollo=kwargs["ultimo_protocollo"],
                ultima_pagina=kwargs["ultima_pagina"],
            )

        with patch(
            "apps.registri_iva.views.get_stampa_stato",
            return_value=StampaDefinitivaInfo(
                registro_codice="4",
                ultimo_protocollo=48,
                ultima_pagina=2,
            ),
        ), patch(
            "apps.registri_iva.views.save_stampa_stato",
            side_effect=_save,
        ):
            response = conferma_stampa_definitiva(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["registro_codice"], "4")
        self.assertEqual(saved[0]["ultima_pagina"], 5)
        self.assertEqual(saved[0]["ultimo_protocollo"], 48)
        self.assertEqual(saved[1]["registro_codice"], LIQUIDAZIONE_STAMPA_CODICE)
        self.assertEqual(saved[1]["data_finale"], date(2026, 1, 31))
