from django.urls import path

from apps.articoli.views import (
    ArticoloCreateView,
    ArticoloDeleteView,
    ArticoloDetailView,
    ArticoloListView,
    ArticoloMovimentiPrintView,
    ArticoloPrintListView,
    ArticoloUpdateView,
    CodiceLookupView,
)

app_name = "articoli"

urlpatterns = [
    path("articoli/", ArticoloListView.as_view(), name="list"),
    path("articoli/stampa/", ArticoloPrintListView.as_view(), name="print_list"),
    path("articoli/nuova/", ArticoloCreateView.as_view(), name="create"),
    path("articoli/lookup-codice/", CodiceLookupView.as_view(), name="lookup_codice"),
    path("articoli/<path:codice>/modifica/", ArticoloUpdateView.as_view(), name="edit"),
    path("articoli/<path:codice>/elimina/", ArticoloDeleteView.as_view(), name="delete"),
    path(
        "articoli/<path:codice>/movimenti/stampa/",
        ArticoloMovimentiPrintView.as_view(),
        name="movimenti_print",
    ),
    path("articoli/<path:codice>/", ArticoloDetailView.as_view(), name="detail"),
]
