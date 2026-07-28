from django.urls import path

from apps.stampi.views import (
    StampoDetailView,
    StampoListView,
    StampoUpdateView,
    SyncStampiView,
)

app_name = "stampi"

urlpatterns = [
    path("stampi/", StampoListView.as_view(), name="list"),
    path("stampi/<int:pk>/", StampoDetailView.as_view(), name="detail"),
    path("stampi/<int:pk>/modifica/", StampoUpdateView.as_view(), name="edit"),
    path("parametri/4d/sync-stampi/", SyncStampiView.as_view(), name="sync"),
]
