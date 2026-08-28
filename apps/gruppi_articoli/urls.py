from django.urls import path

from apps.gruppi_articoli.views import (
    GruppoArticoloCreateView,
    GruppoArticoloDeleteView,
    GruppoArticoloDetailView,
    GruppoArticoloListView,
    GruppoArticoloExportListView,
    GruppoArticoloPrintListView,
    GruppoArticoloUpdateView,
    SyncGruppiArticoliView,
)

app_name = "gruppi_articoli"

urlpatterns = [
    path("gruppi-articoli/", GruppoArticoloListView.as_view(), name="list"),
    path("gruppi-articoli/stampa/", GruppoArticoloPrintListView.as_view(), name="print_list"),
    path("gruppi-articoli/export/", GruppoArticoloExportListView.as_view(), name="export_list"),
    path("gruppi-articoli/nuova/", GruppoArticoloCreateView.as_view(), name="create"),
    path("gruppi-articoli/<path:codice>/modifica/", GruppoArticoloUpdateView.as_view(), name="edit"),
    path("gruppi-articoli/<path:codice>/elimina/", GruppoArticoloDeleteView.as_view(), name="delete"),
    path("gruppi-articoli/<path:codice>/", GruppoArticoloDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-gruppi-articoli/", SyncGruppiArticoliView.as_view(), name="sync"),
]
