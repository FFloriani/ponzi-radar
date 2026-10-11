"""Nó `captura`: visita passiva do site investigado com o Chromium, artefatos na custódia e detecção de anti-bot.

É o único nó que toca o site do alvo (e o do destino, quando a página inicial redireciona para outro domínio), e só
como um visitante comum: `goto` em links, nunca clique, preenchimento nem envio de formulário; downloads recusados e
service workers bloqueados. O Playwright é a exceção à regra "toda saída via `Rede`": o navegador tem pilha de rede
própria e recebe o proxy de `config.rede`.

Destino (melhorias do aceite, T1): o alvo que só redireciona (`phinv.link` → `phinvestimentos.com/login`) não é o site.
Quando a página inicial termina noutro domínio registrável, que não é plataforma de conteúdo (`alvo.PLATAFORMAS`),
serviço de estacionamento (`alvo.SERVICOS_DE_ESTACIONAMENTO`) nem serviço de terceiro (`alvo.SERVICOS_DE_TERCEIROS`),
as subpáginas saem do host dele e a saída `destino` o entrega ao nó `destino`, que o passa aos coletores de domínio. O
redirect para os outros não troca o domínio analisado e fica em `redirect_ignorado`.

Opsec do analista (I5 da revisão final): o WebRTC só usa UDP pelo proxy (`ARGS_DO_NAVEGADOR`) e, com proxy, o
`RTCPeerConnection` some da página (um STUN do site revelaria o IP real); o navegador usa o próprio User-Agent,
coerente com o `sec-ch-ua` (o `ua_navegador` da config é o da `Rede`). Nada esconde a automação: não contornamos
anti-bot. O site também não alcança endereços locais do analista (localhost, IP literal que não é global), a não ser
o próprio host da `url_inicial` (o site de teste local), e as janelas que ele abre sozinho são fechadas sem navegar.

Endereço local por redirect (R4): a rota do contexto (`_Guarda.rotear`) só vê o primeiro pedido de cada cadeia de
redirect, e o bloqueio de URLs do DevTools (`Network.setBlockedURLs`) não vale para navegação. Por isso uma sessão CDP
do navegador inteiro liga o domínio `Fetch` só para os hosts que podem ser endereço local (`_PADROES_DO_FETCH`): o
Chromium pausa cada pedido e cada salto de redirect que casa, de qualquer aba, iframe de outro site, worker ou
subrecurso, e a guarda decide (`_barrar_enderecos_locais`). O pedido permitido segue pela pilha do próprio Chromium
(TLS, HTTP/2, `Sec-Fetch-*`, AIA, proxy sem CONNECT para `http://`), como o de qualquer visitante. WebSocket passa por
`route_web_socket` (o `Fetch` não vê o handshake), que troca o `window.WebSocket` da página por um de JS: trade-off
aceito, o Chromium headless já se anuncia `HeadlessChrome`. E, por garantia, nem a página cuja URL final é endereço
local nem a página de erro que fica no lugar de uma navegação barrada vão para a custódia.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from playwright.async_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Page,
    Request,
    Route,
    WebSocketRoute,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from radar.config import CapturaConfig, RedeConfig
from radar.modelos import Contexto, ErroNo, Feito, Pulado
from radar.motor import NoBase, Servicos
from radar.nos._paginas import Chave, chave_da_pagina, ordenar_paginas
from radar.nos.alvo import dominio_registravel, e_estacionamento, e_plataforma, e_servico_de_terceiro
from radar.pontuacao import (
    ERROS_DE_ALCANCE,
    PREFIXO_CAPTURA_INDISPONIVEL,
    PREFIXO_FALHA_CAPTURA,
    PREFIXO_FALHA_NAVEGACAO,
)

# Desafio anti-bot (R-T8-desafio). O título da página de verificação basta. Marca no HTML sozinha não:
# um login ou cadastro com reCAPTCHA tem `g-recaptcha` e pouco texto e é uma página de verdade, e
# `challenge-platform` aparece em qualquer página atrás da Cloudflare. Marca só conta com um segundo
# sinal de que o servidor barrou o visitante (status 403/429/503 ou `cf-mitigated: challenge`) e
# com a página quase sem texto.
_TITULO_DESAFIO = re.compile(r"just a moment|attention required|verifique (que )?você é humano", re.IGNORECASE)
_MARCAS_DESAFIO = ("cf-chl", "_cf_chl_opt", "cf-turnstile", "challenge-form", "g-recaptcha", "h-captcha")
_STATUS_DE_BLOQUEIO = frozenset({403, 429, 503})
_TEXTO_CURTO = 200
_MOTIVO_DESAFIO = "desafio anti-bot"
# links para estes arquivos nunca são seguidos (não é página e abrir um download é contato demais)
_EXTENSOES_DE_ARQUIVO = frozenset({"zip", "pdf", "exe", "apk", "rar", "7z", "dmg", "msi"})
_JS_LINKS = "() => Array.from(document.links, (link) => link.href)"
_ERRO_DO_CHROMIUM = re.compile(r"net::(ERR_[A-Z0-9_]+)")
# a 1ª linha do erro do Playwright quando o executável do Chromium não está onde ele procura (o caminho e o quadro de
# aviso das linhas seguintes mudam com a versão e o sistema)
_NAVEGADOR_AUSENTE = re.compile(r"BrowserType\.\w+: Executable doesn't exist\b")
MOTIVO_NAVEGADOR_AUSENTE = (
    'navegador do Playwright não encontrado; rode "playwright install chromium" no venv do radar '
    "ou confira PLAYWRIGHT_BROWSERS_PATH no ambiente do servidor MCP"
)
# o WebRTC só usa UDP pelo proxy: sem proxy UDP (HTTP, SOCKS), nenhum candidato ICE sai pela rede do analista
ARGS_DO_NAVEGADOR = (
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--webrtc-ip-handling-policy=disable_non_proxied_udp",
)
# com proxy, o site nem vê o WebRTC: um STUN dele não tem como pedir o IP do analista
_SEM_WEBRTC = """(() => {
  for (const nome of ["RTCPeerConnection", "webkitRTCPeerConnection", "RTCDataChannel", "RTCIceCandidate",
                      "RTCSessionDescription", "RTCRtpSender", "RTCRtpReceiver", "RTCRtpTransceiver"]) {
    try { delete window[nome]; } catch (e) {}
  }
})();"""


class _FalhaDeNavegacao(Exception):
    """O `goto` falhou: o navegador não chegou à página. `original` é o erro do Playwright."""

    def __init__(self, original: PlaywrightError) -> None:
        super().__init__(str(original))
        self.original = original


def _e_desafio(
    titulo: str, html: str, texto: str, status: int | None, cabecalhos: Mapping[str, str]
) -> bool:
    """A página é uma verificação anti-bot (Cloudflare, reCAPTCHA, hCaptcha...), não o conteúdo do site.

    `status` e `cabecalhos` são os da resposta do `goto`. É desafio quando o título casa com
    `_TITULO_DESAFIO`, ou quando o HTML tem uma de `_MARCAS_DESAFIO` E o servidor barrou o
    visitante (`status` em `_STATUS_DE_BLOQUEIO` ou `cf-mitigated: challenge`) E o texto, sem os
    espaços das pontas, tem menos de 200 caracteres.
    """
    if _TITULO_DESAFIO.search(titulo):
        return True
    mitigado = any(
        nome.lower() == "cf-mitigated" and valor.strip().lower() == "challenge"
        for nome, valor in cabecalhos.items()
    )
    if status not in _STATUS_DE_BLOQUEIO and not mitigado:
        return False
    html = html.lower()
    return any(marca in html for marca in _MARCAS_DESAFIO) and len(texto.strip()) < _TEXTO_CURTO


def _e_erro_http(status: int | None) -> bool:
    """A resposta foi um erro HTTP (a página é a de erro do servidor, não o conteúdo do site)."""
    return status is not None and status >= 400


def _opcoes_do_contexto(rede: RedeConfig, caminho_har: Path) -> dict[str, Any]:
    """Argumentos de `browser.new_context`: o navegador de um visitante, que grava o HAR e não baixa nada. Sem
    `user_agent`: o UA nativo é o que o `sec-ch-ua` e o `navigator.userAgentData` confirmam (I5)."""
    opcoes: dict[str, Any] = {
        "accept_downloads": False,
        "service_workers": "block",
        "record_har_path": str(caminho_har),
        "record_har_content": "embed",
    }
    if rede.proxy:
        opcoes["proxy"] = {"server": rede.proxy}
    return opcoes


def _host_local(host: str) -> bool:
    host = host.strip("[]").rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return not ip.is_global or ip.is_multicast


def _loopback(host: str) -> bool:
    host = host.strip("[]").rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (getattr(ip, "ipv4_mapped", None) or ip).is_loopback


def _endereco_local(url: str) -> bool:
    """A URL aponta para um endereço local do analista: `localhost` ou IP literal que não é global (loopback, rede
    privada, link-local, CGNAT, documentação). Nome comum e o que não tem host (`data:`, `about:`) não são."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return False
    return bool(host) and _host_local(host)


