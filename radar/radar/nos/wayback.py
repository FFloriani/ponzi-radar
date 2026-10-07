"""Nós do Wayback Machine: linha do tempo das capturas do domínio e snapshots das páginas."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urlencode, urlsplit

from radar.modelos import Contexto, ErroNo, Feito, Pulado
from radar.motor import NoBase, Servicos
from radar.nos._api import buscar_json
from radar.rede import ErroRede, RespostaRede
from radar.texto import texto_de_html

# páginas de regras (termos, planos, saque, indicação...): a Tarefa 8 também importa esta constante
PRIORIDADE = re.compile(
    r"termos|contrato|plano|faq|como-funciona|saque|indica|rentab|sobre|quem-somos", re.IGNORECASE
)

_BASE = "https://web.archive.org"
_CDX = f"{_BASE}/cdx/search/cdx"
_LIMITE_CDX = 10000
_TIMESTAMP = re.compile(r"\d{14}")
# o CDX do domínio traz imagens, scripts e documentos: só estas extensões (ou nenhuma) são página
_EXTENSOES_DE_PAGINA = frozenset({"html", "htm", "xhtml", "shtml", "php", "asp", "aspx", "jsp", "cfm"})
_BYTES_PARA_META = 4096
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_.:\-]+)""", re.IGNORECASE)


def _iso(timestamp: str) -> str:
    """`AAAAMMDDhhmmss` -> `AAAA-MM-DD`."""
    return f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"


def _data_valida(timestamp: str) -> bool:
    try:
        date.fromisoformat(_iso(timestamp))
    except ValueError:
        return False
    return True


def _capturas(dados: Any) -> list[tuple[str, str]]:
    """`(timestamp, original)` de cada linha do CDX. A primeira linha é o cabeçalho; resposta vazia
    ou só com o cabeçalho é "nenhuma captura". Linha malformada ou com data impossível é ignorada."""
    if not isinstance(dados, list):
        raise ErroNo("Wayback CDX: resposta não é uma lista de capturas", permanente=True)
    if not dados:
        return []
    cabecalho = dados[0]
    if not (isinstance(cabecalho, list) and "timestamp" in cabecalho and "original" in cabecalho):
        raise ErroNo("Wayback CDX: primeira linha não é o cabeçalho esperado", permanente=True)
    i_timestamp, i_original = cabecalho.index("timestamp"), cabecalho.index("original")
    capturas = []
    for linha in dados[1:]:
        if not isinstance(linha, list) or len(linha) <= max(i_timestamp, i_original):
            continue
        timestamp, original = linha[i_timestamp], linha[i_original]
        if (
            isinstance(timestamp, str)
            and _TIMESTAMP.fullmatch(timestamp)
            and _data_valida(timestamp)
            and isinstance(original, str)
            and original
        ):
            capturas.append((timestamp, original))
    return capturas


async def _consultar_cdx(s: Servicos, parametros: dict[str, str | int]) -> list[tuple[str, str]]:
    # ":" e "," ficam como estão (`filter=statuscode:200`, `fl=timestamp,original`). A URL idêntica
    # permite à `Rede` responder do cache a segunda consulta do domínio na mesma execução.
    url = f"{_CDX}?{urlencode(parametros, safe=':,')}"
    return _capturas(await buscar_json(s, url, "Wayback CDX"))


async def _listar_dominio(s: Servicos, dominio: str, as_of: date) -> list[tuple[str, str]]:
    """Capturas com status 200 de todo o domínio até o `as_of`, no máximo uma por URL por dia.

    A ordem do CDX é por URL e só depois por data, e o `limit` corta o fim da lista: quem usa a
    lista não pode contar com a ordem, e em domínios com mais de 10 mil capturas ela é parcial.
    """
    return await _consultar_cdx(
        s,
        {
            "url": dominio,
            "matchType": "domain",
            "output": "json",
            "fl": "timestamp,original",
            "filter": "statuscode:200",
            "collapse": "timestamp:8",
            "limit": _LIMITE_CDX,
            "to": as_of.strftime("%Y%m%d"),
        },
    )


async def _listar_home(s: Servicos, dominio: str, as_of: date) -> list[tuple[str, str]]:
    return await _consultar_cdx(
        s,
        {
            "url": f"{dominio}/",
            "to": as_of.strftime("%Y%m%d"),
            "filter": "statuscode:200",
            "fl": "timestamp,original",
            "output": "json",
        },
    )


class WaybackIndiceNo(NoBase):
    """Linha do tempo das capturas do domínio (e dos subdomínios) até o `as_of`.

    `total` conta as linhas do CDX (uma por URL por dia), não os dias com captura. `primeiro` e
    `ultimo` saem do menor e do maior timestamp, porque o CDX do domínio não vem em ordem de data.
    """

    nome = "wayback_indice"
    entradas = ("alvo",)
    saidas = ("primeiro", "ultimo", "total", "por_mes")
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        capturas = await _listar_dominio(s, entradas["alvo"]["dominio"], ctx.as_of)
        timestamps = sorted(timestamp for timestamp, _ in capturas)
        por_mes = Counter(f"{timestamp[:4]}-{timestamp[4:6]}" for timestamp in timestamps)
        return Feito(
            {
                "primeiro": _iso(timestamps[0]) if timestamps else None,
                "ultimo": _iso(timestamps[-1]) if timestamps else None,
                "total": len(timestamps),
                "por_mes": dict(por_mes),  # as chaves já saem em ordem: os timestamps estão ordenados
            }
        )


