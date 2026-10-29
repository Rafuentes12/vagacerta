import os
from datetime import datetime, timedelta

# Testes não gravam em disco nem acessam a internet.
os.environ["VAGACERTA_BANCO"] = ""
os.environ["VAGACERTA_DESTINOS"] = "mock"

import pytest
from fastapi.testclient import TestClient

from app.config import FUSO
from app.main import criar_app

TERCA_10H30 = datetime(2026, 10, 20, 10, 30, tzinfo=FUSO)


class RelogioControlado:
    def __init__(self, inicio: datetime) -> None:
        self.agora = inicio

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, minutos: float) -> None:
        self.agora += timedelta(minutes=minutos)


@pytest.fixture
def relogio() -> RelogioControlado:
    return RelogioControlado(TERCA_10H30)


@pytest.fixture
def app(relogio):
    return criar_app(relogio=relogio)


@pytest.fixture
def cliente(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def estado(app):
    return app.state.estado