# Os pedidos que o `Fetch` do CDP pausa para a guarda decidir (cada salto de redirect deles também): todo host que
# começa com dígito (o IPv4 literal chega canônico: 2130706433 e 0x7f.1 viram 127.0.0.1), todo IPv6 literal, o
# localhost e a URL com `@` depois do esquema (o usuário e a senha vêm antes do host: http://u:s@127.0.0.1/). Um nome
# comum que casa (123exemplo.com.br, um e-mail na query) só pausa e segue; o resto nem para. `_endereco_local` não
# conhece outro endereço local: nome que resolve para IP privado não é barrado.
_PADROES_DO_FETCH = (
    *(f"*://{digito}*" for digito in "0123456789"), "*://[*", "*://localhost*", "*://*.localhost*", "*://*@*",
)  # fmt: skip


async def _abortar(rota: Route, codigo: str) -> None:
    with contextlib.suppress(PlaywrightError):  # a aba pode ter fechado no meio
        await rota.abort(codigo)


class _Guarda:
    """O filtro de rede da captura: nada de endereço local do analista (só o host da `url_inicial`, e o resto do
    loopback quando ela mesma é local: o site de teste), nem direto nem por redirect, e nada de requisição de janela
    que o site abriu sozinho. `bloqueios` guarda os destinos barrados, para dizer por que uma página falhou."""

    def __init__(self, url_inicial: str) -> None:
        self._host_inicial = (urlsplit(url_inicial).hostname or "").lower()
        self.paginas: set[Page] = set()
        self.bloqueios: list[str] = []

    def permitido(self, url: str) -> bool:
        if not _endereco_local(url):
            return True
        host = (urlsplit(url).hostname or "").lower()
        return host == self._host_inicial or (_loopback(host) and _loopback(self._host_inicial))

    def _da_captura(self, pedido: Request) -> bool:
        try:
            return pedido.frame.page in self.paginas
        except Exception:
            # sem frame: a navegação de uma janela nova antes de o frame dela existir (o popup que o site abre; as
            # abas da captura já existem quando navegam) ou um service worker (já bloqueado no contexto)
            return not pedido.is_navigation_request()

    async def rotear(self, rota: Route) -> None:
        """O primeiro pedido de cada cadeia (os saltos de redirect são do `_barrar_enderecos_locais`): segue pela
        pilha do Chromium se é permitido e de uma aba da captura; senão é abortado."""
        pedido = rota.request
        if self._da_captura(pedido) and self.permitido(pedido.url):
            with contextlib.suppress(PlaywrightError):
                await rota.continue_()
            return
        if self._da_captura(pedido):
            self.bloqueios.append(pedido.url)
        await _abortar(rota, "blockedbyclient")

    async def rotear_websocket(self, ws: WebSocketRoute) -> None:
        if self.permitido(ws.url):
            ws.connect_to_server()  # a conexão sai do navegador, pelo proxy dele
        else:
            self.bloqueios.append(ws.url)
            with contextlib.suppress(PlaywrightError):
                await ws.close(code=1008, reason="endereço local bloqueado")


