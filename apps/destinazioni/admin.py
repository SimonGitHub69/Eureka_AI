from django.contrib import admin

from apps.destinazioni.models import DestinazioneDiversa


@admin.register(DestinazioneDiversa)
class DestinazioneDiversaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "codice",
        "codice_dest",
        "ragione_sociale",
        "citta",
        "provincia",
        "data_modifica",
        "synced_at",
    )
    list_filter = ("provincia", "black_list")
    search_fields = (
        "codice",
        "codice_dest",
        "ragione_sociale",
        "indirizzo",
        "citta",
        "telefono",
        "email",
    )
    ordering = ("codice", "codice_dest")
