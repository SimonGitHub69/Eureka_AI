from django.db import models

from apps.core.models.base import BaseModel


class Configurazione4D(BaseModel):
    attiva = models.BooleanField("Attiva", default=False)
    server = models.CharField(
        "Server 4D",
        max_length=300,
        blank=True,
        help_text="IP o hostname del 4D Server (es. 192.168.1.50).",
    )
    porta = models.PositiveIntegerField(
        "Porta SQL",
        default=19812,
        help_text="Porta SQL di 4D Server (default 19812).",
    )
    utente = models.CharField("Utente", max_length=200, blank=True)
    password = models.CharField("Password", max_length=200, blank=True)
    driver_odbc = models.CharField(
        "Driver ODBC",
        max_length=200,
        blank=True,
        help_text="Lascia vuoto per rilevamento automatico (es. 4D ODBC Driver 64-bit).",
    )
    usa_ssl = models.BooleanField(
        "Usa SSL",
        default=False,
        help_text="Abilita solo se SQL Server di 4D è configurato con SSL.",
    )
    dsn = models.CharField(
        "DSN ODBC",
        max_length=200,
        blank=True,
        help_text="Opzionale: se valorizzato, la connessione usa il DSN invece di server/porta.",
    )

    class Meta:
        verbose_name = "Configurazione 4D"
        verbose_name_plural = "Configurazioni 4D"
        permissions = [
            ("access_parametri_4d", "Può gestire Parametri 4D"),
        ]

    def __str__(self):
        return "Collegamento 4D"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"attiva": False})
        return obj

    @property
    def is_configured(self):
        if (self.dsn or "").strip():
            return True
        return bool((self.server or "").strip() and (self.utente or "").strip() and self.password)
