from django.urls import path

from apps.set_articoli.views import (
    SetArticoloCreateView,
    SetArticoloDeleteView,
    SetArticoloDetailView,
    SetArticoloExportListView,
    SetArticoloListView,
    SetArticoloPrintListView,
    SetArticoloRigaCreateView,
    SetArticoloRigaDeleteView,
    SetArticoloRigaUpdateView,
    SetArticoloUpdateView,
    SyncSetArticoliView,
)

app_name = "set_articoli"

urlpatterns = [
    path("set-articoli/", SetArticoloListView.as_view(), name="list"),
    path("set-articoli/stampa/", SetArticoloPrintListView.as_view(), name="print_list"),
    path("set-articoli/export/", SetArticoloExportListView.as_view(), name="export_list"),
    path("set-articoli/nuova/", SetArticoloCreateView.as_view(), name="create"),
    path("set-articoli/<int:pk>/modifica/", SetArticoloUpdateView.as_view(), name="edit"),
    path("set-articoli/<int:pk>/elimina/", SetArticoloDeleteView.as_view(), name="delete"),
    path("set-articoli/<int:pk>/righe/nuova/", SetArticoloRigaCreateView.as_view(), name="riga_create"),
    path(
        "set-articoli/<int:pk>/righe/<int:riga_id>/modifica/",
        SetArticoloRigaUpdateView.as_view(),
        name="riga_edit",
    ),
    path(
        "set-articoli/<int:pk>/righe/<int:riga_id>/elimina/",
        SetArticoloRigaDeleteView.as_view(),
        name="riga_delete",
    ),
    path("set-articoli/<int:pk>/", SetArticoloDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-set-articoli/", SyncSetArticoliView.as_view(), name="sync"),
]
