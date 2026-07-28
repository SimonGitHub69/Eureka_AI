from django.urls import path

from apps.operatori.views import (
    OperatoreDetailView,
    OperatoreListView,
    SyncOperatoriView,
)

app_name = "operatori"

urlpatterns = [
    path("operatori/", OperatoreListView.as_view(), name="list"),
    path("operatori/<path:codice>/", OperatoreDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-operatori/", SyncOperatoriView.as_view(), name="sync"),
]
