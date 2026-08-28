from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase

from apps.core.models import ParametriContabili
from apps.documenti.forms import AliquotaIvaSpeseForm
from apps.documenti.views import DocumentoParametriSpeseView, _safe_next_url


class AliquotaIvaSpeseFormTests(SimpleTestCase):
    def test_strips_codice(self):
        form = AliquotaIvaSpeseForm(
            data={"aliquota_iva_spese": " 22 "},
            instance=ParametriContabili(pk=1),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["aliquota_iva_spese"], "22")


class SafeNextUrlTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_prefers_relative_next(self):
        request = self.rf.get("/x/", {"next": "/documenti/PRV/"})
        request.META["HTTP_HOST"] = "testserver"
        self.assertEqual(
            _safe_next_url(request, fallback="/fallback/"),
            "/documenti/PRV/",
        )

    def test_rejects_external_next(self):
        request = self.rf.get("/x/", {"next": "https://evil.example/phish"})
        request.META["HTTP_HOST"] = "testserver"
        self.assertEqual(
            _safe_next_url(request, fallback="/fallback/"),
            "/fallback/",
        )


class DocumentoParametriSpeseViewTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()
        User = get_user_model()
        self.user = User(username="prvuser")
        self.tipo = type("T", (), {"codice": "PRV", "label": "Preventivi", "categoria": "PREVENTIVI"})()

    def _attach_messages(self, request):
        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

    @patch("apps.documenti.views._resolve_tipo_doc")
    def test_orv_forbidden(self, mock_tipo):
        mock_tipo.return_value = type("T", (), {"codice": "ORV", "label": "Ordini", "categoria": "ORDINI"})()
        request = self.rf.get("/documenti/ORV/parametri/")
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            DocumentoParametriSpeseView.as_view()(request, tipo_doc="ORV")

    @patch("apps.documenti.views.render")
    @patch("apps.documenti.views._resolve_tipo_doc")
    @patch("apps.core.models.ParametriContabili.get_solo")
    def test_get_ok_for_prv(self, mock_solo, mock_tipo, mock_render):
        from django.http import HttpResponse

        mock_tipo.return_value = self.tipo
        mock_solo.return_value = ParametriContabili(pk=1, aliquota_iva_spese="22")
        mock_render.return_value = HttpResponse("ok")
        request = self.rf.get("/documenti/PRV/parametri/")
        request.user = self.user
        response = DocumentoParametriSpeseView.as_view()(request, tipo_doc="PRV")
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
        ctx = mock_render.call_args.args[2]
        self.assertEqual(ctx["tipo"].codice, "PRV")
        self.assertIn("aliquota_iva_spese", ctx["form"].fields)

    @patch("apps.documenti.views.render")
    @patch("apps.documenti.views._resolve_tipo_doc")
    @patch("apps.core.models.ParametriContabili.get_solo")
    def test_get_ok_for_prt(self, mock_solo, mock_tipo, mock_render):
        from django.http import HttpResponse

        mock_tipo.return_value = type(
            "T", (), {"codice": "PRT", "label": "Preventivi T", "categoria": "PREVENTIVI"}
        )()
        mock_solo.return_value = ParametriContabili(pk=1, aliquota_iva_spese="22")
        mock_render.return_value = HttpResponse("ok")
        request = self.rf.get("/documenti/PRT/parametri/")
        request.user = self.user
        response = DocumentoParametriSpeseView.as_view()(request, tipo_doc="PRT")
        self.assertEqual(response.status_code, 200)

    @patch("apps.documenti.views._resolve_tipo_doc")
    @patch("apps.core.models.ParametriContabili.get_solo")
    def test_post_salva_redirect(self, mock_solo, mock_tipo):
        mock_tipo.return_value = self.tipo
        instance = ParametriContabili(pk=1, aliquota_iva_spese="")
        instance.save = MagicMock()
        mock_solo.return_value = instance

        request = self.rf.post(
            "/documenti/PRV/parametri/",
            {"aliquota_iva_spese": "10", "next": "/documenti/PRV/"},
        )
        request.user = self.user
        self._attach_messages(request)
        response = DocumentoParametriSpeseView.as_view()(request, tipo_doc="PRV")
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/documenti/PRV/")
        instance.save.assert_called()
        self.assertEqual(instance.aliquota_iva_spese, "10")
