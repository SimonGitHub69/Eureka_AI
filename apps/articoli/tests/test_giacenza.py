"""Test calcolo giacenza da movimenti magazzino."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.articoli.giacenza import (
    FLAG_CD_CARICO,
    FLAG_CD_SCARICO,
    attach_giacenze_articoli,
    flag_cd_sign,
    giacenza_articolo,
    giacenze_per_codici,
)


class FlagCdSignTests(SimpleTestCase):
    def test_carico(self):
        for value in FLAG_CD_CARICO:
            self.assertEqual(flag_cd_sign(value), 1)
        self.assertIn(3, FLAG_CD_CARICO)

    def test_scarico(self):
        for value in FLAG_CD_SCARICO:
            self.assertEqual(flag_cd_sign(value), -1)

    def test_neutro(self):
        self.assertEqual(flag_cd_sign(None), 0)
        self.assertEqual(flag_cd_sign(99), 0)
        self.assertEqual(flag_cd_sign(-1), 0)


class GiacenzaQueryTests(SimpleTestCase):
    @patch("apps.articoli.giacenza.connection")
    def test_giacenza_articolo_empty_codice(self, mock_connection):
        self.assertEqual(giacenza_articolo(""), 0.0)
        self.assertEqual(giacenza_articolo(None), 0.0)
        mock_connection.cursor.assert_not_called()

    @patch("apps.articoli.giacenza.connection")
    def test_giacenza_articolo_runs_query(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchone.return_value = (13726.0,)
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        result = giacenza_articolo("va22")

        self.assertEqual(result, 13726.0)
        sql = cursor.execute.call_args[0][0]
        self.assertIn("Flag_CD", sql)
        self.assertIn("CodiceArt", sql)
        self.assertEqual(cursor.execute.call_args[0][1], ["VA22"])

    @patch("apps.articoli.giacenza.connection")
    def test_giacenze_per_codici_batch(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("VA22", 13726.0), ("AB01", 5.0)]
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        result = giacenze_per_codici(["VA22", "ab01", ""])

        self.assertEqual(result, {"VA22": 13726.0, "AB01": 5.0})
        self.assertEqual(cursor.execute.call_args[0][1], [["AB01", "VA22"]])

    @patch("apps.articoli.giacenza.giacenze_per_codici", return_value={"VA22": 10.0})
    def test_attach_giacenze_articoli(self, _mock_batch):
        art = MagicMock(codice="va22")
        other = MagicMock(codice="NEW")
        attach_giacenze_articoli([art, other])
        self.assertEqual(art.giacenza_quantita, 10.0)
        self.assertEqual(other.giacenza_quantita, 0.0)