async def _barrar_enderecos_locais(navegador: Browser, guarda: _Guarda) -> CDPSession:
    """Barra no navegador inteiro (aba, iframe de outro site, worker, subrecurso e cada salto de redirect) o pedido a
    endereço local que a `guarda` não permite: o `Fetch` do CDP pausa os pedidos de `_PADROES_DO_FETCH`, e o barrado
    termina em `BlockedByClient`, com o destino em `guarda.bloqueios`. A rota do Playwright não vê os saltos de
    redirect; esta sessão vê, e o pedido permitido segue pela pilha do Chromium. Vale até o navegador fechar."""
    sessao = await navegador.new_browser_cdp_session()
    pendentes: set[asyncio.Future] = set()

    async def enviar(metodo: str, parametros: dict) -> None:
        with contextlib.suppress(PlaywrightError):  # o pedido ou o navegador pode ter acabado no meio
            await sessao.send(metodo, parametros)

    def pausado(evento: dict) -> None:
        url, pedido = evento["request"]["url"], {"requestId": evento["requestId"]}
        if guarda.permitido(url):
            tarefa = asyncio.ensure_future(enviar("Fetch.continueRequest", pedido))
        else:
            guarda.bloqueios.append(url)  # antes do failRequest: o `goto` que falhar já acha o destino aqui
            tarefa = asyncio.ensure_future(enviar("Fetch.failRequest", {**pedido, "errorReason": "BlockedByClient"}))
        pendentes.add(tarefa)  # o loop só guarda referência fraca da tarefa
        tarefa.add_done_callback(pendentes.discard)

    sessao.on("Fetch.requestPaused", pausado)
    padroes = [{"urlPattern": padrao, "requestStage": "Request"} for padrao in _PADROES_DO_FETCH]
    await sessao.send("Fetch.enable", {"patterns": padroes})
    return sessao


