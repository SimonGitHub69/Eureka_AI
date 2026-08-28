from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import ProgrammingError
from django.db.models import Count
from django.db.utils import OperationalError
from django.urls import reverse
from django.views.generic import TemplateView

from apps.aliquote.models import Aliquota
from apps.registri_iva.models import RegistroIva
from apps.anagrafiche.models import Agente, Cliente, Fornitore
from apps.articoli.models import Articolo
from apps.aziende.models import Azienda
from apps.banche.models import Banca
from apps.carbon.models import LavorazionePartita, Reparto, StampoSerialePartita
from apps.categorie.models import Categoria
from apps.causali_contabili.models import CausaleContabile
from apps.causali_magazzino.models import CausaleMagazzino
from apps.causali_trasp.models import CausaleTrasporto
from apps.condizioni.models import Condizione
from apps.core.programma import is_extra_enabled
from apps.core.pc import get_dashboard_shortcut_modes_for_request
from apps.core.dashboard_shortcuts import (
    DOC_SHORTCUT_BY_CODICE,
    catalog_by_section,
    is_shortcut_on_dashboard,
    shortcut_visible_for_user,
)
from apps.destinazioni.models import DestinazioneDiversa
from apps.distinte_base.models import DistintaBase
from apps.documenti.models import Porto, RigaDocumento, TestaDocumento
from apps.fatture.models import Fattura, FatturaDettaglio
from apps.gruppi_articoli.models import GruppoArticolo
from apps.gruppi_magazzini.models import GruppoMagazzino
from apps.lavorazioni_extra.models import LavorazioneExtra
from apps.depositi.models import Deposito
from apps.magazzini.models import Magazzino
from apps.movimenti.models import MovimentoT
from apps.operatori.models import Operatore
from apps.pdc.models import PianoConti
from apps.primanota.models import Primanota, PrimanotaDettaglio
from apps.raggruppamento_clifor.models import RaggruppamentoClifor
from apps.raggruppamento_conti.models import RaggruppamentoConto
from apps.sconti.models import Sconto
from apps.stampi.models import Stampo
from apps.timbrature.models import Timbratura
from apps.valute.models import Valuta
from apps.vettori.models import Vettore
from apps.zone.models import Zona

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
        "label": "Teste documenti",
        "source": "Preventivi / Ordini / Bolle / Fatture",
        "db_table": "teste_documenti",
        "model": TestaDocumento,
        "list_url": None,
    },
    {
        "label": "Righe documenti",
        "source": "*_Dettaglio",
        "db_table": "righe_documenti",
        "model": RigaDocumento,
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
        "label": "Distinte base",
        "source": "Distinte_Base",
        "db_table": "distinte_base",
        "model": DistintaBase,
        "list_url": "distinte_base:list",
    },
    {
        "label": "Categorie",
        "source": "CatMerce",
        "db_table": "categorie",
        "model": Categoria,
        "list_url": "categorie:list",
    },
    {
        "label": "Condizioni di Pagamento",
        "source": "CondizioniPag",
        "db_table": "condizioni",
        "model": Condizione,
        "list_url": "condizioni:list",
    },
    {
        "label": "Piano dei Conti",
        "source": "PDC",
        "db_table": "pdc",
        "model": PianoConti,
        "list_url": "pdc:list",
    },
    {
        "label": "Causali contabili",
        "source": "CausaliC",
        "db_table": "causali_contabili",
        "model": CausaleContabile,
        "list_url": "causali_contabili:list",
    },
    {
        "label": "Raggruppamento conti",
        "source": "Raggruppamento",
        "db_table": "raggruppamento_conti",
        "model": RaggruppamentoConto,
        "list_url": "raggruppamento_conti:list",
    },
    {
        "label": "Primanota",
        "source": "Primanota",
        "db_table": "primanota",
        "model": Primanota,
        "list_url": "primanota:list",
    },
    {
        "label": "Righe prima nota",
        "source": "Primanota_Dettaglio",
        "db_table": "primanota_dettaglio",
        "model": PrimanotaDettaglio,
        "list_url": None,
    },
    {
        "label": "Raggr. Clienti-Fornitori",
        "source": "Gruppo_Cli_For",
        "db_table": "raggruppamento_clifor",
        "model": RaggruppamentoClifor,
        "list_url": "raggruppamento_clifor:list",
    },
    {
        "label": "Aliquote IVA",
        "source": "AliquoteIva",
        "db_table": "aliquote",
        "model": Aliquota,
        "list_url": "aliquote:list",
    },
    {
        "label": "Registri IVA",
        "source": "RegistriIva",
        "db_table": "registri_iva",
        "model": RegistroIva,
        "list_url": "registri_iva:list",
    },
    {
        "label": "Banche",
        "source": "Banche",
        "db_table": "banche",
        "model": Banca,
        "list_url": "banche:list",
    },
    {
        "label": "Sconti",
        "source": "Sconti",
        "db_table": "sconti",
        "model": Sconto,
        "list_url": "sconti:list",
    },
    {
        "label": "Valute",
        "source": "Valuta",
        "db_table": "valuta",
        "model": Valuta,
        "list_url": "valute:list",
    },
    {
        "label": "Destinazioni diverse",
        "source": "DestCliFor",
        "db_table": "DestCliFor",
        "model": DestinazioneDiversa,
        "list_url": "destinazioni:list",
    },
    {
        "label": "Zone",
        "source": "Zone",
        "db_table": "zone",
        "model": Zona,
        "list_url": "zone:list",
    },
    {
        "label": "Porto",
        "source": "TabPorto",
        "db_table": "tab_porto",
        "model": Porto,
        "list_url": "documenti:porto_list",
    },
    {
        "label": "Spedizionieri",
        "source": "Vettori",
        "db_table": "vettori",
        "model": Vettore,
        "list_url": "vettori:list",
    },
    {
        "label": "Causali trasporto",
        "source": "CausaliTrasp",
        "db_table": "causali_trasp",
        "model": CausaleTrasporto,
        "list_url": "causali_trasp:list",
    },
    {
        "label": "Gruppi articoli",
        "source": "GruppoArt",
        "db_table": "gruppi_articoli",
        "model": GruppoArticolo,
        "list_url": "gruppi_articoli:list",
    },
    {
        "label": "Gruppi Magazzini",
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
        "label": "Depositi",
        "source": "Depositi",
        "db_table": "depositi",
        "model": Deposito,
        "list_url": "depositi:list",
    },
    {
        "label": "Causali magazzino",
        "source": "CausaliMaga",
        "db_table": "causali_maga",
        "model": CausaleMagazzino,
        "list_url": "causali_magazzino:list",
    },
    {
        "label": "Movimenti magazzino",
        "source": "MovimentiT",
        "db_table": "movimentit",
        "model": MovimentoT,
        "list_url": "movimenti:list",
    },
    {
        "label": "Stampi",
        "source": "TabStampi",
        "db_table": "stampi",
        "model": Stampo,
        "list_url": "stampi:list",
    },
    {
        "label": "Lavorazioni extra",
        "source": "TabLavorazioniExtra",
        "db_table": "lavorazioni_extra",
        "model": LavorazioneExtra,
        "list_url": "lavorazioni_extra:list",
    },
    {
        "label": "Reparti",
        "source": "Reparti",
        "db_table": "reparti",
        "model": Reparto,
        "list_url": "carbon:reparti_list",
    },
    {
        "label": "Lavorazioni partite",
        "source": "Lavorazioni_Partite",
        "db_table": "lavorazioni_partite",
        "model": LavorazionePartita,
        "list_url": "carbon:lavorazioni_list",
    },
    {
        "label": "Stampi seriali",
        "source": "TabStampi_Seriali_Partite",
        "db_table": "stampi_seriali_partite",
        "model": StampoSerialePartita,
        "list_url": "carbon:stampi_seriali_list",
    },
    {
        "label": "Operatori",
        "source": "Operatori",
        "db_table": "operatori",
        "model": Operatore,
        "list_url": "operatori:list",
    },
    {
        "label": "Presenze",
        "source": "Timbrature",
        "db_table": "timbrature",
        "model": Timbratura,
        "list_url": "timbrature:list",
    },
)

