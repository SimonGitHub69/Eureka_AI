import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.anagrafiche.codice_fiscale import (
    cf_eligible,
    normalize_cf,
    validate_codice_fiscale,
)
from apps.anagrafiche.forms import _validate_cod_fiscale
from apps.anagrafiche.models import Cliente, Fornitore, get_by_codice

VALID_CF_PERSONA = "RSSMRA80A01H501U"
INVALID_CF_PERSONA = "RSSMRA80A01H501X"
VALID_CF_NUMERICO = "01154930471"
INVALID_CF_NUMERICO = "01154930470"


class AnagraficheNazioneIsoMappingTests(SimpleTestCase):
    def test_cod_nazione_maps_to_codice_iso(self):
        self.assertEqual(Cliente._meta.get_field("cod_nazione").db_column, "CodiceISO")
        self.assertEqual(Fornitore._meta.get_field("cod_nazione").db_column, "CodiceISO")


class CodiceFiscaleValidationTest(SimpleTestCase):
    def test_empty_cf_is_allowed(self):
        result = validate_codice_fiscale("", cod_nazione="IT")
        self.assertIsNone(result.valid)
        self.assertEqual(result.kind, "empty")

    def test_valid_persona_fisica(self):
        result = validate_codice_fiscale(VALID_CF_PERSONA, cod_nazione="IT")
        self.assertTrue(result.valid)
        self.assertEqual(result.kind, "persona")
        self.assertEqual(result.normalized, VALID_CF_PERSONA)

    def test_invalid_persona_fisica_checksum(self):
        result = validate_codice_fiscale(INVALID_CF_PERSONA, cod_nazione="IT")
        self.assertFalse(result.valid)

    def test_valid_numerico(self):
        result = validate_codice_fiscale(VALID_CF_NUMERICO, cod_nazione="IT")
        self.assertTrue(result.valid)
        self.assertEqual(result.kind, "partita_iva")

    def test_invalid_numerico_checksum(self):
        result = validate_codice_fiscale(INVALID_CF_NUMERICO, cod_nazione="IT")
        self.assertFalse(result.valid)

    def test_foreign_subject_skips_strict_validation(self):
        result = validate_codice_fiscale("INVALID123", cod_nazione="DE")
        self.assertFalse(result.eligible)
        self.assertIsNone(result.valid)

    def test_normalize_cf(self):
        self.assertEqual(normalize_cf("rss mra80a01h501u"), VALID_CF_PERSONA)

    def test_cf_eligible(self):
        self.assertTrue(cf_eligible(VALID_CF_PERSONA, "IT"))
        self.assertFalse(cf_eligible("", "IT"))
        self.assertFalse(cf_eligible(VALID_CF_PERSONA, "DE"))


class CodiceFiscaleFormTest(SimpleTestCase):
    def test_validate_helper_accepts_valid_cf(self):
        cleaned = _validate_cod_fiscale(
            {"cod_fiscale": VALID_CF_PERSONA, "cod_nazione": "IT", "partita_iva": ""},
            persona_fisica=True,
        )
        self.assertEqual(cleaned["cod_fiscale"], VALID_CF_PERSONA)

    def test_validate_helper_rejects_invalid_cf(self):
        with self.assertRaises(ValidationError):
            _validate_cod_fiscale(
                {"cod_fiscale": INVALID_CF_PERSONA, "cod_nazione": "IT", "partita_iva": ""},
            )

    def test_validate_helper_allows_foreign_cf(self):
        cleaned = _validate_cod_fiscale(
            {"cod_fiscale": "ABC123", "cod_nazione": "DE", "partita_iva": ""},
        )
        self.assertEqual(cleaned["cod_fiscale"], "ABC123")


class CfCheckApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@example.com", "secret")
        self.client.login(username="testuser", password="secret")

    def test_cf_check_api_valid(self):
        response = self.client.post(
            reverse("anagrafiche:cf_check"),
            data=json.dumps({"cod_fiscale": VALID_CF_PERSONA, "cod_nazione": "IT"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["normalized"], VALID_CF_PERSONA)

    def test_cf_check_preview(self):
        response = self.client.post(
            reverse("anagrafiche:cf_check"),
            data=json.dumps({"preview": True, "cod_fiscale": VALID_CF_PERSONA, "cod_nazione": "IT"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["eligible"])


class AnagraficheViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser2", "test2@example.com", "secret")
        self.client.login(username="testuser2", password="secret")

    def test_clienti_list_returns_200(self):
        response = self.client.get(reverse("anagrafiche:clienti_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clienti")

    def test_fornitori_list_returns_200(self):
        response = self.client.get(reverse("anagrafiche:fornitori_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fornitori")

    def test_cliente_detail_when_data_exists(self):
        cliente = Cliente.objects.first()
        if not cliente:
            self.skipTest("Nessun cliente nel database")
        url = reverse("anagrafiche:cliente_detail", kwargs={"codice": cliente.codice})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cliente.codice)
        self.assertContains(response, "Controllo codice fiscale")

    def test_cliente_detail_c16294_no_fielderror(self):
        """Destinazioni annotate Replace(TextField) non deve crashare il detail."""
        if not Cliente.objects.filter(codice__iexact="C16294").exists():
            self.skipTest("Cliente C16294 assente")
        url = reverse("anagrafiche:cliente_detail", kwargs={"codice": "C16294"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_cliente_edit_shows_destinazioni_card(self):
        cliente = Cliente.objects.first()
        if not cliente:
            self.skipTest("Nessun cliente nel database")
        url = reverse("anagrafiche:cliente_edit", kwargs={"codice": cliente.codice})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Destinazioni diverse")
        self.assertContains(response, reverse("destinazioni:create"))
        self.assertContains(response, f"codice={cliente.codice}")
        self.assertContains(response, "from=anagrafica")
        self.assertNotContains(response, "Salva l'anagrafica per gestire le destinazioni diverse.")

    def test_fornitore_edit_shows_destinazioni_card(self):
        fornitore = Fornitore.objects.first()
        if not fornitore:
            self.skipTest("Nessun fornitore nel database")
        url = reverse("anagrafiche:fornitore_edit", kwargs={"codice": fornitore.codice})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Destinazioni diverse")
        self.assertContains(response, reverse("destinazioni:create"))
        self.assertContains(response, f"codice={fornitore.codice}")
        self.assertContains(response, "from=anagrafica")

    def test_cliente_create_destinazioni_salva_prima(self):
        url = reverse("anagrafiche:cliente_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Destinazioni diverse")
        self.assertContains(response, "Salva l'anagrafica per gestire le destinazioni diverse.")

    def test_get_by_codice_exact(self):
        cliente = Cliente.objects.first()
        if not cliente:
            self.skipTest("Nessun cliente nel database")
        found = get_by_codice(Cliente, cliente.codice)
        self.assertIsNotNone(found)
        self.assertEqual(found.codice, cliente.codice)

    def test_fornitore_detail_when_data_exists(self):
        fornitore = Fornitore.objects.first()
        if not fornitore:
            self.skipTest("Nessun fornitore nel database")
        url = reverse("anagrafiche:fornitore_detail", kwargs={"codice": fornitore.codice})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, fornitore.codice)
        self.assertContains(response, "Controllo codice fiscale")

    def test_search_filter(self):
        cliente = Cliente.objects.exclude(ragione_sociale1__isnull=True).exclude(ragione_sociale1="").first()
        if not cliente:
            self.skipTest("Nessun cliente con ragione sociale")
        term = (cliente.ragione_sociale1 or "")[:8]
        response = self.client.get(reverse("anagrafiche:clienti_list"), {"q": term})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cliente.codice)

    def test_orm_counts(self):
        self.assertGreater(Cliente.objects.count(), 0)
        self.assertGreater(Fornitore.objects.count(), 0)

    def test_urls_resolve(self):
        self.assertEqual(reverse("anagrafiche:clienti_list"), "/clienti/")
        self.assertEqual(reverse("anagrafiche:fornitori_list"), "/fornitori/")
        self.assertEqual(reverse("anagrafiche:cf_check"), "/cf/")


class PartitarioIvaNotaCreditoTests(SimpleTestCase):
    def test_cliente_nc_in_dare_negativo(self):
        from apps.anagrafiche.partitario import _signed_amounts

        # Importo firmato (NC) tutto in Dare, Avere a zero — come maschera 4D.
        self.assertEqual(_signed_amounts("C", "iva", -806.0, 0.0), (-806.0, 0.0))
        self.assertEqual(_signed_amounts("C", "iva", 1000.0, 0.0), (1000.0, 0.0))
        # Fornitore: stesso importo firmato in Avere.
        self.assertEqual(_signed_amounts("F", "iva", -100.0, 0.0), (0.0, -100.0))
        # Legacy pos/neg ancora convertito in Dare firmato.
        self.assertEqual(_signed_amounts("C", "iva", 0.0, 806.0), (-806.0, 0.0))


class PartitarioPdcCassaCorrispettiviTests(SimpleTestCase):
    def test_fetch_pdc_merges_cassa_corrispettivi_rows(self):
        from datetime import date
        from unittest.mock import patch

        from apps.anagrafiche.partitario import _fetch_movimenti_pdc

        dettaglio = [
            {
                "fonte": "gen",
                "id_testa": 1,
                "numero_reg": 10,
                "data_reg": date(2026, 2, 1),
                "tipo": 1,
                "causale": "13Z",
                "codice_paga": "",
                "numero_doc": "",
                "data_doc": None,
                "numero_prot": None,
                "alfa_prot": "",
                "dare_amt": 100.0,
                "avere_amt": 0.0,
                "contro_codice": "C1",
                "descrizione": "gen",
                "pos": 10,
                "id_riga": 1,
            }
        ]
        cassa = [
            {
                "fonte": "gen",
                "id_testa": 2,
                "numero_reg": 5,
                "data_reg": date(2026, 1, 15),
                "tipo": 3,
                "causale": "105",
                "codice_paga": "",
                "numero_doc": "",
                "data_doc": date(2026, 1, 15),
                "numero_prot": 1,
                "alfa_prot": "",
                "dare_amt": 415.26,
                "avere_amt": 0.0,
                "contro_codice": "3.71.11",
                "descrizione": "",
                "pos": 0,
                "id_riga": 0,
            }
        ]
        with (
            patch(
                "apps.anagrafiche.partitario._fetch_movimenti_pdc_dettaglio",
                return_value=dettaglio,
            ),
            patch(
                "apps.anagrafiche.partitario._fetch_movimenti_pdc_cassa_corrispettivi",
                return_value=cassa,
            ),
        ):
            rows = _fetch_movimenti_pdc("1.10.9")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["tipo"], 3)
        self.assertEqual(rows[0]["dare_amt"], 415.26)
        self.assertEqual(rows[1]["tipo"], 1)

    def test_fetch_cassa_corrispettivi_empty_code(self):
        from apps.anagrafiche.partitario import _fetch_movimenti_pdc_cassa_corrispettivi

        self.assertEqual(_fetch_movimenti_pdc_cassa_corrispettivi(""), [])
        self.assertEqual(_fetch_movimenti_pdc_cassa_corrispettivi("   "), [])


class AnagraficaLinkedLabelsTests(SimpleTestCase):
    def test_agente_display_includes_name(self):
        from unittest.mock import patch

        from apps.anagrafiche.lookups import agente_display

        with patch("apps.anagrafiche.lookups.agente_label", return_value="ROSSI MARIO"):
            self.assertEqual(agente_display("7"), "7 – ROSSI MARIO")
        self.assertEqual(agente_display(""), "")

    def test_form_linked_labels_agente_and_agente2(self):
        from unittest.mock import MagicMock, patch

        from apps.anagrafiche.lookups import form_linked_labels

        form = MagicMock()
        form.is_bound = False
        form.instance = MagicMock(agente="7", agente2="21", cond_paga="96")
        with patch(
            "apps.anagrafiche.lookups.resolve_descrizione",
            side_effect=lambda tipo, codice: {
                ("condizione", "96"): "B.B. A RICEVIMENTO FATTURA",
                ("agente", "7"): "ROSSI MARIO",
                ("agente", "21"): "BIANCHI LUCA",
            }.get((tipo, codice), ""),
        ):
            labels = form_linked_labels(form)
        self.assertEqual(labels["agente"], "ROSSI MARIO")
        self.assertEqual(labels["agente2"], "BIANCHI LUCA")
        self.assertEqual(labels["cond_paga"], "B.B. A RICEVIMENTO FATTURA")


class PartitarioPrintTests(SimpleTestCase):
    def test_print_url_resolves(self):
        self.assertEqual(reverse("anagrafiche:partitario_print"), "/partitario/stampa/")

    def test_resolve_subject_requires_code(self):
        from apps.anagrafiche.views_partitario_print import resolve_partitario_subject

        info = resolve_partitario_subject("C", "")
        self.assertTrue(info.error)
        self.assertEqual(info.kind, "C")

    def test_resolve_cliente_ok(self):
        from unittest.mock import MagicMock, patch

        from apps.anagrafiche.views_partitario_print import resolve_partitario_subject

        cliente = MagicMock(codice="C1", ragione_sociale="ACME SRL")
        with patch(
            "apps.anagrafiche.views_partitario_print.get_by_codice",
            return_value=cliente,
        ):
            info = resolve_partitario_subject("C", "C1")
        self.assertEqual(info.error, "")
        self.assertEqual(info.codice, "C1")
        self.assertEqual(info.nome, "ACME SRL")
        self.assertEqual(info.kind_label, "Cliente")

    def test_resolve_sottoconto_rejects_non_contropartita(self):
        from unittest.mock import MagicMock, patch

        from apps.anagrafiche.views_partitario_print import resolve_partitario_subject

        conto = MagicMock(codice="1", descrizione="ATTIVO")
        with (
            patch(
                "apps.anagrafiche.views_partitario_print.PianoConti.objects.get",
                return_value=conto,
            ),
            patch(
                "apps.anagrafiche.views_partitario_print.pdc_is_contropartita",
                return_value=False,
            ),
        ):
            info = resolve_partitario_subject("P", "1")
        self.assertIn("sottoconti", info.error.lower())

    def test_parse_importo_it(self):
        from apps.anagrafiche.views_partitario_print import parse_importo_it

        self.assertEqual(parse_importo_it("1.234,56"), 1234.56)
        self.assertEqual(parse_importo_it("1234,56"), 1234.56)
        self.assertEqual(parse_importo_it("100"), 100.0)
        self.assertIsNone(parse_importo_it(""))
        self.assertIsNone(parse_importo_it("abc"))

    def test_saldo_filter_skipped_for_single_subject(self):
        from apps.anagrafiche.views_partitario_print import saldo_filter_for_request

        self.assertEqual(saldo_filter_for_request("ne", tutti=False), "any")
        self.assertEqual(saldo_filter_for_request("gt", tutti=False), "any")
        self.assertEqual(saldo_filter_for_request("ne", tutti=True), "ne")
        self.assertEqual(saldo_filter_for_request("gt", tutti=True), "gt")
        self.assertEqual(saldo_filter_for_request("nope", tutti=True), "ne")

    def test_saldo_matches_ops(self):
        from apps.anagrafiche.views_partitario_print import saldo_matches

        self.assertTrue(saldo_matches(10, "gt", 5))
        self.assertFalse(saldo_matches(5, "gt", 5))
        self.assertTrue(saldo_matches(5, "gte", 5))
        self.assertTrue(saldo_matches(3, "lt", 5))
        self.assertTrue(saldo_matches(5, "lte", 5))
        self.assertTrue(saldo_matches(1, "ne", 0))
        self.assertFalse(saldo_matches(0, "ne", 0))
        self.assertTrue(saldo_matches(0, "eq", 0))
        self.assertTrue(saldo_matches(99, "any", 0))

    def test_lookup_tipo_per_kind(self):
        from apps.anagrafiche.views_partitario_print import LOOKUP_TIPO_BY_KIND

        self.assertEqual(LOOKUP_TIPO_BY_KIND["C"], "cliente")
        self.assertEqual(LOOKUP_TIPO_BY_KIND["F"], "fornitore")
        self.assertEqual(LOOKUP_TIPO_BY_KIND["P"], "pdc")

    def test_print_view_espone_lookup_facilitato(self):
        from unittest.mock import patch

        from django.contrib.auth import get_user_model
        from django.http import HttpResponse
        from django.test import RequestFactory

        from apps.anagrafiche.views_partitario_print import PartitarioPrintView

        request = RequestFactory().get("/partitario/stampa/", {"kind": "F"})
        request.user = get_user_model()(username="t", is_staff=True)
        fake = HttpResponse("ok")
        with (
            patch(
                "apps.anagrafiche.views_partitario_print.render",
                return_value=fake,
            ) as mocked_render,
            patch(
                "apps.anagrafiche.views_partitario_print.resolve_print_azienda_context",
                return_value={},
            ),
            patch(
                "apps.anagrafiche.views_partitario_print._resolve_azienda_header",
                return_value={},
            ),
        ):
            response = PartitarioPrintView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        ctx = mocked_render.call_args.args[2]
        self.assertEqual(ctx["lookup_tipo"], "fornitore")
        self.assertEqual(ctx["lookup_url"], "/articoli/lookup-codice/")

    def test_build_print_bundle_filters_by_saldo(self):
        from datetime import date
        from unittest.mock import patch

        from apps.anagrafiche.partitario import PartitarioResult
        from apps.anagrafiche.views_partitario_print import (
            PartitarioSubjectInfo,
            build_print_bundle,
        )

        subjects = [
            PartitarioSubjectInfo("A", "A", "Alpha", "C", "Cliente"),
            PartitarioSubjectInfo("B", "B", "Beta", "C", "Cliente"),
            PartitarioSubjectInfo("C", "C", "Gamma", "C", "Cliente"),
        ]

        def fake_build(codice, *, kind, data_da, data_a):
            saldi = {"A": 100.0, "B": 0.0, "C": -20.0}
            return PartitarioResult(
                codice=codice,
                kind=kind,
                data_da=data_da,
                data_a=data_a,
                saldo_precedente=0.0,
                righe=[],
                totale_dare=saldi[codice] if saldi[codice] > 0 else 0.0,
                totale_avere=-saldi[codice] if saldi[codice] < 0 else 0.0,
                saldo_finale=saldi[codice],
            )

        with (
            patch(
                "apps.anagrafiche.views_partitario_print.list_partitario_candidates",
                return_value=subjects,
            ),
            patch(
                "apps.anagrafiche.views_partitario_print.build_partitario",
                side_effect=fake_build,
            ),
        ):
            bundle, err = build_print_bundle(
                kind="C",
                codice="",
                tutti=True,
                data_da=date(2026, 1, 1),
                data_a=date(2026, 9, 28),
                saldo_op="gt",
                saldo_soglia=0.0,
            )
        self.assertEqual(err, "")
        self.assertEqual([b.subject.codice for b in bundle.blocks], ["A"])

        with (
            patch(
                "apps.anagrafiche.views_partitario_print.list_partitario_candidates",
                return_value=subjects,
            ),
            patch(
                "apps.anagrafiche.views_partitario_print.build_partitario",
                side_effect=fake_build,
            ),
        ):
            bundle_ne, err_ne = build_print_bundle(
                kind="C",
                codice="",
                tutti=True,
                data_da=date(2026, 1, 1),
                data_a=date(2026, 9, 28),
                saldo_op="ne",
                saldo_soglia=0.0,
            )
        self.assertEqual(err_ne, "")
        self.assertEqual([b.subject.codice for b in bundle_ne.blocks], ["A", "C"])

