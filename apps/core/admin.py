from django.contrib import admin

from apps.core.models import (
    ComandoVocale,
    Configurazione4D,
    ConfigurazionePC,
    ConfigurazioneProgramma,
    ParametriContabili,
    ParametriMail,
)


@admin.register(ConfigurazioneProgramma)
class ConfigurazioneProgrammaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "assistente_vocale_attivo",
        "navbar_fissa",
        "liste_fisse",
        "suono_errore_attivo",
        "debug_ai_sql",
        "doc_fat",
        "updated_at",
    )
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "assistente_vocale_attivo",
                    "navbar_fissa",
                    "liste_fisse",
                    "suono_errore_attivo",
                    "debug_ai_sql",
                    "suono_errore_wav",
                    "doc_prv",
                    "doc_orv",
                    "doc_ora",
                    "doc_ddt",
                    "doc_fat",
                    "doc_ncr",
                    "doc_ndb",
                    "extra_carbon",
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


@admin.register(ConfigurazionePC)
class ConfigurazionePCAdmin(admin.ModelAdmin):
    list_display = (
        "nome_pc",
        "descrizione",
        "assistente_vocale_attivo",
        "navbar_fissa",
        "liste_fisse",
        "is_active",
        "updated_at",
    )
    search_fields = ("nome_pc", "descrizione")
    list_filter = ("assistente_vocale_attivo", "navbar_fissa", "liste_fisse", "is_active")
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


@admin.register(ParametriContabili)
class ParametriContabiliAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "aliquota_iva_spese",
        "contropartita_spese_trasporto",
        "updated_at",
    )
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")


@admin.register(ParametriMail)
class ParametriMailAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attiva",
        "server_smtp",
        "porta",
        "mittente",
        "updated_at",
    )
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "attiva",
                    "server_smtp",
                    "porta",
                    "usa_tls",
                    "usa_ssl",
                    "utente",
                    "password",
                    "mittente",
                    "nome_mittente",
                    "reply_to",
                    "copia_nascosta",
                    "email_test",
                    "timeout_secondi",
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
