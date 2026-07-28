from django.urls import path

from apps.lavorazioni_extra.views import (
    LavorazioneExtraDetailView,
    LavorazioneExtraListView,
    SyncLavorazioniExtraView,
)

app_name = "lavorazioni_extra"

urlpatterns = [
    path(
        "carbon/lavorazioni-extra/",
        LavorazioneExtraListView.as_view(),
        name="list",
    ),
    path(
        "carbon/lavorazioni-extra/<int:pk>/",
        LavorazioneExtraDetailView.as_view(),
        name="detail",
    ),
    path(
        "parametri/4d/sync-lavorazioni-extra/",
        SyncLavorazioniExtraView.as_view(),
        name="sync",
    ),
]
