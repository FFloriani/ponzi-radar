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


class Rede:
    """Cliente HTTP assíncrono compartilhado por todos os coletores.

    O limite é por host e conta do FIM da requisição anterior ao mesmo host. O cache é
    por instância e só guarda respostas com status < 400. O limite não cobre os hosts
    de redirects: o host controlado é o da URL pedida.
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
        self._client = httpx.AsyncClient(proxy=config.proxy, timeout=config.timeout_s)
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
        url_final = str(alvo)

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

        host = alvo.host.lower()
        total = max(1, self._config.tentativas)
        for n in range(1, total + 1):
            retry_after = None
            try:
                resposta = await self._requisitar(host, alvo, cabecalhos, seguir_redirect)
            except httpx.UnsupportedProtocol as exc:
                raise ErroRede(
                    f"GET {url_final}: {_descrever(exc)}", permanente=True, url=url_final
                ) from exc
            except httpx.TransportError as exc:  # inclui TimeoutException
                erro = ErroRede(
                    f"GET {url_final}: {_descrever(exc)} (tentativa {n} de {total})",
                    permanente=False,
                    url=url_final,
                )
                erro.__cause__ = exc
            except httpx.RequestError as exc:  # ex.: excesso de redirects: repetir não muda nada
                raise ErroRede(
                    f"GET {url_final}: {_descrever(exc)}", permanente=True, url=url_final
                ) from exc
            else:
                status = resposta.status_code
                if status < 400:
                    guardada = RespostaRede(
                        status=status,
                        url=str(resposta.url),
                        conteudo=resposta.content,
                        headers=dict(resposta.headers),
                        de_cache=False,
                    )
                    self._cache[chave] = guardada
                    return guardada
                if status != 429 and status < 500:
                    raise ErroRede(
                        f"GET {url_final}: HTTP {status} (permanente, sem nova tentativa)",
                        permanente=True,
                        status=status,
                        url=url_final,
                    )
                retry_after = _retry_after(resposta)
                erro = ErroRede(
                    f"GET {url_final}: HTTP {status} (tentativa {n} de {total})",
                    permanente=False,
                    status=status,
                    url=url_final,
                )
            if n == total:
                raise erro
            await self._dormir(retry_after if retry_after is not None else float(2 ** (n - 1)))
        raise AssertionError("inalcançável: o laço sempre retorna ou levanta")  # pragma: no cover

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

    async def _requisitar(
        self, host: str, alvo: httpx.URL, cabecalhos: httpx.Headers, seguir_redirect: bool
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
                return await self._client.get(
                    alvo, headers=cabecalhos, follow_redirects=seguir_redirect
                )
            finally:
                self._ultima[host] = self._relogio()
