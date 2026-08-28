from django.urls import path

from apps.banche.views import (
    BancaCreateView,
    BancaDeleteView,
    BancaDetailView,
    BancaListView,
    BancaExportListView,
    BancaPrintListView,
    BancaUpdateView,
    SyncBancheView,
)

app_name = "banche"

urlpatterns = [
    path("banche/", BancaListView.as_view(), name="list"),
    path("banche/stampa/", BancaPrintListView.as_view(), name="print_list"),
    path("banche/export/", BancaExportListView.as_view(), name="export_list"),
    path("banche/nuova/", BancaCreateView.as_view(), name="create"),
    path("banche/<path:codice>/modifica/", BancaUpdateView.as_view(), name="edit"),
    path("banche/<path:codice>/elimina/", BancaDeleteView.as_view(), name="delete"),
    path("banche/<path:codice>/", BancaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-banche/", SyncBancheView.as_view(), name="sync"),
]
