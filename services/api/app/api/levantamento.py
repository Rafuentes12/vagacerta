"""Modo levantamento: contagens de campo da equipe e exportação para calibrar o modelo."""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.estado import Estado, obter_estado, obter_usuario

router = APIRouter(prefix="/levantamento", tags=["levantamento de campo"])


class NovaContagem(BaseModel):
    trecho_id: str
    vagas_livres: int = Field(ge=0)
    lat: float  # posição atual: precisa estar perto do trecho
    lng: float


@router.post("/contagens", status_code=201)
def contar(dados: NovaContagem, usuario: str = Depends(obter_usuario), estado: Estado = Depends(obter_estado)):
    """Vagas livres contadas agora num trecho. Vira um sinal ao vivo no mapa."""
    estado.levantamento.contar(dados.trecho_id, usuario, dados.vagas_livres, estado.relogio(), dados.lat, dados.lng)
    return {"registrado": True, "total_de_contagens": estado.levantamento.total()}


@router.get("/contagens.csv", response_class=PlainTextResponse)
def exportar(estado: Estado = Depends(obter_estado)):
    """Contagens com a previsão do modelo no mesmo horário (abre no Excel ou Google Sheets)."""
    return PlainTextResponse(
        estado.levantamento.exportar_csv(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="contagens_vagacerta.csv"'},
    )
