from django.urls import path

from apps.dashboard.views import DashboardView, SistemaView

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="index"),
    path("sistema/", SistemaView.as_view(), name="sistema"),
]
