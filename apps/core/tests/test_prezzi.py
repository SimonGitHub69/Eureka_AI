"""Test decimali prezzo unitario (Parametri programma)."""

from django.test import SimpleTestCase, TestCase

from apps.core.models import ConfigurazioneProgramma
from apps.core.prezzi import (
    PREZZO_DECIMALI_DEFAULT,
    clamp_prezzo_decimali,
    get_prezzo_decimali,
    get_prezzo_decimali_stampa,
    prezzo_input_step,
    round_prezzo,
    round_prezzo_stampa,
)
from apps.core.templatetags.format_tags import prezzo as prezzo_filter


class PrezzoDecimaliClampTests(SimpleTestCase):
    def test_clamp_prezzo_decimali(self):
        self.assertEqual(clamp_prezzo_decimali(None), PREZZO_DECIMALI_DEFAULT)
        self.assertEqual(clamp_prezzo_decimali(3), 3)
        self.assertEqual(clamp_prezzo_decimali(1), 2)
        self.assertEqual(clamp_prezzo_decimali(9), 6)


class PrezzoDecimaliTests(TestCase):
    def test_get_prezzo_decimali_da_parametri(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.prezzo_decimali = 4
        cfg.save(update_fields=["prezzo_decimali"])
        self.assertEqual(get_prezzo_decimali(), 4)

    def test_round_prezzo_usa_parametro(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.prezzo_decimali = 2
        cfg.save(update_fields=["prezzo_decimali"])
        self.assertEqual(round_prezzo(3.4115), 3.41)

        cfg.prezzo_decimali = 4
        cfg.save(update_fields=["prezzo_decimali"])
        self.assertEqual(round_prezzo(3.41155), 3.4116)

    def test_prezzo_input_step(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.prezzo_decimali = 3
        cfg.save(update_fields=["prezzo_decimali"])
        self.assertEqual(prezzo_input_step(), "0.001")

        cfg.prezzo_decimali = 2
        cfg.save(update_fields=["prezzo_decimali"])
        self.assertEqual(prezzo_input_step(), "0.01")

    def test_prezzo_filter(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.prezzo_decimali = 3
        cfg.save(update_fields=["prezzo_decimali"])
        self.assertEqual(prezzo_filter(12.5), "12,500")

        cfg.prezzo_decimali = 2
        cfg.save(update_fields=["prezzo_decimali"])
        self.assertEqual(prezzo_filter(12.5), "12,50")

    def test_get_prezzo_decimali_stampa_da_parametri(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.prezzo_decimali_stampa = 5
        cfg.save(update_fields=["prezzo_decimali_stampa"])
        self.assertEqual(get_prezzo_decimali_stampa(), 5)

    def test_round_prezzo_stampa_usa_parametro(self):
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.prezzo_decimali = 4
        cfg.prezzo_decimali_stampa = 2
        cfg.save(update_fields=["prezzo_decimali", "prezzo_decimali_stampa"])
        self.assertEqual(round_prezzo(3.41155), 3.4116)
        self.assertEqual(round_prezzo_stampa(3.41155), 3.41)
