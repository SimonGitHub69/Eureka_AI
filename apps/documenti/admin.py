from django.contrib import admin

from apps.documenti.models import (
    ContatoreDocumento,
    RigaDocumento,
    SyncDocumentiLog,
    TestaDocumento,
    TipoDocumento,
)


@admin.register(ContatoreDocumento)
class ContatoreDocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "codice",
        "esercizio",
        "tipo_contatore",
        "label",
        "ultimo_numero",
        "serie_default",
    )
    list_filter = ("tipo_contatore", "esercizio")
    search_fields = ("codice", "label")
    ordering = ("tipo_contatore", "-esercizio", "codice")


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "codice",
        "label",
        "categoria",
        "clifor_tipo",
        "scadenze",
        "contatore",
        "serie",
        "attivo",
        "ordine",
    )
    list_filter = ("attivo", "categoria", "clifor_tipo", "scadenze", "contatore")
    filter_horizontal = ("contatori",)
    ordering = ("ordine", "codice")


@admin.register(TestaDocumento)
class TestaDocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_doc",
        "numero_documento",
        "data_documento",
        "codice_clifor",
        "codice_agente",
        "totale",
    )
    list_filter = ("tipo_doc",)
    search_fields = ("codice_clifor", "codice_agente", "destinatario", "alfa")
    date_hierarchy = "data_documento"


@admin.register(RigaDocumento)
class RigaDocumentoAdmin(admin.ModelAdmin):
    list_display = ("testa", "numero_riga", "codice", "quantita", "prezzo_unitario", "provvigione")
    search_fields = ("codice", "descrizione")


@admin.register(SyncDocumentiLog)
class SyncDocumentiLogAdmin(admin.ModelAdmin):
    list_display = ("started_at", "ok", "teste_count", "righe_count")
    readonly_fields = ("started_at", "finished_at", "message")
