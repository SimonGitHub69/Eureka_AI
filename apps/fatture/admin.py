from django.contrib import admin

from apps.fatture.models import Fattura, FatturaDettaglio, SyncFattureLog


@admin.register(SyncFattureLog)
class SyncFattureLogAdmin(admin.ModelAdmin):
    list_display = (
        "started_at",
        "finished_at",
        "ok",
        "fatture_count",
        "dettaglio_count",
        "started_by",
    )
    list_filter = ("ok",)
    readonly_fields = (
        "started_at",
        "finished_at",
        "ok",
        "fatture_count",
        "dettaglio_count",
        "message",
        "started_by",
    )


@admin.register(Fattura)
class FatturaAdmin(admin.ModelAdmin):
    list_display = (
        "id_testa",
        "alfa",
        "numero_fatt",
        "data_fattura",
        "cliente",
        "totale_fattura",
        "synced_at",
    )
    search_fields = ("id_testa", "numero_fatt", "cliente", "destinatario")
    list_filter = ("alfa",)


@admin.register(FatturaDettaglio)
class FatturaDettaglioAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "id_testa",
        "numero_riga",
        "codice",
        "quantita",
        "prezzo_unitario",
        "iva",
        "synced_at",
    )
    search_fields = ("id", "id_testa", "codice", "descrizione")