async def _fechar_janela(pagina: Page) -> None:
    with contextlib.suppress(PlaywrightError):
        await pagina.close()


def _terceiros(har: bytes, *dominios_do_site: str) -> list[str]:
    """Domínios registráveis das requisições do HAR que não são os do site (o do alvo e, depois de um redirect, o do
    destino), sem repetição e em ordem.

    IP e nome sem sufixo público (`localhost`) não têm domínio registrável: valem pelo próprio host.
    """
    do_site = {dominio.lower() for dominio in dominios_do_site if dominio}
    dominios: set[str] = set()
    for entrada in json.loads(har)["log"]["entries"]:
        try:
            host = urlsplit(entrada["request"]["url"]).hostname
        except ValueError:  # a URL vem do site investigado
            continue
        if not host:  # data:, about:blank...
            continue
        dominio = dominio_registravel(host) or host
        if dominio not in do_site:
            dominios.add(dominio)
    return sorted(dominios)


def _destino_do_redirect(url_final: str, alvo: str) -> tuple[dict | None, dict | None]:
    """`(destino, redirect_ignorado)` da página inicial que terminou em `url_final`.

    - outro domínio registrável (http ou https): `({"url", "dominio"}, None)`, e os coletores passam a analisá-lo;
    - plataforma de conteúdo, serviço de estacionamento ou serviço de terceiro (`alvo.SERVICOS_DE_TERCEIROS`: loja
      de app, comunidade, checkout, hospedagem de arquivo): `(None, {"url", "dominio", "motivo"})`, com o motivo
      `"plataforma"`, `"estacionamento"` ou `"servico_de_terceiro"`: o destino não vira o alvo;
    - o próprio domínio do alvo (`www.`, outro subdomínio), host sem domínio registrável (IP, `localhost`, nome sem
      sufixo público), outro esquema (`about:`, `chrome-error:`) ou URL quebrada: `(None, None)`.

    `url_final` vem do site investigado: nada dela derruba a captura.
    """
    try:
        partes = urlsplit(url_final)
        host = partes.hostname
    except ValueError:
        return None, None
    if partes.scheme not in ("http", "https") or not host:
        return None, None
    dominio = dominio_registravel(host)
    if not dominio or dominio == alvo.lower():
        return None, None
    if e_plataforma(dominio):
        return None, {"url": url_final, "dominio": dominio, "motivo": "plataforma"}
    if e_estacionamento(dominio):
        return None, {"url": url_final, "dominio": dominio, "motivo": "estacionamento"}
    if e_servico_de_terceiro(dominio):
        return None, {"url": url_final, "dominio": dominio, "motivo": "servico_de_terceiro"}
    return {"url": url_final, "dominio": dominio}, None


def _host_do_site(url: str) -> str | None:
    host = urlsplit(url).hostname
    return host.removeprefix("www.") if host else None


def _e_arquivo(caminho: str) -> bool:
    _, ponto, extensao = caminho.rpartition("/")[2].rpartition(".")
    return bool(ponto) and extensao.lower() in _EXTENSOES_DE_ARQUIVO


