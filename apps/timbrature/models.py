from django.db import models


class Timbratura(models.Model):
    """Mirror PostgreSQL della tabella 4D Timbrature — presenza giornaliera operatore."""

    id = models.IntegerField(primary_key=True, db_column="ID")
    cod_operatore = models.TextField(db_column="Cod_Operatore")
    data = models.DateTimeField(db_column="Data")
    e1_ora = models.TimeField(null=True, blank=True, db_column="E1_Ora")
    u1_ora = models.TimeField(null=True, blank=True, db_column="U1_Ora")
    e2_ora = models.TimeField(null=True, blank=True, db_column="E2_Ora")
    u2_ora = models.TimeField(null=True, blank=True, db_column="U2_Ora")
    e3_ora = models.TimeField(null=True, blank=True, db_column="E3_Ora")
    u3_ora = models.TimeField(null=True, blank=True, db_column="U3_Ora")
    note = models.TextField(null=True, blank=True, db_column="Note")
    e1_ora_rett = models.TimeField(null=True, blank=True, db_column="E1_Ora_Rett")
    u1_ora_rett = models.TimeField(null=True, blank=True, db_column="U1_Ora_Rett")
    e2_ora_rett = models.TimeField(null=True, blank=True, db_column="E2_Ora_Rett")
    u2_ora_rett = models.TimeField(null=True, blank=True, db_column="U2_Ora_Rett")
    e3_ora_rett = models.TimeField(null=True, blank=True, db_column="E3_Ora_Rett")
    u3_ora_rett = models.TimeField(null=True, blank=True, db_column="U3_Ora_Rett")
    scheda_validata = models.BooleanField(null=True, blank=True, db_column="Scheda_Validata")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "timbrature"
        verbose_name = "Timbratura"
        verbose_name_plural = "Timbrature"
        ordering = ["-data", "cod_operatore"]

    def __str__(self):
        return f"{self.cod_operatore} · {self.data:%d/%m/%Y}"
