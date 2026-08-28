from django.urls import path

from apps.condizioni.views import (
    CondizioneCreateView,
    CondizioneDeleteView,
    CondizioneDetailView,
    CondizioneListView,
    CondizioneExportListView,
    CondizionePrintListView,
    CondizioneUpdateView,
    SyncCondizioniView,
)

app_name = "condizioni"

urlpatterns = [
    path("condizioni/", CondizioneListView.as_view(), name="list"),
    path("condizioni/stampa/", CondizionePrintListView.as_view(), name="print_list"),
    path("condizioni/export/", CondizioneExportListView.as_view(), name="export_list"),
    path("condizioni/nuova/", CondizioneCreateView.as_view(), name="create"),
    path("condizioni/<path:codice>/modifica/", CondizioneUpdateView.as_view(), name="edit"),
    path("condizioni/<path:codice>/elimina/", CondizioneDeleteView.as_view(), name="delete"),
    path("condizioni/<path:codice>/", CondizioneDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-condizioni/", SyncCondizioniView.as_view(), name="sync"),
]
