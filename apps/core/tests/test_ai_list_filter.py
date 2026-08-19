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
