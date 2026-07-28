from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import ProgrammingError
from django.db.utils import OperationalError
from django.views.generic import TemplateView

from apps.anagrafiche.models import Agente, Cliente, Fornitore
from apps.articoli.models import Articolo
from apps.aziende.models import Azienda
from apps.categorie.models import Categoria
from apps.fatture.models import Fattura, FatturaDettaglio
from apps.gruppi_articoli.models import GruppoArticolo
from apps.gruppi_magazzini.models import GruppoMagazzino
from apps.magazzini.models import Magazzino
from apps.operatori.models import Operatore
from apps.stampi.models import Stampo

# Tabelle mirror importate da 4D (PostgreSQL).
TABELLE_IMPORTATE = (
    {
        "label": "Fatture",
        "source": "Fatture",
        "db_table": "fatture",
        "model": Fattura,
        "list_url": "fatture:list",
    },
    {
        "label": "Righe fattura",
        "source": "Fatture_Dettaglio",
        "db_table": "fatture_dettaglio",
        "model": FatturaDettaglio,
        "list_url": None,
    },
    {
        "label": "Clienti",
        "source": "Clienti",
        "db_table": "clienti",
        "model": Cliente,
        "list_url": "anagrafiche:clienti_list",
    },
    {
        "label": "Fornitori",
        "source": "Fornitori",
        "db_table": "fornitori",
        "model": Fornitore,
        "list_url": "anagrafiche:fornitori_list",
    },
    {
        "label": "Agenti",
        "source": "Agenti",
        "db_table": "agenti",
        "model": Agente,
        "list_url": "anagrafiche:agenti_list",
    },
    {
        "label": "Azienda",
        "source": "Azienda",
        "db_table": "aziende",
        "model": Azienda,
        "list_url": "aziende:list",
    },
    {
        "label": "Articoli",
        "source": "Articoli",
        "db_table": "articoli",
        "model": Articolo,
        "list_url": "articoli:list",
    },
    {
        "label": "Categorie",
        "source": "CatMerce",
        "db_table": "categorie",
        "model": Categoria,
        "list_url": "categorie:list",
    },
    {
        "label": "Gruppi articoli",
        "source": "GruppoArt",
        "db_table": "gruppi_articoli",
        "model": GruppoArticolo,
        "list_url": "gruppi_articoli:list",
    },
    {
        "label": "Raggruppamenti magazzini",
        "source": "RaggMagazzini",
        "db_table": "gruppi_magazzini",
        "model": GruppoMagazzino,
        "list_url": "gruppi_magazzini:list",
    },
    {
        "label": "Magazzini",
        "source": "Magazzini",
        "db_table": "magazzini",
        "model": Magazzino,
        "list_url": "magazzini:list",
    },
    {
        "label": "Stampi",
        "source": "TabStampi",
        "db_table": "stampi",
        "model": Stampo,
        "list_url": "stampi:list",
    },
    {
        "label": "Operatori",
        "source": "Operatori",
        "db_table": "operatori",
        "model": Operatore,
        "list_url": "operatori:list",
    },
)


def _conteggio_tabella(model):
    try:
        return model.objects.count()
    except (ProgrammingError, OperationalError):
        return None


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/index.html"


class SistemaView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/sistema.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tabelle = []
        totale = 0
        for spec in TABELLE_IMPORTATE:
            count = _conteggio_tabella(spec["model"])
            if count is not None:
                totale += count
            tabelle.append(
                {
                    "label": spec["label"],
                    "source": spec["source"],
                    "db_table": spec["db_table"],
                    "count": count,
                    "list_url": spec["list_url"],
                }
            )
        context["tabelle_importate"] = tabelle
        context["tabelle_totale_records"] = totale
        return context
