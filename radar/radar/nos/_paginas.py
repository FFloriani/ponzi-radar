"""Escolha das subpáginas de um site: a política que o `wayback_snapshot` e a `captura` compartilham."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any, TypeVar
from urllib.parse import urlsplit

# páginas de regras (termos, planos, saque, indicação...)
PRIORIDADE = re.compile(
    r"termos|contrato|plano|faq|como-funciona|saque|indica|rentab|sobre|quem-somos", re.IGNORECASE
)

# `(host, caminho, query)`: o que identifica uma página
Chave = tuple[str, str, str]
T = TypeVar("T")


def chave_da_pagina(url: str) -> Chave | None:
    """`(host, caminho, query)` que identifica a página; `None` se a URL não tem host ou é inválida.

    Esquema, `www.`, porta, usuário, fragmento e `/` final não distinguem: `http://x.com:80/faq`,
    `https://www.x.com/faq/` e `http://x.com/faq#topo` são a mesma página.
    """
    try:
        partes = urlsplit(url)
    except ValueError:
        return None
    host = (partes.hostname or "").removeprefix("www.")
    if not host:
        return None
    return host, partes.path.rstrip("/"), partes.query


def casa_prioridade(chave: Chave) -> bool:
    """`PRIORIDADE` olha o caminho e a query, nunca o host: em `planofacil.com.br` tudo casaria."""
    _, caminho, query = chave
    return PRIORIDADE.search(f"{caminho}?{query}" if query else caminho) is not None


def ordenar_paginas(candidatas: Mapping[Chave, T], desempate: Callable[[T], Any]) -> list[Chave]:
    """As chaves de `candidatas` na ordem em que as páginas devem ser lidas, sem variantes repetidas.

    Primeiro as que casam com `PRIORIDADE`; dentro de cada grupo, as páginas sem query (das mais
    rasas e curtas para as mais fundas) e só depois as que dependem de query. Dessas últimas, no
    máximo 1 por (host, caminho): rastreadores de indicação geram uma URL por indicador
    (`/?indicacao=user1`, `user2`...), todas a mesma página, e ocupariam todos os slots. A variante
    que casa com `PRIORIDADE` vence; entre iguais, a de maior `desempate(candidata)` (a primeira
    vista, se empatar).
    """

    def preferencia(chave: Chave) -> tuple[bool, Any]:
        return casa_prioridade(chave), desempate(candidatas[chave])

    escolhidas: list[Chave] = []
    variante: dict[tuple[str, str], Chave] = {}
    for chave in candidatas:
        host, caminho, query = chave
        if not query:
            escolhidas.append(chave)
        elif (host, caminho) not in variante or preferencia(chave) > preferencia(variante[(host, caminho)]):
            variante[(host, caminho)] = chave
    escolhidas.extend(variante.values())
    return sorted(
        escolhidas,
        key=lambda c: (not casa_prioridade(c), bool(c[2]), c[1].count("/"), len(c[1]), *c),
    )
