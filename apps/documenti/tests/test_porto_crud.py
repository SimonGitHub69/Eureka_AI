from django.test import SimpleTestCase
from django.urls import reverse

from apps.documenti.models import Porto


class PortoCrudTests(SimpleTestCase):
    def test_model_is_unmanaged_mirror(self):
        self.assertFalse(Porto._meta.managed)
        self.assertEqual(Porto._meta.db_table, "tab_porto")
        self.assertEqual(Porto._meta.get_field("id").db_column, "ID")
        self.assertEqual(Porto._meta.get_field("descrizione").db_column, "Descrizione")
        self.assertEqual(Porto._meta.get_field("cod_incoterm").db_column, "Cod_Incoterm")

    def test_urls_resolve(self):
        self.assertEqual(reverse("documenti:porto_list"), "/porto/")
        self.assertEqual(reverse("documenti:porto_create"), "/porto/nuovo/")
        self.assertEqual(reverse("documenti:porto_detail", kwargs={"pk": 1}), "/porto/1/")
        self.assertEqual(reverse("documenti:porto_edit", kwargs={"pk": 1}), "/porto/1/modifica/")
        self.assertEqual(reverse("documenti:porto_delete", kwargs={"pk": 1}), "/porto/1/elimina/")
