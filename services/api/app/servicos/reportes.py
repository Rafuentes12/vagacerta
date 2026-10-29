"""Crowdsourcing ("vaga livre/ocupada") e a métrica de acerto ("encontrou a vaga?")."""

import threading
from datetime import datetime, timedelta

from app.catalogo import Catalogo
from app.erros import ErroNegocio
from app.modelos import FeedbackChegada
from app.persistencia import Registro
from app.servicos.disponibilidade import ServicoDisponibilidade, Sinal
from app.servicos.proximidade import exigir_proximidade

INTERVALO_MINIMO = timedelta(minutes=2)  # por usuário e por vaga


class ServicoReportes:
    def __init__(self, catalogo: Catalogo, disponibilidade: ServicoDisponibilidade, distancia_maxima_m: float,
                 registro: Registro) -> None:
        self._catalogo = catalogo
        self._registro = registro
        self._distancia_maxima_m = distancia_maxima_m
        self._disponibilidade = disponibilidade
        self._feedbacks: list[FeedbackChegada] = []
        self._lock = threading.Lock()

    def reportar(self, alvo_id: str, usuario_id: str, livre: bool, agora: datetime, lat: float, lng: float) -> None:
        """Antifraude simples: precisa estar perto da vaga e esperar entre um reporte e outro."""
        if self._catalogo.trecho(alvo_id) is None:
            raise ErroNegocio("Reportes de vaga livre/ocupada valem só para vagas de rua", 422)
        if not self._registro.restaurando:
            exigir_proximidade(self._catalogo, alvo_id, lat, lng, self._distancia_maxima_m, "reportar esta vaga")
        recentes = [s for s in self._disponibilidade.sinais(alvo_id)
                    if s.usuario_id == usuario_id and s.fonte == "usuario" and agora - s.criado_em < INTERVALO_MINIMO]
        if recentes:
            raise ErroNegocio("Aguarde um pouco antes de reportar esta vaga de novo", 429)
        self._disponibilidade.registrar(
            Sinal(alvo_id=alvo_id, fonte="usuario", criado_em=agora, livre=livre, usuario_id=usuario_id)
        )

    def registrar_chegada(self, alvo_id: str, usuario_id: str, encontrou: bool, agora: datetime) -> FeedbackChegada:
        if not (self._catalogo.trecho(alvo_id) or self._catalogo.estacionamento(alvo_id)):
            raise ErroNegocio("Vaga não encontrada", 404)
        feedback = FeedbackChegada(alvo_id=alvo_id, usuario_id=usuario_id, encontrou=encontrou, registrado_em=agora)
        with self._lock:
            self._feedbacks.append(feedback)
        self._registro.gravar("chegada", alvo_id=alvo_id, usuario_id=usuario_id, encontrou=encontrou, quando=agora)
        return feedback

    def metricas(self) -> dict:
        with self._lock:
            total = len(self._feedbacks)
            acertos = sum(f.encontrou for f in self._feedbacks)
        return {
            "chegadas_avaliadas": total,
            "acertos": acertos,
            "taxa_acerto": round(acertos / total, 3) if total else None,
        }
