"""Único ponto de saída HTTP do radar: limite por host, novas tentativas, cache e proxy."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any, Literal

import httpx

from radar.config import RedeConfig

_TETO_RETRY_AFTER_S = 60.0
_MAX_REDIRECTS = 10
# texto do RemoteProtocolError do httpx quando o `Location` da resposta não é uma URL
_LOCATION_INVALIDO = "Invalid URL in location header"
# cabeçalhos do chamador que não podem acompanhar um redirect para outra origem
_CREDENCIAIS = ("authorization", "cookie")
_RETRY_AFTER = re.compile(r"\d+(?:\.\d+)?")
_CHARSET = re.compile(r"""charset\s*=\s*["']?([^\s;"']+)""", re.IGNORECASE)


class ErroRede(Exception):
    """Falha de rede. `permanente=True` não adianta repetir (404, 403, URL inválida...)."""

    def __init__(
        self, mensagem: str, permanente: bool = False, status: int | None = None, url: str = ""
    ) -> None:
        super().__init__(mensagem)
        self.permanente = permanente
        self.status = status
        self.url = url


@dataclass(frozen=True)
class RespostaRede:
    """`headers` tem as chaves em minúsculas; `url` é a final, depois dos redirects."""

    status: int
    url: str
    conteudo: bytes
    headers: dict[str, str]
    de_cache: bool = False

    def _charset(self) -> str | None:
        for nome, valor in self.headers.items():
            if nome.lower() == "content-type":
                achado = _CHARSET.search(valor)
                return achado.group(1) if achado else None
        return None

    @property
    def texto(self) -> str:
        """Decodifica pelo charset do Content-Type; sem ele (ou desconhecido), UTF-8 com `replace`."""
        charset = self._charset()
        texto = None
        if charset:
            try:
                texto = self.conteudo.decode(charset, errors="replace")
            except LookupError:
                pass
        if texto is None:
            texto = self.conteudo.decode("utf-8", errors="replace")
        return texto.removeprefix("﻿")

    def json(self) -> Any:
        return json.loads(self.conteudo)


def _retry_after(resposta: httpx.Response) -> float | None:
    """Segundos do `Retry-After` numérico, com teto; data HTTP ou lixo viram `None`."""
    bruto = resposta.headers.get("retry-after", "").strip()
    if not _RETRY_AFTER.fullmatch(bruto):
        return None
    return min(float(bruto), _TETO_RETRY_AFTER_S)


def _descrever(exc: Exception) -> str:
    detalhe = str(exc)
    return f"{type(exc).__name__}: {detalhe}" if detalhe else type(exc).__name__


def _origem(url: httpx.URL) -> tuple[str, str, int | None]:
    return (url.scheme, url.host.lower(), url.port)


def _destino_do_redirect(atual: httpx.URL, resposta: httpx.Response, url_pedida: str) -> httpx.URL:
    """Resolve o `Location` contra a URL que o devolveu; só http/https, senão erro permanente."""
    location = resposta.headers["location"]
    try:
        destino = atual.join(location)
    except httpx.InvalidURL as exc:
        raise ErroRede(
            f"GET {url_pedida}: Location inválido no redirect de {atual}: {location!r} ({exc})",
            permanente=True,
            status=resposta.status_code,
            url=url_pedida,
        ) from exc
    if destino.scheme not in ("http", "https"):
        raise ErroRede(
            f"GET {url_pedida}: redirect de {atual} para protocolo não suportado: {location!r}",
            permanente=True,
            status=resposta.status_code,
            url=url_pedida,
        )
    return destino


class Rede:
    """Cliente HTTP assíncrono compartilhado por todos os coletores.

    O limite é por host e conta do FIM da requisição anterior ao mesmo host. Os redirects
    são seguidos aqui, não pelo httpx (até 10 saltos): cada salto é uma requisição como
    outra qualquer, com o limite do seu host e as suas novas tentativas. O cache é por
    instância e só guarda respostas com status < 400. O proxy vem só de `config.proxy`:
    as variáveis de ambiente (HTTP_PROXY etc.) são ignoradas.
    """

    def __init__(
        self,
        config: RedeConfig,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._dormir = dormir
        self._relogio = relogio
        # follow_redirects=False: quem segue o Location é `get`, salto a salto, pelo limite do host.
        # trust_env=False: sem proxy configurado a conexão é direta, nunca a do ambiente.
        self._client = httpx.AsyncClient(
            proxy=config.proxy,
            timeout=config.timeout_s,
            follow_redirects=False,
            trust_env=False,
        )
        self._travas: dict[str, asyncio.Lock] = {}
        self._ultima: dict[str, float] = {}
        self._cache: dict[tuple, RespostaRede] = {}

    async def get(
        self,
        url: str,
        *,
        tipo: Literal["api", "navegador"] = "api",
        params: dict | None = None,
        headers: dict | None = None,
        seguir_redirect: bool = True,
    ) -> RespostaRede:
        if tipo not in ("api", "navegador"):
            raise ValueError(f"tipo de User-Agent desconhecido: {tipo!r}")
        try:
            base = httpx.URL(url)
            alvo = base.copy_merge_params(params) if params else base
        except httpx.InvalidURL as exc:
            raise ErroRede(f"GET {url}: URL inválida ({exc})", permanente=True, url=url) from exc
        url_pedida = str(alvo)

        cabecalhos = httpx.Headers(
            {"User-Agent": self._config.ua_navegador if tipo == "navegador" else self._config.ua_api}
        )
        cabecalhos.update(headers or {})
        chave = (
            str(base),
            tuple(sorted(httpx.QueryParams(params).multi_items())),
            seguir_redirect,
            tuple(sorted(cabecalhos.items())),
        )
        if (guardada := self._cache.get(chave)) is not None:
            return replace(guardada, de_cache=True)

        atual = alvo
        for salto in range(_MAX_REDIRECTS + 1):
            resposta = await self._buscar(atual, cabecalhos)
            if not seguir_redirect or not resposta.has_redirect_location:
                break
            if salto == _MAX_REDIRECTS:
                raise ErroRede(
                    f"GET {url_pedida}: mais de {_MAX_REDIRECTS} redirects seguidos (último: {atual})",
                    permanente=True,
                    status=resposta.status_code,
                    url=url_pedida,
                )
            destino = _destino_do_redirect(atual, resposta, url_pedida)
            if _origem(destino) != _origem(atual):
                # credenciais do chamador não seguem para outra origem
                cabecalhos = httpx.Headers(cabecalhos)
                for nome in _CREDENCIAIS:
                    cabecalhos.pop(nome, None)
            atual = destino

        guardada = RespostaRede(
            status=resposta.status_code,
            url=str(resposta.url),
            conteudo=resposta.content,
            headers=dict(resposta.headers),
            de_cache=False,
        )
        self._cache[chave] = guardada
        return guardada

    async def get_json(self, url: str, **kw: Any) -> Any:
        resposta = await self.get(url, **kw)
        try:
            return resposta.json()
        except ValueError as exc:  # JSONDecodeError e UnicodeDecodeError
            raise ErroRede(
                f"GET {resposta.url}: corpo não é JSON válido ({exc})",
                permanente=True,
                status=resposta.status,
                url=resposta.url,
            ) from exc

    async def fechar(self) -> None:
        await self._client.aclose()

    async def _buscar(self, alvo: httpx.URL, cabecalhos: httpx.Headers) -> httpx.Response:
        """Uma URL (sem seguir redirect), com novas tentativas. Devolve só status < 400."""
        url = str(alvo)
        host = alvo.host.lower()
        total = max(1, self._config.tentativas)
        for n in range(1, total + 1):
            retry_after = None
            try:
                resposta = await self._requisitar(host, alvo, cabecalhos)
            except (httpx.UnsupportedProtocol, httpx.InvalidURL) as exc:
                # a URL do salto já foi validada; o InvalidURL vem do Location que o httpx
                # tenta resolver mesmo sem seguir o redirect
                raise ErroRede(f"GET {url}: {_descrever(exc)}", permanente=True, url=url) from exc
            except httpx.TransportError as exc:  # inclui TimeoutException
                if _LOCATION_INVALIDO in str(exc):  # o servidor vai repetir o mesmo Location
                    raise ErroRede(
                        f"GET {url}: {_descrever(exc)}", permanente=True, url=url
                    ) from exc
                erro = ErroRede(
                    f"GET {url}: {_descrever(exc)} (tentativa {n} de {total})",
                    permanente=False,
                    url=url,
                )
                erro.__cause__ = exc
            except httpx.RequestError as exc:  # o que sobra não é transitório: repetir não muda nada
                raise ErroRede(f"GET {url}: {_descrever(exc)}", permanente=True, url=url) from exc
            else:
                status = resposta.status_code
                if status < 400:
                    return resposta
                if status != 429 and status < 500:
                    raise ErroRede(
                        f"GET {url}: HTTP {status} (permanente, sem nova tentativa)",
                        permanente=True,
                        status=status,
                        url=url,
                    )
                retry_after = _retry_after(resposta)
                erro = ErroRede(
                    f"GET {url}: HTTP {status} (tentativa {n} de {total})",
                    permanente=False,
                    status=status,
                    url=url,
                )
            if n == total:
                raise erro
            await self._dormir(retry_after if retry_after is not None else float(2 ** (n - 1)))
        raise AssertionError("inalcançável: o laço sempre retorna ou levanta")  # pragma: no cover

    async def _requisitar(
        self, host: str, alvo: httpx.URL, cabecalhos: httpx.Headers
    ) -> httpx.Response:
        """Uma requisição respeitando o limite do host. A trava cobre espera + requisição."""
        trava = self._travas.get(host)
        if trava is None:
            trava = self._travas[host] = asyncio.Lock()
        async with trava:
            limites = self._config.limites
            ultima = self._ultima.get(host)
            if ultima is not None:
                espera = limites.get(host, limites["*"]) - (self._relogio() - ultima)
                if espera > 0:
                    await self._dormir(espera)
            try:
                return await self._client.get(alvo, headers=cabecalhos)
            finally:
                self._ultima[host] = self._relogio()
