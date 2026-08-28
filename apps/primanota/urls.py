from django.urls import path

from apps.primanota.views import (
    PrimanotaCreateView,
    PrimanotaDaCausaleView,
    PrimanotaDeleteView,
    PrimanotaDetailView,
    PrimanotaListView,
    PrimanotaPrintListView,
    PrimanotaProssimoNumeroView,
    PrimanotaRigaCreateView,
    PrimanotaRigaDeleteView,
    PrimanotaRigaUpdateView,
    PrimanotaUpdateView,
    SyncPrimanotaView,
)

app_name = "primanota"
urlpatterns = [
    path("primanota/", PrimanotaListView.as_view(), name="list"),
    path("primanota/stampa/", PrimanotaPrintListView.as_view(), name="print_list"),
    path("primanota/nuova/", PrimanotaCreateView.as_view(), name="create"),
    path(
        "primanota/prossimo-numero/",
        PrimanotaProssimoNumeroView.as_view(),
        name="prossimo_numero",
    ),
    path(
        "primanota/da-causale/",
        PrimanotaDaCausaleView.as_view(),
        name="da_causale",
    ),
    path("primanota/<int:pk>/modifica/", PrimanotaUpdateView.as_view(), name="edit"),
    path("primanota/<int:pk>/elimina/", PrimanotaDeleteView.as_view(), name="delete"),
    path(
        "primanota/<int:pk>/righe/nuova/",
        PrimanotaRigaCreateView.as_view(),
        name="riga_create",
    ),
    path(
        "primanota/<int:pk>/righe/<int:riga_pk>/modifica/",
        PrimanotaRigaUpdateView.as_view(),
        name="riga_edit",
    ),
    path(
        "primanota/<int:pk>/righe/<int:riga_pk>/elimina/",
        PrimanotaRigaDeleteView.as_view(),
        name="riga_delete",
    ),
    path("primanota/<int:pk>/", PrimanotaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-primanota/", SyncPrimanotaView.as_view(), name="sync"),
]  # righe dettaglio: riga_create, riga_edit, riga_delete
