"""Busca de destinos (endereços e pontos de interesse).

- `DestinosPhoton`: busca real com o Photon (geocodificador gratuito sobre o OpenStreetMap),
  limitada a Curitiba. Se o Photon falhar, cai para a lista fixa.
- `DestinosMock`: lista fixa de lugares de Curitiba (testes e uso sem internet).

Depois, um `DestinosGooglePlaces` com a mesma interface pode substituir o Photon
(endereços brasileiros costumam ser mais completos no Google).
"""

import json
import sys
import threading
import unicodedata
import urllib.parse
import urllib.request
from typing import Optional, Protocol

from app.catalogo import PASTA_MOCK
from app.modelos import Destino

PHOTON = "https://photon.komoot.io/api/"
USER_AGENT = "VagaCerta-MVP-academico/0.1 (PUCPR)"
CURITIBA_CENTRO = (-25.437, -49.28)
CURITIBA_CAIXA = "-49.40,-25.55,-49.18,-25.33"  # oeste,sul,leste,norte
TAMANHO_MINIMO = 3


class ProvedorDestinos(Protocol):
    def buscar(self, texto: str, limite: int = 5) -> list[Destino]: ...
    def obter(self, destino_id: str) -> Optional[Destino]: ...


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


class DestinosMock:
    def __init__(self) -> None:
        dados = json.loads((PASTA_MOCK / "destinos.json").read_text(encoding="utf-8"))
        self._destinos = [Destino(**d) for d in dados]

    def buscar(self, texto: str, limite: int = 5) -> list[Destino]:
        termo = _normalizar(texto)
        if not termo:
            return self._destinos[:limite]
        achados = [d for d in self._destinos if termo in _normalizar(f"{d.nome} {d.endereco}")]
        return achados[:limite]

    def obter(self, destino_id: str) -> Optional[Destino]:
        return next((d for d in self._destinos if d.id == destino_id), None)


def _destino_do_photon(feature: dict) -> Optional[Destino]:
    p = feature.get("properties", {})
    lng, lat = feature.get("geometry", {}).get("coordinates", (None, None))
    rua = " ".join(x for x in (p.get("street"), p.get("housenumber")) if x)
    nome = p.get("name") or rua
    if not nome or lat is None:
        return None
    partes = [x for x in (rua if p.get("name") else None, p.get("district") or p.get("locality"), p.get("city")) if x]
    return Destino(id=f"osm-{p.get('osm_type', 'X')}{p.get('osm_id', '')}", nome=nome,
                   endereco=", ".join(partes) or "Curitiba", lat=lat, lng=lng)


class DestinosPhoton:
    def __init__(self, reserva: Optional[DestinosMock] = None) -> None:
        self._reserva = reserva or DestinosMock()
        self._vistos: dict[str, Destino] = {}
        self._cache: dict[str, list[Destino]] = {}
        self._lock = threading.Lock()

    def _consultar(self, texto: str, limite: int) -> list[Destino]:
        chave = _normalizar(texto)
        with self._lock:
            if chave in self._cache:
                return self._cache[chave]
        parametros = urllib.parse.urlencode({"q": texto, "limit": limite + 3, "lat": CURITIBA_CENTRO[0],
                                             "lon": CURITIBA_CENTRO[1], "bbox": CURITIBA_CAIXA})
        pedido = urllib.request.Request(f"{PHOTON}?{parametros}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(pedido, timeout=4) as resposta:
            features = json.load(resposta).get("features", [])
        destinos, nomes = [], set()
        for f in features:
            d = _destino_do_photon(f)
            if d and (d.nome, d.endereco) not in nomes:
                nomes.add((d.nome, d.endereco))
                destinos.append(d)
        with self._lock:
            self._cache[chave] = destinos
            self._vistos.update({d.id: d for d in destinos})
        return destinos

    def buscar(self, texto: str, limite: int = 5) -> list[Destino]:
        locais = self._reserva.buscar(texto, limite)
        if len(_normalizar(texto)) < TAMANHO_MINIMO:
            return locais
        try:
            externos = self._consultar(texto, limite)
        except Exception as erro:  # sem internet, Photon fora do ar etc.: segue com a lista fixa
            print(f"Photon indisponível ({erro}); usando a lista fixa", file=sys.stderr)
            return locais
        nomes = {_normalizar(d.nome) for d in locais}
        return (locais + [d for d in externos if _normalizar(d.nome) not in nomes])[:limite]

    def obter(self, destino_id: str) -> Optional[Destino]:
        return self._reserva.obter(destino_id) or self._vistos.get(destino_id)
