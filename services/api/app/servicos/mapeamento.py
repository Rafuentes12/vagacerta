"""Mapeamento colaborativo: os motoristas corrigem e completam o mapa de vagas.

- Trecho de rua: "tem EstaR", "sem EstaR" ou "proibido estacionar".
- Estacionamento: "fechou" ou "preço por hora".
- Estacionamento que falta no mapa: sugestão feita no local.

Uma resposta só muda o mapa quando CONFIRMACOES_NECESSARIAS usuários diferentes concordam
(e ela supera as respostas contrárias). Cada usuário conta uma vez: vale a resposta mais
recente dele. Todas as ações exigem estar perto do local (antifraude simples).
"""

import secrets
import statistics
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.catalogo import Catalogo
from app.erros import ErroNegocio
from app.geo import distancia_m
from app.modelos import (
    Atributos,
    Estacionamento,
    ResultadoMapeamento,
    ResultadoSugestao,
    SugestaoEstacionamento,
    TipoReporteEstacionamento,
    TipoReporteTrecho,
)
from app.persistencia import Registro
from app.servicos.proximidade import exigir_proximidade

CONFIRMACOES_NECESSARIAS = 2
JANELA_VALIDADE = timedelta(days=90)
INTERVALO_REPETICAO = timedelta(minutes=10)
RAIO_MESMO_LOCAL_M = 60        # sugestões a até 60 m uma da outra são do mesmo estacionamento
RAIO_JA_CADASTRADO_M = 40
PRECO_MAXIMO_HORA = 100.0
CAPACIDADE_PADRAO_SUGERIDO = 20

REGIME_DA_RESPOSTA = {"tem_estar": "estar", "sem_estar": "livre", "proibido": "proibido"}
TEXTO_DA_RESPOSTA = {"tem_estar": "tem EstaR", "sem_estar": "não tem EstaR", "proibido": "é proibido estacionar"}


@dataclass
class _Reporte:
    usuario_id: str
    tipo: str
    quando: datetime
    valor: Optional[float] = None


def _ultimas_por_usuario(reportes: list[_Reporte], agora: datetime) -> dict[str, _Reporte]:
    ultimas: dict[str, _Reporte] = {}
    for r in reportes:
        if agora - r.quando <= JANELA_VALIDADE:
            ultimas[r.usuario_id] = r  # a lista está em ordem cronológica
    return ultimas


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


