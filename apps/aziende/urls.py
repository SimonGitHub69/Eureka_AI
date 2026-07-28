from django.urls import path

from apps.aziende.views import (
    AziendaDetailView,
    AziendaDatiUpdateView,
    AziendaListView,
    SyncAziendeView,
)

app_name = "aziende"

urlpatterns = [
    path("aziende/", AziendaListView.as_view(), name="list"),
    path("aziende/<int:pk>/", AziendaDetailView.as_view(), name="detail"),
    path("aziende/<int:pk>/modifica/", AziendaDatiUpdateView.as_view(), name="edit"),
    path("parametri/4d/sync-aziende/", SyncAziendeView.as_view(), name="sync"),
]
