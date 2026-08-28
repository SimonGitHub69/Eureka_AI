from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.condizioni.forms import CondizioneForm


class CondizioneFineMeseFormTests(SimpleTestCase):
    def _base_data(self, **overrides):
        data = {
            "codice": "FM1",
            "descrizione": "Fine mese test",
            "tipo_pagamento": "",
            "numero_rate": "",
            "prima_rata": "",
            "intervallo": "",
            "giorno_fisso": "",
            "mese_esclusione": "",
            "mese_esclusione2": "",
            "gg_mese_esclus": "",
            "gg_mese_esclus2": "",
            "codice_banca": "",
            "pag_fatt_elett_pa": "",
        }
        data.update(overrides)
        return data

    def test_fine_mese_forces_giorno_fisso_31(self):
        qs = MagicMock()
        qs.exists.return_value = False
        with patch("apps.condizioni.forms.Condizione.objects.filter", return_value=qs):
            form = CondizioneForm(
                data=self._base_data(fine_mese="on", giorno_fisso="15"),
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertTrue(form.cleaned_data["fine_mese"])
            self.assertEqual(form.cleaned_data["giorno_fisso"], 31)

    def test_senza_fine_mese_giorno_fisso_libero(self):
        qs = MagicMock()
        qs.exists.return_value = False
        with patch("apps.condizioni.forms.Condizione.objects.filter", return_value=qs):
            form = CondizioneForm(data=self._base_data(giorno_fisso="15"))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertFalse(form.cleaned_data["fine_mese"])
            self.assertEqual(form.cleaned_data["giorno_fisso"], 15)

    def test_fine_mese_readonly_su_giorno_fisso(self):
        instance = MagicMock()
        instance.pk = "FM1"
        instance.fine_mese = True
        instance.giorno_fisso = 15
        instance.pag_fatt_elett_pa = ""
        form = CondizioneForm(instance=instance)
        attrs = form.fields["giorno_fisso"].widget.attrs
        self.assertEqual(attrs.get("readonly"), "readonly")
        self.assertEqual(attrs.get("data-field-locked"), "true")
        self.assertIn("eureka-field-locked", attrs.get("class", ""))
        self.assertEqual(form.initial["giorno_fisso"], 31)

    def test_fine_mese_locked_anche_su_post_invalido(self):
        qs = MagicMock()
        qs.exists.return_value = False
        with patch("apps.condizioni.forms.Condizione.objects.filter", return_value=qs):
            form = CondizioneForm(
                data=self._base_data(
                    fine_mese="on",
                    giorno_fisso="15",
                    codice="",
                ),
            )
            self.assertFalse(form.is_valid())
            attrs = form.fields["giorno_fisso"].widget.attrs
            self.assertEqual(attrs.get("readonly"), "readonly")
            self.assertEqual(attrs.get("data-field-locked"), "true")
