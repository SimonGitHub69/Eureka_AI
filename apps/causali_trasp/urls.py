from django.urls import path

from apps.causali_trasp.views import (
    CausaleTrasportoCreateView,
    CausaleTrasportoDeleteView,
    CausaleTrasportoDetailView,
    CausaleTrasportoListView,
    CausaleTrasportoExportListView,
    CausaleTrasportoPrintListView,
    CausaleTrasportoUpdateView,
    SyncCausaliTraspView,
)

app_name = "causali_trasp"

urlpatterns = [
    path("causali-trasp/", CausaleTrasportoListView.as_view(), name="list"),
    path("causali-trasp/stampa/", CausaleTrasportoPrintListView.as_view(), name="print_list"),
    path("causali-trasp/export/", CausaleTrasportoExportListView.as_view(), name="export_list"),
    path("causali-trasp/nuova/", CausaleTrasportoCreateView.as_view(), name="create"),
    path(
        "causali-trasp/<path:codice>/modifica/",
        CausaleTrasportoUpdateView.as_view(),
        name="edit",
    ),
    path(
        "causali-trasp/<path:codice>/elimina/",
        CausaleTrasportoDeleteView.as_view(),
        name="delete",
    ),
    path("causali-trasp/<path:codice>/", CausaleTrasportoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-causali-trasp/", SyncCausaliTraspView.as_view(), name="sync"),
]
