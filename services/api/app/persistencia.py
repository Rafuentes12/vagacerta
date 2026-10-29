"""Registro persistente das ações dos usuários (SQLite).

Cada ação aceita pela API (reporte, mapeamento, sessão, contagem, "encontrou a vaga?") é
gravada como um evento. Ao iniciar, a API reaplica os eventos pelos mesmos serviços —
assim as regras (consenso, mediana de preço, sessões) continuam num lugar só, e um
reinício não apaga mais o que os motoristas contribuíram.

Durante a reaplicação (`restaurando = True`) os serviços pulam as checagens que dependem
do momento original (proximidade, intervalo entre reportes) e nada é gravado de novo.
"""

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Iterator, Optional


class Registro:
    def __init__(self, caminho: Optional[str]) -> None:
        """`caminho` vazio ou None: não persiste nada (testes)."""
        self.restaurando = False
        self._lock = threading.Lock()
        self._con: Optional[sqlite3.Connection] = None
        if caminho:
            self._con = sqlite3.connect(caminho, check_same_thread=False)
            self._con.execute(
                "CREATE TABLE IF NOT EXISTS eventos ("
                " seq INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, dados TEXT NOT NULL)"
            )
            self._con.commit()

    @property
    def ativo(self) -> bool:
        return self._con is not None

    def gravar(self, evento: str, **dados: Any) -> None:
        if self._con is None or self.restaurando:
            return
        texto = json.dumps(dados, default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v))
        with self._lock:
            self._con.execute("INSERT INTO eventos (tipo, dados) VALUES (?, ?)", (evento, texto))
            self._con.commit()

    def eventos(self) -> Iterator[tuple[str, dict]]:
        if self._con is None:
            return
        with self._lock:
            linhas = self._con.execute("SELECT tipo, dados FROM eventos ORDER BY seq").fetchall()
        for tipo, texto in linhas:
            dados = json.loads(texto)
            if "quando" in dados:
                dados["quando"] = datetime.fromisoformat(dados["quando"])
            yield tipo, dados
