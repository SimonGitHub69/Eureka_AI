from django.urls import path

from apps.geografia.views import (
    CittaCreateView,
    CittaDeleteView,
    CittaDetailView,
    CittaListView,
    CittaExportListView,
    CittaPrintListView,
    CittaUpdateView,
    ProvinciaCreateView,
    ProvinciaDeleteView,
    ProvinciaDetailView,
    ProvinciaListView,
    ProvinciaExportListView,
    ProvinciaPrintListView,
    ProvinciaUpdateView,
    RegioneCreateView,
    RegioneDeleteView,
    RegioneDetailView,
    RegioneListView,
    RegioneExportListView,
    RegionePrintListView,
    RegioneUpdateView,
)

app_name = "geografia"

urlpatterns = [
    path("regioni/", RegioneListView.as_view(), name="regioni_list"),
    path("regioni/stampa/", RegionePrintListView.as_view(), name="regioni_print_list"),
    path("regioni/export/", RegioneExportListView.as_view(), name="regioni_export_list"),
    path("regioni/nuova/", RegioneCreateView.as_view(), name="regioni_create"),
    path("regioni/<str:codice>/modifica/", RegioneUpdateView.as_view(), name="regione_edit"),
    path("regioni/<str:codice>/elimina/", RegioneDeleteView.as_view(), name="regione_delete"),
    path("regioni/<str:codice>/", RegioneDetailView.as_view(), name="regione_detail"),
    path("province/", ProvinciaListView.as_view(), name="province_list"),
    path("province/stampa/", ProvinciaPrintListView.as_view(), name="province_print_list"),
    path("province/export/", ProvinciaExportListView.as_view(), name="province_export_list"),
    path("province/nuova/", ProvinciaCreateView.as_view(), name="province_create"),
    path("province/<str:sigla>/modifica/", ProvinciaUpdateView.as_view(), name="provincia_edit"),
    path("province/<str:sigla>/elimina/", ProvinciaDeleteView.as_view(), name="provincia_delete"),
    path("province/<str:sigla>/", ProvinciaDetailView.as_view(), name="provincia_detail"),
    path("citta/", CittaListView.as_view(), name="citta_list"),
    path("citta/stampa/", CittaPrintListView.as_view(), name="citta_print_list"),
    path("citta/export/", CittaExportListView.as_view(), name="citta_export_list"),
    path("citta/nuova/", CittaCreateView.as_view(), name="citta_create"),
    path(
        "citta/<str:codice_istat>/modifica/",
        CittaUpdateView.as_view(),
        name="citta_edit",
    ),
    path(
        "citta/<str:codice_istat>/elimina/",
        CittaDeleteView.as_view(),
        name="citta_delete",
    ),
    path("citta/<str:codice_istat>/", CittaDetailView.as_view(), name="citta_detail"),
]
