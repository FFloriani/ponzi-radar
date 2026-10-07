"""Nó `captura`: visita passiva do site investigado com o Chromium, artefatos na custódia e detecção de anti-bot.

É o único nó que toca o site do alvo, e só como um visitante comum: `goto` em links, nunca clique,
preenchimento nem envio de formulário; downloads recusados e service workers bloqueados. O Playwright
é a exceção à regra "toda saída via `Rede`": o navegador tem pilha de rede própria e recebe o proxy e
o `User-Agent` de `config.rede`.
"""

from __future__ import annotations

import contextlib
import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from playwright.async_api import BrowserContext, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from radar.config import CapturaConfig, RedeConfig
from radar.modelos import Contexto, ErroNo, Feito, Pulado
from radar.motor import NoBase, Servicos
from radar.nos._paginas import Chave, chave_da_pagina, ordenar_paginas
from radar.nos.alvo import dominio_registravel

# Desafio anti-bot: o título da página de verificação, ou marcas de captcha/desafio no HTML numa
# página quase sem texto (a de um site de verdade, com captcha num formulário, tem mais de 200 caracteres)
_TITULO_DESAFIO = re.compile(r"just a moment|attention required|verifique (que )?você é humano", re.IGNORECASE)
_MARCAS_DESAFIO = ("cf-chl", "challenge-platform", "g-recaptcha", "h-captcha")
_TEXTO_CURTO = 200
_MOTIVO_DESAFIO = "desafio anti-bot"
# links para estes arquivos nunca são seguidos (não é página e abrir um download é contato demais)
_EXTENSOES_DE_ARQUIVO = frozenset({"zip", "pdf", "exe", "apk", "rar", "7z", "dmg", "msi"})
_JS_LINKS = "() => Array.from(document.links, (link) => link.href)"


def _e_desafio(titulo: str, html: str, texto: str) -> bool:
    """A página é uma verificação anti-bot (Cloudflare, reCAPTCHA, hCaptcha...), não o conteúdo do site."""
    if _TITULO_DESAFIO.search(titulo):
        return True
    html = html.lower()
    return any(marca in html for marca in _MARCAS_DESAFIO) and len(texto.strip()) < _TEXTO_CURTO


def _opcoes_do_contexto(rede: RedeConfig, caminho_har: Path) -> dict[str, Any]:
    """Argumentos de `browser.new_context`: o navegador de um visitante, que grava o HAR e não baixa nada."""
    opcoes: dict[str, Any] = {
        "accept_downloads": False,
        "service_workers": "block",
        "user_agent": rede.ua_navegador,
        "record_har_path": str(caminho_har),
        "record_har_content": "embed",
    }
    if rede.proxy:
        opcoes["proxy"] = {"server": rede.proxy}
    return opcoes


def _terceiros(har: bytes, dominio_alvo: str) -> list[str]:
    """Domínios registráveis das requisições do HAR que não são o do alvo, sem repetição e em ordem.

    IP e nome sem sufixo público (`localhost`) não têm domínio registrável: valem pelo próprio host.
    """
    alvo = dominio_alvo.lower()
    dominios: set[str] = set()
    for entrada in json.loads(har)["log"]["entries"]:
        try:
            host = urlsplit(entrada["request"]["url"]).hostname
        except ValueError:  # a URL vem do site investigado
            continue
        if not host:  # data:, about:blank...
            continue
        dominio = dominio_registravel(host) or host
        if dominio != alvo:
            dominios.add(dominio)
    return sorted(dominios)


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


def _escolher_links(hrefs: list, site: list[str], limite: int) -> list[str]:
    """As subpáginas a visitar: até `limite` links do mesmo host que as páginas do `site`.

    `site` são as páginas já capturadas (a URL inicial e a em que ela terminou, depois dos
    redirects): o host de cada uma vale como "mesmo host" (com ou sem `www.`) e nenhuma é revisitada.
    Links para arquivos, de outro esquema que não http(s) e repetidos depois de tirar o fragmento
    ficam de fora. A ordem e o corte de variantes de query são os do `wayback_snapshot`
    (`ordenar_paginas`): as páginas de regras primeiro, as sem query antes das com query, no máximo
    1 variante de query por caminho (a primeira do documento).
    """
    hosts = {host for host in map(_host_do_site, site) if host}
    ja_vistas = {chave for chave in map(chave_da_pagina, site) if chave is not None}
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
    linha = next((linha.strip() for linha in str(erro).splitlines() if linha.strip()), "")
    if isinstance(erro, PlaywrightError):
        return linha or type(erro).__name__
    return f"{type(erro).__name__}: {linha}" if linha else type(erro).__name__


def _bytes(texto: str) -> bytes:
    # o texto vem do site investigado. O Playwright 1.63 já troca surrogate solitário (UTF-16 inválido)
    # por U+FFFD, mas sem `replace` um que escapasse derrubaria o nó em vez de só virar "?"
    return texto.encode("utf-8", errors="replace")


@dataclass
class _Visita:
    """O que o navegador viu numa página, ainda fora da custódia. `url` é onde ela terminou."""

    url: str
    titulo: str
    html: str
    texto: str
    screenshot: bytes
    links: list = field(default_factory=list)

    @property
    def e_desafio(self) -> bool:
        return _e_desafio(self.titulo, self.html, self.texto)


