from django.db import models


class GruppoArticolo(models.Model):
    """Mirror PostgreSQL della tabella 4D GruppoArt (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    color_fore = models.IntegerField(null=True, blank=True, db_column="ColorFore")
    color_back = models.IntegerField(null=True, blank=True, db_column="ColorBack")
    font_style = models.TextField(null=True, blank=True, db_column="FontStyle")
    color_fore_gz = models.IntegerField(null=True, blank=True, db_column="ColorForeGZ")
    color_back_gz = models.IntegerField(null=True, blank=True, db_column="ColorBackGZ")
    font_style_gz = models.TextField(null=True, blank=True, db_column="FontStyleGZ")
    color_fore_mz = models.IntegerField(null=True, blank=True, db_column="ColorForeMZ")
    color_back_mz = models.IntegerField(null=True, blank=True, db_column="ColorBackMZ")
    font_style_mz = models.TextField(null=True, blank=True, db_column="FontStyleMZ")
    f_disattivato = models.BooleanField(null=True, blank=True, db_column="F_Disattivato")
    rgb_color_fore_gz = models.IntegerField(null=True, blank=True, db_column="RGB_ColorForeGZ")
    rgb_color_back_gz = models.IntegerField(null=True, blank=True, db_column="RGB_ColorBackGZ")
    rgb_color_fore_mz = models.IntegerField(null=True, blank=True, db_column="RGB_ColorForeMZ")
    rgb_color_back_mz = models.IntegerField(null=True, blank=True, db_column="RGB_ColorBackMZ")
    rgb_color_fore = models.IntegerField(null=True, blank=True, db_column="RGB_ColorFore")
    rgb_color_back = models.IntegerField(null=True, blank=True, db_column="RGB_ColorBack")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "gruppi_articoli"
        verbose_name = "Gruppo articolo"
        verbose_name_plural = "Gruppi articoli"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
