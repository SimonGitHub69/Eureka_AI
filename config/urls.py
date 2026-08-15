from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.urls import include, path

admin.site.site_header = "Eureka AI"
admin.site.site_title = "Eureka AI"
admin.site.index_title = "Amministrazione"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", include("apps.dashboard.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.fatture.urls")),
    path("", include("apps.documenti.urls")),
    path("", include("apps.anagrafiche.urls")),
    path("", include("apps.articoli.urls")),
    path("", include("apps.distinte_base.urls")),
    path("", include("apps.categorie.urls")),
    path("", include("apps.condizioni.urls")),
    path("", include("apps.aliquote.urls")),
    path("", include("apps.banche.urls")),
    path("", include("apps.sconti.urls")),
    path("", include("apps.aziende.urls")),
    path("", include("apps.gruppi_articoli.urls")),
    path("", include("apps.gruppi_magazzini.urls")),
    path("", include("apps.magazzini.urls")),
    path("", include("apps.stampi.urls")),
    path("", include("apps.operatori.urls")),
    path("", include("apps.timbrature.urls")),
    path("", include("apps.schede_lavorazione.urls")),
    path("", include("apps.agenda.urls")),
    path("", include("apps.carbon.urls")),
    path("", include("apps.lavorazioni_extra.urls")),
    path("", include("apps.geografia.urls")),
    path("", include("apps.pdc.urls")),
    path("", include("apps.causali_contabili.urls")),
    path("", include("apps.raggruppamento_conti.urls")),
    path("", include("apps.raggruppamento_clifor.urls")),
]

if settings.SERVE_MEDIA:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