def _link_do_site(href: Any, hosts: set[str]) -> str | None:
    """`href` sem o fragmento se for uma página http(s) de um dos `hosts`; senão `None`."""
    if not isinstance(href, str):
        return None
    try:
        partes = urlsplit(href)
        host = partes.hostname
        _ = partes.port  # só para validar a porta
    except ValueError:
        return None
    if partes.scheme not in ("http", "https") or not host or host.removeprefix("www.") not in hosts:
        return None
    if _e_arquivo(partes.path):
        return None
    return urlunsplit(partes._replace(fragment=""))


def _escolher_links(
    hrefs: list, url_inicial: str, url_final: str, alvo: str, limite: int, destino: str | None = None
) -> list[str]:
    """As subpáginas a visitar: até `limite` links do mesmo host da `url_inicial` (com ou sem `www.`).

    `url_final` é onde a página inicial terminou depois dos redirects. Ela nunca é revisitada, mas o
    host dela só vale como "mesmo host" se for do domínio registrável do `alvo` (`www.exemplo.com`,
    `app.exemplo.com`). Um golpe que redireciona para `t.me` ou `wa.me` não faz a captura rastrear
    o Telegram. Com `destino` (o domínio registrável da `url_final`, quando o redirect trocou de domínio e
    `_destino_do_redirect` o aceitou), as subpáginas são só as do host da `url_final`: o redirecionador não é o site.
    Links para arquivos, de outro esquema que não http(s) e repetidos depois de tirar o
    fragmento ficam de fora. A ordem e o corte de variantes de query são os do `wayback_snapshot`
    (`ordenar_paginas`): as páginas de regras primeiro, as sem query antes das com query, no máximo
    1 variante de query por caminho (a primeira do documento).
    """
    host_final = _host_do_site(url_final)
    if destino:
        hosts = {host_final} if host_final else set()
    else:
        hosts = {host for host in [_host_do_site(url_inicial)] if host}
        if host_final and dominio_registravel(host_final) == alvo.lower():
            hosts.add(host_final)
    ja_vistas = {chave for chave in map(chave_da_pagina, [url_inicial, url_final]) if chave is not None}
    candidatas: dict[Chave, tuple[int, str]] = {}
    for posicao, href in enumerate(hrefs):
        url = _link_do_site(href, hosts)
        chave = chave_da_pagina(url) if url else None
        if chave is not None and chave not in ja_vistas and chave not in candidatas:
            candidatas[chave] = (posicao, url)
    ordem = ordenar_paginas(candidatas, desempate=lambda candidata: -candidata[0])
    return [candidatas[chave][1] for chave in ordem[: max(0, limite)]]


def _motivo(erro: Exception) -> str:
    """A primeira linha da mensagem: o Playwright anexa o log de chamadas nas seguintes."""
    if isinstance(erro, _FalhaDeNavegacao):
        erro = erro.original
    linha = next((linha.strip() for linha in str(erro).splitlines() if linha.strip()), "")
    if isinstance(erro, PlaywrightError):
        return linha or type(erro).__name__
    return f"{type(erro).__name__}: {linha}" if linha else type(erro).__name__


def _erro_da_captura(erro: Exception) -> ErroNo:
    """O `ErroNo` (não permanente) de uma falha da captura, na forma que o E6 lê (`pontuacao.site_nao_respondeu`):

    - o `goto` da página inicial não alcançou o site (`ERROS_DE_ALCANCE` ou timeout): "captura falhou: navegação:
      net::ERR_..." ou "captura falhou: navegação: timeout";
    - o Playwright não achou o executável do Chromium: "captura indisponível: navegador do Playwright não encontrado;
      rode "playwright install chromium" no venv do radar ou confira PLAYWRIGHT_BROWSERS_PATH no ambiente do servidor
      MCP" (o ambiente reduzido de um cliente MCP sem o `PLAYWRIGHT_BROWSERS_PATH` do analista cai aqui). Sem o caminho
      nem o quadro de aviso do Playwright, e como as demais falhas do analista: não conta para o E6;
    - qualquer outra falha é do lado do analista: "captura indisponível: <motivo>" (navegador que não inicia, proxy ou
      túnel fora, sem internet, certificado e TLS, erro inesperado do código).
    """
    if isinstance(erro, _FalhaDeNavegacao):
        if isinstance(erro.original, PlaywrightTimeout):
            return ErroNo(f"{PREFIXO_FALHA_NAVEGACAO} timeout", permanente=False)
        codigo = _ERRO_DO_CHROMIUM.search(str(erro.original))
        if codigo is not None and codigo.group(1) in ERROS_DE_ALCANCE:
            return ErroNo(f"{PREFIXO_FALHA_NAVEGACAO} net::{codigo.group(1)}", permanente=False)
    elif isinstance(erro, PlaywrightError) and _NAVEGADOR_AUSENTE.match(_motivo(erro)):
        return ErroNo(f"{PREFIXO_CAPTURA_INDISPONIVEL} {MOTIVO_NAVEGADOR_AUSENTE}", permanente=False)
    return ErroNo(f"{PREFIXO_CAPTURA_INDISPONIVEL} {_motivo(erro)}", permanente=False)


