from django.urls import path

from apps.agenda.views import (
    AgendaView,
    EventiListApiView,
    EventoDetailApiView,
    SchedeLavorazioneCalendarioApiView,
)

app_name = "agenda"

urlpatterns = [
    path("agenda/", AgendaView.as_view(), name="calendario"),
    path("agenda/api/eventi/", EventiListApiView.as_view(), name="eventi_api"),
    path(
        "agenda/api/eventi/<int:pk>/",
        EventoDetailApiView.as_view(),
        name="evento_api",
    ),
    path(
        "agenda/api/schede-lavorazione/",
        SchedeLavorazioneCalendarioApiView.as_view(),
        name="schede_api",
    ),
]
