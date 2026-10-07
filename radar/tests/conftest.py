"""Fixtures compartilhadas: o site sintético servido em localhost para os testes da captura."""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

import pytest

SITE_SINTETICO = Path(__file__).parent / "fixtures" / "site_sintetico"


class Pedido(NamedTuple):
    """O que o servidor viu de uma requisição: caminho (com query) e `User-Agent`."""

    caminho: str
    user_agent: str


class _Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.pedidos.append(Pedido(self.path, self.headers.get("User-Agent", "")))
        if self.path == "/inicio":
            # a URL que o usuário digitou redireciona para a página de verdade
            self.send_response(302)
            self.send_header("Location", "/index.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/baixar":
            # download disfarçado de link comum: sem extensão, só o cabeçalho denuncia
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="contrato.bin"')
            self.send_header("Content-Length", "3")
            self.end_headers()
            self.wfile.write(b"abc")
            return
        super().do_GET()

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - assinatura da stdlib
        pass  # a saída dos testes fica limpa


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), partial(_Handler, directory=str(SITE_SINTETICO)))
        self.pedidos: list[Pedido] = []


@pytest.fixture
def _servidor_local():
    servidor = _Servidor()
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        yield servidor
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=5)


@pytest.fixture
def servidor_local(_servidor_local) -> str:
    """URL base (`http://127.0.0.1:<porta>`) do site sintético, numa porta livre."""
    return f"http://127.0.0.1:{_servidor_local.server_port}"


@pytest.fixture
def pedidos_locais(_servidor_local) -> list[Pedido]:
    """As requisições que o servidor local recebeu, em ordem."""
    return _servidor_local.pedidos
