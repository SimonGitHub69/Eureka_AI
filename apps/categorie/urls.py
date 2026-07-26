from django.urls import path

from apps.categorie.views import CategoriaDetailView, CategoriaListView, SyncCategorieView

app_name = "categorie"

urlpatterns = [
    path("categorie/", CategoriaListView.as_view(), name="list"),
    path("categorie/<path:codice>/", CategoriaDetailView.as_view(), name="detail"),
    path("parametri/4d/sync-categorie/", SyncCategorieView.as_view(), name="sync"),
]
