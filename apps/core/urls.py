from django.urls import path

from apps.articoli.views import ArticoloInventarioPrintView
from apps.core.stampe import StampeHubView
from apps.core.views import (
    AiAssistantView,
    AiExportDownloadView,
    ComandiVocaliListView,
    ComandoVocaleDeleteView,
    ComandoVocaleDuplicateView,
    ComandoVocaleFormView,
    ConfigurazionePCBindView,
    ConfigurazionePCCreateView,
    ConfigurazionePCDeleteView,
    ConfigurazionePCListView,
    ConfigurazionePCUpdateView,
    HelperOpenApiView,
    HelperShareApiView,
    OfflineHubView,
    OfflineSyncApiView,
    Parametri4DView,
    ParametriContabiliView,
    ParametriMailView,
    ParametriProgrammaView,
    ServiceWorkerView,
    Sync4DCancelView,
    Sync4DClearView,
    Sync4DStartView,
    Sync4DStatusView,
    SyncAnagraficheView,
)

app_name = "core"

urlpatterns = [
    path("stampe/", StampeHubView.as_view(), name="stampe"),
    path(
        "stampe/inventario/",
        ArticoloInventarioPrintView.as_view(),
        name="stampe_inventario",
    ),
    path(
        "parametri/programma/",
        ParametriProgrammaView.as_view(),
        name="parametri_programma",
    ),
    path(
        "parametri/contabili/",
        ParametriContabiliView.as_view(),
        name="parametri_contabili",
    ),
    path(
        "parametri/mail/",
        ParametriMailView.as_view(),
        name="parametri_mail",
    ),
    path(
        "parametri/pc/",
        ConfigurazionePCListView.as_view(),
        name="configurazione_pc_list",
    ),
    path(
        "parametri/pc/nuovo/",
        ConfigurazionePCCreateView.as_view(),
        name="configurazione_pc_create",
    ),
    path(
        "parametri/pc/<int:pk>/modifica/",
        ConfigurazionePCUpdateView.as_view(),
        name="configurazione_pc_update",
    ),
    path(
        "parametri/pc/<int:pk>/usa/",
        ConfigurazionePCBindView.as_view(),
        name="configurazione_pc_bind",
    ),
    path(
        "parametri/pc/<int:pk>/elimina/",
        ConfigurazionePCDeleteView.as_view(),
        name="configurazione_pc_delete",
    ),
    path("parametri/4d/", Parametri4DView.as_view(), name="parametri_4d"),
    path("parametri/4d/sync-all/start/", Sync4DStartView.as_view(), name="sync_4d_start"),
    path(
        "parametri/4d/sync-all/status/<str:task_id>/",
        Sync4DStatusView.as_view(),
        name="sync_4d_status",
    ),
    path("parametri/4d/sync-all/clear/", Sync4DClearView.as_view(), name="sync_4d_clear"),
    path("parametri/4d/sync-all/cancel/", Sync4DCancelView.as_view(), name="sync_4d_cancel"),
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
    path("offline/", OfflineHubView.as_view(), name="offline"),
    path("api/offline/sync/", OfflineSyncApiView.as_view(), name="offline_sync"),
    path("api/helper/open/", HelperOpenApiView.as_view(), name="helper_open"),
    path("api/helper/share/", HelperShareApiView.as_view(), name="helper_share"),
    path("api/ai/ask/", AiAssistantView.as_view(), name="ai_ask"),
    path(
        "api/ai/export/<str:token>/",
        AiExportDownloadView.as_view(),
        name="ai_export_download",
    ),
    path("sw.js", ServiceWorkerView.as_view(), name="service_worker"),
]
