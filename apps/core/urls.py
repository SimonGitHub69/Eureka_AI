from django.urls import path

from apps.core.views import (
    ComandiVocaliListView,
    ComandoVocaleDeleteView,
    ComandoVocaleDuplicateView,
    ComandoVocaleFormView,
    Parametri4DView,
    SyncAnagraficheView,
)

app_name = "core"

urlpatterns = [
    path("parametri/4d/", Parametri4DView.as_view(), name="parametri_4d"),
    path(
        "parametri/4d/sync-anagrafiche/",
        SyncAnagraficheView.as_view(),
        name="sync_anagrafiche",
    ),
    path("parametri/comandi-vocali/", ComandiVocaliListView.as_view(), name="comandi_vocali_list"),
    path("parametri/comandi-vocali/nuovo/", ComandoVocaleFormView.as_view(), name="comando_vocale_create"),
    path(
        "parametri/comandi-vocali/<int:pk>/modifica/",
        ComandoVocaleFormView.as_view(),
        name="comando_vocale_edit",
    ),
    path(
        "parametri/comandi-vocali/<int:pk>/elimina/",
        ComandoVocaleDeleteView.as_view(),
        name="comando_vocale_delete",
    ),
    path(
        "parametri/comandi-vocali/<int:pk>/duplica/",
        ComandoVocaleDuplicateView.as_view(),
        name="comando_vocale_duplicate",
    ),
]
