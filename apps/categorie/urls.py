from django.urls import path

from apps.categorie.views import (
    CategoriaCreateView,
    CategoriaDeleteView,
    CategoriaDetailView,
    CategoriaListView,
    CategoriaExportListView,
    CategoriaPrintListView,
    CategoriaUpdateView,
    SyncCategorieView,
)

app_name = "categorie"

urlpatterns = [
    path("categorie/", CategoriaListView.as_view(), name="list"),
    path("categorie/stampa/", CategoriaPrintListView.as_view(), name="print_list"),
    path("categorie/export/", CategoriaExportListView.as_view(), name="export_list"),
    path("categorie/nuova/", CategoriaCreateView.as_view(), name="create"),
    path("categorie/<path:codice>/modifica/", CategoriaUpdateView.as_view(), name="edit"),
    path("categorie/<path:codice>/elimina/", CategoriaDeleteView.as_view(), name="delete"),
    path("categorie/<path:codice>/", CategoriaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-categorie/", SyncCategorieView.as_view(), name="sync"),
]
