from django.urls import path

from apps.zone.views import (
    SyncZoneView,
    ZonaCreateView,
    ZonaDeleteView,
    ZonaDetailView,
    ZonaListView,
    ZonaExportListView,
    ZonaPrintListView,
    ZonaUpdateView,
)

app_name = "zone"

urlpatterns = [
    path("zone/", ZonaListView.as_view(), name="list"),
    path("zone/stampa/", ZonaPrintListView.as_view(), name="print_list"),
    path("zone/export/", ZonaExportListView.as_view(), name="export_list"),
    path("zone/nuova/", ZonaCreateView.as_view(), name="create"),
    path("zone/<path:codice>/modifica/", ZonaUpdateView.as_view(), name="edit"),
    path("zone/<path:codice>/elimina/", ZonaDeleteView.as_view(), name="delete"),
    path("zone/<path:codice>/", ZonaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-zone/", SyncZoneView.as_view(), name="sync"),
]
