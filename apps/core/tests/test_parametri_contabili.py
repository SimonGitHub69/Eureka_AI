from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.forms import ParametriContabiliForm
from apps.core.models import ParametriContabili, SPESE_CONTROPARTITA_FIELDS
from apps.documenti.castelletto import AliquotaInfo, calcola_castelletto, get_aliquota_iva_spese


_CACHE = {
    "22": AliquotaInfo(codice="22", percentuale=Decimal("22"), descrizione="IVA 22%"),
    "10": AliquotaInfo(codice="10", percentuale=Decimal("10"), descrizione="IVA 10%"),
}


class ParametriContabiliModelTests(TestCase):
    def test_get_solo_creates_singleton(self):
        a = ParametriContabili.get_solo()
        b = ParametriContabili.get_solo()
        self.assertEqual(a.pk, 1)
        self.assertEqual(b.pk, 1)
        self.assertEqual(ParametriContabili.objects.count(), 1)

    def test_aliquota_iva_spese_codice_strips(self):
        cfg = ParametriContabili.get_solo()
        cfg.aliquota_iva_spese = "  10  "
        cfg.save()
        self.assertEqual(cfg.aliquota_iva_spese_codice(), "10")
        self.assertEqual(get_aliquota_iva_spese(), "10")

    def test_spese_contropartita_fields_cover_all(self):
        names = {name for name, _ in SPESE_CONTROPARTITA_FIELDS}
        self.assertIn("contropartita_spese_imballo", names)
        self.assertIn("contropartita_spese_trasporto", names)
        self.assertIn("contropartita_spese_incasso", names)
        self.assertIn("contropartita_spese_varie", names)
        self.assertIn("contropartita_spese_bolli", names)
        self.assertIn("contropartita_spese_e15", names)


class ParametriContabiliFormContropartitaTests(SimpleTestCase):
    def _data(self, **overrides):
        base = {
            "aliquota_iva_spese": "",
            "contropartita_spese_imballo": "",
            "contropartita_spese_trasporto": "",
            "contropartita_spese_incasso": "",
            "contropartita_spese_varie": "",
            "contropartita_spese_bolli": "",
            "contropartita_spese_e15": "",
            "note": "",
        }
        base.update(overrides)
        return base

    def test_form_rejects_mastro_e_conto(self):
        form = ParametriContabiliForm(
            data=self._data(
                contropartita_spese_imballo="1",
                contropartita_spese_trasporto="1.10",
                contropartita_spese_incasso="1.10.1",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("contropartita_spese_imballo", form.errors)
        self.assertIn("contropartita_spese_trasporto", form.errors)
        self.assertNotIn("contropartita_spese_incasso", form.errors)
        self.assertIn(
            "contropartita", form.errors["contropartita_spese_imballo"][0].lower()
        )
        self.assertIn(
            "contropartita", form.errors["contropartita_spese_trasporto"][0].lower()
        )

    def test_form_accepts_contropartita_format(self):
        form = ParametriContabiliForm(
            data=self._data(
                aliquota_iva_spese=" 22 ",
                contropartita_spese_imballo=" 6.01.01 ",
                contropartita_spese_trasporto="6.01.02",
                note="test",
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["aliquota_iva_spese"], "22")
        self.assertEqual(form.cleaned_data["contropartita_spese_imballo"], "6.01.01")
        self.assertEqual(form.cleaned_data["contropartita_spese_trasporto"], "6.01.02")


class ParametriContabiliFormTests(TestCase):
    def test_form_saves_fields(self):
        cfg = ParametriContabili.get_solo()
        form = ParametriContabiliForm(
            data={
                "aliquota_iva_spese": " 22 ",
                "contropartita_spese_imballo": " 6.01.01 ",
                "contropartita_spese_trasporto": "6.01.02",
                "contropartita_spese_incasso": "",
                "contropartita_spese_varie": "",
                "contropartita_spese_bolli": "",
                "contropartita_spese_e15": "",
                "note": "test",
            },
            instance=cfg,
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.aliquota_iva_spese, "22")
        self.assertEqual(obj.contropartita_spese_imballo, "6.01.01")
        self.assertEqual(obj.contropartita_spese_trasporto, "6.01.02")
        self.assertEqual(obj.note, "test")


class ParametriContabiliCastellettoTests(TestCase):
    def test_spese_usano_aliquota_configurata(self):
        cfg = ParametriContabili.get_solo()
        cfg.aliquota_iva_spese = "10"
        cfg.save()

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
            aliquote_cache=_CACHE,
            aliquota_iva_spese=get_aliquota_iva_spese(),
        )
        spese = [r for r in result.righe if r.is_spese]
        self.assertEqual(len(spese), 1)
        self.assertEqual(spese[0].codice_iva, "10")
        self.assertEqual(spese[0].percentuale, Decimal("10"))
        self.assertEqual(spese[0].iva, Decimal("1.00"))

    def test_spese_fallback_prima_riga_se_vuota(self):
        cfg = ParametriContabili.get_solo()
        cfg.aliquota_iva_spese = ""
        cfg.save()

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
            aliquote_cache=_CACHE,
            aliquota_iva_spese=get_aliquota_iva_spese(),
        )
        spese = [r for r in result.righe if r.is_spese]
        self.assertEqual(spese[0].codice_iva, "22")
        self.assertEqual(spese[0].iva, Decimal("2.20"))


class ParametriContabiliViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="contabili_user",
            password="testpass123",
        )
        self.client.login(username="contabili_user", password="testpass123")

    def test_get_form(self):
        response = self.client.get(reverse("core:parametri_contabili"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aliquota IVA spese")
        self.assertContains(response, "Contropartite PDC spese")
        self.assertContains(response, 'data-lookup-tipo="iva"')
        self.assertContains(response, 'data-lookup-tipo="pdc"')

    def test_post_salva(self):
        response = self.client.post(
            reverse("core:parametri_contabili"),
            {
                "aliquota_iva_spese": "22",
                "contropartita_spese_imballo": "1.1.1",
                "contropartita_spese_trasporto": "",
                "contropartita_spese_incasso": "",
                "contropartita_spese_varie": "",
                "contropartita_spese_bolli": "",
                "contropartita_spese_e15": "",
                "note": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        cfg = ParametriContabili.get_solo()
        self.assertEqual(cfg.aliquota_iva_spese, "22")
        self.assertEqual(cfg.contropartita_spese_imballo, "1.1.1")
