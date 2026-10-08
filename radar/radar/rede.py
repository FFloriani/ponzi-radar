"""Único ponto de saída HTTP do radar: limite por host, novas tentativas, cache, sessões e proxy."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import httpx

from radar.config import UA_API, RedeConfig

# teto de memória do cache de cada sessão: passando dele, saem as respostas usadas há mais tempo (I4)
TETO_DO_CACHE_BYTES = 64 * 1024 * 1024
# o UA das APIs quando há proxy (ou Tor): o padrão diz quem é o analista
UA_API_NEUTRO = "radar/0.1"
# cabeçalhos que descrevem o corpo como veio na rede; o corpo lido com teto já está decodificado
_CABECALHOS_DO_CORPO = frozenset({"content-encoding", "content-length", "transfer-encoding"})

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
        """Decodifica pelo charset do Content-Type; sem ele (ou desconhecido), UTF-8 com `replace`.

        O cabeçalho vem do servidor consultado, então o charset pode ser qualquer coisa: o nome
        que o Python não conhece (`LookupError`) e o codec que não decodifica texto, como `idna` ou
        `undefined` (`UnicodeError`), caem no UTF-8.
        """
        charset = self._charset()
        texto = None
        if charset:
            try:
                texto = self.conteudo.decode(charset, errors="replace")
            except (LookupError, UnicodeError):
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


@dataclass
class _Limitador:
    """O limite por host, um só para a `Rede` e todas as sessões dela: a cortesia com as fontes não muda com o
    número de execuções abertas."""

    travas: dict[str, asyncio.Lock] = field(default_factory=dict)
    ultima: dict[str, float] = field(default_factory=dict)


def _tamanho(n: int) -> str:
    return f"{n / 1_000_000:g} MB" if n >= 1_000_000 else f"{n} bytes"


class Rede:
    """Cliente HTTP assíncrono dos coletores.

    O limite é por host e conta do FIM da requisição anterior ao mesmo host. Os redirects
    são seguidos aqui, não pelo httpx (até 10 saltos): cada salto é uma requisição como
    outra qualquer, com o limite do seu host e as suas novas tentativas. O timeout de cada requisição (e de cada
    salto) é `config.timeouts[host]` ou, sem entrada para o host, `config.timeout_s`. O proxy
    vem só de `config.proxy`: as variáveis de ambiente (HTTP_PROXY etc.) são ignoradas.

    Sessões (I4): cada execução usa `sessao()`, com cache, cookies e conexões próprios; o limite por host continua
    um só. O servidor MCP fica aberto por dias, e "analisa de novo" não pode devolver o DNS, o registro e os sócios da
    primeira execução, nem levar os cookies de um caso para outro. O cache só guarda respostas com status < 400,
    tem teto de memória (`TETO_DO_CACHE_BYTES`, as usadas há mais tempo saem primeiro) e não guarda o que foi pedido
    com `usar_cache=False`.
    """

    def __init__(
        self,
        config: RedeConfig,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
        relogio: Callable[[], float] = time.monotonic,
        *,
        _limitador: _Limitador | None = None,
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
        self._limitador = _limitador if _limitador is not None else _Limitador()
        self._cache: OrderedDict[tuple, RespostaRede] = OrderedDict()
        self._bytes_no_cache = 0
        # com proxy, o UA padrão das APIs (que leva o endereço do projeto) vira um neutro; um escolhido na config fica
        self.ua_api = UA_API_NEUTRO if config.proxy and config.ua_api == UA_API else config.ua_api

    def sessao(self) -> Rede:
        """Uma sessão para uma execução: cache, cookies e conexões próprios, o mesmo limite por host. Quem a cria a
        fecha (`fechar()`)."""
        return type(self)(self._config, self._dormir, self._relogio, _limitador=self._limitador)

    async def get(
        self,
        url: str,
        *,
        tipo: Literal["api", "navegador"] = "api",
        params: dict | None = None,
        headers: dict | None = None,
        seguir_redirect: bool = True,
        usar_cache: bool = True,
        max_bytes: int | None = None,
    ) -> RespostaRede:
        """`usar_cache=False` ignora a resposta guardada, vai à rede e não guarda a nova (e tira a velha do cache).

        O cache em memória não expira. Quem tem validade própria, como os índices da CVM e do BCB,
        precisa disso para um processo longo não devolver o arquivo baixado horas atrás.

        `max_bytes`: o corpo é lido em partes e, passando do teto (contado já descomprimido), a leitura para e a
        requisição vira `ErroRede` permanente ("corpo acima do teto"): uma URL de corpo enorme ou infinito não enche
        a memória.
        """
        if tipo not in ("api", "navegador"):
            raise ValueError(f"tipo de User-Agent desconhecido: {tipo!r}")
        try:
            base = httpx.URL(url)
            alvo = base.copy_merge_params(params) if params else base
        except httpx.InvalidURL as exc:
            raise ErroRede(f"GET {url}: URL inválida ({exc})", permanente=True, url=url) from exc
        url_pedida = str(alvo)

        cabecalhos = httpx.Headers(
            {"User-Agent": self._config.ua_navegador if tipo == "navegador" else self.ua_api}
        )
        cabecalhos.update(headers or {})
        chave = (
            str(base),
            tuple(sorted(httpx.QueryParams(params).multi_items())),
            seguir_redirect,
            tuple(sorted(cabecalhos.items())),
            max_bytes,
        )
        if not usar_cache:
            self._descartar(chave)
        elif (guardada := self._cache.get(chave)) is not None:
            self._cache.move_to_end(chave)
            # cópia dos cabeçalhos: quem lê não muda o que está guardado
            return replace(guardada, de_cache=True, headers=dict(guardada.headers))

        atual = alvo
        for salto in range(_MAX_REDIRECTS + 1):
            resposta = await self._buscar(atual, cabecalhos, max_bytes)
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

        nova = RespostaRede(
            status=resposta.status_code,
            url=str(resposta.url),
            conteudo=resposta.content,
            headers=dict(resposta.headers),
            de_cache=False,
        )
        if usar_cache:
            self._guardar(chave, nova)
        return replace(nova, headers=dict(nova.headers))

    def _descartar(self, chave: tuple) -> None:
        if (velha := self._cache.pop(chave, None)) is not None:
            self._bytes_no_cache -= len(velha.conteudo)

    def _guardar(self, chave: tuple, resposta: RespostaRede) -> None:
        """Guarda no cache, dentro do teto: saem as usadas há mais tempo; a que sozinha passa do teto não entra."""
        self._descartar(chave)
        tamanho = len(resposta.conteudo)
        if tamanho > TETO_DO_CACHE_BYTES:
            return
        self._cache[chave] = resposta
        self._bytes_no_cache += tamanho
        while self._bytes_no_cache > TETO_DO_CACHE_BYTES:
            _, velha = self._cache.popitem(last=False)
            self._bytes_no_cache -= len(velha.conteudo)

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

    async def _buscar(self, alvo: httpx.URL, cabecalhos: httpx.Headers, max_bytes: int | None) -> httpx.Response:
        """Uma URL (sem seguir redirect), com novas tentativas. Devolve só status < 400."""
        url = str(alvo)
        host = alvo.host.lower()
        total = max(1, self._config.tentativas)
        for n in range(1, total + 1):
            retry_after = None
            try:
                resposta = await self._requisitar(host, alvo, cabecalhos, max_bytes)
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
        self, host: str, alvo: httpx.URL, cabecalhos: httpx.Headers, max_bytes: int | None = None
    ) -> httpx.Response:
        """Uma requisição respeitando o limite do host. A trava cobre espera + requisição."""
        limitador = self._limitador
        trava = limitador.travas.get(host)
        if trava is None:
            trava = limitador.travas[host] = asyncio.Lock()
        async with trava:
            limites = self._config.limites
            ultima = limitador.ultima.get(host)
            if ultima is not None:
                espera = limites.get(host, limites["*"]) - (self._relogio() - ultima)
                if espera > 0:
                    await self._dormir(espera)
            # o timeout vale por requisição, no host de cada salto: o Wayback é bem mais lento que o resto
            timeout = self._config.timeouts.get(host, self._config.timeout_s)
            try:
                if max_bytes is None:
                    return await self._client.get(alvo, headers=cabecalhos, timeout=timeout)
                return await self._ler_com_teto(alvo, cabecalhos, timeout, max_bytes)
            finally:
                limitador.ultima[host] = self._relogio()

    async def _ler_com_teto(
        self, alvo: httpx.URL, cabecalhos: httpx.Headers, timeout: float, max_bytes: int
    ) -> httpx.Response:
        """O GET em partes, parando ao passar de `max_bytes` (o corpo descomprimido). O erro HTTP volta sem corpo:
        quem decide a nova tentativa é o status."""
        async with self._client.stream("GET", alvo, headers=cabecalhos, timeout=timeout) as resposta:
            corpo = bytearray()
            if resposta.status_code < 400:
                async for parte in resposta.aiter_bytes():
                    corpo += parte
                    if len(corpo) > max_bytes:
                        raise ErroRede(
                            f"GET {alvo}: corpo acima do teto de {_tamanho(max_bytes)}; a leitura foi interrompida",
                            permanente=True,
                            status=resposta.status_code,
                            url=str(alvo),
                        )
            cabecalhos_da_resposta = [
                (nome, valor) for nome, valor in resposta.headers.multi_items()
                if nome.lower() not in _CABECALHOS_DO_CORPO
            ]  # fmt: skip
            return httpx.Response(
                resposta.status_code, headers=cabecalhos_da_resposta, content=bytes(corpo), request=resposta.request
            )
