from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core.context_processors import ai_debug_flags, programma_documenti
from apps.core.models import ConfigurazioneProgramma
from apps.core.programma import (
    get_ai_example_prompt,
    get_ai_recent_searches_limit,
    get_documenti_menu_extra,
    get_documenti_menu_flags,
    get_documenti_menu_items,
    is_documento_menu_enabled,
)
from apps.documenti.models import TipoDocumento


class ProgrammaDocumentiMenuTests(TestCase):
    def setUp(self):
        self.cfg = ConfigurazioneProgramma.get_solo()
        self.cfg.doc_prv = True
        self.cfg.doc_orv = True
        self.cfg.doc_ora = False
        self.cfg.doc_ddt = True
        self.cfg.doc_fat = False
        self.cfg.doc_ncr = True
        self.cfg.doc_ndb = False
        self.cfg.save()

    def test_get_documenti_menu_flags(self):
        flags = get_documenti_menu_flags()
        self.assertTrue(flags["PRV"])
        self.assertFalse(flags["ORA"])
        self.assertFalse(flags["FAT"])
        self.assertFalse(flags["NDB"])

    def test_is_documento_menu_enabled_case_insensitive(self):
        self.assertTrue(is_documento_menu_enabled("prv"))
        self.assertFalse(is_documento_menu_enabled("ora"))
        self.assertFalse(is_documento_menu_enabled("UNKNOWN"))

    def test_custom_tipo_unknown_without_row_is_disabled(self):
        self.assertFalse(is_documento_menu_enabled("OR2"))

    def test_defaults_are_all_enabled(self):
        self.cfg.doc_prv = True
        self.cfg.doc_orv = True
        self.cfg.doc_ora = True
        self.cfg.doc_ddt = True
        self.cfg.doc_fat = True
        self.cfg.doc_ncr = True
        self.cfg.doc_ndb = True
        self.cfg.save()
        self.assertTrue(all(get_documenti_menu_flags().values()))

    def test_context_processor_for_authenticated_user(self):
        user = get_user_model().objects.create_user(
            username="tester",
            password="testpass123",
        )
        request = RequestFactory().get("/")
        request.user = user
        ctx = programma_documenti(request)
        self.assertFalse(ctx["eureka_doc_menu"]["ORA"])
        self.assertTrue(ctx["eureka_doc_menu"]["PRV"])
        self.assertTrue(ctx["eureka_doc_menu_any"])

    def test_context_processor_anonymous_defaults_all_enabled(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        ctx = programma_documenti(request)
        self.assertTrue(all(ctx["eureka_doc_menu"].values()))
        self.assertEqual(ctx["eureka_doc_menu_extra"], [])

    def test_extra_altro_attivo_is_in_menu(self):
        TipoDocumento.objects.create(
            codice="XTR",
            label="Extra trasporto",
            categoria=TipoDocumento.CATEGORIA_ALTRO,
            attivo=True,
            ordine=90,
        )
        extras = get_documenti_menu_extra()
        self.assertEqual([t.codice for t in extras], ["XTR"])
        self.assertTrue(is_documento_menu_enabled("XTR"))

    def test_extra_altro_non_attivo_is_not_in_menu(self):
        TipoDocumento.objects.create(
            codice="XTR",
            label="Extra trasporto",
            categoria=TipoDocumento.CATEGORIA_ALTRO,
            attivo=False,
            ordine=90,
        )
        self.assertEqual(get_documenti_menu_extra(), [])
        self.assertFalse(is_documento_menu_enabled("XTR"))

    def test_built_in_codes_are_not_duplicated_in_extra(self):
        TipoDocumento.objects.update_or_create(
            codice="DDT",
            defaults={
                "label": "DDT / Bolle",
                "categoria": TipoDocumento.CATEGORIA_ALTRO,
                "attivo": True,
            },
        )
        self.assertNotIn("DDT", [t.codice for t in get_documenti_menu_extra()])

    def test_preventivi_ff_not_in_menu(self):
        TipoDocumento.objects.update_or_create(
            codice="PRF",
            defaults={
                "label": "PREVENTIVO FF",
                "categoria": TipoDocumento.CATEGORIA_PREVENTIVI,
                "serie": "FF",
                "attivo": True,
                "ordine": 0,
                "clifor_tipo": "C",
                "source_table_4d": "Preventivi",
            },
        )
        self.assertNotIn("PRF", [t.codice for t in get_documenti_menu_extra()])
        self.assertTrue(is_documento_menu_enabled("PRF"))
        codes = [item["codice"] for item in get_documenti_menu_items()]
        self.assertNotIn("PRF", codes)

    def test_menu_items_follow_ordine_field(self):
        TipoDocumento.objects.filter(codice="PRV").update(ordine=5)
        TipoDocumento.objects.filter(codice="ORV").update(ordine=40)
        TipoDocumento.objects.filter(codice="DDT").update(ordine=15)
        TipoDocumento.objects.filter(codice="NCR").update(ordine=20)
        codes = [item["codice"] for item in get_documenti_menu_items()]
        self.assertEqual(codes, ["PRV", "DDT", "NCR", "ORV"])

    def test_extra_altro_is_inserted_by_ordine(self):
        TipoDocumento.objects.filter(codice="ORV").update(ordine=10)
        TipoDocumento.objects.filter(codice="PRV").update(ordine=30)
        TipoDocumento.objects.filter(codice="DDT").update(ordine=40)
        TipoDocumento.objects.filter(codice="NCR").update(ordine=60)
        TipoDocumento.objects.create(
            codice="XTR",
            label="Extra trasporto",
            categoria=TipoDocumento.CATEGORIA_ALTRO,
            attivo=True,
            ordine=25,
        )
        codes = [item["codice"] for item in get_documenti_menu_items()]
        self.assertEqual(codes, ["ORV", "XTR", "PRV", "DDT", "NCR"])

    def test_context_processor_items_follow_ordine(self):
        TipoDocumento.objects.filter(codice="PRV").update(ordine=1)
        TipoDocumento.objects.filter(codice="ORV").update(ordine=2)
        user = get_user_model().objects.create_user(
            username="orderuser",
            password="testpass123",
        )
        request = RequestFactory().get("/")
        request.user = user
        ctx = programma_documenti(request)
        codes = [item["codice"] for item in ctx["eureka_doc_menu_items"]]
        self.assertEqual(codes[0], "PRV")
        self.assertEqual(codes[1], "ORV")
        self.assertNotIn("ORA", codes)
        self.assertNotIn("FAT", codes)


class ProgrammaExtraMenuTests(TestCase):
    def setUp(self):
        self.cfg = ConfigurazioneProgramma.get_solo()

    def test_carbon_enabled_by_default(self):
        from apps.core.programma import get_extra_menu_flags, is_extra_enabled

        self.assertTrue(is_extra_enabled("CARBON"))
        self.assertTrue(get_extra_menu_flags()["CARBON"])

    def test_carbon_can_be_disabled(self):
        from apps.core.programma import is_extra_enabled

        self.cfg.extra_carbon = False
        self.cfg.save()
        self.assertFalse(is_extra_enabled("carbon"))
        self.assertFalse(is_extra_enabled("unknown"))

    def test_context_processor_exposes_extra_carbon(self):
        user = get_user_model().objects.create_user(
            username="extrauser",
            password="testpass123",
        )
        self.cfg.extra_carbon = False
        self.cfg.save()
        request = RequestFactory().get("/")
        request.user = user
        ctx = programma_documenti(request)
        self.assertFalse(ctx["eureka_extra_carbon"])
        self.assertFalse(ctx["eureka_extra_menu"]["CARBON"])

    def test_carbon_hub_forbidden_when_disabled(self):
        user = get_user_model().objects.create_user(
            username="carbonuser",
            password="testpass123",
        )
        self.cfg.extra_carbon = False
        self.cfg.save()
        self.client.force_login(user)
        from django.urls import reverse

        response = self.client.get(reverse("carbon:hub"))
        self.assertEqual(response.status_code, 403)

    def test_salva_parametri_nasconde_voce_menu_carbon(self):
        user = get_user_model().objects.create_superuser(
            username="progadmin",
            password="testpass123",
        )
        self.client.force_login(user)
        self.assertTrue(ConfigurazioneProgramma.get_solo().extra_carbon)

        response = self.client.post(
            reverse("core:parametri_programma"),
            {
                "suono_errore_attivo": "on",
                "doc_prv": "on",
                "doc_orv": "on",
                "doc_ora": "on",
                "doc_ddt": "on",
                "doc_fat": "on",
                "doc_ncr": "on",
                "doc_ndb": "on",
                "note": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ConfigurazioneProgramma.get_solo().extra_carbon)

        dashboard = self.client.get(reverse("dashboard:index"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertFalse(dashboard.context["eureka_extra_carbon"])
        self.assertNotContains(dashboard, 'data-nav-section="carbon"')
        self.assertNotContains(dashboard, "st-nav-section-label\">CARBON")


class ProgrammaAiSettingsTests(TestCase):
    DEFAULT_AI_EXAMPLE_PROMPT = (
        "Cerca tutti i movimenti IVA il cui imponibile è compreso tra 1500 e 1750 "
        "nell'anno in corso"
    )

    def setUp(self):
        self.cfg = ConfigurazioneProgramma.get_solo()

    def test_ai_example_prompt_default(self):
        self.assertEqual(self.cfg.ai_example_prompt, self.DEFAULT_AI_EXAMPLE_PROMPT)
        self.assertEqual(get_ai_example_prompt(), self.DEFAULT_AI_EXAMPLE_PROMPT)

    def test_ai_example_prompt_is_exposed_in_context(self):
        custom = "Elenca i clienti con fatturato superiore a 10000 euro"
        self.cfg.ai_example_prompt = custom
        self.cfg.save()

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        ctx = ai_debug_flags(request)

        self.assertEqual(ctx["eureka_ai_example_prompt"], custom)

    def test_ai_example_prompt_falls_back_when_blank(self):
        self.cfg.ai_example_prompt = "   "
        self.cfg.save(update_fields=["ai_example_prompt"])
        self.assertEqual(get_ai_example_prompt(), self.DEFAULT_AI_EXAMPLE_PROMPT)

    def test_ai_recent_searches_limit_default_is_10(self):
        self.assertEqual(self.cfg.ai_recent_searches_limit, 10)
        self.assertEqual(get_ai_recent_searches_limit(), 10)

    def test_ai_recent_searches_limit_is_exposed_in_context(self):
        self.cfg.ai_recent_searches_limit = 25
        self.cfg.debug_ai_sql = True
        self.cfg.save()

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        ctx = ai_debug_flags(request)

        self.assertEqual(ctx["eureka_ai_recent_searches_limit"], 25)
        self.assertTrue(ctx["eureka_ai_debug_sql"])

    def test_ai_recent_searches_limit_is_clamped(self):
        self.cfg.ai_recent_searches_limit = 0
        self.cfg.save(update_fields=["ai_recent_searches_limit"])
        self.assertEqual(get_ai_recent_searches_limit(), 10)

        self.cfg.ai_recent_searches_limit = 999
        self.cfg.save(update_fields=["ai_recent_searches_limit"])
        self.assertEqual(get_ai_recent_searches_limit(), 100)

    def test_salva_parametri_programma_con_limite_ai(self):
        user = get_user_model().objects.create_superuser(
            username="aiadmin",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("core:parametri_programma"),
            {
                "suono_errore_attivo": "on",
                "debug_ai_sql": "on",
                "ai_recent_searches_limit": "15",
                "ai_example_prompt": "Mostra le fatture del mese scorso",
                "inventario_discrepanza_pct": "20",
                "prezzo_decimali": "4",
                "doc_prv": "on",
                "doc_orv": "on",
                "doc_ora": "on",
                "doc_ddt": "on",
                "doc_fat": "on",
                "doc_ncr": "on",
                "doc_ndb": "on",
                "extra_carbon": "on",
                "note": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        cfg = ConfigurazioneProgramma.get_solo()
        self.assertEqual(cfg.ai_recent_searches_limit, 15)
        self.assertTrue(cfg.debug_ai_sql)
        self.assertEqual(cfg.ai_example_prompt, "Mostra le fatture del mese scorso")
        self.assertEqual(cfg.inventario_discrepanza_pct, 20)
        self.assertEqual(cfg.prezzo_decimali, 4)