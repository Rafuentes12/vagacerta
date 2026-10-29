"""Modo levantamento: a equipe conta vagas livres na rua para calibrar o modelo.

Cada contagem vira um sinal ao vivo de alta confiança ("N vagas · contagem da equipe") e
fica guardada para exportação em CSV, ao lado do que o modelo previa naquele momento.
É a verdade de campo da seção 6 do planejamento.
"""

import csv
import io
import threading
from dataclasses import dataclass
from datetime import datetime

from app.catalogo import Catalogo
from app.erros import ErroNegocio
from app.persistencia import Registro
from app.servicos.demanda import dia_e_hora, nivel
from app.servicos.disponibilidade import ServicoDisponibilidade, Sinal
from app.servicos.proximidade import exigir_proximidade


@dataclass
class Contagem:
    trecho_id: str
    usuario_id: str
    vagas_livres: int
    quando: datetime


class ServicoLevantamento:
    def __init__(self, catalogo: Catalogo, disponibilidade: ServicoDisponibilidade,
                 distancia_maxima_m: float, registro: Registro) -> None:
        self._catalogo = catalogo
        self._disponibilidade = disponibilidade
        self._distancia_maxima_m = distancia_maxima_m
        self._registro = registro
        self._contagens: list[Contagem] = []
        self._lock = threading.Lock()

    def contar(self, trecho_id: str, usuario_id: str, vagas_livres: int, agora: datetime,
               lat: float, lng: float) -> Contagem:
        trecho = self._catalogo.trecho(trecho_id)
        if trecho is None:
            raise ErroNegocio("Trecho não encontrado", 404)
        if not 0 <= vagas_livres <= trecho.capacidade * 2:
            raise ErroNegocio(f"Número de vagas livres fora do esperado (capacidade estimada: {trecho.capacidade})", 422)
        if not self._registro.restaurando:
            exigir_proximidade(self._catalogo, trecho_id, lat, lng, self._distancia_maxima_m, "contar este trecho")
            self._disponibilidade.registrar(Sinal(alvo_id=trecho_id, fonte="equipe", criado_em=agora,
                                                  vagas_livres=vagas_livres, usuario_id=usuario_id))
        contagem = Contagem(trecho_id, usuario_id, vagas_livres, agora)
        with self._lock:
            self._contagens.append(contagem)
        self._registro.gravar("contagem", trecho_id=trecho_id, usuario_id=usuario_id, vagas_livres=vagas_livres,
                              quando=agora, lat=lat, lng=lng)
        return contagem

    def total(self) -> int:
        with self._lock:
            return len(self._contagens)

    def exportar_csv(self) -> str:
        """Uma linha por contagem, com a previsão do modelo para o mesmo trecho e horário."""
        saida = io.StringIO()
        escritor = csv.writer(saida)
        escritor.writerow(["quando", "dia", "hora", "trecho_id", "trecho", "regime", "capacidade_estimada",
                           "vagas_livres_contadas", "vagas_livres_modelo", "prob_livre_modelo", "nivel_modelo",
                           "explicacao_modelo", "usuario_id"])
        with self._lock:
            contagens = list(self._contagens)
        for c in contagens:
            trecho = self._catalogo.trecho(c.trecho_id)
            if trecho is None:
                continue
            previsto = self._disponibilidade.estimativa_do_modelo(c.trecho_id, c.quando)
            tipo_dia, hora, _ = dia_e_hora(c.quando)
            escritor.writerow([
                c.quando.isoformat(timespec="minutes"), tipo_dia, round(hora, 2), trecho.id, trecho.nome,
                trecho.regime, trecho.capacidade, c.vagas_livres, previsto.vagas_livres,
                round(previsto.prob_livre, 3), nivel(previsto.prob_livre), previsto.explicacao, c.usuario_id,
            ])
        return saida.getvalue()
