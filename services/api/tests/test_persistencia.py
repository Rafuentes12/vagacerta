"""As ações dos usuários sobrevivem a um reinício da API (SQLite)."""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.main import criar_app
from app.provedores.destinos import DestinosPhoton, _destino_do_photon
from tests.conftest import TERCA_10H30

PERTO_DA_T05 = {"lat": -25.4311, "lng": -49.2770}
LONGE = {"lat": -25.4500, "lng": -49.2500}


def usuario(nome):
    return {"X-Usuario-Id": nome}


@pytest.fixture
def banco(tmp_path):
    return str(tmp_path / "vagacerta.db")


def nova_api(banco, relogio):
    return TestClient(criar_app(relogio=relogio, banco=banco, busca_destinos="mock"))


def test_acoes_voltam_depois_de_reiniciar(banco, relogio):
    api = nova_api(banco, relogio)
    estado = api.app.state.estado
    trecho = next(t for t in estado.catalogo.trechos() if t.regime == "a_confirmar")
    perto_trecho = {"lat": trecho.coordenadas[0][0], "lng": trecho.coordenadas[0][1]}
    est = next(e for e in estado.catalogo.estacionamentos() if e.id.startswith("osm-"))
    perto_est = {"lat": est.lat, "lng": est.lng}

    for quem in ("ana", "bia"):
        api.post(f"/mapeamento/trechos/{trecho.id}", json={"tipo": "tem_estar", **perto_trecho}, headers=usuario(quem))
    api.post(f"/mapeamento/estacionamentos/{est.id}", json={"tipo": "preco", "preco_hora": 15, **perto_est},
             headers=usuario("ana"))
    sessao = api.post("/sessoes", json={"alvo_id": "t-05", "placa": "ABC1D23", "duracao_min": 60, **PERTO_DA_T05},
                      headers=usuario("caio")).json()
    api.post(f"/sessoes/{sessao['id']}/estender", json={"minutos": 30}, headers=usuario("caio"))
    api.post("/chegadas", json={"alvo_id": "t-01", "encontrou": True})
    api.post("/levantamento/contagens", json={"trecho_id": "t-05", "vagas_livres": 2, **PERTO_DA_T05})

    # "Reinicia" a API: novo processo, mesmo banco.
    api2 = nova_api(banco, relogio)
    estado2 = api2.app.state.estado
    assert estado2.catalogo.trecho(trecho.id).regime == "estar"
    assert estado2.catalogo.trecho(trecho.id).situacao == "confirmado_usuarios"
    assert estado2.catalogo.estacionamento(est.id).preco_hora == 15
    ativa = api2.get("/sessoes/ativa", headers=usuario("caio")).json()
    assert ativa["id"] == sessao["id"] and ativa["valor_pago"] == 6.0  # 1 h 30 de EstaR
    assert api2.get("/metricas").json()["chegadas_avaliadas"] == 1
    assert estado2.levantamento.total() == 1
    assert estado2.disponibilidade.estado("t-05", TERCA_10H30).fonte == "equipe"


def test_sessao_encerrada_continua_encerrada(banco, relogio):
    api = nova_api(banco, relogio)
    sessao = api.post("/sessoes", json={"alvo_id": "t-05", "placa": "ABC1D23", "duracao_min": 60, **PERTO_DA_T05}).json()
    api.post(f"/sessoes/{sessao['id']}/encerrar")
    api2 = nova_api(banco, relogio)
    assert api2.get("/sessoes/ativa").json() is None


def test_sugestao_confirmada_reaparece_com_o_mesmo_id(banco, relogio):
    api = nova_api(banco, relogio)
    local = {"lat": -25.4460, "lng": -49.2930}
    api.post("/mapeamento/sugestoes", json={"nome": "Estacionamento Teste", **local}, headers=usuario("ana"))
    criado = api.post("/mapeamento/sugestoes", json={"nome": "Estacionamento Teste", **local},
                      headers=usuario("bia")).json()["estacionamento"]
    api2 = nova_api(banco, relogio)
    assert api2.app.state.estado.catalogo.estacionamento(criado["id"]) is not None


def test_sem_banco_nada_e_gravado(relogio):
    api = TestClient(criar_app(relogio=relogio, banco=""))
    assert api.get("/saude").json()["persistencia"] is False


# --- Levantamento -----------------------------------------------------------------------------------


def test_contagem_vira_sinal_ao_vivo_e_entra_no_csv(cliente):
    r = cliente.post("/levantamento/contagens", json={"trecho_id": "t-05", "vagas_livres": 3, **PERTO_DA_T05})
    assert r.status_code == 201
    vaga = next(v for v in cliente.get("/vagas", params={**PERTO_DA_T05, "raio_m": 300}).json() if v["id"] == "t-05")
    assert vaga["estado"]["ao_vivo"] and vaga["estado"]["rotulo"].startswith("3 vagas · contagem da equipe")

    linhas = list(csv.DictReader(io.StringIO(cliente.get("/levantamento/contagens.csv").text)))
    assert len(linhas) == 1
    assert linhas[0]["trecho_id"] == "t-05" and linhas[0]["vagas_livres_contadas"] == "3"
    assert linhas[0]["nivel_modelo"] in ("facil", "moderado", "dificil")


def test_contagem_exige_estar_perto(cliente):
    r = cliente.post("/levantamento/contagens", json={"trecho_id": "t-05", "vagas_livres": 3, **LONGE})
    assert r.status_code == 422


# --- Busca de destino (Photon) ----------------------------------------------------------------------


def test_photon_converte_resultado_em_destino():
    feature = {"geometry": {"coordinates": [-49.29, -25.44]},
               "properties": {"name": "Hospital Exemplo", "street": "Rua X", "housenumber": "10",
                              "district": "Batel", "city": "Curitiba", "osm_type": "W", "osm_id": 123}}
    destino = _destino_do_photon(feature)
    assert destino.nome == "Hospital Exemplo" and destino.endereco == "Rua X 10, Batel, Curitiba"
    assert (destino.lat, destino.lng) == (-25.44, -49.29) and destino.id == "osm-W123"


def test_photon_fora_do_ar_usa_a_lista_fixa(monkeypatch):
    busca = DestinosPhoton()

    def falha(*_):
        raise OSError("sem internet")

    monkeypatch.setattr(busca, "_consultar", falha)
    assert [d.nome for d in busca.buscar("guaira")] == ["Teatro Guaíra"]
