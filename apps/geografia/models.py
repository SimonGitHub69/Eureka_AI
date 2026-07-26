from django.db import models


class Regione(models.Model):
    """Regione italiana (codice ISTAT)."""

    codice = models.CharField("Codice ISTAT", max_length=2, primary_key=True)
    nome = models.CharField("Nome", max_length=100, db_index=True)

    class Meta:
        verbose_name = "Regione"
        verbose_name_plural = "Regioni"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Provincia(models.Model):
    """Provincia / città metropolitana italiana."""

    sigla = models.CharField("Sigla", max_length=2, primary_key=True)
    codice_istat = models.CharField("Codice ISTAT", max_length=3, unique=True)
    nome = models.CharField("Nome", max_length=100, db_index=True)
    regione = models.ForeignKey(
        Regione,
        on_delete=models.PROTECT,
        related_name="province",
        verbose_name="Regione",
    )

    class Meta:
        verbose_name = "Provincia"
        verbose_name_plural = "Province"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.sigla})"


class Citta(models.Model):
    """Comune / città italiana (codice ISTAT)."""

    codice_istat = models.CharField("Codice ISTAT", max_length=6, primary_key=True)
    nome = models.CharField("Nome", max_length=150, db_index=True)
    provincia = models.ForeignKey(
        Provincia,
        on_delete=models.PROTECT,
        related_name="citta",
        verbose_name="Provincia",
    )
    cap = models.CharField("CAP principale", max_length=5, blank=True, db_index=True)
    codice_catastale = models.CharField(
        "Codice catastale", max_length=4, blank=True, db_index=True
    )

    class Meta:
        verbose_name = "Città"
        verbose_name_plural = "Città"
        ordering = ["nome", "codice_istat"]

    def __str__(self):
        return f"{self.nome} ({self.provincia.sigla})"
