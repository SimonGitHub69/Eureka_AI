from django.urls import path

from apps.distinte_base.views import (
    DistintaBaseDetailView,
    DistintaBaseListView,
    SyncDistinteBaseView,
)

app_name = "distinte_base"

urlpatterns = [
    path("distinte-base/", DistintaBaseListView.as_view(), name="list"),
    path("distinte-base/<int:pk>/", DistintaBaseDetailView.as_view(), name="detail"),
    path(
        "parametri/4d/sync-distinte-base/",
        SyncDistinteBaseView.as_view(),
        name="sync",
    ),
]
