from django.db import models
from django.urls import reverse


class RegistroIva(models.Model):
    """Mirror PostgreSQL della tabella 4D RegistriIva (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    tipo_registro = models.TextField(null=True, blank=True, db_column="TipoRegistro")
    upa = models.IntegerField(null=True, blank=True, db_column="UPA")
    data_upa = models.DateTimeField(null=True, blank=True, db_column="DataUPA")
    ups = models.IntegerField(null=True, blank=True, db_column="UPS")
    data_ups = models.DateTimeField(null=True, blank=True, db_column="DataUPS")
    dettaglio = models.BigIntegerField(null=True, blank=True, db_column="Dettaglio")
    upap = models.IntegerField(null=True, blank=True, db_column="UPAP")
    data_upap = models.DateTimeField(null=True, blank=True, db_column="DataUPAP")
    upsp = models.IntegerField(null=True, blank=True, db_column="UPSP")
    data_upsp = models.DateTimeField(null=True, blank=True, db_column="DataUPSP")
    dettaglio_p = models.BigIntegerField(null=True, blank=True, db_column="DettaglioP")
    registro_cee = models.BooleanField(null=True, blank=True, db_column="RegistroCEE")
    perc_pro_rata = models.FloatField(null=True, blank=True, db_column="Perc_ProRata")
    prog_boll = models.IntegerField(null=True, blank=True, db_column="ProgBoll")
    prog_boll_p = models.IntegerField(null=True, blank=True, db_column="ProgBollP")
    registro_art74 = models.BooleanField(null=True, blank=True, db_column="RegistroArt74")
    iva_art17_ter = models.BooleanField(null=True, blank=True, db_column="Iva_art17_ter")
    disattivato = models.BooleanField(null=True, blank=True, db_column="Disattivato")
    disattiva_check_prot = models.BooleanField(
        null=True, blank=True, db_column="Disattiva_Check_Prot"
    )
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "registri_iva"
        verbose_name = "Registro IVA"
        verbose_name_plural = "Registri IVA"
        ordering = ["codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"

    def get_absolute_url(self):
        return reverse("registri_iva:detail", kwargs={"codice": self.codice})

    @property
    def label(self) -> str:
        return (self.descrizione or "").strip()
