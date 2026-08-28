from django.apps import AppConfig


class DocumentiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.documenti"
    verbose_name = "Documenti"

    def ready(self):
        from apps.documenti import signals  # noqa: F401
