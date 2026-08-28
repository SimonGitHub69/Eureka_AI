from django.urls import path

from apps.distinte_base.views import (
    DistintaBaseCreateView,
    DistintaBaseDeleteView,
    DistintaBaseDetailView,
    DistintaBaseListView,
    DistintaBasePrintListView,
    DistintaBaseUpdateView,
    SyncDistinteBaseView,
)

app_name = "distinte_base"

urlpatterns = [
    path("distinte-base/", DistintaBaseListView.as_view(), name="list"),
    path("distinte-base/stampa/", DistintaBasePrintListView.as_view(), name="print_list"),
    path("distinte-base/nuova/", DistintaBaseCreateView.as_view(), name="create"),
    path("distinte-base/<int:pk>/modifica/", DistintaBaseUpdateView.as_view(), name="edit"),
    path("distinte-base/<int:pk>/elimina/", DistintaBaseDeleteView.as_view(), name="delete"),
    path("distinte-base/<int:pk>/", DistintaBaseDetailView.as_view(), name="detail"),
    path(
        "parametri/4d/sync-distinte-base/",
        SyncDistinteBaseView.as_view(),
        name="sync",
    ),
]
