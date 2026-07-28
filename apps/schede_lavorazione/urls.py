from django.urls import path

from apps.schede_lavorazione.views import (
    LookupPezzoApiView,
    SaveRigheApiView,
    SchedaLavorazioneCreateView,
    SchedaLavorazioneDeleteView,
    SchedaLavorazioneDetailView,
    SchedaLavorazioneListView,
    SchedaLavorazionePrintView,
    SchedaLavorazioneUpdateView,
)

app_name = "schede_lavorazione"

urlpatterns = [
    path("schede-lavorazione/", SchedaLavorazioneListView.as_view(), name="list"),
    path("schede-lavorazione/nuova/", SchedaLavorazioneCreateView.as_view(), name="create"),
    path(
        "schede-lavorazione/<int:pk>/modifica/",
        SchedaLavorazioneUpdateView.as_view(),
        name="edit",
    ),
    path("schede-lavorazione/<int:pk>/", SchedaLavorazioneDetailView.as_view(), name="detail"),
    path(
        "schede-lavorazione/<int:pk>/stampa/",
        SchedaLavorazionePrintView.as_view(),
        name="print",
    ),
    path(
        "schede-lavorazione/<int:pk>/elimina/",
        SchedaLavorazioneDeleteView.as_view(),
        name="delete",
    ),
    path(
        "schede-lavorazione/api/pezzo/",
        LookupPezzoApiView.as_view(),
        name="api_lookup_pezzo",
    ),
    path(
        "schede-lavorazione/<int:pk>/api/righe/",
        SaveRigheApiView.as_view(),
        name="api_save_righe",
    ),
]
