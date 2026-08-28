from django.urls import path

from apps.movimenti.views import (
    MovimentoDetailView,
    MovimentoExportListView,
    MovimentoListView,
    MovimentoPrintListView,
    SyncMovimentiView,
)

app_name = "movimenti"

urlpatterns = [
    path("movimenti/", MovimentoListView.as_view(), name="list"),
    path("movimenti/stampa/", MovimentoPrintListView.as_view(), name="print_list"),
    path("movimenti/export/", MovimentoExportListView.as_view(), name="export_list"),
    path("movimenti/<int:pk>/", MovimentoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-movimenti/", SyncMovimentiView.as_view(), name="sync"),
]
