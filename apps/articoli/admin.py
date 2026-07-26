from django.contrib import admin

from apps.articoli.models import Articolo


@admin.register(Articolo)
class ArticoloAdmin(admin.ModelAdmin):
    list_display = (
        "codice",
        "descrizione",
        "cat_omogenea",
        "unita_misura",
        "listino1",
        "fl_disattivato",
        "synced_at",
    )
    search_fields = (
        "codice",
        "descrizione",
        "cat_omogenea",
        "cod_fornitore",
        "codice_alternativo1",
        "codice_alternativo2",
    )
    list_filter = ("fl_disattivato", "giacenza", "disponibile")
