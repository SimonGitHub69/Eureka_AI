from django.db import models
from django.db.models import Max

from apps.core.models.base import BaseModel


class AzioneComandoVocale(models.TextChoices):
    NAVIGATE = "navigate", "Apri pagina"
    SEARCH = "search", "Cerca"


class DestinazioneComandoVocale(models.TextChoices):
    DASHBOARD = "dashboard", "Dashboard"
    CLIENTI = "clienti", "Clienti"
    FORNITORI = "fornitori", "Fornitori"
    AGENTI = "agenti", "Agenti"
    ARTICOLI = "articoli", "Articoli"
    FATTURE = "fatture", "Fatture"
    CATEGORIE = "categorie", "Categorie"
    GRUPPI_ARTICOLI = "gruppi_articoli", "Gruppi articoli"
    PARAMETRI_4D = "parametri_4d", "Parametri 4D"
    SISTEMA = "sistema", "Sistema"
    SYNC_FATTURE = "sync_fatture", "Sync fatture 4D"
    SYNC_ANAGRAFICHE = "sync_anagrafiche", "Sync anagrafiche 4D"
    SYNC_CATEGORIE = "sync_categorie", "Sync categorie 4D"
    SYNC_GRUPPI_ARTICOLI = "sync_gruppi_articoli", "Sync gruppi articoli 4D"


class MatchModeComandoVocale(models.TextChoices):
    CONTAINS = "contains", "Contiene"
    EXACT = "exact", "Esatto"
    STARTS_WITH = "starts_with", "Inizia con"


class ComandoVocale(BaseModel):
    frase = models.CharField(
        "Frase",
        max_length=200,
        help_text='Testo da riconoscere, es. "apri clienti" o "cerca cliente".',
    )
    azione = models.CharField(
        "Azione",
        max_length=20,
        choices=AzioneComandoVocale.choices,
    )
    destinazione = models.CharField(
        "Destinazione",
        max_length=40,
        choices=DestinazioneComandoVocale.choices,
    )
    query = models.CharField(
        "Query di ricerca",
        max_length=200,
        blank=True,
        help_text='Solo per azione "Cerca": query fissa. Lascia vuoto per usare il testo dopo la frase.',
    )
    attivo = models.BooleanField("Attivo", default=True)
    ordine = models.IntegerField("Ordine", default=0)
    match_mode = models.CharField(
        "Modalità di match",
        max_length=20,
        choices=MatchModeComandoVocale.choices,
        default=MatchModeComandoVocale.CONTAINS,
    )

    class Meta:
        verbose_name = "Comando vocale"
        verbose_name_plural = "Comandi vocali"
        ordering = ["ordine", "frase"]

    def __str__(self):
        return self.frase

    def to_voice_dict(self):
        return {
            "frase": self.frase,
            "azione": self.azione,
            "destinazione": self.destinazione,
            "query": self.query,
            "match_mode": self.match_mode,
            "ordine": self.ordine,
        }

    def duplicate(self, user=None):
        suffix = " (copia)"
        new_frase = f"{self.frase}{suffix}"
        if len(new_frase) > self._meta.get_field("frase").max_length:
            trim = self._meta.get_field("frase").max_length - len(suffix)
            new_frase = f"{self.frase[:trim]}{suffix}"

        max_ordine = (
            ComandoVocale.objects.filter(is_active=True).aggregate(m=Max("ordine"))["m"] or 0
        )

        copy = ComandoVocale(
            frase=new_frase,
            azione=self.azione,
            destinazione=self.destinazione,
            query=self.query,
            match_mode=self.match_mode,
            ordine=max_ordine + 1,
            attivo=False,
            note=self.note,
            created_by=user,
            updated_by=user,
        )
        copy.save()
        return copy
