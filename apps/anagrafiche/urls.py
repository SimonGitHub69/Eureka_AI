from django.urls import path

from apps.anagrafiche.cf_views import CfCheckApiView
from apps.anagrafiche.vies_views import ViesCheckApiView
from apps.anagrafiche.views import (
    AgenteCreateView,
    AgenteDeleteView,
    AgenteDetailView,
    AgenteListView,
    AgenteUpdateView,
    ClienteCreateView,
    ClienteDeleteView,
    ClienteDetailView,
    ClienteListView,
    ClientePartitarioView,
    ClienteUpdateView,
    ClienteViesCheckView,
    FornitoreCreateView,
    FornitoreDeleteView,
    FornitoreDetailView,
    FornitoreListView,
    FornitorePartitarioView,
    FornitoreUpdateView,
    FornitoreViesCheckView,
)

app_name = "anagrafiche"

urlpatterns = [
    path("vies/", ViesCheckApiView.as_view(), name="vies_check"),
    path("cf/", CfCheckApiView.as_view(), name="cf_check"),
    path("clienti/", ClienteListView.as_view(), name="clienti_list"),
    path("clienti/nuovo/", ClienteCreateView.as_view(), name="cliente_create"),
    path("clienti/<path:codice>/modifica/", ClienteUpdateView.as_view(), name="cliente_edit"),
    path("clienti/<path:codice>/elimina/", ClienteDeleteView.as_view(), name="cliente_delete"),
    path("clienti/<path:codice>/vies/", ClienteViesCheckView.as_view(), name="cliente_vies"),
    path(
        "clienti/<path:codice>/partitario/",
        ClientePartitarioView.as_view(),
        name="cliente_partitario",
    ),
    path("clienti/<path:codice>/", ClienteDetailView.as_view(), name="cliente_detail"),
    path("fornitori/", FornitoreListView.as_view(), name="fornitori_list"),
    path("fornitori/nuovo/", FornitoreCreateView.as_view(), name="fornitore_create"),
    path("fornitori/<path:codice>/modifica/", FornitoreUpdateView.as_view(), name="fornitore_edit"),
    path("fornitori/<path:codice>/elimina/", FornitoreDeleteView.as_view(), name="fornitore_delete"),
    path("fornitori/<path:codice>/vies/", FornitoreViesCheckView.as_view(), name="fornitore_vies"),
    path(
        "fornitori/<path:codice>/partitario/",
        FornitorePartitarioView.as_view(),
        name="fornitore_partitario",
    ),
    path("fornitori/<path:codice>/", FornitoreDetailView.as_view(), name="fornitore_detail"),
    path("agenti/", AgenteListView.as_view(), name="agenti_list"),
    path("agenti/nuovo/", AgenteCreateView.as_view(), name="agente_create"),
    path("agenti/<path:codice>/modifica/", AgenteUpdateView.as_view(), name="agente_edit"),
    path("agenti/<path:codice>/elimina/", AgenteDeleteView.as_view(), name="agente_delete"),
    path("agenti/<path:codice>/", AgenteDetailView.as_view(), name="agente_detail"),
]
