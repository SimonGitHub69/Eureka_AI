from django.urls import path

from apps.registri_iva.views import (
    RegistroIvaCreateView,
    RegistroIvaDeleteView,
    RegistroIvaDetailView,
    RegistroIvaExportListView,
    RegistroIvaListView,
    RegistroIvaUpdateView,
    SyncRegistriIvaView,
    registro_iva_print_dispatch,
)

app_name = "registri_iva"

urlpatterns = [
    path("registri-iva/", RegistroIvaListView.as_view(), name="list"),
    path("registri-iva/stampa/", registro_iva_print_dispatch, name="print_list"),
    path("registri-iva/export/", RegistroIvaExportListView.as_view(), name="export_list"),
    path("registri-iva/nuovo/", RegistroIvaCreateView.as_view(), name="create"),
    path("registri-iva/<path:codice>/modifica/", RegistroIvaUpdateView.as_view(), name="edit"),
    path("registri-iva/<path:codice>/elimina/", RegistroIvaDeleteView.as_view(), name="delete"),
    path("registri-iva/<path:codice>/", RegistroIvaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-registri-iva/", SyncRegistriIvaView.as_view(), name="sync"),
]
