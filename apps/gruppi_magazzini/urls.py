from django.urls import path

from apps.gruppi_magazzini.views import (
    GruppoMagazzinoDetailView,
    GruppoMagazzinoListView,
    SyncGruppiMagazziniView,
)

app_name = "gruppi_magazzini"

urlpatterns = [
    path("gruppi-magazzini/", GruppoMagazzinoListView.as_view(), name="list"),
    path("gruppi-magazzini/<path:cod>/", GruppoMagazzinoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-gruppi-magazzini/", SyncGruppiMagazziniView.as_view(), name="sync"),
]
