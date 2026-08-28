from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.documenti.mail_documento import (
    apply_mail_template,
    default_mail_body,
    default_mail_subject,
    parse_destinatari,
    resolve_documento_email,
)
from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO
from apps.documenti.models import TestaDocumento, TipoDocumento


class MailDocumentoHelpersTests(SimpleTestCase):
    def test_parse_destinatari(self):
        self.assertEqual(
            parse_destinatari("a@b.it; c@d.it, invalido"),
            ["a@b.it", "c@d.it"],
        )

    def test_resolve_email_da_anagrafica(self):
        doc = SimpleNamespace(
            codice_clifor="C001",
            clifor_tipo="C",
            email_pec="",
        )
        cliente = SimpleNamespace(
            email="vendite@acme.it",
            email_commerciale="",
            pec="",
        )
        with patch(
            "apps.anagrafiche.models.get_by_codice",
            return_value=cliente,
        ):
            self.assertEqual(resolve_documento_email(doc), "vendite@acme.it")

    def test_resolve_email_fallback_pec(self):
        doc = SimpleNamespace(
            codice_clifor="",
            clifor_tipo="C",
            email_pec="pec@acme.it",
        )
        self.assertEqual(resolve_documento_email(doc), "pec@acme.it")

    def test_default_subject(self):
        doc = SimpleNamespace(
            tipo_doc=SimpleNamespace(label="Preventivo"),
            numero_documento="6/FF",
        )
        self.assertEqual(default_mail_subject(doc), "Preventivo 6/FF")

    def test_testo_mail_parametri_con_segnaposto(self):
        doc = SimpleNamespace(
            tipo_doc=SimpleNamespace(
                codice="PRV",
                categoria="PREVENTIVI",
                testo_mail="Offerta {numero} del {data} per {cliente}, totale {totale}",
            ),
            numero_documento="12/FF",
            data_documento=None,
            destinatario="Acme",
            codice_clifor="C001",
            totale=100,
            cliente_ragione_sociale="Acme Srl",
        )
        body = default_mail_body(doc)
        self.assertIn("Offerta 12/FF", body)
        self.assertIn("Acme Srl", body)
        self.assertIn("100,00", body)

    def test_apply_mail_template_doppie_graffe(self):
        doc = SimpleNamespace(
            tipo_doc=SimpleNamespace(codice="PRV", categoria="PREVENTIVI", label="Preventivi"),
            numero_documento="1/A",
            data_documento=None,
            destinatario="X",
            codice_clifor="",
            totale=None,
            cliente_ragione_sociale="",
        )
        self.assertEqual(apply_mail_template("N. {{numero}}", doc), "N. 1/A")


class DocumentoInviaMailViewTests(TestCase):
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
        cls.doc = TestaDocumento.objects.create(
            tipo_doc_id="PRV",
            id_4d=9001,
            numero=12,
            alfa="FF",
            codice_clifor="C001",
            destinatario="Acme",
            totale=100,
        )

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mailer",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def test_lista_ha_pulsante_mail(self):
        response = self.client.get(reverse("documenti:list", kwargs={"tipo_doc": "PRV"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invia per mail")
        self.assertContains(response, "/invia-mail/")

    def test_maschera_invio_get(self):
        url = reverse(
            "documenti:invia_mail",
            kwargs={"tipo_doc": "PRV", "pk": self.doc.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invia Preventivo")
        self.assertContains(response, "12/FF")

    @patch("apps.documenti.pdf_documento.render_documento_pdf", return_value=b"%PDF-1.4 test")
    @patch("apps.core.mail.send_mail_automatica")
    def test_invio_post(self, mock_send, _mock_pdf):
        mock_send.return_value = None
        url = reverse(
            "documenti:invia_mail",
            kwargs={"tipo_doc": "PRV", "pk": self.doc.pk},
        )
        response = self.client.post(
            url,
            {
                "destinatario": "cliente@acme.it",
                "oggetto": "Preventivo 12/FF",
                "messaggio": "Buongiorno",
                "next": reverse("documenti:list", kwargs={"tipo_doc": "PRV"}),
            },
        )
        self.assertEqual(response.status_code, 302)
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["to"], ["cliente@acme.it"])
        self.assertEqual(kwargs["subject"], "Preventivo 12/FF")
        self.assertEqual(len(kwargs["attachments"]), 1)
        self.assertTrue(kwargs["attachments"][0][0].endswith(".pdf"))
        self.assertEqual(kwargs["attachments"][0][2], "application/pdf")
