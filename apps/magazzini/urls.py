from django.urls import path

from apps.magazzini.views import (
    MagazzinoDetailView,
    MagazzinoListView,
    SyncMagazziniView,
)

app_name = "magazzini"

urlpatterns = [
    path("magazzini/", MagazzinoListView.as_view(), name="list"),
    path("magazzini/<path:codice>/", MagazzinoDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-magazzini/", SyncMagazziniView.as_view(), name="sync"),
]
