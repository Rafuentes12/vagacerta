"""Configuração lida de variáveis de ambiente.

VAGACERTA_AGORA     Data/hora inicial simulada (ISO, ex.: 2026-10-20T10:30). O relógio
                    avança normalmente a partir dela. Útil para demonstrar o app em
                    horário comercial mesmo testando à noite.
VAGACERTA_CORS      Origens liberadas no CORS, separadas por vírgula (padrão: *).
VAGACERTA_DISTANCIA_MAX_M
                    Distância máxima (m) entre o usuário e a vaga para iniciar um
                    estacionamento ou reportar algo sobre ela (padrão: 300).
VAGACERTA_BANCO     Arquivo SQLite onde ficam as ações dos usuários (padrão:
                    services/api/dados/vagacerta.db). Vazio = só em memória.
VAGACERTA_DESTINOS  "photon" (busca real no OpenStreetMap, padrão) ou "mock" (lista fixa).
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")

Relogio = Callable[[], datetime]


def criar_relogio() -> Relogio:
    fixo = os.getenv("VAGACERTA_AGORA")
    if not fixo:
        return lambda: datetime.now(FUSO)

    inicio_simulado = datetime.fromisoformat(fixo)
    if inicio_simulado.tzinfo is None:
        inicio_simulado = inicio_simulado.replace(tzinfo=FUSO)
    inicio_real = datetime.now(FUSO)
    return lambda: inicio_simulado + (datetime.now(FUSO) - inicio_real)


CORS_ORIGENS = os.getenv("VAGACERTA_CORS", "*").split(",")
DISTANCIA_MAXIMA_M = float(os.getenv("VAGACERTA_DISTANCIA_MAX_M", "300"))
BANCO_PADRAO = Path(__file__).parent.parent / "dados" / "vagacerta.db"
BANCO = os.getenv("VAGACERTA_BANCO", str(BANCO_PADRAO))
BUSCA_DESTINOS = os.getenv("VAGACERTA_DESTINOS", "photon")
