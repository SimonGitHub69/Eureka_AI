from django.db import models


class Categoria(models.Model):
    """Mirror PostgreSQL della tabella 4D CatMerce (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    c_vendita_prop = models.TextField(null=True, blank=True, db_column="CVenditaProp")
    provvigione = models.FloatField(null=True, blank=True, db_column="Provvigione")
    categoria_utf = models.TextField(null=True, blank=True, db_column="CategoriaUTF")
    fl_calcola_sfrido = models.BooleanField(null=True, blank=True, db_column="FlCalcolaSfrido")
    tipo_rotolo = models.BooleanField(null=True, blank=True, db_column="TipoRotolo")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "categorie"
        verbose_name = "Categoria"
        verbose_name_plural = "Categorie"
        ordering = ["descrizione", "codice"]

    def __str__(self):
        label = self.descrizione or self.codice
        return f"{label} ({self.codice})"
