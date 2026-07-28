from django.contrib import admin

from apps.core.models import (
    ComandoVocale,
    Configurazione4D,
    ConfigurazionePC,
    ConfigurazioneProgramma,
)


@admin.register(ConfigurazioneProgramma)
class ConfigurazioneProgrammaAdmin(admin.ModelAdmin):
    list_display = ("id", "assistente_vocale_attivo", "navbar_fissa", "updated_at")
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")
    fieldsets = (
        (None, {"fields": ("assistente_vocale_attivo", "navbar_fissa", "note")}),
        (
            "Audit",
            {
                "classes": ("collapse",),
                "fields": (
                    "uuid",
                    "is_active",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )


@admin.register(ConfigurazionePC)
class ConfigurazionePCAdmin(admin.ModelAdmin):
    list_display = (
        "nome_pc",
        "descrizione",
        "assistente_vocale_attivo",
        "navbar_fissa",
        "is_active",
        "updated_at",
    )
    search_fields = ("nome_pc", "descrizione")
    list_filter = ("assistente_vocale_attivo", "navbar_fissa", "is_active")
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")



@admin.register(Configurazione4D)
class Configurazione4DAdmin(admin.ModelAdmin):
    list_display = ("id", "attiva", "server", "porta", "utente", "dsn", "updated_at")
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "attiva",
                    "server",
                    "porta",
                    "utente",
                    "password",
                    "driver_odbc",
                    "usa_ssl",
                    "dsn",
                    "note",
                )
            },
        ),
        (
            "Audit",
            {
                "classes": ("collapse",),
                "fields": (
                    "uuid",
                    "is_active",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )


@admin.register(ComandoVocale)
class ComandoVocaleAdmin(admin.ModelAdmin):
    list_display = ("frase", "azione", "destinazione", "attivo", "ordine", "match_mode", "updated_at")
    list_filter = ("azione", "destinazione", "attivo", "match_mode")
    search_fields = ("frase", "query", "note")
    ordering = ("ordine", "frase")
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")
