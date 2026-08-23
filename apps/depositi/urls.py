from django.urls import path

from apps.depositi.views import DepositoDetailView, DepositoListView, SyncDepositiView

app_name = "depositi"

urlpatterns = [
    path("depositi/", DepositoListView.as_view(), name="list"),
    path("depositi/<path:codice>/", DepositoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-depositi/", SyncDepositiView.as_view(), name="sync"),
]
