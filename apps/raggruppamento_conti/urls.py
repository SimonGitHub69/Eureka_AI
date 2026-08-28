from django.urls import path

from apps.raggruppamento_conti.views import (
    RaggruppamentoContoCreateView,
    RaggruppamentoContoDeleteView,
    RaggruppamentoContoDetailView,
    RaggruppamentoContoListView,
    RaggruppamentoContoPrintListView,
    RaggruppamentoContoUpdateView,
    SyncRaggruppamentoContiView,
)

app_name = "raggruppamento_conti"
urlpatterns = [
    path("raggruppamento-conti/", RaggruppamentoContoListView.as_view(), name="list"),
    path(
        "raggruppamento-conti/stampa/",
        RaggruppamentoContoPrintListView.as_view(),
        name="print_list",
    ),
    path(
        "raggruppamento-conti/nuovo/",
        RaggruppamentoContoCreateView.as_view(),
        name="create",
    ),
    path(
        "raggruppamento-conti/<path:codice>/modifica/",
        RaggruppamentoContoUpdateView.as_view(),
        name="edit",
    ),
    path(
        "raggruppamento-conti/<path:codice>/elimina/",
        RaggruppamentoContoDeleteView.as_view(),
        name="delete",
    ),
    path(
        "raggruppamento-conti/<path:codice>/",
        RaggruppamentoContoDetailView.as_view(),
        name="detail",
    ),
    path(
        "parametri/4d/sync-raggruppamento-conti/",
        SyncRaggruppamentoContiView.as_view(),
        name="sync",
    ),
]