def _bytes(texto: str) -> bytes:
    # o texto vem do site investigado. O Playwright 1.63 já troca surrogate solitário (UTF-16 inválido)
    # por U+FFFD, mas sem `replace` um que escapasse derrubaria o nó em vez de só virar "?"
    return texto.encode("utf-8", errors="replace")


@dataclass
class _Visita:
    """O que o navegador viu numa página, ainda fora da custódia.

    `url` é onde ela terminou; `status` e `cabecalhos` são os da resposta do `goto` (`None` e `{}` se o
    Playwright não devolveu resposta).
    """

    url: str
    status: int | None
    cabecalhos: dict[str, str]
    titulo: str
    html: str
    texto: str
    screenshot: bytes
    links: list = field(default_factory=list)

    @property
    def e_desafio(self) -> bool:
        return _e_desafio(self.titulo, self.html, self.texto, self.status, self.cabecalhos)

    @property
    def e_erro_http(self) -> bool:
        return _e_erro_http(self.status)


async def _visitar(
    contexto: BrowserContext, url: str, cfg: CapturaConfig, com_links: bool, guarda: _Guarda
) -> _Visita:
    """Abre `url` numa aba nova (o travamento de uma não contamina as outras) e lê o que renderizou. A janela que a
    página abrir sozinha é fechada (e as requisições dela, barradas pela `guarda`)."""
    pagina = await contexto.new_page()
    guarda.paginas.add(pagina)
    pagina.on("popup", _fechar_janela)
    try:
        try:
            resposta = await pagina.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as erro:
            raise _FalhaDeNavegacao(erro) from erro
        try:
            await pagina.wait_for_load_state("networkidle", timeout=cfg.networkidle_s * 1000)
        except PlaywrightTimeout:
            pass  # polling e relógios mantêm a rede ocupada para sempre: o que já carregou basta
        return _Visita(
            url=pagina.url,
            status=resposta.status if resposta else None,
            cabecalhos=dict(resposta.headers) if resposta else {},
            titulo=await pagina.title(),
            html=await pagina.content(),
            texto=await pagina.inner_text("body"),
            screenshot=await pagina.screenshot(full_page=True),
            links=await pagina.evaluate(_JS_LINKS) if com_links else [],
        )
    finally:
        with contextlib.suppress(PlaywrightError):
            await pagina.close()


def _guardar_pagina(s: Servicos, v: _Visita) -> dict:
    return {
        "url": v.url,
        "status": v.status,
        "html": s.custodia.guardar(_bytes(v.html), "html", tipo="pagina", origem=v.url),
        "texto": s.custodia.guardar(_bytes(v.texto), "txt", tipo="texto", origem=v.url),
        "screenshot": s.custodia.guardar(v.screenshot, "png", tipo="screenshot", origem=v.url),
    }


def _guardar_desafio(s: Servicos, v: _Visita) -> None:
    """O HTML da verificação fica na custódia como prova do bloqueio, mas não vira página."""
    s.custodia.guardar(_bytes(v.html), "html", tipo="desafio", origem=v.url)


@dataclass
class _Percurso:
    """O que a captura levou do site: as páginas (sem o HAR), se a inicial era um desafio anti-bot, as subpáginas que
    falharam e o redirect da página inicial (`_destino_do_redirect`)."""

    paginas: list[dict]
    bloqueada: bool
    falhas: list[dict]
    destino: dict | None
    redirect_ignorado: dict | None


