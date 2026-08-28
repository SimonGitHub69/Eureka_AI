from django.urls import path

from apps.gruppi_magazzini.views import (
    GruppoMagazzinoCreateView,
    GruppoMagazzinoDeleteView,
    GruppoMagazzinoDetailView,
    GruppoMagazzinoListView,
    GruppoMagazzinoExportListView,
    GruppoMagazzinoPrintListView,
    GruppoMagazzinoUpdateView,
    SyncGruppiMagazziniView,
)

app_name = "gruppi_magazzini"

urlpatterns = [
    path("gruppi-magazzini/", GruppoMagazzinoListView.as_view(), name="list"),
    path("gruppi-magazzini/stampa/", GruppoMagazzinoPrintListView.as_view(), name="print_list"),
    path("gruppi-magazzini/export/", GruppoMagazzinoExportListView.as_view(), name="export_list"),
    path("gruppi-magazzini/nuova/", GruppoMagazzinoCreateView.as_view(), name="create"),
    path("gruppi-magazzini/<path:cod>/modifica/", GruppoMagazzinoUpdateView.as_view(), name="edit"),
    path("gruppi-magazzini/<path:cod>/elimina/", GruppoMagazzinoDeleteView.as_view(), name="delete"),
    path("gruppi-magazzini/<path:cod>/", GruppoMagazzinoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-gruppi-magazzini/", SyncGruppiMagazziniView.as_view(), name="sync"),
]
