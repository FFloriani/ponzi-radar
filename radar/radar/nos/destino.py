"""Nó `destino`: o domínio que os coletores analisam, o do alvo ou o do site para onde ele redireciona.

O aceite de 08/10/2026 mostrou o problema: `phinv.link` só redirecionava para `phinvestimentos.com/login`, e o RDAP, o
DNS, o CT e o Wayback olharam o redirecionador. A captura vê o redirect da página inicial e o entrega na saída
`destino` (`captura._destino_do_redirect`: outro domínio registrável que não é plataforma, serviço de estacionamento
nem serviço de terceiro); este nó o repassa aos coletores de domínio (`rdap`, `dns`, `ct`, `wayback_indice`,
`wayback_snapshot`) e a `registros` e `cvm_alertas`, que casam o domínio do alvo e o do destino.

Sem captura feita (pulada no modo `nenhum` e no retroativo, ou em erro) ou sem destino, vale o domínio do alvo. A
captura cuja página inicial é um desafio anti-bot (`bloqueada=True`) é feita e entrega o destino visto antes do desafio:
ele vale (ruling do controlador, M1 da revisão da T1), porque o desafio costuma estar no próprio host do destino. O nó
nunca falha: a saída da captura é conferida de novo (o destino tem de ser um domínio registrável, outro que o do alvo,
fora das plataformas, dos estacionamentos e dos serviços de terceiros) e o que não serve vira "sem redirect".
Consequência aceita: no modo com captura, os coletores de domínio esperam a captura terminar.
"""

from __future__ import annotations

from typing import Any

from radar.modelos import Contexto, Feito
from radar.motor import NoBase, Servicos
from radar.nos.alvo import dominio_registravel, e_estacionamento, e_plataforma, e_servico_de_terceiro


def _destino_valido(destino: Any, alvo: str) -> tuple[str, str] | None:
    """`(dominio, url)` do destino que a captura entregou, se ele serve como domínio analisado; senão `None`."""
    if not isinstance(destino, dict):
        return None
    dominio, url = destino.get("dominio"), destino.get("url")
    if not isinstance(dominio, str) or not isinstance(url, str) or not url:
        return None
    dominio = dominio.strip().lower()
    if not dominio or dominio != dominio_registravel(dominio) or dominio == alvo.lower():
        return None
    if e_plataforma(dominio) or e_estacionamento(dominio) or e_servico_de_terceiro(dominio):
        return None
    return dominio, url


class DestinoNo(NoBase):
    """Saídas: `dominio` (o que os coletores analisam), `redirecionado_de` (o domínio do alvo, quando houve redirect;
    senão `None`) e `url_destino` (onde a página inicial terminou, quando houve redirect; senão `None`)."""

    nome = "destino"
    entradas = ("alvo",)
    opcionais = ("captura",)
    saidas = ("dominio", "redirecionado_de", "url_destino")
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        alvo = entradas["alvo"]["dominio"]
        captura = entradas.get("captura")
        destino = _destino_valido(captura.get("destino") if isinstance(captura, dict) else None, alvo)
        if destino is None:
            return Feito({"dominio": alvo, "redirecionado_de": None, "url_destino": None})
        dominio, url = destino
        return Feito({"dominio": dominio, "redirecionado_de": alvo, "url_destino": url})
