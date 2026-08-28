from django.db import models


class Operatore(models.Model):
    """Mirror PostgreSQL della tabella 4D Operatori (gestita dal sync)."""

    codice = models.TextField(primary_key=True, db_column="Codice")
    nome = models.TextField(null=True, blank=True, db_column="Nome")
    reparto = models.TextField(null=True, blank=True, db_column="Reparto")
    firma_privacy = models.BooleanField(null=True, blank=True, db_column="FirmaPrivacy")
    firma_consegna_dpi = models.BooleanField(null=True, blank=True, db_column="FirmaConsegnaDPI")
    data_assunzione = models.DateField(null=True, blank=True, db_column="DataAssunzione")
    data_dimissioni = models.DateField(null=True, blank=True, db_column="DataDimissioni")
    tutor = models.TextField(null=True, blank=True, db_column="Tutor")
    data_verifica_formazione = models.DateField(
        null=True, blank=True, db_column="DataVerificaFormazione"
    )
    esito_formazione = models.TextField(null=True, blank=True, db_column="EsitoFormazione")
    tessera_vaccinazioni = models.TextField(
        null=True, blank=True, db_column="TesseraVaccinazioni"
    )
    data_scadenza_vaccinazione = models.DateField(
        null=True, blank=True, db_column="DataScadenzaVaccinazione"
    )
    operatore_disattivo = models.BooleanField(
        null=True, blank=True, db_column="OperatoreDisattivo"
    )
    num_badge = models.TextField(null=True, blank=True, db_column="NumBadge")
    nome_breve = models.TextField(null=True, blank=True, db_column="NomeBreve")
    data_modifica = models.DateField(null=True, blank=True, db_column="DataModifica")
    ora_e1 = models.TimeField(null=True, blank=True, db_column="Ora_E1")
    ora_u1 = models.TimeField(null=True, blank=True, db_column="Ora_U1")
    ora_e2 = models.TimeField(null=True, blank=True, db_column="Ora_E2")
    ora_u2 = models.TimeField(null=True, blank=True, db_column="Ora_U2")
    matricola_timbratore = models.TextField(
        null=True, blank=True, db_column="Matricola_Timbratore"
    )
    email = models.TextField(null=True, blank=True, db_column="email")
    ora_modifica = models.TimeField(null=True, blank=True, db_column="OraModifica")
    calendario_google = models.TextField(
        null=True, blank=True, db_column="Calendario_Google"
    )
    sigla = models.TextField(null=True, blank=True, db_column="Sigla")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "operatori"
        verbose_name = "Operatore"
        verbose_name_plural = "Operatori"
        ordering = ["codice"]

    def __str__(self):
        return self.nome or str(self.codice)