class ServicoMapeamento:
    def __init__(self, catalogo: Catalogo, distancia_maxima_m: float, registro: Optional[Registro] = None) -> None:
        self._catalogo = catalogo
        self._registro = registro or Registro(None)
        self._distancia_maxima_m = distancia_maxima_m
        self._trechos: dict[str, list[_Reporte]] = {}
        self._estacionamentos: dict[str, list[_Reporte]] = {}
        self._sugestoes: list[SugestaoEstacionamento] = []
        self._lock = threading.Lock()

    def _evitar_repeticao(self, reportes: list[_Reporte], usuario_id: str, tipo: str, agora: datetime) -> None:
        if not self._registro.restaurando and any(r.usuario_id == usuario_id and r.tipo == tipo and agora - r.quando < INTERVALO_REPETICAO
               for r in reportes):
            raise ErroNegocio("Você já enviou essa informação há pouco. Obrigado!", 429)

    # --- Trechos de rua -------------------------------------------------------------------

    def reportar_trecho(self, trecho_id: str, usuario_id: str, tipo: TipoReporteTrecho,
                        lat: float, lng: float, agora: datetime) -> ResultadoMapeamento:
        if self._catalogo.trecho(trecho_id) is None:
            raise ErroNegocio("Trecho não encontrado", 404)
        if not self._registro.restaurando:
            exigir_proximidade(self._catalogo, trecho_id, lat, lng, self._distancia_maxima_m, "mapear este trecho")

        with self._lock:
            reportes = self._trechos.setdefault(trecho_id, [])
            self._evitar_repeticao(reportes, usuario_id, tipo, agora)
            reportes.append(_Reporte(usuario_id, tipo, agora))
            contagem = Counter(r.tipo for r in _ultimas_por_usuario(reportes, agora).values())
        self._registro.gravar("reporte_trecho", trecho_id=trecho_id, usuario_id=usuario_id, tipo=tipo, quando=agora)

        lider, votos = contagem.most_common(1)[0]
        segundo = contagem.most_common(2)[1][1] if len(contagem) > 1 else 0
        aplicado = False
        if votos >= CONFIRMACOES_NECESSARIAS and votos > segundo:
            trecho = self._catalogo.trecho(trecho_id)
            novo_regime = REGIME_DA_RESPOSTA[lider]
            if trecho.regime != novo_regime or trecho.situacao != "confirmado_usuarios":
                self._catalogo.atualizar_trecho(
                    trecho_id, regime=novo_regime, situacao="confirmado_usuarios",
                    fonte=f"Confirmado por {votos} usuários em {agora:%d/%m/%Y}",
                )
                aplicado = True

        faltam = max(0, CONFIRMACOES_NECESSARIAS - contagem[tipo])
        if aplicado:
            mensagem = f"Mapa atualizado: este trecho {TEXTO_DA_RESPOSTA[lider]}."
        elif faltam:
            mensagem = f"Obrigado! Falta {_plural(faltam, 'confirmação', 'confirmações')} de outros motoristas."
        else:
            mensagem = "Obrigado! Há respostas diferentes para este trecho; vale a da maioria."
        return ResultadoMapeamento(registrado=True, contagem=dict(contagem), aplicado=aplicado,
                                   faltam=faltam, mensagem=mensagem)

    # --- Estacionamentos ------------------------------------------------------------------

    def reportar_estacionamento(self, estacionamento_id: str, usuario_id: str, tipo: TipoReporteEstacionamento,
                                lat: float, lng: float, agora: datetime,
                                preco_hora: Optional[float] = None) -> ResultadoMapeamento:
        est = self._catalogo.estacionamento(estacionamento_id)
        if est is None or not est.ativo:
            raise ErroNegocio("Estacionamento não encontrado", 404)
        if est.parceiro_id:
            raise ErroNegocio("Este estacionamento é parceiro: os dados vêm dele mesmo", 422)
        if tipo == "preco" and (preco_hora is None or not 0 <= preco_hora <= PRECO_MAXIMO_HORA):
            raise ErroNegocio(f"Informe um preço por hora entre R$ 0 e R$ {PRECO_MAXIMO_HORA:.0f}", 422)
        if not self._registro.restaurando:
            exigir_proximidade(self._catalogo, estacionamento_id, lat, lng, self._distancia_maxima_m,
                               "informar dados deste estacionamento")

        with self._lock:
            reportes = self._estacionamentos.setdefault(estacionamento_id, [])
            self._evitar_repeticao(reportes, usuario_id, tipo, agora)
            reportes.append(_Reporte(usuario_id, tipo, agora, preco_hora))
            self._registro.gravar("reporte_estacionamento", estacionamento_id=estacionamento_id,
                                  usuario_id=usuario_id, tipo=tipo, preco_hora=preco_hora, quando=agora)
            ultimas = {}
            for r in reportes:  # última resposta de cada usuário, por tipo
                if agora - r.quando <= JANELA_VALIDADE:
                    ultimas[(r.usuario_id, r.tipo)] = r
        do_tipo = [r for (_, t), r in ultimas.items() if t == tipo]

        if tipo == "preco":
            mediana = round(statistics.median(r.valor for r in do_tipo), 2)
            self._catalogo.atualizar_estacionamento(
                estacionamento_id, preco_hora=mediana, preco_diaria=None,
                fonte_preco=f"informado por {_plural(len(do_tipo), 'usuário', 'usuários')}",
            )
            return ResultadoMapeamento(
                registrado=True, contagem={"preco": len(do_tipo)}, aplicado=True, faltam=0,
                mensagem=f"Obrigado! Preço exibido agora: R$ {mediana:.2f}/h".replace(".", ","),
            )

        faltam = max(0, CONFIRMACOES_NECESSARIAS - len(do_tipo))
        if not faltam:
            self._catalogo.atualizar_estacionamento(estacionamento_id, ativo=False)
        return ResultadoMapeamento(
            registrado=True, contagem={"fechado": len(do_tipo)}, aplicado=not faltam, faltam=faltam,
            mensagem=("Obrigado! Este estacionamento saiu do mapa." if not faltam else
                      f"Obrigado! Falta {_plural(faltam, 'confirmação', 'confirmações')} para tirá-lo do mapa."),
        )

    # --- Estacionamentos que faltam no mapa ------------------------------------------------

    def sugerir_estacionamento(self, usuario_id: str, nome: str, lat: float, lng: float, agora: datetime,
                               preco_hora: Optional[float] = None,
                               sugestao_id: Optional[str] = None) -> ResultadoSugestao:
        nome = nome.strip()
        if len(nome) < 3:
            raise ErroNegocio("Informe o nome do estacionamento", 422)
        if preco_hora is not None and not 0 <= preco_hora <= PRECO_MAXIMO_HORA:
            raise ErroNegocio(f"Informe um preço por hora entre R$ 0 e R$ {PRECO_MAXIMO_HORA:.0f}", 422)
        for est in self._catalogo.estacionamentos():
            if est.ativo and distancia_m(lat, lng, est.lat, est.lng) <= RAIO_JA_CADASTRADO_M:
                raise ErroNegocio(f"Já existe um estacionamento aqui: {est.nome}", 409)

        with self._lock:
            pendentes = [s for s in self._sugestoes if s.status == "pendente"
                         and agora - s.criada_em <= JANELA_VALIDADE
                         and distancia_m(lat, lng, s.lat, s.lng) <= RAIO_MESMO_LOCAL_M]
            if any(s.usuario_id == usuario_id for s in pendentes):
                raise ErroNegocio("Você já sugeriu este estacionamento. Falta outro motorista confirmar.", 409)
            nova = SugestaoEstacionamento(
                id=sugestao_id or f"sug-{secrets.token_hex(4)}", usuario_id=usuario_id, nome=nome, lat=lat, lng=lng,
                preco_hora=preco_hora, criada_em=agora, status="pendente",
            )
            self._sugestoes.append(nova)
            self._registro.gravar("sugestao", sugestao_id=nova.id, usuario_id=usuario_id, nome=nome, lat=lat,
                                  lng=lng, preco_hora=preco_hora, quando=agora)
            grupo = pendentes + [nova]
            usuarios = {s.usuario_id for s in grupo}
            faltam = max(0, CONFIRMACOES_NECESSARIAS - len(usuarios))
            if faltam:
                return ResultadoSugestao(
                    status="pendente", faltam=faltam,
                    mensagem=f"Obrigado! O estacionamento aparece no mapa quando mais "
                             f"{_plural(faltam, 'motorista confirmar', 'motoristas confirmarem')}.",
                )
            for s in grupo:
                s.status = "confirmada"

        precos = [s.preco_hora for s in grupo if s.preco_hora is not None]
        estacionamento = Estacionamento(
            id=nova.id,
            nome=Counter(s.nome for s in grupo).most_common(1)[0][0],
            endereco="Informado por usuários",
            lat=round(statistics.fmean(s.lat for s in grupo), 6),
            lng=round(statistics.fmean(s.lng for s in grupo), 6),
            capacidade=CAPACIDADE_PADRAO_SUGERIDO,
            capacidade_estimada=True,
            preco_hora=round(statistics.median(precos), 2) if precos else None,
            fonte_preco=f"informado por {_plural(len(precos), 'usuário', 'usuários')}" if precos else None,
            setor_referencia=self._setor_mais_proximo(lat, lng),
            atributos=Atributos(coberto=False, altura_max_m=None, recarga_ev=False, vagas_pcd=False),
            fonte=f"Sugerido por {len(usuarios)} usuários",
            situacao="confirmado_usuarios",
        )
        self._catalogo.adicionar_estacionamento(estacionamento)
        return ResultadoSugestao(status="confirmada", faltam=0, estacionamento=estacionamento,
                                 mensagem="Obrigado! O estacionamento já aparece no mapa.")

    def sugestoes_pendentes(self) -> list[SugestaoEstacionamento]:
        with self._lock:
            return [s for s in self._sugestoes if s.status == "pendente"]

    def _setor_mais_proximo(self, lat: float, lng: float) -> str:
        trechos = self._catalogo.trechos()
        if not trechos:
            return "centro"
        return min(trechos, key=lambda t: distancia_m(lat, lng, t.lat, t.lng)).setor_id
