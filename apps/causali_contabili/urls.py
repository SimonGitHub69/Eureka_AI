from django.urls import path

from apps.causali_contabili.views import (
    CausaleContabileCreateView,
    CausaleContabileDeleteView,
    CausaleContabileDetailView,
    CausaleContabileListView,
    CausaleContabilePrintListView,
    CausaleContabileUpdateView,
    SyncCausaliContabiliView,
)

app_name = "causali_contabili"
urlpatterns = [
    path("causali-contabili/", CausaleContabileListView.as_view(), name="list"),
    path("causali-contabili/stampa/", CausaleContabilePrintListView.as_view(), name="print_list"),
    path("causali-contabili/nuova/", CausaleContabileCreateView.as_view(), name="create"),
    path(
        "causali-contabili/<path:codice>/modifica/",
        CausaleContabileUpdateView.as_view(),
        name="edit",
    ),
    path(
        "causali-contabili/<path:codice>/elimina/",
        CausaleContabileDeleteView.as_view(),
        name="delete",
    ),
    path(
        "causali-contabili/<path:codice>/",
        CausaleContabileDetailView.as_view(),
        name="detail",
    ),
    path(
        "parametri/4d/sync-causali-contabili/",
        SyncCausaliContabiliView.as_view(),
        name="sync",
    ),
]
