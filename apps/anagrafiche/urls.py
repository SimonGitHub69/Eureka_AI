from django.urls import path

from apps.anagrafiche.views import (
    AgenteDetailView,
    AgenteListView,
    ClienteDetailView,
    ClienteListView,
    FornitoreDetailView,
    FornitoreListView,
)

app_name = "anagrafiche"

urlpatterns = [
    path("clienti/", ClienteListView.as_view(), name="clienti_list"),
    path("clienti/<path:codice>/", ClienteDetailView.as_view(), name="cliente_detail"),
    path("fornitori/", FornitoreListView.as_view(), name="fornitori_list"),
    path("fornitori/<path:codice>/", FornitoreDetailView.as_view(), name="fornitore_detail"),
    path("agenti/", AgenteListView.as_view(), name="agenti_list"),
    path("agenti/<path:codice>/", AgenteDetailView.as_view(), name="agente_detail"),
]
