from django.db import models


class Stampo(models.Model):
    """Mirror PostgreSQL della tabella 4D TabStampi (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    cod_stampo = models.TextField(null=True, blank=True, db_column="CodStampo")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    cod_cliente = models.TextField(null=True, blank=True, db_column="CodCliente")
    tipo_attrezzatura = models.TextField(null=True, blank=True, db_column="Tipo_Attrezzatura")
    progetto = models.TextField(null=True, blank=True, db_column="Progetto")
    cod_reparto = models.TextField(null=True, blank=True, db_column="CodReparto")
    componente = models.TextField(null=True, blank=True, db_column="Componente")
    materiale = models.TextField(null=True, blank=True, db_column="Materiale")
    lato = models.TextField(null=True, blank=True, db_column="Lato")
    kit = models.TextField(null=True, blank=True, db_column="Kit")
    versione = models.TextField(null=True, blank=True, db_column="Versione")
    note = models.TextField(null=True, blank=True, db_column="Note")
    c_lavoro = models.BooleanField(null=True, blank=True, db_column="C_Lavoro")
    attrezzatura_bloccata = models.BooleanField(
        null=True, blank=True, db_column="Attrezzatura_Bloccata"
    )
    multi_impronta = models.BooleanField(null=True, blank=True, db_column="Multi_Impronta")
    codice_art_stampo = models.TextField(null=True, blank=True, db_column="CodiceArtStampo")
    cod_art_cd1 = models.TextField(null=True, blank=True, db_column="CodArtCD1")
    cod_art_cd2 = models.TextField(null=True, blank=True, db_column="CodArtCD2")
    cod_art_cd3 = models.TextField(null=True, blank=True, db_column="CodArtCD3")
    cod_art_cd4 = models.TextField(null=True, blank=True, db_column="CodArtCD4")
    cod_art_cd5 = models.TextField(null=True, blank=True, db_column="CodArtCD5")
    cod_art_cd6 = models.TextField(null=True, blank=True, db_column="CodArtCD6")
    cod_art_cd7 = models.TextField(null=True, blank=True, db_column="CodArtCD7")
    cod_art_cd8 = models.TextField(null=True, blank=True, db_column="CodArtCD8")
    cod_art_cd9 = models.TextField(null=True, blank=True, db_column="CodArtCD9")
    cod_art_cd10 = models.TextField(null=True, blank=True, db_column="CodArtCD10")
    cod_art_cd11 = models.TextField(null=True, blank=True, db_column="CodArtCD11")
    cod_art_cd12 = models.TextField(null=True, blank=True, db_column="CodArtCD12")
    cod_art_cd13 = models.TextField(null=True, blank=True, db_column="CodArtCD13")
    cod_art_cd14 = models.TextField(null=True, blank=True, db_column="CodArtCD14")
    cod_art_cd15 = models.TextField(null=True, blank=True, db_column="CodArtCD15")
    cod_art_cd16 = models.TextField(null=True, blank=True, db_column="CodArtCD16")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    synced_at = models.DateTimeField(null=True, blank=True)

    ARTICOLI_CD_FIELDS = tuple(f"cod_art_cd{i}" for i in range(1, 17))

    class Meta:
        managed = False
        db_table = "stampi"
        verbose_name = "Stampo"
        verbose_name_plural = "Stampi"
        ordering = ["cod_stampo", "id"]

    def __str__(self):
        label = self.cod_stampo or f"ID {self.id}"
        if self.descrizione:
            return f"{label} · {self.descrizione}"
        return label

    def articoli_cd_list(self):
        """Lista (01..16, valore) per card Articoli CD."""
        items = []
        for i, field_name in enumerate(self.ARTICOLI_CD_FIELDS, start=1):
            items.append((f"{i:02d}", getattr(self, field_name) or ""))
        return items
