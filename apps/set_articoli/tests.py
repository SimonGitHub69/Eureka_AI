from django.test import SimpleTestCase
from django.urls import reverse
from unittest.mock import MagicMock, patch

from apps.core import views as core_views
from apps.set_articoli.forms import SetArticoloDForm
from apps.set_articoli.sync import TABLES, sync_set_articoli


class SetArticoliWiringTests(SimpleTestCase):
    def test_urls_resolve(self):
        self.assertEqual(reverse("set_articoli:list"), "/set-articoli/")
        self.assertEqual(reverse("set_articoli:create"), "/set-articoli/nuova/")
        self.assertEqual(reverse("set_articoli:detail", kwargs={"pk": 75}), "/set-articoli/75/")
        self.assertEqual(
            reverse("set_articoli:riga_create", kwargs={"pk": 75}),
            "/set-articoli/75/righe/nuova/",
        )
        self.assertEqual(reverse("set_articoli:sync"), "/parametri/4d/sync-set-articoli/")
        self.assertEqual(reverse("set_articoli:print_list"), "/set-articoli/stampa/")

    def test_sync_step_registered(self):
        step = next(s for s in core_views.SYNC_4D_STEPS if s["key"] == "set_articoli")
        self.assertEqual(step["runner"], sync_set_articoli)
        self.assertEqual(step["tables"], ("set_articoli_h", "set_articoli_d"))
        self.assertEqual(step["label"], "Set Articoli")
        self.assertEqual(step["description"], "Set_Articoli_H e Set_Articoli_D")

    def test_sync_tables_match_4d(self):
        sources = [t["source"] for t in TABLES]
        targets = [t["target"] for t in TABLES]
        self.assertEqual(sources, ["Set_Articoli_H", "Set_Articoli_D"])
        self.assertEqual(targets, ["set_articoli_h", "set_articoli_d"])
        self.assertTrue(all(t["pk"] == "ID" for t in TABLES))


class SetArticoloDFormDuplicateTests(SimpleTestCase):
    @patch("apps.set_articoli.forms.resolve_articolo")
    @patch("apps.set_articoli.forms.SetArticoloD.objects")
    def test_rejects_duplicate_cod_art_on_same_testa(self, mock_objects, mock_resolve):
        mock_resolve.return_value = {
            "found": True,
            "codice": "TUB135B",
            "descrizione": "Tubolare",
            "unita_misura": "MT",
        }
        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.exists.return_value = True
        mock_objects.filter.return_value = qs

        testa = MagicMock()
        form = SetArticoloDForm(
            data={"cod_art": "tub135b", "desc_art": "", "qta": "1", "um": "", "pos": "10"},
            testa=testa,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("cod_art", form.errors)
        self.assertIn("già presente", form.errors["cod_art"][0])
        mock_objects.filter.assert_called()
        kwargs = mock_objects.filter.call_args.kwargs
        self.assertEqual(kwargs["testa"], testa)
        self.assertEqual(kwargs["cod_art__iexact"], "TUB135B")

    @patch("apps.set_articoli.forms.resolve_articolo")
    @patch("apps.set_articoli.forms.SetArticoloD.objects")
    def test_allows_same_cod_art_when_editing_own_row(self, mock_objects, mock_resolve):
        mock_resolve.return_value = {
            "found": True,
            "codice": "TUB135B",
            "descrizione": "Tubolare",
            "unita_misura": "MT",
        }
        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.exists.return_value = False
        mock_objects.filter.return_value = qs

        testa = MagicMock()
        instance = MagicMock()
        instance.pk = 99
        instance.testa_id = 1
        form = SetArticoloDForm(
            data={"cod_art": "TUB135B", "desc_art": "x", "qta": "2", "um": "MT", "pos": "10"},
            instance=instance,
            testa=testa,
        )
        self.assertTrue(form.is_valid())
        qs.exclude.assert_called_with(pk=99)
