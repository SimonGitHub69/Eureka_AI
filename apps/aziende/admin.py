from django.contrib import admin

from apps.aziende.models import AziendaDati


@admin.register(AziendaDati)
class AziendaDatiAdmin(admin.ModelAdmin):
    list_display = ("azienda_id", "logo", "is_active", "updated_at")
    search_fields = ("azienda_id", "note")
    list_filter = ("is_active",)
    readonly_fields = ("uuid", "created_at", "updated_at", "created_by", "updated_by")
    fieldsets = (
        (None, {"fields": ("azienda_id", "logo", "note")}),
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
