from django.urls import path

from apps.operatori.views import (
    OperatoreCreateView,
    OperatoreDeleteView,
    OperatoreDetailView,
    OperatoreListView,
    OperatoreExportListView,
    OperatorePrintListView,
    OperatoreQrPrintView,
    OperatoreUpdateView,
    SyncOperatoriView,
)

app_name = "operatori"

urlpatterns = [
    path("operatori/", OperatoreListView.as_view(), name="list"),
    path("operatori/stampa/", OperatorePrintListView.as_view(), name="print_list"),
    path("operatori/export/", OperatoreExportListView.as_view(), name="export_list"),
    path("operatori/stampa-qr/", OperatoreQrPrintView.as_view(), name="qr_print"),
    path("operatori/nuova/", OperatoreCreateView.as_view(), name="create"),
    path("operatori/<path:codice>/modifica/", OperatoreUpdateView.as_view(), name="edit"),
    path("operatori/<path:codice>/elimina/", OperatoreDeleteView.as_view(), name="delete"),
    path("operatori/<path:codice>/", OperatoreDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-operatori/", SyncOperatoriView.as_view(), name="sync"),
]
