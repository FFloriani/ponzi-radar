"""Nós do Wayback Machine: linha do tempo das capturas do domínio e snapshots das páginas."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urlencode

from radar.modelos import Contexto, ErroNo, Feito, Pulado
from radar.motor import NoBase, Servicos
from radar.nos._api import buscar_json
# a definição de PRIORIDADE mora em _paginas (a captura usa a mesma política); daqui ela continua importável
from radar.nos._paginas import (  # noqa: F401
    PRIORIDADE,
    Chave,
    casa_prioridade,
    chave_da_pagina,
    ordenar_paginas,
)
from radar.rede import ErroRede
from radar.texto import decodificar, texto_de_html

_BASE = "https://web.archive.org"
_CDX = f"{_BASE}/cdx/search/cdx"
_LIMITE_CDX = 10000
_TIMESTAMP = re.compile(r"\d{14}")
# o CDX filtra por mimetype, mas o tipo vem do que o servidor declarou: uma imagem, um script ou um
# documento servido como text/html (página de erro com status 200, por exemplo) não é página de regras
_EXTENSOES_DE_PAGINA = frozenset({"html", "htm", "xhtml", "shtml", "php", "asp", "aspx", "jsp", "cfm"})


def _iso(timestamp: str) -> str:
    """`AAAAMMDDhhmmss` -> `AAAA-MM-DD`."""
    return f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"


def _data_valida(timestamp: str) -> bool:
    try:
        date.fromisoformat(_iso(timestamp))
    except ValueError:
        return False
    return True


def _capturas(dados: Any) -> tuple[list[tuple[str, str]], int]:
    """`(timestamp, original)` de cada linha do CDX e quantas linhas de dados vieram.

    A primeira linha é o cabeçalho; resposta vazia ou só com o cabeçalho é "nenhuma captura".
    Linha malformada ou com data impossível é ignorada, mas a contagem de linhas de dados é feita
    antes de qualquer descarte: é ela que mostra se o `limit` do CDX foi atingido.
    """
    if not isinstance(dados, list):
        raise ErroNo("Wayback CDX: resposta não é uma lista de capturas", permanente=True)
    if not dados:
        return [], 0
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
    return capturas, len(dados) - 1


async def _consultar_cdx(
    s: Servicos, parametros: list[tuple[str, str | int]]
) -> tuple[list[tuple[str, str]], int]:
    # ":", "," e "/" ficam como estão (`filter=mimetype:text/html`, `fl=timestamp,original`). A URL
    # idêntica permite à `Rede` responder do cache a segunda listagem do domínio na mesma execução.
    url = f"{_CDX}?{urlencode(parametros, safe=':,/')}"
    return _capturas(await buscar_json(s, url, "Wayback CDX"))


async def _listar_dominio(
    s: Servicos, dominio: str, as_of: date
) -> tuple[list[tuple[str, str]], bool]:
    """Capturas HTML (status 200) de todo o domínio até o `as_of`, e se o CDX chegou ao `limit`.

    Sem `collapse`: cada captura é uma linha. A ordem do CDX é por URL e só depois por data, e o
    `limit` corta o fim da lista: quem usa a lista não pode contar com a ordem, e quando vem
    `truncado` ela está incompleta (faltam capturas de qualquer época, não só as mais recentes).
    """
    capturas, linhas = await _consultar_cdx(
        s,
        [
            ("url", dominio),
            ("matchType", "domain"),
            ("output", "json"),
            ("fl", "timestamp,original"),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("limit", _LIMITE_CDX),
            ("to", as_of.strftime("%Y%m%d")),
        ],
    )
    return capturas, linhas >= _LIMITE_CDX


async def _listar_home(s: Servicos, dominio: str, as_of: date) -> list[tuple[str, str]]:
    capturas, _ = await _consultar_cdx(
        s,
        [
            ("url", f"{dominio}/"),
            ("to", as_of.strftime("%Y%m%d")),
            ("filter", "statuscode:200"),
            ("fl", "timestamp,original"),
            ("output", "json"),
        ],
    )
    return capturas


class WaybackIndiceNo(NoBase):
    """Linha do tempo das capturas HTML do domínio (e dos subdomínios) até o `as_of`.

    `total` e `por_mes` contam capturas, não URLs nem dias. `primeiro` e `ultimo` saem do menor e do
    maior timestamp, porque o CDX do domínio não vem em ordem de data. `truncado` é `True` quando o
    CDX devolveu 10 mil linhas (o `limit`): o resto do domínio não entrou na conta.
    """

    nome = "wayback_indice"
    entradas = ("alvo",)
    saidas = ("primeiro", "ultimo", "total", "por_mes", "truncado")
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        capturas, truncado = await _listar_dominio(s, entradas["alvo"]["dominio"], ctx.as_of)
        timestamps = sorted(timestamp for timestamp, _ in capturas)
        por_mes = Counter(f"{timestamp[:4]}-{timestamp[4:6]}" for timestamp in timestamps)
        return Feito(
            {
                "primeiro": _iso(timestamps[0]) if timestamps else None,
                "ultimo": _iso(timestamps[-1]) if timestamps else None,
                "total": len(timestamps),
                "por_mes": dict(por_mes),  # as chaves já saem em ordem: os timestamps estão ordenados
                "truncado": truncado,
            }
        )


def _parece_pagina(caminho: str) -> bool:
    _, ponto, extensao = caminho.rpartition("/")[2].rpartition(".")
    return not ponto or extensao.lower() in _EXTENSOES_DE_PAGINA


def _subpaginas(capturas: list[tuple[str, str]], limite: int) -> list[tuple[str, str]]:
    """Até `limite` páginas de regras do domínio, cada uma pelo snapshot mais recente da lista.

    A home fica de fora (é buscada à parte), assim como o que não é página e o que não casa com
    `PRIORIDADE`. A ordem de leitura e o corte de variantes de query são os de `ordenar_paginas`;
    entre variantes iguais vale a de captura mais recente.
    """
    recentes: dict[Chave, tuple[str, str]] = {}
    for captura in capturas:
        chave = chave_da_pagina(captura[1])
        if chave is None:
            continue
        _, caminho, query = chave
        if not (caminho or query) or not _parece_pagina(caminho) or not casa_prioridade(chave):
            continue
        if chave not in recentes or captura > recentes[chave]:
            recentes[chave] = captura
    ordem = ordenar_paginas(recentes, desempate=lambda captura: captura)
    return [recentes[chave] for chave in ordem[: max(0, limite)]]


async def _baixar(s: Servicos, timestamp: str, original: str) -> dict:
    """Snapshot cru (`id_`: sem a barra do Wayback e sem links reescritos), HTML e texto na custódia."""
    url = f"{_BASE}/web/{timestamp}id_/{original}"
    try:
        resposta = await s.rede.get(url, tipo="api")
    except ErroRede as erro:
        raise ErroNo(f"Wayback: {erro}", permanente=erro.permanente) from erro
    texto = texto_de_html(decodificar(resposta.conteudo, resposta.headers.get("content-type")))
    return {
        "url": original,
        "timestamp": timestamp,
        "html": s.custodia.guardar(resposta.conteudo, "html", tipo="snapshot", origem=url),
        "texto": s.custodia.guardar(texto.encode("utf-8"), "txt", tipo="texto", origem=url),
    }


def _motivo(erro: Exception) -> str:
    return erro.mensagem if isinstance(erro, ErroNo) else f"{type(erro).__name__}: {erro}"


class WaybackSnapshotNo(NoBase):
    """Fonte da página quando não há captura ao vivo utilizável.

    Roda se a análise é retroativa, se `modo_contato` é `nenhum`, se a captura não terminou `feito`
    (não há `captura` nas entradas) ou se ela foi bloqueada. Senão: `Pulado("captura ok")`.
    Busca a página inicial e as subpáginas de regras mais recentes até o `as_of`.

    Só a falha da página inicial derruba o nó. Tudo o que vem depois dela (a listagem do domínio e
    cada subpágina, o que inclui erro inesperado ao processar o conteúdo do site) vai para `falhas`
    e o nó termina `feito` com o que já tem; `url` e `timestamp` são `None` quando a falha é da
    listagem. `truncado` diz se a listagem de onde saíram as subpáginas estava incompleta.
    """

    nome = "wayback_snapshot"
    entradas = ("alvo",)
    opcionais = ("captura",)
    saidas = ("paginas", "falhas", "truncado")
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

        falhas: list[dict] = []
        truncado = False
        limite = s.config.captura.max_subpaginas
        if limite > 0:
            try:
                capturas, truncado = await _listar_dominio(s, dominio, ctx.as_of)
            except ErroNo as erro:
                falhas.append({"url": None, "timestamp": None, "motivo": erro.mensagem})
            else:
                for timestamp, original in _subpaginas(capturas, limite):
                    try:
                        paginas.append(await _baixar(s, timestamp, original))
                    except Exception as erro:  # o HTML é do site investigado: nada dele derruba o nó
                        falhas.append(
                            {"url": original, "timestamp": timestamp, "motivo": _motivo(erro)}
                        )
        return Feito({"paginas": paginas, "falhas": falhas, "truncado": truncado})
