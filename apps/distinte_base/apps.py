from django.apps import AppConfig


class DistinteBaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.distinte_base"
    label = "distinte_base"
    verbose_name = "Distinte base"
