from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.sorting import order_by_fields


class OrderByFieldsTests(SimpleTestCase):
    def test_tiebreaker_tuple_dopo_data(self):
        self.assertEqual(
            order_by_fields(
                "data_documento",
                "desc",
                tiebreaker=("-numero", "alfa", "-id_4d"),
            ),
            ("-data_documento", "-numero", "alfa", "-id_4d"),
        )

    def test_tiebreaker_salts_campo_uguale_allo_sort(self):
        self.assertEqual(
            order_by_fields("numero", "desc", tiebreaker=("-numero", "alfa", "-id_4d")),
            ("-numero", "alfa", "-id_4d"),
        )

    def test_tiebreaker_stringa_invariata(self):
        self.assertEqual(
            order_by_fields("localita", "asc", tiebreaker="codice"),
            ("localita", "codice"),
        )


class ListSortRememberTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("sortuser", password="x")
        self.client.force_login(self.user)

    def test_sort_is_restored_when_returning_to_list(self):
        list_url = reverse("anagrafiche:clienti_list")
        sorted_url = f"{list_url}?sort=localita&dir=desc"

        response = self.client.get(sorted_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sort"], "localita")
        self.assertEqual(response.context["dir"], "desc")

        # Come dopo "Elenco" dalla scheda: lista senza query string
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("sort=localita", response["Location"])
        self.assertIn("dir=desc", response["Location"])

    def test_filters_without_sort_still_restore_sort(self):
        list_url = reverse("anagrafiche:clienti_list")
        self.client.get(f"{list_url}?sort=partita_iva&dir=asc")

        response = self.client.get(f"{list_url}?q=rossi")
        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertIn("sort=partita_iva", location)
        self.assertIn("dir=asc", location)
        self.assertIn("q=rossi", location)
