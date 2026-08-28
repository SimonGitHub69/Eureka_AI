from django.urls import path

from apps.aziende.views import (
    AziendaCreateView,
    AziendaDeleteView,
    AziendaDetailView,
    AziendaDatiUpdateView,
    AziendaListView,
    AziendaExportListView,
    AziendaPrintListView,
    AziendaUpdateView,
    SyncAziendeView,
)

app_name = "aziende"

urlpatterns = [
    path("aziende/", AziendaListView.as_view(), name="list"),
    path("aziende/stampa/", AziendaPrintListView.as_view(), name="print_list"),
    path("aziende/export/", AziendaExportListView.as_view(), name="export_list"),
    path("aziende/nuova/", AziendaCreateView.as_view(), name="azienda_create"),
    path(
        "aziende/<int:pk>/modifica-anagrafica/",
        AziendaUpdateView.as_view(),
        name="azienda_update",
    ),
    path("aziende/<int:pk>/elimina/", AziendaDeleteView.as_view(), name="azienda_delete"),
    path("aziende/<int:pk>/modifica/", AziendaDatiUpdateView.as_view(), name="edit"),
    path("aziende/<int:pk>/", AziendaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-aziende/", SyncAziendeView.as_view(), name="sync"),
]
