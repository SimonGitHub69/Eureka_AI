"""Lettura parametri programma con eventuale override da postazione PC."""

from __future__ import annotations

from apps.core.models import ConfigurazioneProgramma
from apps.core.pc import (
    detect_client_pc_name,
    get_configurazione_pc,
    get_nome_pc_from_request,
)


def get_configurazione_programma():
    return ConfigurazioneProgramma.get_solo()


def get_assistente_vocale_attivo(request=None) -> bool:
    if request is not None:
        cfg_pc = _cfg_pc_for(request)
        if cfg_pc is not None:
            return bool(cfg_pc.assistente_vocale_attivo)
    return bool(get_configurazione_programma().assistente_vocale_attivo)


def get_navbar_fissa(request=None) -> bool:
    if request is not None:
        cfg_pc = _cfg_pc_for(request)
        if cfg_pc is not None:
            return bool(cfg_pc.navbar_fissa)
    return bool(get_configurazione_programma().navbar_fissa)


def _cfg_pc_for(request):
    nome = detect_client_pc_name(request) or get_nome_pc_from_request(request)
    return get_configurazione_pc(nome) if nome else None


def current_pc_context(request=None) -> dict:
    nome = ""
    cfg = None
    if request is not None:
        nome = detect_client_pc_name(request) or get_nome_pc_from_request(request)
        cfg = get_configurazione_pc(nome) if nome else None

    label = str(cfg) if cfg else nome
    return {
        "current_pc_name": nome,
        "current_pc_label": label,
        "current_pc_config": cfg,
    }
