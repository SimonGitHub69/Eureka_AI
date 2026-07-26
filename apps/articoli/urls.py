from django.urls import path

from apps.articoli.views import ArticoloDetailView, ArticoloListView

app_name = "articoli"

urlpatterns = [
    path("articoli/", ArticoloListView.as_view(), name="list"),
    path("articoli/<path:codice>/", ArticoloDetailView.as_view(), name="detail"),
]
