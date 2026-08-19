from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.core import ai_assistant


class AiAssistantPromptGuardTests(SimpleTestCase):
    def test_detects_article_category_request(self):
        self.assertTrue(
            ai_assistant._is_article_category_request(
                "mostrami gli articoli del settore abbigliamento"
            )
        )

    def test_does_not_mark_plain_article_search_as_category_request(self):
        self.assertFalse(
            ai_assistant._is_article_category_request(
                "cerca articoli con vite nella descrizione"
            )
        )

    def test_detects_explicit_article_text_search(self):
        self.assertTrue(
            ai_assistant._is_explicit_article_text_search(
                "cerca articoli con abbigliamento nella descrizione"
            )
        )

    def test_build_user_prompt_adds_structured_guard_for_category_requests(self):
        guarded = ai_assistant._build_ai_user_prompt(
            "mostrami gli articoli della categoria abbigliamento"
        )
        self.assertIn('articoli."CatOmogenea"', guarded)
        self.assertIn('articoli."CodGruppo"', guarded)
        self.assertIn('{"sql": null, "spiegazione": "..."}', guarded)
        self.assertIn('Non usare articoli."Descrizione"', guarded)

    def test_build_user_prompt_keeps_explicit_text_search_unchanged(self):
        prompt = "cerca articoli con abbigliamento nella descrizione"
        self.assertEqual(ai_assistant._build_ai_user_prompt(prompt), prompt)

    @override_settings(AI_BACKEND="openai")
    @patch("apps.core.ai_assistant._execute_query", return_value=([], False))
    @patch("apps.core.ai_assistant._get_model", return_value="test-model")
    @patch("apps.core.ai_assistant._get_client")
    def test_ask_ai_sends_guarded_prompt_for_article_category_requests(
        self,
        get_client_mock,
        _get_model_mock,
        _execute_query_mock,
    ):
        fake_client = SimpleNamespace()
        fake_client.chat = SimpleNamespace()
        fake_client.chat.completions = SimpleNamespace()
        fake_client.chat.completions.create = lambda **kwargs: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"sql":"SELECT \\"Codice\\", \\"CatOmogenea\\" FROM articoli LIMIT 1","spiegazione":"ok"}'
                    )
                )
            ]
        )
        get_client_mock.return_value = fake_client

        ai_assistant.ask_ai("mostrami gli articoli del settore abbigliamento")

        create_call = get_client_mock.return_value.chat.completions.create
        self.assertIsNotNone(create_call)

    @override_settings(AI_BACKEND="openai")
    @patch("apps.core.ai_assistant._execute_query", return_value=([], False))
    @patch("apps.core.ai_assistant._get_model", return_value="test-model")
    @patch("apps.core.ai_assistant._get_client")
    def test_ask_ai_message_contains_structured_guard(
        self,
        get_client_mock,
        _get_model_mock,
        _execute_query_mock,
    ):
        recorded = {}

        def fake_create(**kwargs):
            recorded["messages"] = kwargs["messages"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"sql":"SELECT \\"Codice\\", \\"CatOmogenea\\" FROM articoli LIMIT 1","spiegazione":"ok"}'
                        )
                    )
                ]
            )

        fake_client = SimpleNamespace()
        fake_client.chat = SimpleNamespace()
        fake_client.chat.completions = SimpleNamespace(create=fake_create)
        get_client_mock.return_value = fake_client

        ai_assistant.ask_ai("mostrami gli articoli del settore abbigliamento")

        user_message = recorded["messages"][1]["content"]
        self.assertIn('articoli."CatOmogenea"', user_message)
        self.assertIn('articoli."CodGruppo"', user_message)
        self.assertIn("Non usare articoli.", user_message)

    @override_settings(AI_BACKEND="openai")
    @patch("apps.core.ai_assistant._execute_query", return_value=([], False))
    @patch("apps.core.ai_assistant._get_model", return_value="test-model")
    @patch("apps.core.ai_assistant._get_client")
    def test_ask_ai_keeps_explicit_description_search_prompt(
        self,
        get_client_mock,
        _get_model_mock,
        _execute_query_mock,
    ):
        recorded = {}

        def fake_create(**kwargs):
            recorded["messages"] = kwargs["messages"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"sql":"SELECT \\"Codice\\", \\"Descrizione\\" FROM articoli WHERE \\"Descrizione\\" ILIKE \'%abbigliamento%\' LIMIT 1","spiegazione":"ok"}'
                        )
                    )
                ]
            )

        fake_client = SimpleNamespace()
        fake_client.chat = SimpleNamespace()
        fake_client.chat.completions = SimpleNamespace(create=fake_create)
        get_client_mock.return_value = fake_client

        prompt = "cerca articoli con abbigliamento nella descrizione"
        ai_assistant.ask_ai(prompt)

        self.assertEqual(recorded["messages"][1]["content"], prompt)