DOC_CARD_COLORS = {
    "PRV": "azure",
    "ORV": "blue",
    "ORA": "indigo",
    "DDT": "orange",
    "FAT": "primary",
    "NCR": "red",
    "NDB": "purple",
}


def _conteggio_tabella(model):
    try:
        return model.objects.count()
    except (ProgrammingError, OperationalError):
        return None


def _conteggi_documenti_per_tipo() -> dict[str, int]:
    try:
        rows = TestaDocumento.objects.values("tipo_doc_id").annotate(n=Count("id"))
        return {row["tipo_doc_id"]: row["n"] for row in rows}
    except (ProgrammingError, OperationalError):
        return {}


def _subtitle_count(count, singular: str, plural: str, fallback: str) -> str:
    if count is None:
        return fallback
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural}"


def _card(*, href: str, icon: str, color: str, label: str, subtitle: str) -> dict:
    return {
        "href": href,
        "icon": icon,
        "color": color,
        "label": label,
        "subtitle": subtitle,
    }


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dashboard_sections"] = self._sections()
        return context

    def _shortcut_modes(self) -> dict[str, str]:
        return get_dashboard_shortcut_modes_for_request(self.request)

    def _sections(self) -> list[dict]:
        modes = self._shortcut_modes()
        sections = []
        for section_label, _items in catalog_by_section():
            if section_label == "Fatturazione Magazzino · Documenti":
                cards = self._documenti_cards(modes)
            elif section_label == "CARBON" and not is_extra_enabled("CARBON"):
                continue
            else:
                cards = self._catalog_cards(modes, section_label)
            if cards:
                sections.append({"title": section_label, "cards": cards})
        return sections

    def _documenti_cards(self, modes: dict[str, str]) -> list[dict]:
        from apps.core.programma import get_documenti_menu_items
        from apps.documenti.views import list_tipo_codes_for

        try:
            items = get_documenti_menu_items()
        except Exception:
            return []
        counts = _conteggi_documenti_per_tipo()
        cards = []
        for item in items:
            shortcut_key = DOC_SHORTCUT_BY_CODICE.get((item.get("codice") or "").upper())
            if shortcut_key and not is_shortcut_on_dashboard(modes, shortcut_key):
                continue
            if item.get("is_fatture"):
                n = _conteggio_tabella(Fattura)
            else:
                n = sum(counts.get(code, 0) for code in list_tipo_codes_for(item["codice"]))
            cards.append(
                _card(
                    href=item["href"],
                    icon=item["icon"],
                    color=DOC_CARD_COLORS.get(item["codice"], "secondary"),
                    label=item["label"],
                    subtitle=_subtitle_count(n, "documento", "documenti", "Apri elenco"),
                )
            )
        return cards

    def _catalog_cards(self, modes: dict[str, str], section_label: str) -> list[dict]:
        from django.urls import NoReverseMatch

        from apps.core.dashboard_shortcuts import NAVBAR_SHORTCUT_CATALOG

        cards = []
        user = self.request.user
        for item in NAVBAR_SHORTCUT_CATALOG:
            if item["section"] != section_label:
                continue
            if (item.get("key") or "").startswith("doc_"):
                continue
            if not is_shortcut_on_dashboard(modes, item["key"]):
                continue
            if not shortcut_visible_for_user(item, user):
                continue
            try:
                kwargs = item.get("url_kwargs") or {}
                href = reverse(item["url_name"], kwargs=kwargs)
            except NoReverseMatch:
                continue
            cards.append(
                _card(
                    href=href,
                    icon=item["icon"],
                    color=item.get("color") or "secondary",
                    label=item["label"],
                    subtitle=item.get("subtitle") or "Apri elenco",
                )
            )
        return cards


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
