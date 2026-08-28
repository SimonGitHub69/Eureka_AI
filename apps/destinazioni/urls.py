from django.urls import path

from apps.destinazioni.views import (
    DestinazioneCreateView,
    DestinazioneDeleteView,
    DestinazioneDetailView,
    DestinazioneListView,
    DestinazioneExportListView,
    DestinazionePrintListView,
    DestinazioneUpdateView,
    SyncDestinazioniView,
)

app_name = "destinazioni"

urlpatterns = [
    path("destinazioni/", DestinazioneListView.as_view(), name="list"),
    path("destinazioni/stampa/", DestinazionePrintListView.as_view(), name="print_list"),
    path("destinazioni/export/", DestinazioneExportListView.as_view(), name="export_list"),
    path("destinazioni/nuova/", DestinazioneCreateView.as_view(), name="create"),
    path("destinazioni/<int:pk>/modifica/", DestinazioneUpdateView.as_view(), name="edit"),
    path("destinazioni/<int:pk>/elimina/", DestinazioneDeleteView.as_view(), name="delete"),
    path("destinazioni/<int:pk>/", DestinazioneDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-destinazioni/", SyncDestinazioniView.as_view(), name="sync"),
]
