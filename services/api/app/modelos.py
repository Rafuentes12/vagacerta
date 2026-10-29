"""Modelos de domínio e de resposta da API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Contexto = Literal["urgencia", "trabalho", "lazer"]
TipoVaga = Literal["comum", "idoso", "pcd", "carga_descarga"]
Credencial = Literal["nenhuma", "idoso", "pcd"]
FonteSinal = Literal["cancela", "atendente", "equipe", "usuario", "saida"]
# Regime de uma vaga de rua: "a_confirmar" = estimada do mapa, pode ser EstaR ou livre.
Regime = Literal["estar", "a_confirmar", "livre", "proibido"]
# De onde vem a classificação. Só "estimado" é desenhado tracejado no app.
Situacao = Literal["mapeado", "fonte_oficial", "estimado", "confirmado_usuarios"]
Acesso = Literal["publico", "clientes"]

# Faixa de horário [hora_inicio, hora_fim) por tipo de dia; None = fechado / sem cobrança.
Horario = dict[str, Optional[tuple[int, int]]]


class Coordenada(BaseModel):
    lat: float
    lng: float


# --- Catálogo ---------------------------------------------------------------


class Setor(BaseModel):
    id: str
    nome: str
    tempo_max_min: int
    preco_fracao_15min: float
    horario_cobranca: Horario


class Trecho(BaseModel):
    id: str
    setor_id: str
    nome: str
    tipo: TipoVaga
    capacidade: int
    coordenadas: list[tuple[float, float]]
    regime: Regime = "estar"
    situacao: Situacao = "mapeado"
    fonte: str = "Dados fictícios do MVP"
    estimativa: Optional[dict] = None  # como a capacidade foi estimada (trechos gerados do OSM)

    @property
    def lat(self) -> float:
        return sum(c[0] for c in self.coordenadas) / len(self.coordenadas)

    @property
    def lng(self) -> float:
        return sum(c[1] for c in self.coordenadas) / len(self.coordenadas)


class Atributos(BaseModel):
    coberto: bool
    altura_max_m: Optional[float]
    recarga_ev: bool
    vagas_pcd: bool


class Estacionamento(BaseModel):
    id: str
    nome: str
    endereco: str
    lat: float
    lng: float
    capacidade: int
    preco_hora: Optional[float] = None    # None = preço não informado
    preco_diaria: Optional[float] = None
    parceiro_id: Optional[str] = None
    aceita_reserva: bool = False
    cota_reserva: int = 0
    setor_referencia: str
    horario: Optional[Horario] = None     # None = horário não informado
    atributos: Atributos
    capacidade_estimada: bool = False
    acesso: Acesso = "publico"
    fonte: str = "Dados fictícios do MVP"
    fonte_preco: Optional[str] = None
    situacao: Situacao = "mapeado"
    ativo: bool = True                    # False quando usuários confirmam que fechou


class Parceiro(BaseModel):
    id: str
    nome: str


class Destino(BaseModel):
    id: str
    nome: str
    endereco: str
    lat: float
    lng: float


# --- Disponibilidade ----------------------------------------------------------


class EstadoVaga(BaseModel):
    prob_livre: float
    vagas_livres_estimadas: int
    confianca: float
    fonte: str
    atualizado_ha_min: Optional[int]
    ao_vivo: bool                  # há sinal recente (parceiro, cancela, usuário)?
    nivel: Literal["facil", "moderado", "dificil"]
    explicacao: Optional[str]      # ex.: "Sexta, 22h · perto de 8 bares, 5 restaurantes"
    rotulo: str


class Descricao(BaseModel):
    """Como a vaga deve ser apresentada: regime, confiabilidade do dado e fonte."""

    regime: Optional[Regime] = None
    situacao: Situacao
    tracejado: bool
    rotulo_regime: str
    fonte: str
    capacidade: int
    capacidade_estimada: bool
    estimativa: Optional[dict] = None
    preco_hora: Optional[float] = None
    acesso: Optional[Acesso] = None
    parceiro: bool = False         # estacionamento parceiro: dados vêm dele, não dos usuários


class VagaNoMapa(Descricao):
    id: str
    tipo: Literal["rua", "estacionamento"]
    nome: str
    lat: float
    lng: float
    tipo_vaga: Optional[TipoVaga] = None
    coordenadas: Optional[list[tuple[float, float]]] = None
    estado: EstadoVaga


# --- Recomendação --------------------------------------------------------------


class Candidato(Descricao):
    id: str
    tipo: Literal["rua", "estacionamento"]
    nome: str
    lat: float
    lng: float
    coordenadas: Optional[list[tuple[float, float]]] = None
    caminhada_m: int
    caminhada_min: int
    tempo_carro_min: Optional[int]
    preco_estimado: Optional[float]  # None = preço não informado
    estado: EstadoVaga
    pode_reservar: bool
    nota: float
    componentes: dict[str, float]
    motivos: list[str]
    avisos: list[str]


class Descartado(BaseModel):
    id: str
    nome: str
    motivo: str


class RespostaRecomendacao(BaseModel):
    destino: Coordenada
    contexto: Contexto
    duracao_min: int
    chegada_prevista: datetime
    candidatos: list[Candidato]
    descartados: list[Descartado]
    mensagem: Optional[str] = None


# --- Reservas, sessões e reportes -----------------------------------------------


class Reserva(BaseModel):
    id: str
    estacionamento_id: str
    usuario_id: str
    codigo: str
    criada_em: datetime
    expira_em: datetime
    status: Literal["ativa", "expirada", "cancelada", "utilizada"]


class Sessao(BaseModel):
    id: str
    tipo: Literal["rua", "estacionamento"]
    alvo_id: str
    usuario_id: str
    placa: str
    inicio: datetime
    fim_previsto: datetime
    valor_pago: Optional[float]  # None = preço não informado (paga direto no estacionamento)
    pagamento: Literal["simulado"] = "simulado"
    status: Literal["ativa", "encerrada"]


class FeedbackChegada(BaseModel):
    alvo_id: str
    usuario_id: str
    encontrou: bool
    registrado_em: datetime


# --- Mapeamento colaborativo -------------------------------------------------------------------

TipoReporteTrecho = Literal["tem_estar", "sem_estar", "proibido"]
TipoReporteEstacionamento = Literal["fechado", "preco"]


class ResultadoMapeamento(BaseModel):
    registrado: bool
    contagem: dict[str, int]       # usuários distintos por resposta
    aplicado: bool                 # a classificação mudou por consenso?
    faltam: int                    # quantas confirmações faltam para a sua resposta valer
    mensagem: str


class SugestaoEstacionamento(BaseModel):
    id: str
    usuario_id: str
    nome: str
    lat: float
    lng: float
    preco_hora: Optional[float]
    criada_em: datetime
    status: Literal["pendente", "confirmada"]


class ResultadoSugestao(BaseModel):
    status: Literal["pendente", "confirmada"]
    faltam: int
    estacionamento: Optional[Estacionamento] = None
    mensagem: str
