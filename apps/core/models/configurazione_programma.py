from django.db import models

from apps.core.models.base import BaseModel


class ConfigurazioneProgramma(BaseModel):
    """Parametri generali dell'applicazione (singleton pk=1)."""

    assistente_vocale_attivo = models.BooleanField(
        "Assistente vocale",
        default=True,
        help_text="Se disattivo, microfono e comandi vocali non sono disponibili.",
    )
    navbar_fissa = models.BooleanField(
        "Barra superiore fissa",
        default=True,
        help_text="Se attivo, la barra con menu e utente resta in alto durante lo scorrimento (utile su tablet).",
    )
    liste_fisse = models.BooleanField(
        "Intestazione liste fissa",
        default=True,
        help_text="Se attivo, titolo e filtri delle liste e la barra delle schede restano in alto durante lo scorrimento.",
    )
    suono_errore_attivo = models.BooleanField(
        "Suono errore",
        default=True,
        help_text="Riproduce un suono quando la pagina mostra errori di validazione o messaggi di errore.",
    )
    suono_errore_wav = models.FileField(
        "File suono errore (.wav)",
        upload_to="eureka/sounds/",
        blank=True,
        null=True,
        help_text="File audio .wav personalizzato. Se vuoto, viene usato il suono predefinito.",
    )
    doc_prv = models.BooleanField(
        "Preventivi",
        default=True,
        help_text="Mostra Preventivi nel menu Fatturazione Magazzino.",
    )
    doc_orv = models.BooleanField(
        "Ordini vendita",
        default=True,
        help_text="Mostra Ordini vendita nel menu Fatturazione Magazzino.",
    )
    doc_ora = models.BooleanField(
        "Ordini acquisto",
        default=True,
        help_text="Mostra Ordini acquisto nel menu Fatturazione Magazzino.",
    )
    doc_ddt = models.BooleanField(
        "DDT / Bolle",
        default=True,
        help_text="Mostra DDT / Bolle nel menu Fatturazione Magazzino.",
    )
    doc_fat = models.BooleanField(
        "Fatture",
        default=True,
        help_text="Mostra Fatture nel menu Fatturazione Magazzino.",
    )
    doc_ncr = models.BooleanField(
        "Note di credito",
        default=True,
        help_text="Mostra Note di credito nel menu Fatturazione Magazzino.",
    )
    doc_ndb = models.BooleanField(
        "Note di debito",
        default=True,
        help_text="Mostra Note di debito nel menu Fatturazione Magazzino.",
    )
    extra_carbon = models.BooleanField(
        "CARBON",
        default=True,
        help_text="Mostra la personalizzazione CARBON nel menu laterale (produzione, seriali, stampi, schede di lavorazione).",
    )

    debug_ai_sql = models.BooleanField(
        "Mostra SQL e spiegazione AI (debug)",
        default=False,
        help_text="Mostra nel modale dell'assistente AI la query SQL generata e la relativa spiegazione. Da usare solo per debug.",
    )
    ai_recent_searches_limit = models.PositiveSmallIntegerField(
        "Ricerche recenti AI per utente",
        default=10,
        help_text="Numero massimo di ricerche recenti della bacchetta magica da conservare nel browser per ogni utente.",
    )
    ai_example_prompt = models.CharField(
        "Testo di esempio (Assistente AI)",
        max_length=500,
        default=(
            "Cerca tutti i movimenti IVA il cui imponibile è compreso tra 1500 e 1750 "
            "nell'anno in corso"
        ),
        help_text=(
            "Testo mostrato come suggerimento nel modale della bacchetta magica "
            "(dopo «Ad esempio:»)."
        ),
    )
    inventario_discrepanza_pct = models.PositiveSmallIntegerField(
        "Soglia discrepanza prezzi inventario (%)",
        default=25,
        help_text=(
            "Nella stampa inventario evidenzia (e filtra) le righe in cui "
            "|ultimo − medio| / max(ultimo, medio) supera questa percentuale. "
            "Valori tipici: 15–30."
        ),
    )
    prezzo_decimali = models.PositiveSmallIntegerField(
        "Decimali prezzi unitari",
        default=3,
        help_text=(
            "Numero massimo di decimali per i prezzi unitari a video "
            "(schede articolo, movimenti di magazzino, righe documento, ecc.). "
            "Importi e totali restano a 2 decimali."
        ),
    )
    prezzo_decimali_stampa = models.PositiveSmallIntegerField(
        "Decimali prezzi unitari in stampa",
        default=3,
        help_text=(
            "Numero massimo di decimali per i prezzi unitari nelle stampe "
            "(inventario, movimenti articolo, elenco articoli, ecc.). "
            "Importi e totali in stampa restano a 2 decimali."
        ),
    )

    class Meta:
        verbose_name = "Parametri programma"
        verbose_name_plural = "Parametri programma"

    def __str__(self):
        return "Parametri programma"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "assistente_vocale_attivo": True,
                "navbar_fissa": True,
                "liste_fisse": True,
                "suono_errore_attivo": True,
                "doc_prv": True,
                "doc_orv": True,
                "doc_ora": True,
                "doc_ddt": True,
                "doc_fat": True,
                "doc_ncr": True,
                "doc_ndb": True,
                "extra_carbon": True,
                "debug_ai_sql": False,
                "ai_recent_searches_limit": 10,
                "ai_example_prompt": (
                    "Cerca tutti i movimenti IVA il cui imponibile è compreso tra 1500 e 1750 "
                    "nell'anno in corso"
                ),
                "inventario_discrepanza_pct": 25,
                "prezzo_decimali": 3,
                "prezzo_decimali_stampa": 3,
            },
        )
        return obj
