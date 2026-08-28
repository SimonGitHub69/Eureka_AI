import socket

from django.test import SimpleTestCase

from apps.core.mail import describe_mail_error, normalize_smtp_host, test_mail_connection
from apps.core.models import ParametriMail


class NormalizeSmtpHostTests(SimpleTestCase):
    def test_hostname_semplice(self):
        self.assertEqual(normalize_smtp_host("smtp.gmail.com"), ("smtp.gmail.com", None))

    def test_host_con_porta(self):
        self.assertEqual(normalize_smtp_host("smtp.gmail.com:587"), ("smtp.gmail.com", 587))

    def test_url_smtp(self):
        self.assertEqual(
            normalize_smtp_host("smtp://mail.azienda.it:465"),
            ("mail.azienda.it", 465),
        )

    def test_url_https_senza_porta(self):
        self.assertEqual(
            normalize_smtp_host("https://smtp.gmail.com/"),
            ("smtp.gmail.com", None),
        )

    def test_vuoto(self):
        self.assertEqual(normalize_smtp_host("  "), ("", None))


class DescribeMailErrorTests(SimpleTestCase):
    def test_getaddrinfo_windows(self):
        exc = socket.gaierror(11001, "getaddrinfo failed")
        msg = describe_mail_error(exc, host="smtp.provider.it")
        self.assertIn("smtp.provider.it", msg)
        self.assertIn("Impossibile trovare il server SMTP", msg)
        self.assertNotIn("11001", msg)

    def test_email_nel_campo_server(self):
        cfg = ParametriMail(
            server_smtp="info@azienda.it",
            mittente="info@azienda.it",
            porta=587,
        )
        result = test_mail_connection(cfg)
        self.assertFalse(result.ok)
        self.assertIn("hostname", result.message)
