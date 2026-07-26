from django.contrib import admin

from apps.geografia.models import Citta, Provincia, Regione


@admin.register(Regione)
class RegioneAdmin(admin.ModelAdmin):
    list_display = ("codice", "nome")
    search_fields = ("codice", "nome")


@admin.register(Provincia)
class ProvinciaAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nome", "codice_istat", "regione")
    list_filter = ("regione",)
    search_fields = ("sigla", "nome", "codice_istat")


@admin.register(Citta)
class CittaAdmin(admin.ModelAdmin):
    list_display = ("nome", "codice_istat", "provincia", "cap", "codice_catastale")
    list_filter = ("provincia__regione", "provincia")
    search_fields = ("nome", "codice_istat", "cap", "codice_catastale")
