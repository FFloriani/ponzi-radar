"""Chamada comum dos coletores de API: GET pela `Rede`, resposta bruta na custódia, JSON decodificado."""

from __future__ import annotations

from typing import Any

from radar.modelos import ErroNo
from radar.motor import Servicos
from radar.rede import ErroRede


async def buscar_json(s: Servicos, url: str, rotulo: str, headers: dict | None = None) -> Any:
    """GET em `url` e o JSON da resposta.

    O corpo bruto vai para a custódia mesmo quando não é JSON (é evidência do que a API devolveu).
    Falha de rede vira `ErroNo` que herda `permanente` do `ErroRede`; corpo que não é JSON é
    `ErroNo` permanente. A mensagem sempre começa com `rotulo`.
    """
    try:
        resposta = await s.rede.get(url, tipo="api", headers=headers)
    except ErroRede as erro:
        raise ErroNo(f"{rotulo}: {erro}", permanente=erro.permanente) from erro
    try:
        dados = resposta.json()
    except ValueError as erro:  # JSONDecodeError e UnicodeDecodeError
        s.custodia.guardar(resposta.conteudo, "txt", tipo="api", origem=url)
        raise ErroNo(
            f"{rotulo}: GET {url} devolveu corpo que não é JSON ({erro})", permanente=True
        ) from erro
    s.custodia.guardar(resposta.conteudo, "json", tipo="api", origem=url)
    return dados
