from django.db import models


class LavorazioneExtra(models.Model):
    """Mirror PostgreSQL della tabella 4D TabLavorazioniExtra (gestita dal sync)."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    cod = models.TextField(null=True, blank=True, db_column="Cod")
    descrizione = models.TextField(null=True, blank=True, db_column="Descrizione")
    f_componente = models.BooleanField(null=True, blank=True, db_column="F_Componente")
    f_richiedi_note = models.BooleanField(null=True, blank=True, db_column="F_RichiediNote")
    f_codice_fittizio = models.BooleanField(null=True, blank=True, db_column="F_CodiceFittizio")
    f_pausa_non_retrib = models.BooleanField(null=True, blank=True, db_column="F_PausaNonRetrib")
    f_note_automatiche = models.BooleanField(null=True, blank=True, db_column="F_NoteAutomatiche")
    f_export_storico = models.BooleanField(null=True, blank=True, db_column="F_ExportStorico")
    data_modifica = models.DateTimeField(null=True, blank=True, db_column="DataModifica")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    f_vincolante = models.BooleanField(null=True, blank=True, db_column="F_Vincolante")
    cod_reparto = models.TextField(null=True, blank=True, db_column="CodReparto")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "lavorazioni_extra"
        verbose_name = "Lavorazione extra"
        verbose_name_plural = "Lavorazioni extra"
        ordering = ["cod", "id"]

    def __str__(self):
        label = self.cod or f"ID {self.id}"
        if self.descrizione:
            return f"{label} · {self.descrizione}"
        return label
