from django.urls import path

from apps.valute.views import (
    SyncValuteView,
    ValutaCambioCreateView,
    ValutaCambioDeleteView,
    ValutaCambioUpdateView,
    ValutaCreateView,
    ValutaDeleteView,
    ValutaDetailView,
    ValutaExportListView,
    ValutaListView,
    ValutaPrintListView,
    ValutaUpdateView,
)

app_name = "valute"

urlpatterns = [
    path("valute/", ValutaListView.as_view(), name="list"),
    path("valute/stampa/", ValutaPrintListView.as_view(), name="print_list"),
    path("valute/export/", ValutaExportListView.as_view(), name="export_list"),
    path("valute/nuova/", ValutaCreateView.as_view(), name="create"),
    path("valute/<path:codice>/cambi/nuovo/", ValutaCambioCreateView.as_view(), name="cambio_create"),
    path(
        "valute/<path:codice>/cambi/<int:pk>/modifica/",
        ValutaCambioUpdateView.as_view(),
        name="cambio_edit",
    ),
    path(
        "valute/<path:codice>/cambi/<int:pk>/elimina/",
        ValutaCambioDeleteView.as_view(),
        name="cambio_delete",
    ),
    path("valute/<path:codice>/modifica/", ValutaUpdateView.as_view(), name="edit"),
    path("valute/<path:codice>/elimina/", ValutaDeleteView.as_view(), name="delete"),
    path("valute/<path:codice>/", ValutaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-valute/", SyncValuteView.as_view(), name="sync"),
]