async def _percorrer(
    contexto: BrowserContext, ctx: Contexto, cfg: CapturaConfig, s: Servicos, guarda: _Guarda
) -> _Percurso:
    """Visita a página inicial e as subpáginas.

    Falha na página inicial levanta: `_FalhaDeNavegacao` se o `goto` falhou, `PlaywrightError` se o resto da
    leitura falhou, `ErroNo` se o servidor respondeu com erro HTTP (o HTML da página de erro fica na custódia como
    prova) ou se a guarda barrou a página (redirect ou URL final em endereço local: nada dela vai para a custódia).
    Falha numa subpágina, inclusive erro HTTP, endereço local barrado e erro inesperado ao processar o conteúdo do
    site, vai para `falhas` e as outras seguem. O redirect da página inicial vale também quando ela é um desafio: o
    domínio de onde o desafio veio é o que o Wayback e os coletores olham.
    """
    inicio = await _visita_guardada(contexto, ctx.url_inicial, cfg, True, guarda)
    destino, ignorado = _destino_do_redirect(inicio.url, ctx.alvo)
    if inicio.e_desafio:
        _guardar_desafio(s, inicio)
        screenshot = s.custodia.guardar(inicio.screenshot, "png", tipo="screenshot", origem=inicio.url)
        # sem texto e sem seguir links
        paginas = [{"url": inicio.url, "status": inicio.status, "screenshot": screenshot}]
        return _Percurso(paginas, True, [], destino, ignorado)
    if inicio.e_erro_http:
        # o site caiu ou recusou o visitante: sem conteúdo para analisar, o motor cai no Wayback
        s.custodia.guardar(_bytes(inicio.html), "html", tipo="pagina", origem=inicio.url)
        raise ErroNo(f"{PREFIXO_FALHA_CAPTURA} HTTP {inicio.status}", permanente=False)

    paginas = [_guardar_pagina(s, inicio)]
    falhas: list[dict] = []
    links = _escolher_links(
        inicio.links, ctx.url_inicial, inicio.url, ctx.alvo, cfg.max_subpaginas, destino and destino["dominio"]
    )
    for url in links:
        try:
            visita = await _visita_guardada(contexto, url, cfg, False, guarda)
            if visita.e_desafio:
                _guardar_desafio(s, visita)
                falhas.append({"url": url, "motivo": _MOTIVO_DESAFIO})
                break  # o site pediu verificação: não insiste
            if visita.e_erro_http:
                falhas.append({"url": url, "motivo": f"HTTP {visita.status}"})
                continue
            paginas.append(_guardar_pagina(s, visita))
        except _EnderecoLocal as erro:
            falhas.append({"url": url, "motivo": str(erro)})
        except Exception as erro:  # o conteúdo é do site investigado: nada dele derruba o nó
            falhas.append({"url": url, "motivo": _motivo(erro)})
    return _Percurso(paginas, False, falhas, destino, ignorado)


class _EnderecoLocal(Exception):
    """A guarda barrou a página: o redirect, a navegação que a página fez sozinha ou a URL final é endereço local do
    analista."""


async def _visita_guardada(
    contexto: BrowserContext, url: str, cfg: CapturaConfig, com_links: bool, guarda: _Guarda
) -> _Visita:
    """`_visitar`, mas a página que a guarda barrou vira `_EnderecoLocal` (com o destino): o `goto` que falhou, ou a
    página de erro do Chromium (`chrome-error://`) que ficou no lugar de uma navegação barrada depois do `goto` (JS,
    meta refresh). A que terminou num endereço local, sem a guarda ter visto, nunca é devolvida (defesa em
    profundidade)."""
    antes = len(guarda.bloqueios)
    try:
        visita = await _visitar(contexto, url, cfg, com_links=com_links, guarda=guarda)
    except _FalhaDeNavegacao:
        if len(guarda.bloqueios) > antes:
            raise _EnderecoLocal(f"redirect para endereço local bloqueado: {guarda.bloqueios[antes]}") from None
        raise
    if visita.url.startswith("chrome-error:") and len(guarda.bloqueios) > antes:
        raise _EnderecoLocal(f"navegação para endereço local bloqueada: {guarda.bloqueios[-1]}")
    if not guarda.permitido(visita.url):
        raise _EnderecoLocal(f"página em endereço local bloqueada: {visita.url}")
    return visita


