from django.urls import path

from apps.fatture.views import (
    AnalisiFatturatoView,
    ClassificaClientiView,
    FatturaDetailView,
    FatturaElettronicaXmlView,
    FatturaListView,
    FatturatoRegioniView,
    SyncFattureView,
)

app_name = "fatture"

urlpatterns = [
    path("fatture/", FatturaListView.as_view(), name="list"),
    path("fatture/analisi/", AnalisiFatturatoView.as_view(), name="analisi"),
    path(
        "fatture/analisi/regioni/",
        FatturatoRegioniView.as_view(),
        name="analisi_regioni",
    ),
    path(
        "fatture/analisi/classifica/",
        ClassificaClientiView.as_view(),
        name="classifica",
    ),
    path("fatture/<int:id_testa>/", FatturaDetailView.as_view(), name="detail"),
    path(
        "fatture/<int:id_testa>/xml-sdi/",
        FatturaElettronicaXmlView.as_view(),
        name="xml_sdi",
    ),
    path("parametri/4d/sync-fatture/", SyncFattureView.as_view(), name="sync"),
]
