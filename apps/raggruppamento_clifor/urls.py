from django.urls import path

from apps.raggruppamento_clifor.views import (
    RaggruppamentoCliforCreateView,
    RaggruppamentoCliforDeleteView,
    RaggruppamentoCliforDetailView,
    RaggruppamentoCliforListView,
    RaggruppamentoCliforUpdateView,
    SyncRaggruppamentoCliforView,
)

app_name = "raggruppamento_clifor"
urlpatterns = [
    path("raggruppamento-clifor/", RaggruppamentoCliforListView.as_view(), name="list"),
    path(
        "raggruppamento-clifor/nuovo/",
        RaggruppamentoCliforCreateView.as_view(),
        name="create",
    ),
    path(
        "raggruppamento-clifor/<path:codice>/modifica/",
        RaggruppamentoCliforUpdateView.as_view(),
        name="edit",
    ),
    path(
        "raggruppamento-clifor/<path:codice>/elimina/",
        RaggruppamentoCliforDeleteView.as_view(),
        name="delete",
    ),
    path(
        "raggruppamento-clifor/<path:codice>/",
        RaggruppamentoCliforDetailView.as_view(),
        name="detail",
    ),
    path(
        "parametri/4d/sync-raggruppamento-clifor/",
        SyncRaggruppamentoCliforView.as_view(),
        name="sync",
    ),
]
