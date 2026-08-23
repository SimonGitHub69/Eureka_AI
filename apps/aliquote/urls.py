from django.urls import path

from apps.aliquote.views import (
    AliquotaCreateView,
    AliquotaDeleteView,
    AliquotaDetailView,
    AliquotaDuplicateView,
    AliquotaListView,
    AliquotaExportListView,
    AliquotaPrintListView,
    AliquotaUpdateView,
    SyncAliquoteView,
)

app_name = "aliquote"

urlpatterns = [
    path("aliquote/", AliquotaListView.as_view(), name="list"),
    path("aliquote/stampa/", AliquotaPrintListView.as_view(), name="print_list"),
    path("aliquote/export/", AliquotaExportListView.as_view(), name="export_list"),
    path("aliquote/nuova/", AliquotaCreateView.as_view(), name="create"),
    path("aliquote/<path:codice>/modifica/", AliquotaUpdateView.as_view(), name="edit"),
    path("aliquote/<path:codice>/duplica/", AliquotaDuplicateView.as_view(), name="duplicate"),
    path("aliquote/<path:codice>/elimina/", AliquotaDeleteView.as_view(), name="delete"),
    path("aliquote/<path:codice>/", AliquotaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-aliquote/", SyncAliquoteView.as_view(), name="sync"),
]
