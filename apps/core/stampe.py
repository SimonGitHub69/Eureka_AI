"""Stampe di Fatturazione Magazzino (menu laterale + hub)."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

STAMPE_FATTURAZIONE = (
    {
        "key": "articoli",
        "label": "Articoli",
        "icon": "ti-package",
        "url_name": "articoli:print_list",
        "subtitle": "Elenco anagrafica articoli",
    },
    {
        "key": "inventario",
        "label": "Inventario",
        "icon": "ti-packages",
        "url_name": "core:stampe_inventario",
        "subtitle": "Valori articoli / giacenze",
    },
    {
        "key": "distinte_base",
        "label": "Distinte base",
        "icon": "ti-list-tree",
        "url_name": "distinte_base:print_list",
        "subtitle": "Distinte e componenti",
    },
    {
        "key": "movimenti",
        "label": "Movimenti",
        "icon": "ti-transfer",
        "url_name": "movimenti:print_list",
        "subtitle": "Movimenti di magazzino",
    },
)

STAMPE_PRIMANOTA = (
    {
        "key": "pdc",
        "label": "Piano dei Conti",
        "icon": "ti-report-money",
        "url_name": "pdc:print_list",
        "subtitle": "Elenco piano dei conti",
    },
    {
        "key": "primanota",
        "label": "Primanota",
        "icon": "ti-notebook",
        "url_name": "primanota:print_list",
        "subtitle": "Elenco registrazioni",
    },
    {
        "key": "registri_iva",
        "label": "Registri IVA",
        "icon": "ti-book-2",
        "url_name": "registri_iva:print_list",
        "subtitle": "Libro registro IVA per periodo",
    },
    {
        "key": "causali_contabili",
        "label": "Causali Contabili",
        "icon": "ti-file-description",
        "url_name": "causali_contabili:print_list",
        "subtitle": "Elenco causali contabili",
    },
    {
        "key": "raggruppamento_conti",
        "label": "Raggruppamento Conti",
        "icon": "ti-category-2",
        "url_name": "raggruppamento_conti:print_list",
        "subtitle": "Elenco raggruppamenti conti",
    },
    {
        "key": "raggruppamento_clifor",
        "label": "Raggr. Clienti-Fornitori",
        "icon": "ti-users-group",
        "url_name": "raggruppamento_clifor:print_list",
        "subtitle": "Elenco raggruppamenti clienti/fornitori",
    },
)


def stampe_fatturazione_items() -> list[dict]:
    items = []
    for spec in STAMPE_FATTURAZIONE:
        items.append(
            {
                **spec,
                "href": reverse(spec["url_name"]),
            }
        )
    return items


class StampeHubView(LoginRequiredMixin, TemplateView):
    template_name = "core/stampe_hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stampe_items"] = stampe_fatturazione_items()
        return context