async def _visitar(contexto: BrowserContext, url: str, cfg: CapturaConfig, com_links: bool) -> _Visita:
    """Abre `url` numa aba nova (o travamento de uma não contamina as outras) e lê o que renderizou."""
    pagina = await contexto.new_page()
    try:
        await pagina.goto(url, wait_until="domcontentloaded")
        try:
            await pagina.wait_for_load_state("networkidle", timeout=cfg.networkidle_s * 1000)
        except PlaywrightTimeout:
            pass  # polling e relógios mantêm a rede ocupada para sempre: o que já carregou basta
        return _Visita(
            url=pagina.url,
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
        "html": s.custodia.guardar(_bytes(v.html), "html", tipo="pagina", origem=v.url),
        "texto": s.custodia.guardar(_bytes(v.texto), "txt", tipo="texto", origem=v.url),
        "screenshot": s.custodia.guardar(v.screenshot, "png", tipo="screenshot", origem=v.url),
    }


def _guardar_desafio(s: Servicos, v: _Visita) -> None:
    """O HTML da verificação fica na custódia como prova do bloqueio, mas não vira página."""
    s.custodia.guardar(_bytes(v.html), "html", tipo="desafio", origem=v.url)


async def _percorrer(
    contexto: BrowserContext, url_inicial: str, cfg: CapturaConfig, s: Servicos
) -> tuple[list[dict], bool, list[dict]]:
    """Visita a página inicial e as subpáginas. Devolve `(paginas sem o HAR, bloqueada, falhas)`.

    Falha na página inicial levanta (`PlaywrightError`). Falha numa subpágina, inclusive erro
    inesperado ao processar o conteúdo do site, vai para `falhas` e as outras seguem.
    """
    inicio = await _visitar(contexto, url_inicial, cfg, com_links=True)
    if inicio.e_desafio:
        _guardar_desafio(s, inicio)
        screenshot = s.custodia.guardar(inicio.screenshot, "png", tipo="screenshot", origem=inicio.url)
        return [{"url": inicio.url, "screenshot": screenshot}], True, []  # sem texto e sem seguir links

    paginas = [_guardar_pagina(s, inicio)]
    falhas: list[dict] = []
    for url in _escolher_links(inicio.links, [url_inicial, inicio.url], cfg.max_subpaginas):
        try:
            visita = await _visitar(contexto, url, cfg, com_links=False)
            if visita.e_desafio:
                _guardar_desafio(s, visita)
                falhas.append({"url": url, "motivo": _MOTIVO_DESAFIO})
                break  # o site pediu verificação: não insiste
            paginas.append(_guardar_pagina(s, visita))
        except Exception as erro:  # o conteúdo é do site investigado: nada dele derruba o nó
            falhas.append({"url": url, "motivo": _motivo(erro)})
    return paginas, False, falhas


async def _capturar(ctx: Contexto, dominio: str, s: Servicos) -> Feito:
    cfg = s.config.captura
    async with async_playwright() as playwright:
        navegador = await playwright.chromium.launch()
        try:
            with tempfile.TemporaryDirectory(prefix="radar-har-") as pasta_tmp:
                caminho_har = Path(pasta_tmp) / "captura.har"
                contexto = await navegador.new_context(**_opcoes_do_contexto(s.config.rede, caminho_har))
                try:
                    contexto.set_default_timeout(cfg.timeout_pagina_s * 1000)
                    paginas, bloqueada, falhas = await _percorrer(contexto, ctx.url_inicial, cfg, s)
                finally:
                    await contexto.close()  # o HAR só é gravado quando o contexto fecha
                har = caminho_har.read_bytes()
        finally:
            await navegador.close()

    ref_har = s.custodia.guardar(har, "har", tipo="har", origem=ctx.url_inicial)
    return Feito(
        {
            "paginas": [{**pagina, "har": ref_har} for pagina in paginas],  # um HAR por execução
            "terceiros": _terceiros(har, dominio),
            "bloqueada": bloqueada,
            "falhas": falhas,
        }
    )


class CapturaNo(NoBase):
    """Visita passiva da página inicial e de até `max_subpaginas` links do mesmo host.

    Saídas: `paginas` (`url`, `html`, `texto`, `screenshot`, `har`: refs da custódia), `terceiros`
    (domínios registráveis das requisições, diferentes do alvo), `bloqueada` e `falhas` (as
    subpáginas que não puderam ser capturadas, com o motivo).

    Se a página inicial é uma verificação anti-bot, `bloqueada` é `True` e `paginas` só tem a
    screenshot dela (sem `html` nem `texto`); nenhum link é seguido e o `wayback_snapshot` assume.
    Falha ao abrir a página inicial é `ErroNo` não permanente.
    """

    nome = "captura"
    entradas = ("alvo",)
    saidas = ("paginas", "terceiros", "bloqueada", "falhas")
    toca_alvo = True
    as_of = "so_atual"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito | Pulado:
        if ctx.modo_contato == "nenhum":
            return Pulado("modo_contato=nenhum")
        try:
            return await _capturar(ctx, entradas["alvo"]["dominio"], s)
        except PlaywrightError as erro:
            raise ErroNo(f"captura falhou: {_motivo(erro)}", permanente=False) from erro
