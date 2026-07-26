from django.urls import path

from apps.gruppi_articoli.views import (
    GruppoArticoloDetailView,
    GruppoArticoloListView,
    SyncGruppiArticoliView,
)

app_name = "gruppi_articoli"

urlpatterns = [
    path("gruppi-articoli/", GruppoArticoloListView.as_view(), name="list"),
    path("gruppi-articoli/<path:codice>/", GruppoArticoloDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-gruppi-articoli/", SyncGruppiArticoliView.as_view(), name="sync"),
]
