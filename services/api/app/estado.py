"""Monta os serviços da aplicação (injeção de dependências simples).

Tudo fica em memória: reiniciar a API volta aos dados iniciais (mock do Centro + Batel do OSM)
e descarta reportes, sessões e mudanças feitas pelo mapeamento colaborativo.
"""

import json
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import Header, Request

from app.catalogo import PASTA_MOCK, Catalogo, CatalogoArquivos
from app.config import BANCO, BUSCA_DESTINOS, DISTANCIA_MAXIMA_M, Relogio, criar_relogio
from app.erros import ErroNegocio
from app.persistencia import Registro
from app.provedores.destinos import DestinosMock, DestinosPhoton, ProvedorDestinos
from app.provedores.rotas import ProvedorRotas, RotasEstimadas
from app.servicos.disponibilidade import ServicoDisponibilidade, Sinal
from app.servicos.levantamento import ServicoLevantamento
from app.servicos.mapeamento import ServicoMapeamento
from app.servicos.reportes import ServicoReportes
from app.servicos.reservas import ServicoReservas
from app.servicos.sessoes import ServicoSessoes


@dataclass
class Estado:
    relogio: Relogio
    catalogo: Catalogo
    destinos: ProvedorDestinos
    rotas: ProvedorRotas
    disponibilidade: ServicoDisponibilidade
    reservas: ServicoReservas
    sessoes: ServicoSessoes
    reportes: ServicoReportes
    mapeamento: ServicoMapeamento
    levantamento: ServicoLevantamento
    registro: Registro

    @classmethod
    def criar(cls, relogio: Relogio | None = None, semear: bool = True,
              distancia_maxima_m: float = DISTANCIA_MAXIMA_M, banco: Optional[str] = BANCO,
              busca_destinos: str = BUSCA_DESTINOS) -> "Estado":
        relogio = relogio or criar_relogio()
        if banco:
            Path(banco).parent.mkdir(parents=True, exist_ok=True)
        registro = Registro(banco)
        catalogo = CatalogoArquivos()
        disponibilidade = ServicoDisponibilidade(catalogo, registro=registro)
        estado = cls(
            relogio=relogio,
            catalogo=catalogo,
            destinos=DestinosPhoton() if busca_destinos == "photon" else DestinosMock(),
            rotas=RotasEstimadas(),
            disponibilidade=disponibilidade,
            reservas=ServicoReservas(catalogo),
            sessoes=ServicoSessoes(catalogo, disponibilidade, distancia_maxima_m, registro),
            reportes=ServicoReportes(catalogo, disponibilidade, distancia_maxima_m, registro),
            mapeamento=ServicoMapeamento(catalogo, distancia_maxima_m, registro),
            levantamento=ServicoLevantamento(catalogo, disponibilidade, distancia_maxima_m, registro),
            registro=registro,
        )
        if semear:
            estado._semear_sinais()
        estado._restaurar()
        return estado

    def _restaurar(self) -> None:
        """Reaplica as ações gravadas, na ordem e com o horário original."""
        self.registro.restaurando = True
        aplicados = ignorados = 0
        try:
            for tipo, d in self.registro.eventos():
                try:
                    self._aplicar(tipo, d)
                    aplicados += 1
                except ErroNegocio:
                    ignorados += 1  # ex.: trecho que deixou de existir ao regenerar os dados do OSM
        finally:
            self.registro.restaurando = False
        if aplicados or ignorados:
            print(f"Restauradas {aplicados} ações do banco ({ignorados} ignoradas)", file=sys.stderr)

    def _aplicar(self, tipo: str, d: dict) -> None:
        quando, usuario = d["quando"], d.get("usuario_id")
        if tipo == "sinal":
            self.disponibilidade.registrar(Sinal(alvo_id=d["alvo_id"], fonte=d["fonte"], criado_em=quando,
                                                 vagas_livres=d["vagas_livres"], livre=d["livre"],
                                                 usuario_id=usuario), gravar=False)
        elif tipo == "reporte_trecho":
            self.mapeamento.reportar_trecho(d["trecho_id"], usuario, d["tipo"], 0, 0, quando)
        elif tipo == "reporte_estacionamento":
            self.mapeamento.reportar_estacionamento(d["estacionamento_id"], usuario, d["tipo"], 0, 0, quando,
                                                    d.get("preco_hora"))
        elif tipo == "sugestao":
            self.mapeamento.sugerir_estacionamento(usuario, d["nome"], d["lat"], d["lng"], quando,
                                                   d.get("preco_hora"), sugestao_id=d["sugestao_id"])
        elif tipo == "sessao_iniciada":
            self.sessoes.iniciar(d["alvo_id"], usuario, d["placa"], d["duracao_min"], quando, d["lat"], d["lng"],
                                 sessao_id=d["sessao_id"])
        elif tipo == "sessao_estendida":
            self.sessoes.estender(d["sessao_id"], usuario, d["minutos"], quando)
        elif tipo == "sessao_encerrada":
            self.sessoes.encerrar(d["sessao_id"], usuario, quando)
        elif tipo == "chegada":
            self.reportes.registrar_chegada(d["alvo_id"], usuario, d["encontrou"], quando)
        elif tipo == "contagem":
            self.levantamento.contar(d["trecho_id"], usuario, d["vagas_livres"], quando, d["lat"], d["lng"])

    def _semear_sinais(self) -> None:
        agora = self.relogio()
        for s in json.loads((PASTA_MOCK / "sinais_iniciais.json").read_text(encoding="utf-8")):
            self.disponibilidade.registrar(Sinal(
                alvo_id=s["alvo_id"],
                fonte=s["fonte"],
                criado_em=agora - timedelta(minutes=s["minutos_atras"]),
                vagas_livres=s.get("vagas_livres"),
                livre=s.get("livre"),
            ), gravar=False)


def obter_estado(request: Request) -> Estado:
    return request.app.state.estado


def obter_usuario(x_usuario_id: str = Header(default="demo")) -> str:
    """Sem login no MVP: o app manda um id fixo. Depois: validar o JWT do Supabase Auth."""
    return x_usuario_id
