import json
from unittest.mock import patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.core.pagination import AI_FILTER_SESSION_KEY, resolve_ai_filter, store_ai_filter
from apps.core.views import AiAssistantView


def _request_with_session(path="/"):
    request = RequestFactory().get(path)
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    return request


class AiListFilterStorageTests(SimpleTestCase):
    def test_store_and_resolve_ai_filter_by_token(self):
        request = _request_with_session("/clienti/")

        token = store_ai_filter(request, table="clienti", pks=["C1", "C2"])
        payload = resolve_ai_filter(request, token=token, expected_table="clienti")

        self.assertIsNotNone(payload)
        self.assertEqual(payload["table"], "clienti")
        self.assertEqual(payload["pks"], ["C1", "C2"])
        self.assertEqual(payload["count"], 2)
        self.assertIn(token, request.session[AI_FILTER_SESSION_KEY])

    def test_resolve_ai_filter_rejects_other_tables(self):
        request = _request_with_session("/clienti/")

        token = store_ai_filter(request, table="clienti", pks=["C1"])

        self.assertIsNone(resolve_ai_filter(request, token=token, expected_table="fornitori"))


class _AuthenticatedUser:
    is_authenticated = True


class AiAssistantListUrlTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.core.ai_assistant.ask_ai")
    def test_ai_list_url_contains_token_and_persists_filter(self, ask_ai_mock):
        ask_ai_mock.return_value = {
            "ok": True,
            "risultati": [{"Codice": "C001"}],
            "link": {
                "url_name": "anagrafiche:cliente_detail",
                "pk_column": "Codice",
                "pk_param": "codice",
            },
            "table": "clienti",
        }

        request = self.factory.post(
            reverse("core:ai_ask"),
            data=json.dumps({"prompt": "clienti spagna"}),
            content_type="application/json",
        )
        request.user = _AuthenticatedUser()
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        response = AiAssistantView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("?ai=1&ai_token=", payload["list_url"])

        token = payload["list_url"].split("ai_token=", 1)[1]
        session_filters = request.session[AI_FILTER_SESSION_KEY]
        self.assertIn(token, session_filters)
        self.assertEqual(session_filters[token]["table"], "clienti")
        self.assertEqual(session_filters[token]["pks"], ["C001"])

    @patch("apps.core.ai_assistant.ask_ai")
    def test_ai_primanota_list_url_contains_token_and_persists_filter(self, ask_ai_mock):
        ask_ai_mock.return_value = {
            "ok": True,
            "risultati": [{"ID": 101}, {"ID": 102}],
            "link": {
                "url_name": "primanota:detail",
                "pk_column": "ID",
                "pk_param": "pk",
            },
            "table": "primanota",
        }

        request = self.factory.post(
            reverse("core:ai_ask"),
            data=json.dumps(
                {
                    "prompt": (
                        "Cerca in Primanota IVA dove imponibile è compreso tra "
                        "1500 e 1750 euro nell'anno in corso"
                    )
                }
            ),
            content_type="application/json",
        )
        request.user = _AuthenticatedUser()
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        response = AiAssistantView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("/primanota/?ai=1&ai_token=", payload["list_url"])

        token = payload["list_url"].split("ai_token=", 1)[1]
        session_filters = request.session[AI_FILTER_SESSION_KEY]
        self.assertIn(token, session_filters)
        self.assertEqual(session_filters[token]["table"], "primanota")
        self.assertEqual(session_filters[token]["pks"], ["101", "102"])

    @patch("apps.core.ai_assistant.ask_ai")
    def test_ai_primanota_dettaglio_query_maps_to_primanota_list(self, ask_ai_mock):
        ask_ai_mock.return_value = {
            "ok": True,
            "risultati": [{"id_added_by_converter": 55}],
            "link": {
                "url_name": "primanota:detail",
                "pk_column": "id_added_by_converter",
                "pk_param": "pk",
            },
            "table": "primanota_dettaglio",
        }

        request = self.factory.post(
            reverse("core:ai_ask"),
            data=json.dumps({"prompt": "primanota iva imponibile > 1000"}),
            content_type="application/json",
        )
        request.user = _AuthenticatedUser()
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        response = AiAssistantView.as_view()(request)

        payload = json.loads(response.content)
        self.assertIn("/primanota/?ai=1&ai_token=", payload["list_url"])
        token = payload["list_url"].split("ai_token=", 1)[1]
        self.assertEqual(
            request.session[AI_FILTER_SESSION_KEY][token]["table"],
            "primanota",
        )

    @patch("apps.core.ai_assistant.ask_ai")
    def test_ai_pdc_list_url_contains_token_and_persists_filter(self, ask_ai_mock):
        ask_ai_mock.return_value = {
            "ok": True,
            "risultati": [{"Codice": "4.01"}, {"Codice": "4.01.001"}],
            "link": {
                "url_name": "pdc:detail",
                "pk_column": "Codice",
                "pk_param": "codice",
            },
            "table": "pdc",
        }

        request = self.factory.post(
            reverse("core:ai_ask"),
            data=json.dumps(
                {"prompt": "cerca nel Piano dei conti dove descrizione è cassa"}
            ),
            content_type="application/json",
        )
        request.user = _AuthenticatedUser()
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        response = AiAssistantView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("/pdc/?ai=1&ai_token=", payload["list_url"])

        token = payload["list_url"].split("ai_token=", 1)[1]
        session_filters = request.session[AI_FILTER_SESSION_KEY]
        self.assertIn(token, session_filters)
        self.assertEqual(session_filters[token]["table"], "pdc")
        self.assertEqual(session_filters[token]["pks"], ["4.01", "4.01.001"])


class AiAssistantExportDownloadUrlTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.core.ai_assistant.ask_ai")
    def test_ai_response_includes_download_url(self, ask_ai_mock):
        token = "a" * 32
        ask_ai_mock.return_value = {
            "ok": True,
            "risultati": [{"Codice": "A1", "Descrizione": "Scarpe"}],
            "link": {
                "url_name": "articoli:detail",
                "pk_column": "Codice",
                "pk_param": "codice",
            },
            "table": "articoli",
            "export_token": token,
            "download_filename": "articoli_2026-08-20.xlsx",
            "export_requested": True,
        }

        request = self.factory.post(
            reverse("core:ai_ask"),
            data=json.dumps(
                {
                    "prompt": (
                        "articoli con descrizione sinonimi di calzature "
                        "genera un file xlsx"
                    )
                }
            ),
            content_type="application/json",
        )
        request.user = _AuthenticatedUser()
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        response = AiAssistantView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(
            payload["download_url"],
            reverse("core:ai_export_download", kwargs={"token": token}),
        )
        self.assertNotIn("export_token", payload)
        self.assertIn("list_url", payload)

    @patch("apps.core.ai_assistant.ask_ai")
    def test_ai_export_with_fornitore_join_includes_list_url(self, ask_ai_mock):
        token = "b" * 32
        ask_ai_mock.return_value = {
            "ok": True,
            "risultati": [
                {
                    "Codice": "A1",
                    "Descrizione": "Scarpe",
                    "CodFornitore": "F1",
                    "RagioneSocialeFornitore": "Forn SpA",
                }
            ],
            "table": "articoli",
            "export_token": token,
            "download_filename": "articoli_2026-08-20.xlsx",
            "export_requested": True,
        }

        request = self.factory.post(
            reverse("core:ai_ask"),
            data=json.dumps(
                {
                    "prompt": (
                        "articoli con descrizione sinonimi di calzature "
                        "crea un file xlsx con codice, descrizione, codice fornitore, "
                        "ragione sociale fornitore"
                    )
                }
            ),
            content_type="application/json",
        )
        request.user = _AuthenticatedUser()
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        response = AiAssistantView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("/articoli/?ai=1&ai_token=", payload["list_url"])
        self.assertEqual(
            payload["download_url"],
            reverse("core:ai_export_download", kwargs={"token": token}),
        )
        token = payload["list_url"].split("ai_token=", 1)[1]
        self.assertEqual(
            request.session[AI_FILTER_SESSION_KEY][token]["pks"],
            ["A1"],
        )

    @patch("apps.core.ai_assistant._execute_query")
    def test_ai_export_without_codice_in_prompt_still_builds_list_url(
        self,
        execute_query_mock,
    ):
        execute_query_mock.return_value = (
            [{"Codice": "A1", "Descrizione": "Scarpe", "Listino1": 10.5}],
            False,
        )
        request = self.factory.post(
            reverse("core:ai_ask"),
            data=json.dumps(
                {
                    "prompt": (
                        "articoli calzature genera xlsx con descrizione e prezzo"
                    )
                }
            ),
            content_type="application/json",
        )
        request.user = _AuthenticatedUser()
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        response = AiAssistantView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("/articoli/?ai=1&ai_token=", payload["list_url"])
        self.assertIn("download_url", payload)
        token = payload["list_url"].split("ai_token=", 1)[1]
        self.assertEqual(
            request.session[AI_FILTER_SESSION_KEY][token]["pks"],
            ["A1"],
        )

    def test_export_download_serves_xlsx(self):
        import tempfile
        from pathlib import Path

        from django.test import override_settings

        from apps.core.ai_export import save_ai_xlsx
        from apps.core.views import AiExportDownloadView

        rows = [{"Codice": "A1", "Descrizione": "Scarpe"}]
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(AI_EXPORT_DIR=tmp):
                saved = save_ai_xlsx(
                    rows=rows,
                    table="articoli",
                    filename_stem="articoli",
                    sheet_title="Articoli",
                )
                request = self.factory.get(
                    reverse(
                        "core:ai_export_download",
                        kwargs={"token": saved["token"]},
                    )
                )
                request.user = _AuthenticatedUser()
                response = AiExportDownloadView.as_view()(
                    request, token=saved["token"]
                )
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(
                        "spreadsheetml.sheet",
                        response["Content-Type"],
                    )
                    self.assertIn(
                        saved["filename"],
                        response["Content-Disposition"],
                    )
                    self.assertTrue(
                        (Path(tmp) / f"{saved['token']}.xlsx").is_file()
                    )
                finally:
                    response.close()

    def test_export_download_serves_csv(self):
        import tempfile
        from pathlib import Path

        from django.test import override_settings

        from apps.core.ai_export import save_ai_export
        from apps.core.views import AiExportDownloadView

        rows = [{"Codice": "A1", "Descrizione": "Scarpe"}]
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(AI_EXPORT_DIR=tmp):
                saved = save_ai_export(
                    rows=rows,
                    table="articoli",
                    filename_stem="articoli",
                    fmt="csv",
                )
                request = self.factory.get(
                    reverse(
                        "core:ai_export_download",
                        kwargs={"token": saved["token"]},
                    )
                )
                request.user = _AuthenticatedUser()
                response = AiExportDownloadView.as_view()(
                    request, token=saved["token"]
                )
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("text/csv", response["Content-Type"])
                    self.assertIn(
                        saved["filename"],
                        response["Content-Disposition"],
                    )
                    self.assertTrue(
                        (Path(tmp) / f"{saved['token']}.csv").is_file()
                    )
                finally:
                    response.close()
