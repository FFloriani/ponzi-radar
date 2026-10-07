"""Fixtures compartilhadas: o site sintético servido em localhost para os testes da captura."""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

import pytest

SITE_SINTETICO = Path(__file__).parent / "fixtures" / "site_sintetico"
# /status/<código>[/<arquivo>]: responde com esse status (e o arquivo do site, ou uma página de erro)
_STATUS = re.compile(r"/status/(\d{3})(?:/([\w.\-]+))?")
# /mitigado/<arquivo>: o arquivo com status 200 e o cabeçalho `cf-mitigated: challenge` da Cloudflare
_MITIGADO = re.compile(r"/mitigado/([\w.\-]+)")
_PAGINA_DE_ERRO = (
    "<!doctype html><html><head><meta charset='utf-8'><title>Erro</title></head>"
    "<body>Página de erro do servidor.</body></html>"
)


class Pedido(NamedTuple):
    """O que o servidor viu de uma requisição: caminho (com query) e `User-Agent`."""

    caminho: str
    user_agent: str


class _Handler(SimpleHTTPRequestHandler):
    def _responder_html(self, status: int, corpo: bytes, cabecalhos: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        for nome, valor in (cabecalhos or {}).items():
            self.send_header(nome, valor)
        self.end_headers()
        self.wfile.write(corpo)

    def _redirecionar(self, destino: str) -> None:
        self.send_response(302)
        self.send_header("Location", destino)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self.server.pedidos.append(Pedido(self.path, self.headers.get("User-Agent", "")))
        caminho = self.path.partition("?")[0]
        if caminho == "/inicio":
            # a URL que o usuário digitou redireciona para a página de verdade
            self._redirecionar("/index.html")
            return
        if caminho == "/saida":
            # redireciona para outro host (localhost em vez de 127.0.0.1): como um golpe que manda para o Telegram
            self._redirecionar(f"http://localhost:{self.server.server_port}/index.html")
            return
        if achado := _STATUS.fullmatch(caminho):
            arquivo = achado.group(2)
            corpo = (SITE_SINTETICO / arquivo).read_bytes() if arquivo else _PAGINA_DE_ERRO.encode()
            self._responder_html(int(achado.group(1)), corpo)
            return
        if achado := _MITIGADO.fullmatch(caminho):
            corpo = (SITE_SINTETICO / achado.group(1)).read_bytes()
            self._responder_html(200, corpo, {"cf-mitigated": "challenge"})
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


class _HandlerDoProxy(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.requisicoes.append(self.path)  # a URL absoluta, como um proxy HTTP a recebe
        corpo = (
            "<!doctype html><html><head><meta charset='utf-8'><title>Via proxy</title></head>"
            "<body>Conteúdo servido pelo proxy.</body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - assinatura da stdlib
        pass


class _Proxy(ThreadingHTTPServer):
    """Proxy HTTP de mentira: responde a qualquer GET com uma página própria e guarda as URLs pedidas."""

    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _HandlerDoProxy)
        self.requisicoes: list[str] = []


@contextmanager
def _em_thread(servidor):
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        yield servidor
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=5)


@pytest.fixture
def _servidor_local():
    with _em_thread(_Servidor()) as servidor:
        yield servidor


@pytest.fixture
def proxy_local():
    """Um proxy HTTP em 127.0.0.1 que responde a tudo com a mesma página; `.requisicoes` são as URLs pedidas."""
    with _em_thread(_Proxy()) as proxy:
        yield proxy


@pytest.fixture
def servidor_local(_servidor_local) -> str:
    """URL base (`http://127.0.0.1:<porta>`) do site sintético, numa porta livre."""
    return f"http://127.0.0.1:{_servidor_local.server_port}"


@pytest.fixture
def pedidos_locais(_servidor_local) -> list[Pedido]:
    """As requisições que o servidor local recebeu, em ordem."""
    return _servidor_local.pedidos
