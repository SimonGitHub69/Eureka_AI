from django.urls import path

from apps.pdc.views import (
    PdcCreateView,
    PdcDeleteView,
    PdcDetailView,
    PdcListView,
    PdcPartitarioView,
    PdcPrintListView,
    PdcUpdateView,
    SyncPdcView,
)

app_name = "pdc"
urlpatterns = [
    path("pdc/", PdcListView.as_view(), name="list"),
    path("pdc/stampa/", PdcPrintListView.as_view(), name="print_list"),
    path("pdc/nuovo/", PdcCreateView.as_view(), name="create"),
    path("pdc/<path:codice>/modifica/", PdcUpdateView.as_view(), name="edit"),
    path("pdc/<path:codice>/elimina/", PdcDeleteView.as_view(), name="delete"),
    path("pdc/<path:codice>/partitario/", PdcPartitarioView.as_view(), name="partitario"),
    path("pdc/<path:codice>/", PdcDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-pdc/", SyncPdcView.as_view(), name="sync"),
]