def _chave(original: str) -> tuple[str, str, str] | None:
    """`(host, caminho, query)` que identifica a página.

    Esquema, `www.`, porta, usuário e `/` final não distinguem: `http://x.com:80/faq`,
    `https://www.x.com/faq/` e `http://x.com/faq` são a mesma página.
    """
    try:
        partes = urlsplit(original)
    except ValueError:
        return None
    host = (partes.hostname or "").removeprefix("www.")
    if not host:
        return None
    return host, partes.path.rstrip("/"), partes.query


def _parece_pagina(caminho: str) -> bool:
    _, ponto, extensao = caminho.rpartition("/")[2].rpartition(".")
    return not ponto or extensao.lower() in _EXTENSOES_DE_PAGINA


def _subpaginas(capturas: list[tuple[str, str]], limite: int) -> list[tuple[str, str]]:
    """Até `limite` páginas de regras do domínio, cada uma pelo snapshot mais recente da lista.

    A home fica de fora (é buscada à parte). `PRIORIDADE` olha o caminho e a query, nunca o
    domínio: em `planofacil.com.br` toda URL casaria com "plano". Empata-se pelas mais rasas e
    curtas, que costumam ser as páginas principais (`/termos`, `/faq`) e não posts do blog.
    """
    recentes: dict[tuple[str, str, str], tuple[str, str]] = {}
    for captura in capturas:
        chave = _chave(captura[1])
        if chave is None:
            continue
        _, caminho, query = chave
        if not (caminho or query) or not _parece_pagina(caminho):
            continue
        if not PRIORIDADE.search(f"{caminho}?{query}" if query else caminho):
            continue
        if chave not in recentes or captura > recentes[chave]:
            recentes[chave] = captura
    ordem = sorted(recentes, key=lambda c: (c[1].count("/"), len(c[1]), *c))
    return [recentes[chave] for chave in ordem[: max(0, limite)]]


def _decodificar(resposta: RespostaRede) -> str:
    """Charset do cabeçalho; sem ele, o do `<meta>` do HTML (sites antigos em ISO-8859-1); senão UTF-8."""
    if "charset" not in resposta.headers.get("content-type", "").lower():
        achado = _META_CHARSET.search(resposta.conteudo[:_BYTES_PARA_META])
        if achado:
            try:
                texto = resposta.conteudo.decode(achado.group(1).decode("ascii"), errors="replace")
            except LookupError:  # charset que o Python não conhece
                pass
            else:
                return texto.removeprefix("﻿")
    return resposta.texto


async def _baixar(s: Servicos, timestamp: str, original: str) -> dict:
    """Snapshot cru (`id_`: sem a barra do Wayback e sem links reescritos), HTML e texto na custódia."""
    url = f"{_BASE}/web/{timestamp}id_/{original}"
    try:
        resposta = await s.rede.get(url, tipo="api")
    except ErroRede as erro:
        raise ErroNo(f"Wayback: {erro}", permanente=erro.permanente) from erro
    texto = texto_de_html(_decodificar(resposta))
    return {
        "url": original,
        "timestamp": timestamp,
        "html": s.custodia.guardar(resposta.conteudo, "html", tipo="snapshot", origem=url),
        "texto": s.custodia.guardar(texto.encode("utf-8"), "txt", tipo="texto", origem=url),
    }


class WaybackSnapshotNo(NoBase):
    """Fonte da página quando não há captura ao vivo utilizável.

    Roda se a análise é retroativa, se `modo_contato` é `nenhum`, se a captura não terminou `feito`
    (não há `captura` nas entradas) ou se ela foi bloqueada. Senão: `Pulado("captura ok")`.
    Busca a página inicial e as subpáginas de regras mais recentes até o `as_of`. A falha de uma
    subpágina só a tira da saída e vai para `falhas`; a falha da página inicial derruba o nó.
    """

    nome = "wayback_snapshot"
    entradas = ("alvo",)
    opcionais = ("captura",)
    saidas = ("paginas", "falhas")
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito | Pulado:
        captura = entradas.get("captura")
        if not (
            ctx.retroativo
            or ctx.modo_contato == "nenhum"
            or captura is None
            or captura.get("bloqueada") is True
        ):
            return Pulado("captura ok")

        dominio = entradas["alvo"]["dominio"]
        home = await _listar_home(s, dominio, ctx.as_of)
        if not home:
            raise ErroNo(f"sem snapshot até {ctx.as_of.isoformat()}", permanente=True)
        # a lista vem em ordem crescente de data; o máximo não depende disso
        paginas = [await _baixar(s, *max(home))]

        falhas = []
        limite = s.config.captura.max_subpaginas
        if limite > 0:
            capturas = await _listar_dominio(s, dominio, ctx.as_of)
            for timestamp, original in _subpaginas(capturas, limite):
                try:
                    paginas.append(await _baixar(s, timestamp, original))
                except ErroNo as erro:
                    falhas.append({"url": original, "timestamp": timestamp, "motivo": erro.mensagem})
        return Feito({"paginas": paginas, "falhas": falhas})
