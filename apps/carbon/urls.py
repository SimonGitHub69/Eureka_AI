from django.urls import path

from apps.carbon.views import (
    CarbonHubView,
    LavorazionePartitaDetailView,
    LavorazionePartitaListView,
    RepartoDetailView,
    RepartoExportListView,
    RepartoListView,
    RepartoPrintListView,
    StampoSerialeDetailView,
    StampoSerialeListView,
    SyncCarbonView,
)
from apps.core.mixins import require_extra
from apps.carbon import seriali_views

app_name = "carbon"

_carbon = require_extra("CARBON")

urlpatterns = [
    path("carbon/", CarbonHubView.as_view(), name="hub"),
    path("carbon/seriali/", _carbon(seriali_views.seriali_dashboard), name="seriali_dashboard"),
    path("carbon/seriali/api/kpi/", _carbon(seriali_views.api_kpi), name="seriali_api_kpi"),
    path("carbon/seriali/api/seriali-lista/", _carbon(seriali_views.api_seriali_lista), name="seriali_api_lista"),
    path("carbon/seriali/api/seriali-stato/", _carbon(seriali_views.api_seriali_stato), name="seriali_api_stato"),
    path("carbon/seriali/api/seriali-reparto/", _carbon(seriali_views.api_seriali_reparto), name="seriali_api_reparto"),
    path(
        "carbon/seriali/api/lavorazioni-giorno/",
        _carbon(seriali_views.api_lavorazioni_giorno),
        name="seriali_api_lavorazioni_giorno",
    ),
    path(
        "carbon/seriali/api/lavorazioni-extra/",
        _carbon(seriali_views.api_lavorazioni_extra),
        name="seriali_api_lavorazioni_extra",
    ),
    path(
        "carbon/seriali/api/stampi-opzioni/",
        _carbon(seriali_views.api_stampi_opzioni),
        name="seriali_api_stampi_opzioni",
    ),
    path(
        "carbon/seriali/api/stampi-seriali/",
        _carbon(seriali_views.api_stampi_seriali),
        name="seriali_api_stampi_seriali",
    ),
    path(
        "carbon/seriali/api/catalogo-extra/",
        _carbon(seriali_views.api_catalogo_extra),
        name="seriali_api_catalogo_extra",
    ),
    path(
        "carbon/seriali/api/codartser-suggest/",
        _carbon(seriali_views.api_codartser_suggest),
        name="seriali_api_codartser_suggest",
    ),
    path(
        "carbon/seriali/api/stampi-dettaglio/",
        _carbon(seriali_views.api_stampi_dettaglio),
        name="seriali_api_stampi_dettaglio",
    ),
    path("carbon/reparti/", RepartoListView.as_view(), name="reparti_list"),
    path("carbon/reparti/stampa/", RepartoPrintListView.as_view(), name="reparti_print_list"),
    path("carbon/reparti/export/", RepartoExportListView.as_view(), name="reparti_export_list"),
    path("carbon/reparti/<str:pk>/", RepartoDetailView.as_view(), name="reparti_detail"),
    path(
        "carbon/lavorazioni-partite/",
        LavorazionePartitaListView.as_view(),
        name="lavorazioni_list",
    ),
    path(
        "carbon/lavorazioni-partite/<int:pk>/",
        LavorazionePartitaDetailView.as_view(),
        name="lavorazioni_detail",
    ),
    path(
        "carbon/stampi-seriali/",
        StampoSerialeListView.as_view(),
        name="stampi_seriali_list",
    ),
    path(
        "carbon/stampi-seriali/<int:pk>/",
        StampoSerialeDetailView.as_view(),
        name="stampi_seriali_detail",
    ),
    path("parametri/4d/sync-carbon/", SyncCarbonView.as_view(), name="sync"),
]
