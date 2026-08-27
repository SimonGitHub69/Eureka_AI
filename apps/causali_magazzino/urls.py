from django.urls import path

from apps.causali_magazzino.views import (
    CausaleMagazzinoCreateView,
    CausaleMagazzinoDeleteView,
    CausaleMagazzinoDetailView,
    CausaleMagazzinoListView,
    CausaleMagazzinoExportListView,
    CausaleMagazzinoPrintListView,
    CausaleMagazzinoUpdateView,
    SyncCausaliMagazzinoView,
)

app_name = "causali_magazzino"

urlpatterns = [
    path("causali-magazzino/", CausaleMagazzinoListView.as_view(), name="list"),
    path("causali-magazzino/stampa/", CausaleMagazzinoPrintListView.as_view(), name="print_list"),
    path("causali-magazzino/export/", CausaleMagazzinoExportListView.as_view(), name="export_list"),
    path("causali-magazzino/nuova/", CausaleMagazzinoCreateView.as_view(), name="create"),
    path(
        "causali-magazzino/<path:codice>/modifica/",
        CausaleMagazzinoUpdateView.as_view(),
        name="edit",
    ),
    path(
        "causali-magazzino/<path:codice>/elimina/",
        CausaleMagazzinoDeleteView.as_view(),
        name="delete",
    ),
    path(
        "causali-magazzino/<path:codice>/",
        CausaleMagazzinoDetailView.as_view(),
        name="detail",
    ),
    path(
        "parametri/4d/sync-causali-magazzino/",
        SyncCausaliMagazzinoView.as_view(),
        name="sync",
    ),
]