class AiAssistantPrimaryKeyFixTests(SimpleTestCase):
    def test_removes_wrong_id_when_codice_present(self):
        sql = 'SELECT "ID", "Codice", "Descrizione" FROM articoli WHERE "Descrizione" ILIKE \'%calzature%\''
        fixed = ai_assistant._fix_primary_key_columns(sql)
        self.assertNotIn('"ID"', fixed)
        self.assertIn('"Codice"', fixed)

    def test_replaces_id_with_codice_when_codice_missing(self):
        sql = 'SELECT "ID", "Descrizione" FROM articoli LIMIT 3'
        fixed = ai_assistant._fix_primary_key_columns(sql)
        self.assertNotIn('"ID"', fixed)
        self.assertIn('"Codice"', fixed)

    def test_keeps_id_for_primanota(self):
        sql = 'SELECT "ID", "DataReg" FROM primanota LIMIT 10'
        fixed = ai_assistant._fix_primary_key_columns(sql)
        self.assertIn('"ID"', fixed)

    @override_settings(AI_BACKEND="openai")
    @patch("apps.core.ai_assistant._execute_query", return_value=([{"Codice": "A1", "Descrizione": "Calzature"}], False))
    @patch("apps.core.ai_assistant._get_model", return_value="test-model")
    @patch("apps.core.ai_assistant._get_client")
    def test_ask_ai_fixes_wrong_id_in_generated_sql(
        self,
        get_client_mock,
        _get_model_mock,
        _execute_query_mock,
    ):
        fake_client = SimpleNamespace()
        fake_client.chat = SimpleNamespace()
        fake_client.chat.completions = SimpleNamespace()
        fake_client.chat.completions.create = lambda **kwargs: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"sql":"SELECT \\"ID\\", \\"Codice\\", \\"Descrizione\\" FROM articoli '
                            'WHERE \\"Descrizione\\" ILIKE \'%calzature%\' LIMIT 3","spiegazione":"ok"}'
                        )
                    )
                )
            ]
        )
        get_client_mock.return_value = fake_client

        result = ai_assistant.ask_ai("articoli con calzature nella descrizione", limit=3)

        self.assertTrue(result["ok"])
        self.assertNotIn('"ID"', result["sql"])
        self.assertIn('"Codice"', result["sql"])
        execute_sql = _execute_query_mock.call_args[0][0]
        self.assertNotIn('"ID"', execute_sql)


class AiAssistantRateLimitTests(SimpleTestCase):
    @override_settings(AI_BACKEND="groq")
    @patch("apps.core.ai_assistant._is_ollama_available", return_value=False)
    @patch("apps.core.ai_assistant._get_client")
    def test_ask_ai_returns_friendly_message_on_groq_429(
        self,
        get_client_mock,
        _ollama_mock,
    ):
        class RateLimitError(Exception):
            pass

        fake_client = SimpleNamespace()
        fake_client.chat = SimpleNamespace()
        fake_client.chat.completions = SimpleNamespace()

        def fake_create(**kwargs):
            raise RateLimitError(
                "Error code: 429 - Rate limit reached for model "
                "openai/gpt-oss-20b ... tokens per day (TPD): Limit 200000"
            )

        fake_client.chat.completions.create = fake_create
        get_client_mock.return_value = fake_client

        with patch(
            "apps.core.ai_assistant._is_groq_rate_limit_error",
            side_effect=lambda exc: "429" in str(exc),
        ):
            result = ai_assistant.ask_ai("mostrami i clienti")

        self.assertFalse(result["ok"])
        self.assertIn("Limite Groq raggiunto", result["errore"])
        self.assertNotIn("Error code: 429", result["errore"])

    @override_settings(AI_BACKEND="groq", OLLAMA_MODEL="llama3.1")
    @patch("apps.core.ai_assistant._execute_query", return_value=([], False))
    @patch("apps.core.ai_assistant._is_ollama_available", return_value=True)
    @patch("apps.core.ai_assistant._get_ollama_client")
    @patch("apps.core.ai_assistant._get_client")
    def test_ask_ai_falls_back_to_ollama_on_groq_429(
        self,
        get_client_mock,
        get_ollama_client_mock,
        _ollama_available_mock,
        _execute_query_mock,
    ):
        groq_client = SimpleNamespace()
        groq_client.chat = SimpleNamespace()
        groq_client.chat.completions = SimpleNamespace()
        groq_client.chat.completions.create = lambda **kwargs: (_ for _ in ()).throw(
            Exception("Error code: 429 - Rate limit reached")
        )
        get_client_mock.return_value = groq_client

        ollama_client = SimpleNamespace()
        ollama_client.chat = SimpleNamespace()
        ollama_client.chat.completions = SimpleNamespace()
        ollama_client.chat.completions.create = lambda **kwargs: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"sql":"SELECT \\"Codice\\" FROM clienti LIMIT 1","spiegazione":"ok"}'
                    )
                )
            ]
        )
        get_ollama_client_mock.return_value = ollama_client

        result = ai_assistant.ask_ai("mostrami i clienti")

        self.assertTrue(result["ok"])
        get_ollama_client_mock.assert_called_once()
