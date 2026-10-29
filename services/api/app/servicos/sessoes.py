"""Sessões de estacionamento com pagamento SIMULADO.

No MVP nada é cobrado de verdade. Depois:
- estacionamentos privados → gateway com Pix/cartão e split da comissão;
- EstaR → app homologado pela URBS (no MVP o app só abre um app homologado).
Ao encerrar uma sessão de rua, a vaga vira um sinal "vaga liberada" para outros usuários.
Só dá para iniciar uma sessão estando perto da vaga (padrão: 300 m), como no EstaR real,
em que o app de pagamento pede a localização do carro.
"""

import re
import secrets
import threading
from datetime import datetime, timedelta
from typing import Optional

from app.catalogo import Catalogo
from app.servicos.proximidade import exigir_proximidade
from app.erros import ErroNegocio
from app.modelos import Sessao
from app.persistencia import Registro
from app.servicos import regras
from app.servicos.disponibilidade import ServicoDisponibilidade, Sinal

PLACA_VALIDA = re.compile(r"^[A-Z]{3}-?\d[A-Z0-9]\d{2}$")  # antiga (ABC-1234) ou Mercosul (ABC1D23)


class ServicoSessoes:
    def __init__(self, catalogo: Catalogo, disponibilidade: ServicoDisponibilidade, distancia_maxima_m: float,
                 registro: Registro) -> None:
        self._catalogo = catalogo
        self._registro = registro
        self._distancia_maxima_m = distancia_maxima_m
        self._disponibilidade = disponibilidade
        self._sessoes: dict[str, Sessao] = {}
        self._lock = threading.Lock()

    def _preco(self, alvo_id: str, inicio: datetime, duracao_min: int) -> tuple[str, Optional[float]]:
        trecho = self._catalogo.trecho(alvo_id)
        if trecho:
            setor = self._catalogo.setor(trecho.setor_id)
            avaliacao = regras.avaliar_rua(setor, inicio, duracao_min, trecho.regime)
            if not avaliacao.permitido:
                raise ErroNegocio(avaliacao.motivo, 422)
            return "rua", avaliacao.preco
        est = self._catalogo.estacionamento(alvo_id)
        if est and est.ativo:
            return "estacionamento", regras.preco_estacionamento(est, duracao_min)
        raise ErroNegocio("Vaga não encontrada", 404)

    def iniciar(self, alvo_id: str, usuario_id: str, placa: str, duracao_min: int, agora: datetime,
                lat: float, lng: float, sessao_id: Optional[str] = None) -> Sessao:
        placa = placa.strip().upper()
        if not PLACA_VALIDA.match(placa):
            raise ErroNegocio("Placa inválida (use ABC1D23 ou ABC-1234)", 422)
        if not self._registro.restaurando:
            exigir_proximidade(self._catalogo, alvo_id, lat, lng, self._distancia_maxima_m, "iniciar o estacionamento")
        tipo, valor = self._preco(alvo_id, agora, duracao_min)
        with self._lock:
            if any(s.usuario_id == usuario_id and s.status == "ativa" for s in self._sessoes.values()):
                raise ErroNegocio("Você já tem uma sessão ativa", 409)
            sessao = Sessao(
                id=sessao_id or f"ses-{secrets.token_hex(4)}", tipo=tipo, alvo_id=alvo_id, usuario_id=usuario_id,
                placa=placa, inicio=agora, fim_previsto=agora + timedelta(minutes=duracao_min),
                valor_pago=valor, status="ativa",
            )
            self._sessoes[sessao.id] = sessao
        self._registro.gravar("sessao_iniciada", sessao_id=sessao.id, alvo_id=alvo_id, usuario_id=usuario_id,
                              placa=placa, duracao_min=duracao_min, quando=agora, lat=lat, lng=lng)
        return sessao

    def _da_pessoa(self, sessao_id: str, usuario_id: str) -> Sessao:
        sessao = self._sessoes.get(sessao_id)
        if sessao is None:
            raise ErroNegocio("Sessão não encontrada", 404)
        if sessao.usuario_id != usuario_id:
            raise ErroNegocio("Sessão de outro usuário", 403)
        if sessao.status != "ativa":
            raise ErroNegocio("Sessão já encerrada", 409)
        return sessao

    def estender(self, sessao_id: str, usuario_id: str, minutos: int, agora: datetime) -> Sessao:
        with self._lock:
            sessao = self._da_pessoa(sessao_id, usuario_id)
            nova_duracao = int((sessao.fim_previsto - sessao.inicio).total_seconds() / 60) + minutos
            _, valor_total = self._preco(sessao.alvo_id, sessao.inicio, nova_duracao)
            sessao.fim_previsto = sessao.inicio + timedelta(minutes=nova_duracao)
            sessao.valor_pago = valor_total
        self._registro.gravar("sessao_estendida", sessao_id=sessao_id, usuario_id=usuario_id, minutos=minutos,
                              quando=agora)
        return sessao

    def encerrar(self, sessao_id: str, usuario_id: str, agora: datetime) -> Sessao:
        with self._lock:
            sessao = self._da_pessoa(sessao_id, usuario_id)
            sessao.status = "encerrada"
        self._registro.gravar("sessao_encerrada", sessao_id=sessao_id, usuario_id=usuario_id, quando=agora)
        if sessao.tipo == "rua" and not self._registro.restaurando:  # o sinal já foi gravado à parte
            self._disponibilidade.registrar(
                Sinal(alvo_id=sessao.alvo_id, fonte="saida", criado_em=agora, livre=True, usuario_id=usuario_id)
            )
        return sessao

    def ativa_do_usuario(self, usuario_id: str) -> Sessao | None:
        with self._lock:
            return next((s for s in self._sessoes.values()
                         if s.usuario_id == usuario_id and s.status == "ativa"), None)
