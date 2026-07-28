from django.contrib import admin

from apps.agenda.models import EventoAgenda


@admin.register(EventoAgenda)
class EventoAgendaAdmin(admin.ModelAdmin):
    list_display = (
        "titolo",
        "inizio",
        "fine",
        "tutto_il_giorno",
        "colore",
        "is_active",
        "created_by",
    )
    list_filter = ("tutto_il_giorno", "colore", "is_active")
    search_fields = ("titolo", "descrizione", "luogo")
    date_hierarchy = "inizio"
