from .base import BaseModel
from .comando_vocale import (
    AzioneComandoVocale,
    ComandoVocale,
    DestinazioneComandoVocale,
    MatchModeComandoVocale,
)
from .configurazione_4d import Configurazione4D
from .configurazione_pc import ConfigurazionePC
from .configurazione_programma import ConfigurazioneProgramma

__all__ = [
    "AzioneComandoVocale",
    "BaseModel",
    "ComandoVocale",
    "Configurazione4D",
    "ConfigurazionePC",
    "ConfigurazioneProgramma",
    "DestinazioneComandoVocale",
    "MatchModeComandoVocale",
]