async def _capturar(ctx: Contexto, dominio: str, s: Servicos) -> Feito:
    cfg = s.config.captura
    async with async_playwright() as playwright:
        navegador = await playwright.chromium.launch(args=list(ARGS_DO_NAVEGADOR))
        try:
            with tempfile.TemporaryDirectory(prefix="radar-har-") as pasta_tmp:
                caminho_har = Path(pasta_tmp) / "captura.har"
                contexto = await navegador.new_context(**_opcoes_do_contexto(s.config.rede, caminho_har))
                try:
                    contexto.set_default_timeout(cfg.timeout_pagina_s * 1000)
                    if s.config.rede.proxy:
                        await contexto.add_init_script(_SEM_WEBRTC)
                    guarda = _Guarda(ctx.url_inicial)
                    await contexto.route("**/*", guarda.rotear)
                    await contexto.route_web_socket("**/*", guarda.rotear_websocket)
                    await _barrar_enderecos_locais(navegador, guarda)  # o navegador é desta captura e fecha no fim
                    try:
                        percurso = await _percorrer(contexto, ctx, cfg, s, guarda)
                    except _EnderecoLocal as erro:
                        raise ErroNo(f"{PREFIXO_FALHA_CAPTURA} {erro}", permanente=False) from erro
                finally:
                    await contexto.close()  # o HAR só é gravado quando o contexto fecha
                har = caminho_har.read_bytes()
        finally:
            await navegador.close()

    ref_har = s.custodia.guardar(har, "har", tipo="har", origem=ctx.url_inicial)
    destino = percurso.destino
    return Feito(
        {
            "paginas": [{**pagina, "har": ref_har} for pagina in percurso.paginas],  # um HAR por execução
            "terceiros": _terceiros(har, dominio, *([destino["dominio"]] if destino else [])),
            "bloqueada": percurso.bloqueada,
            "falhas": percurso.falhas,
            "destino": destino,
            "redirect_ignorado": percurso.redirect_ignorado,
        }
    )


class CapturaNo(NoBase):
    """Visita passiva da página inicial e de até `max_subpaginas` links do mesmo host da `url_inicial` (ou, depois de
    um redirect para outro domínio, do host onde a página inicial terminou).

    Saídas: `paginas` (`url`, `status` HTTP, e `html`, `texto`, `screenshot`, `har` como refs da
    custódia), `terceiros` (domínios registráveis das requisições, diferentes do alvo e do destino), `bloqueada`,
    `falhas` (as subpáginas que não puderam ser capturadas, com o motivo), `destino` (`{"url", "dominio"}` quando a
    página inicial terminou noutro domínio registrável, senão `None`) e `redirect_ignorado` (`{"url", "dominio",
    "motivo"}` quando esse domínio é plataforma, estacionamento ou serviço de terceiro e o alvo continua o mesmo,
    senão `None`); ver
    `_destino_do_redirect`.

    Os erros do nó distinguem o site do analista (I2, ver `_erro_da_captura`): "captura falhou: HTTP <código>" e
    "captura falhou: navegação: ..." falam do site; "captura indisponível: ..." é falha local e não conta para o E6.

    Se a página inicial é uma verificação anti-bot (ver `_e_desafio`), `bloqueada` é `True` e
    `paginas` só tem a `url`, o `status`, a screenshot e o HAR dela (sem `html` nem `texto`); nenhum
    link é seguido e o `wayback_snapshot` assume. Falha ao abrir a página inicial, ou resposta dela com
    erro HTTP (status >= 400 que não é desafio), é `ErroNo` não permanente: o `wayback_snapshot` assume
    do mesmo jeito. Subpágina com erro HTTP vai para `falhas` com o motivo `HTTP <status>`.
    """

    nome = "captura"
    entradas = ("alvo",)
    saidas = ("paginas", "terceiros", "bloqueada", "falhas", "destino", "redirect_ignorado")
    toca_alvo = True
    as_of = "so_atual"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito | Pulado:
        if ctx.modo_contato == "nenhum":
            return Pulado("modo_contato=nenhum")
        try:
            return await _capturar(ctx, entradas["alvo"]["dominio"], s)
        except ErroNo:
            raise
        except Exception as erro:  # o navegador, a rede do analista ou o próprio código: ver `_erro_da_captura`
            raise _erro_da_captura(erro) from erro
