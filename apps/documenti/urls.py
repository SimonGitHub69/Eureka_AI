from django.urls import path

from apps.documenti.parametri_views import (
    ContatoriDocumentoCreateView,
    ContatoriDocumentoDeleteView,
    ContatoriDocumentoDetailView,
    ContatoriDocumentoDuplicateView,
    ContatoriDocumentoListView,
    ContatoriDocumentoUpdateView,
    ParametriDocumentoColonneView,
    ParametriDocumentoCreateView,
    ParametriDocumentoDeleteView,
    ParametriDocumentoDetailView,
    ParametriDocumentoListView,
    ParametriDocumentoUpdateView,
)
from apps.documenti.porto_views import (
    PortoCreateView,
    PortoDeleteView,
    PortoDetailView,
    PortoListView,
    PortoExportListView,
    PortoPrintListView,
    PortoUpdateView,
)
from apps.documenti.views import (
    CalcPesoDocumentoView,
    CalcScadenzeView,
    DocumentoCreateView,
    DocumentoDeleteView,
    DocumentoDetailView,
    DocumentoIndexView,
    DocumentoInviaMailView,
    DocumentoListView,
    DocumentoParametriSpeseView,
    DocumentoPrintView,
    DocumentoUpdateView,
    SyncDocumentiCancelView,
    SyncDocumentiStatusView,
    SyncDocumentiView,
)

app_name = "documenti"

urlpatterns = [
    path("porto/", PortoListView.as_view(), name="porto_list"),
    path("porto/stampa/", PortoPrintListView.as_view(), name="porto_print_list"),
    path("porto/export/", PortoExportListView.as_view(), name="porto_export_list"),
    path("porto/nuovo/", PortoCreateView.as_view(), name="porto_create"),
    path("porto/<int:pk>/modifica/", PortoUpdateView.as_view(), name="porto_edit"),
    path("porto/<int:pk>/elimina/", PortoDeleteView.as_view(), name="porto_delete"),
    path("porto/<int:pk>/", PortoDetailView.as_view(), name="porto_detail"),
    path("parametri-documento/", ParametriDocumentoListView.as_view(), name="parametri_list"),
    path("parametri-documento/nuovo/", ParametriDocumentoCreateView.as_view(), name="parametri_create"),
    path(
        "parametri-documento/contatori/",
        ContatoriDocumentoListView.as_view(),
        name="contatori_list",
    ),
    path(
        "parametri-documento/contatori/nuovo/",
        ContatoriDocumentoCreateView.as_view(),
        name="contatori_create",
    ),
    path(
        "parametri-documento/contatori/<int:pk>/modifica/",
        ContatoriDocumentoUpdateView.as_view(),
        name="contatori_edit",
    ),
    path(
        "parametri-documento/contatori/<int:pk>/duplica/",
        ContatoriDocumentoDuplicateView.as_view(),
        name="contatori_duplicate",
    ),
    path(
        "parametri-documento/contatori/<int:pk>/elimina/",
        ContatoriDocumentoDeleteView.as_view(),
        name="contatori_delete",
    ),
    path(
        "parametri-documento/contatori/<int:pk>/",
        ContatoriDocumentoDetailView.as_view(),
        name="contatori_detail",
    ),
    path(
        "parametri-documento/<path:codice>/modifica/",
        ParametriDocumentoUpdateView.as_view(),
        name="parametri_edit",
    ),
    path(
        "parametri-documento/<path:codice>/elimina/",
        ParametriDocumentoDeleteView.as_view(),
        name="parametri_delete",
    ),
    path(
        "parametri-documento/<path:codice>/colonne/",
        ParametriDocumentoColonneView.as_view(),
        name="parametri_colonne",
    ),
    path(
        "parametri-documento/<path:codice>/",
        ParametriDocumentoDetailView.as_view(),
        name="parametri_detail",
    ),
    path("documenti/", DocumentoIndexView.as_view(), name="index"),
    path("documenti/calc-peso/", CalcPesoDocumentoView.as_view(), name="calc_peso"),
    path("documenti/calc-scadenze/", CalcScadenzeView.as_view(), name="calc_scadenze"),
    path("documenti/<str:tipo_doc>/nuovo/", DocumentoCreateView.as_view(), name="create"),
    path(
        "documenti/<str:tipo_doc>/parametri/",
        DocumentoParametriSpeseView.as_view(),
        name="parametri_spese",
    ),
    path(
        "documenti/<str:tipo_doc>/<int:pk>/modifica/",
        DocumentoUpdateView.as_view(),
        name="edit",
    ),
    path(
        "documenti/<str:tipo_doc>/<int:pk>/elimina/",
        DocumentoDeleteView.as_view(),
        name="delete",
    ),
    path(
        "documenti/<str:tipo_doc>/<int:pk>/stampa/",
        DocumentoPrintView.as_view(),
        name="print",
    ),
    path(
        "documenti/<str:tipo_doc>/<int:pk>/invia-mail/",
        DocumentoInviaMailView.as_view(),
        name="invia_mail",
    ),
    path(
        "documenti/<str:tipo_doc>/<int:pk>/",
        DocumentoDetailView.as_view(),
        name="detail",
    ),
    path("documenti/<str:tipo_doc>/", DocumentoListView.as_view(), name="list"),
    path("parametri/4d/sync-documenti/", SyncDocumentiView.as_view(), name="sync"),
    path(
        "parametri/4d/sync-documenti/status/<int:log_id>/",
        SyncDocumentiStatusView.as_view(),
        name="sync_status",
    ),
    path(
        "parametri/4d/sync-documenti/cancel/",
        SyncDocumentiCancelView.as_view(),
        name="sync_cancel",
    ),
]
