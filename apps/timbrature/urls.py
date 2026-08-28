from django.urls import path

from apps.timbrature.views import (
    SyncTimbratureView,
    TimbraturaDetailView,
    TimbraturaListView,
    TimbraturaExportListView,
    TimbraturaPrintListView,
)

app_name = "timbrature"

urlpatterns = [
    path("timbrature/", TimbraturaListView.as_view(), name="list"),
    path("timbrature/stampa/", TimbraturaPrintListView.as_view(), name="print_list"),
    path("timbrature/export/", TimbraturaExportListView.as_view(), name="export_list"),
    path("timbrature/<path:pk>/", TimbraturaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-timbrature/", SyncTimbratureView.as_view(), name="sync"),
]
