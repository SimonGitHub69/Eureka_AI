from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.urls import reverse


class ValuteCambioUrlTests(SimpleTestCase):
    def test_cambio_crud_urls_resolve(self):
        codice = "USD"
        pk = 42
        self.assertEqual(
            reverse("valute:cambio_create", kwargs={"codice": codice}),
            f"/valute/{codice}/cambi/nuovo/",
        )
        self.assertEqual(
            reverse("valute:cambio_edit", kwargs={"codice": codice, "pk": pk}),
            f"/valute/{codice}/cambi/{pk}/modifica/",
        )
        self.assertEqual(
            reverse("valute:cambio_delete", kwargs={"codice": codice, "pk": pk}),
            f"/valute/{codice}/cambi/{pk}/elimina/",
        )


class ValutaChoicesTests(SimpleTestCase):
    def test_choices_include_table_and_current_orphan(self):
        from apps.valute.lookups import valuta_choices

        euro = MagicMock(codice="Euro", descrizione="Euro", abbrev="EUR")
        usd = MagicMock(codice="USD", descrizione="Dollaro USA", abbrev="USD")
        qs = MagicMock()
        qs.order_by.return_value = [euro, usd]
        with (
            patch("apps.valute.lookups.Valuta") as model,
            patch("apps.valute.lookups.transaction.atomic") as atomic,
        ):
            model.objects = qs
            atomic.return_value.__enter__ = MagicMock()
            atomic.return_value.__exit__ = MagicMock(return_value=False)
            choices = valuta_choices("VECCIA")
        self.assertEqual(choices[0], ("", "—"))
        self.assertIn(("Euro", "Euro"), choices)
        self.assertIn(("USD", "USD — Dollaro USA"), choices)
        self.assertIn(("VECCIA", "VECCIA"), choices)

    def test_choices_ok_if_table_missing(self):
        from django.db.utils import OperationalError

        from apps.valute.lookups import valuta_choices

        qs = MagicMock()
        qs.order_by.side_effect = OperationalError("missing")
        with (
            patch("apps.valute.lookups.Valuta") as model,
            patch("apps.valute.lookups.transaction.atomic") as atomic,
        ):
            model.objects = qs
            atomic.return_value.__enter__ = MagicMock()
            atomic.return_value.__exit__ = MagicMock(return_value=False)
            choices = valuta_choices("Euro")
        self.assertEqual(choices, [("", "—"), ("Euro", "Euro")])


class CambioInfoTests(SimpleTestCase):
    def test_cambio_info_from_valuta_det(self):
        from datetime import datetime

        from apps.valute.lookups import cambio_info

        valuta = MagicMock(codice="Euro", cambio=0.0)
        det = MagicMock(cambio=1.0, data=datetime(2002, 1, 1))
        qs = MagicMock()
        qs.filter.return_value.exclude.return_value.order_by.return_value = [det]
        with (
            patch("apps.valute.lookups.resolve_valuta", return_value=valuta),
            patch("apps.valute.lookups.ValutaDet") as det_model,
            patch("apps.valute.lookups.transaction.atomic") as atomic,
        ):
            det_model.objects = qs
            atomic.return_value.__enter__ = MagicMock()
            atomic.return_value.__exit__ = MagicMock(return_value=False)
            info = cambio_info("EURO")
        self.assertEqual(info["codice"], "Euro")
        self.assertEqual(info["cambio"], 1.0)
        self.assertEqual(info["data"].year, 2002)

    def test_cambio_info_as_of_uses_historical_rate(self):
        from datetime import date, datetime

        from apps.valute.lookups import cambio_info

        valuta = MagicMock(codice="USD", cambio=0.0)
        newer = MagicMock(cambio=0.95, data=datetime(2026, 8, 18))
        older = MagicMock(cambio=0.9084, data=datetime(2019, 11, 12, 23, 0, 0))
        qs = MagicMock()
        qs.filter.return_value.exclude.return_value.order_by.return_value = [newer, older]
        with (
            patch("apps.valute.lookups.resolve_valuta", return_value=valuta),
            patch("apps.valute.lookups.ValutaDet") as det_model,
            patch("apps.valute.lookups.transaction.atomic") as atomic,
        ):
            det_model.objects = qs
            atomic.return_value.__enter__ = MagicMock()
            atomic.return_value.__exit__ = MagicMock(return_value=False)
            info = cambio_info("USD", alla_data=date(2019, 11, 30))
        self.assertEqual(info["cambio"], 0.9084)
        self.assertEqual(info["data"], date(2019, 11, 13))


class CambioVisibleTests(SimpleTestCase):
    def test_hidden_when_abbrev_is_eur(self):
        from apps.valute.lookups import is_cambio_visible

        euro = MagicMock(abbrev="EUR")
        with patch("apps.valute.lookups.resolve_valuta", return_value=euro):
            self.assertFalse(is_cambio_visible("Euro"))

    def test_visible_when_abbrev_is_not_eur(self):
        from apps.valute.lookups import is_cambio_visible

        usd = MagicMock(abbrev="USD")
        with patch("apps.valute.lookups.resolve_valuta", return_value=usd):
            self.assertTrue(is_cambio_visible("USD"))

    def test_hidden_when_valuta_empty(self):
        from apps.valute.lookups import is_cambio_visible

        self.assertFalse(is_cambio_visible(""))
        self.assertFalse(is_cambio_visible(None))

    def test_cambio_info_empty_without_valuta(self):
        from apps.valute.lookups import cambio_info

        with patch("apps.valute.lookups.resolve_valuta", return_value=None):
            info = cambio_info("")
        self.assertIsNone(info["cambio"])
        self.assertIsNone(info["data"])


class DetValueToDateTests(SimpleTestCase):
    def test_utc_offset_becomes_next_local_day(self):
        from datetime import datetime

        from apps.valute.forms import det_value_to_date

        # 4D: 01/01/2002 00:00 Europe/Rome = 31/12/2001 23:00 UTC naive
        self.assertEqual(
            det_value_to_date(datetime(2001, 12, 31, 23, 0, 0)),
            datetime(2002, 1, 1).date(),
        )

    def test_local_midnight_keeps_calendar_day(self):
        from datetime import datetime

        from apps.valute.forms import det_value_to_date

        self.assertEqual(
            det_value_to_date(datetime(2002, 1, 1, 0, 0, 0)),
            datetime(2002, 1, 1).date(),
        )
