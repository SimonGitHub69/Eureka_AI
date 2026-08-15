from django.urls import path

from apps.sconti.views import (
    ScontoCreateView,
    ScontoDeleteView,
    ScontoDetailView,
    ScontoExportListView,
    ScontoListView,
    ScontoPrintListView,
    ScontoUpdateView,
    SyncScontiView,
)

app_name = "sconti"

urlpatterns = [
    path("sconti/", ScontoListView.as_view(), name="list"),
    path("sconti/stampa/", ScontoPrintListView.as_view(), name="print_list"),
    path("sconti/export/", ScontoExportListView.as_view(), name="export_list"),
    path("sconti/nuovo/", ScontoCreateView.as_view(), name="create"),
    path("sconti/<path:codice>/modifica/", ScontoUpdateView.as_view(), name="edit"),
    path("sconti/<path:codice>/elimina/", ScontoDeleteView.as_view(), name="delete"),
    path("sconti/<path:codice>/", ScontoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-sconti/", SyncScontiView.as_view(), name="sync"),
]
