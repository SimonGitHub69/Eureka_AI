from django.urls import path

from apps.magazzini.views import (
    MagazzinoCreateView,
    MagazzinoDeleteView,
    MagazzinoDetailView,
    MagazzinoListView,
    MagazzinoExportListView,
    MagazzinoPrintListView,
    MagazzinoUpdateView,
    SyncMagazziniView,
)

app_name = "magazzini"

urlpatterns = [
    path("magazzini/", MagazzinoListView.as_view(), name="list"),
    path("magazzini/stampa/", MagazzinoPrintListView.as_view(), name="print_list"),
    path("magazzini/export/", MagazzinoExportListView.as_view(), name="export_list"),
    path("magazzini/nuova/", MagazzinoCreateView.as_view(), name="create"),
    path("magazzini/<path:codice>/modifica/", MagazzinoUpdateView.as_view(), name="edit"),
    path("magazzini/<path:codice>/elimina/", MagazzinoDeleteView.as_view(), name="delete"),
    path("magazzini/<path:codice>/", MagazzinoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-magazzini/", SyncMagazziniView.as_view(), name="sync"),
]
