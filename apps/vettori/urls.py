from django.urls import path

from apps.vettori.views import (
    SyncVettoriView,
    VettoreCreateView,
    VettoreDeleteView,
    VettoreDetailView,
    VettoreListView,
    VettoreExportListView,
    VettorePrintListView,
    VettoreUpdateView,
)

app_name = "vettori"

urlpatterns = [
    path("vettori/", VettoreListView.as_view(), name="list"),
    path("vettori/stampa/", VettorePrintListView.as_view(), name="print_list"),
    path("vettori/export/", VettoreExportListView.as_view(), name="export_list"),
    path("vettori/nuovo/", VettoreCreateView.as_view(), name="create"),
    path("vettori/<path:codice>/modifica/", VettoreUpdateView.as_view(), name="edit"),
    path("vettori/<path:codice>/elimina/", VettoreDeleteView.as_view(), name="delete"),
    path("vettori/<path:codice>/", VettoreDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-vettori/", SyncVettoriView.as_view(), name="sync"),
]
