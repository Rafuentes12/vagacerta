"""Disponibilidade: junta sinais de várias fontes num estado por vaga.

Cada sinal tem uma confiança inicial que cai pela metade a cada "meia-vida"
(um reporte de usuário vale minutos; uma contagem de cancela, um pouco mais).
Sem sinal ao vivo, vale o modelo de demanda (estabelecimentos reais do OSM + Erlang B,
ver demanda.py), apresentado como "Fácil / Moderado / Difícil (estimativa)".
O app mostra a fonte e a idade da informação para ser honesto sobre a incerteza.
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.catalogo import Catalogo
from app.erros import ErroNegocio
from app.modelos import EstadoVaga, FonteSinal
from app.persistencia import Registro
from app.servicos.demanda import Estimativa, ModeloDemanda, nivel


@dataclass(frozen=True)
class ConfigFonte:
    confianca: float
    meia_vida_min: float
    rotulo: str


FONTES: dict[str, ConfigFonte] = {
    "cancela": ConfigFonte(0.95, 10, "cancela"),
    "atendente": ConfigFonte(0.85, 20, "atendente"),
    "equipe": ConfigFonte(0.90, 15, "contagem da equipe"),
    "saida": ConfigFonte(0.70, 4, "vaga liberada por usuário"),
    "usuario": ConfigFonte(0.60, 3, "reporte de usuário"),
}
PESO_MODELO = 0.30
TEXTO_NIVEL = {"facil": "Fácil", "moderado": "Moderado", "dificil": "Difícil"}
PESO_MINIMO = 0.05  # abaixo disso o sinal é considerado vencido


@dataclass
class Sinal:
    alvo_id: str
    fonte: FonteSinal
    criado_em: datetime
    vagas_livres: Optional[int] = None  # estacionamentos (cancela/atendente)
    livre: Optional[bool] = None        # trechos de rua (usuários)
    usuario_id: Optional[str] = None


def _prob_por_vagas(vagas: int) -> float:
    if vagas <= 0:
        return 0.05
    return {1: 0.6, 2: 0.8}.get(vagas, 0.95)


def _idade_min(desde: datetime, ate: datetime) -> float:
    return max(0.0, (ate - desde).total_seconds() / 60)


def _texto_idade(minutos: float) -> str:
    return "há menos de 1 min" if minutos < 1 else f"há {int(minutos)} min"


class ServicoDisponibilidade:
    def __init__(self, catalogo: Catalogo, modelo: Optional[ModeloDemanda] = None,
                 registro: Optional[Registro] = None) -> None:
        self._catalogo = catalogo
        self._modelo = modelo or ModeloDemanda(catalogo)
        self._registro = registro or Registro(None)
        self._sinais: dict[str, list[Sinal]] = {}
        self._lock = threading.Lock()

    def registrar(self, sinal: Sinal, gravar: bool = True) -> None:
        if self._capacidade(sinal.alvo_id) is None:
            raise ErroNegocio(f"Vaga '{sinal.alvo_id}' não existe", 404)
        with self._lock:
            self._sinais.setdefault(sinal.alvo_id, []).append(sinal)
        if gravar:
            self._registro.gravar("sinal", alvo_id=sinal.alvo_id, fonte=sinal.fonte, quando=sinal.criado_em,
                                  vagas_livres=sinal.vagas_livres, livre=sinal.livre, usuario_id=sinal.usuario_id)

    def estimativa_do_modelo(self, alvo_id: str, momento: datetime) -> Estimativa:
        """O que o modelo previa, sem os sinais ao vivo (para comparar com as contagens de campo)."""
        return self._modelo.estimar(alvo_id, self._capacidade(alvo_id), momento)

    def sinais(self, alvo_id: str) -> list[Sinal]:
        with self._lock:
            return list(self._sinais.get(alvo_id, []))

    def _capacidade(self, alvo_id: str) -> Optional[int]:
        alvo = self._catalogo.trecho(alvo_id) or self._catalogo.estacionamento(alvo_id)
        return alvo.capacidade if alvo else None

    def estado(self, alvo_id: str, agora: datetime, momento: Optional[datetime] = None) -> EstadoVaga:
        """Estado da vaga previsto para `momento` (ex.: horário de chegada), visto em `agora`."""
        momento = momento or agora
        capacidade = self._capacidade(alvo_id)
        if capacidade is None:
            raise ErroNegocio(f"Vaga '{alvo_id}' não existe", 404)

        # Modelo v1: demanda dos estabelecimentos próximos no horário previsto + Erlang B.
        estimativa = self._modelo.estimar(alvo_id, capacidade, momento)
        p_modelo = estimativa.prob_livre

        melhor: Optional[tuple[float, Sinal]] = None
        for sinal in self.sinais(alvo_id):
            if sinal.criado_em > agora:
                continue
            cfg = FONTES[sinal.fonte]
            peso = cfg.confianca * 0.5 ** (_idade_min(sinal.criado_em, momento) / cfg.meia_vida_min)
            if peso >= PESO_MINIMO and (melhor is None or peso > melhor[0]):
                melhor = (peso, sinal)

        if melhor is None or melhor[0] < PESO_MODELO:
            p = p_modelo
            if melhor is not None:  # sinal fraco ainda puxa um pouco a estimativa
                p = (melhor[0] * self._prob_sinal(melhor[1]) + PESO_MODELO * p_modelo) / (melhor[0] + PESO_MODELO)
            dificuldade = nivel(p)
            return EstadoVaga(
                prob_livre=round(p, 2),
                vagas_livres_estimadas=estimativa.vagas_livres,
                confianca=PESO_MODELO,
                fonte="modelo",
                atualizado_ha_min=None,
                ao_vivo=False,
                nivel=dificuldade,
                explicacao=estimativa.explicacao,
                rotulo=f"{TEXTO_NIVEL[dificuldade]} (estimativa)",
            )

        peso, sinal = melhor
        p_sinal = self._prob_sinal(sinal)
        p = (peso * p_sinal + PESO_MODELO * p_modelo) / (peso + PESO_MODELO)
        idade_agora = _idade_min(sinal.criado_em, agora)
        rotulo_fonte = FONTES[sinal.fonte].rotulo
        livres = sinal.vagas_livres if sinal.vagas_livres is not None else estimativa.vagas_livres

        if sinal.vagas_livres is not None:
            texto = f"{livres} vagas" if livres != 1 else "1 vaga"
            if livres == 0:
                texto = "Lotado"
        elif p >= 0.5:
            texto = "Livre agora"
        else:
            texto = "Provavelmente ocupada"

        return EstadoVaga(
            prob_livre=round(p, 2),
            vagas_livres_estimadas=livres,
            confianca=round(peso, 2),
            fonte=sinal.fonte,
            atualizado_ha_min=int(idade_agora),
            ao_vivo=True,
            nivel=nivel(p),
            explicacao=estimativa.explicacao,
            rotulo=f"{texto} · {rotulo_fonte} · {_texto_idade(idade_agora)}",
        )

    @staticmethod
    def _prob_sinal(sinal: Sinal) -> float:
        if sinal.vagas_livres is not None:
            return _prob_por_vagas(sinal.vagas_livres)
        return 0.9 if sinal.livre else 0.1
