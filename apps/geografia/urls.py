from django.urls import path

from apps.geografia.views import (
    CittaDetailView,
    CittaListView,
    ProvinciaDetailView,
    ProvinciaListView,
    RegioneDetailView,
    RegioneListView,
)

app_name = "geografia"

urlpatterns = [
    path("regioni/", RegioneListView.as_view(), name="regioni_list"),
    path("regioni/<str:codice>/", RegioneDetailView.as_view(), name="regione_detail"),
    path("province/", ProvinciaListView.as_view(), name="province_list"),
    path("province/<str:sigla>/", ProvinciaDetailView.as_view(), name="provincia_detail"),
    path("citta/", CittaListView.as_view(), name="citta_list"),
    path("citta/<str:codice_istat>/", CittaDetailView.as_view(), name="citta_detail"),
]
