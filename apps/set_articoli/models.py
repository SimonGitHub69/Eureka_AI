from django.db import models


class SetArticoloH(models.Model):
    """Mirror PostgreSQL della tabella 4D Set_Articoli_H (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    numero_set = models.IntegerField(null=True, blank=True, db_column="NumeroSet", db_index=True)
    nome_set = models.TextField(null=True, blank=True, db_column="NomeSet")
    data_set = models.DateTimeField(null=True, blank=True, db_column="DataSet")
    disattivato = models.BooleanField(null=True, blank=True, db_column="Disattivato")
    fornitore = models.TextField(null=True, blank=True, db_column="Fornitore")
    note = models.TextField(null=True, blank=True, db_column="Note")
    controllo_doc = models.BooleanField(null=True, blank=True, db_column="ControlloDoc")
    note_controllo = models.TextField(null=True, blank=True, db_column="NoteControllo")
    utente_modifica = models.TextField(null=True, blank=True, db_column="UtenteModifica")
    utente_stampa = models.TextField(null=True, blank=True, db_column="UtenteStampa")
    utente_creazione = models.TextField(null=True, blank=True, db_column="UtenteCreazione")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "set_articoli_h"
        verbose_name = "Set articoli"
        verbose_name_plural = "Set articoli"
        ordering = ["numero_set", "nome_set", "id"]

    def __str__(self):
        label = self.nome_set or f"Set {self.numero_set or self.id}"
        return f"{label} ({self.numero_set or self.id})"

    @property
    def data_set_date(self):
        value = self.data_set
        if value is None:
            return None
        return value.date() if hasattr(value, "date") else value


class SetArticoloD(models.Model):
    """Mirror PostgreSQL della tabella 4D Set_Articoli_D (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    testa = models.ForeignKey(
        SetArticoloH,
        on_delete=models.CASCADE,
        db_column="ID_Testa",
        to_field="id",
        related_name="righe",
        db_constraint=False,
    )
    cod_art = models.TextField(null=True, blank=True, db_column="CodArt", db_index=True)
    desc_art = models.TextField(null=True, blank=True, db_column="DescArt")
    qta = models.FloatField(null=True, blank=True, db_column="Qta")
    pos = models.SmallIntegerField(null=True, blank=True, db_column="Pos")
    um = models.TextField(null=True, blank=True, db_column="UM")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "set_articoli_d"
        verbose_name = "Riga set articoli"
        verbose_name_plural = "Righe set articoli"
        ordering = ["pos", "id"]

    def __str__(self):
        return f"{self.cod_art or '?'} ({self.id})"
