from django.urls import path

from apps.movimenti.views import (
    MovimentoDetailView,
    MovimentoExportListView,
    MovimentoListView,
    MovimentoPrintListView,
    StatisticheMagazzinoArticoliSetView,
    StatisticheMagazzinoExportView,
    StatisticheMagazzinoPrintView,
    StatisticheMagazzinoView,
    SyncMovimentiView,
)

app_name = "movimenti"

urlpatterns = [
    path("movimenti/", MovimentoListView.as_view(), name="list"),
    path("movimenti/stampa/", MovimentoPrintListView.as_view(), name="print_list"),
    path("movimenti/export/", MovimentoExportListView.as_view(), name="export_list"),
    path(
        "elaborazioni/statistiche-magazzino/",
        StatisticheMagazzinoView.as_view(),
        name="statistiche",
    ),
    path(
        "elaborazioni/statistiche-magazzino/articoli-set/",
        StatisticheMagazzinoArticoliSetView.as_view(),
        name="statistiche_articoli_set",
    ),
    path(
        "elaborazioni/statistiche-magazzino/stampa/",
        StatisticheMagazzinoPrintView.as_view(),
        name="statistiche_print",
    ),
    path(
        "elaborazioni/statistiche-magazzino/export/",
        StatisticheMagazzinoExportView.as_view(),
        name="statistiche_export",
    ),
    path("movimenti/<int:pk>/", MovimentoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-movimenti/", SyncMovimentiView.as_view(), name="sync"),
]
