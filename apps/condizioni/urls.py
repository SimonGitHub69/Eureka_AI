from django.urls import path

from apps.condizioni.views import (
    CondizioneDetailView,
    CondizioneListView,
    SyncCondizioniView,
)

app_name = "condizioni"

urlpatterns = [
    path("condizioni/", CondizioneListView.as_view(), name="list"),
    path("condizioni/<path:codice>/", CondizioneDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-condizioni/", SyncCondizioniView.as_view(), name="sync"),
]
