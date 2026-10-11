"""Nó `dns`: registros A, AAAA, MX, NS e TXT por DNS sobre HTTPS (Cloudflare)."""

from __future__ import annotations

from urllib.parse import quote

from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos
from radar.nos._api import buscar_json

_URL = "https://cloudflare-dns.com/dns-query"
# número do tipo de registro no DNS: a resposta de um A pode trazer CNAMEs (5) que não são endereços
_TIPOS = {"A": 1, "AAAA": 28, "MX": 15, "NS": 2, "TXT": 16}
# do redirecionador, só os endereços: a validação recusa o IP literal dele como fonte (M2 da revisão da T1)
_TIPOS_DO_REDIRECIONADOR = ("A", "AAAA")
_NXDOMAIN = 3
# RCODE do DoH: 0 (NOERROR) e 3 (NXDOMAIN) são respostas de verdade; o resto é falha de resolução
_STATUS_VALIDOS = (0, _NXDOMAIN)
_NOMES_STATUS = {1: "FORMERR", 2: "SERVFAIL", 4: "NOTIMP", 5: "REFUSED"}


async def _consultar(s: Servicos, dominio: str, tipo: str) -> tuple[list[str], bool]:
    """Os registros `tipo` de `dominio` e se a resposta foi NXDOMAIN. `ErroNo` quando a resposta não é JSON ou o
    resolvedor não conseguiu responder (SERVFAIL, REFUSED...): lista vazia aí seria "sem registros", e isso o DNS
    não disse."""
    dados = await buscar_json(
        s,
        f"{_URL}?name={quote(dominio, safe='')}&type={tipo}",
        f"DNS {tipo}",
        headers={"accept": "application/dns-json"},
    )
    if not isinstance(dados, dict):
        raise ErroNo(f"DNS {tipo}: resposta não é um objeto JSON", permanente=True)
    status = dados.get("Status")
    if status not in _STATUS_VALIDOS:
        nome = _NOMES_STATUS.get(status) if isinstance(status, int) else None
        raise ErroNo(
            f"DNS {tipo}: Status {status} ({nome or 'desconhecido'}) "
            f"para {dominio}: falha de resolução, não ausência de registros",
            permanente=False,
        )
    registros = dados.get("Answer")
    codigo = _TIPOS[tipo]
    encontrados = [
        r["data"]
        for r in (registros if isinstance(registros, list) else [])
        if isinstance(r, dict) and r.get("type") == codigo and isinstance(r.get("data"), str)
    ]
    return encontrados, status == _NXDOMAIN


async def _enderecos_do_redirecionador(s: Servicos, dominio: str) -> dict:
    """O A e o AAAA do redirecionador, por DoH (não toca o site). A falha não derruba o nó: os registros do destino
    são o dado da análise; a do redirecionador fica em `erro`, com as listas vazias."""
    enderecos: dict = {}
    try:
        for tipo in _TIPOS_DO_REDIRECIONADOR:
            enderecos[tipo], _ = await _consultar(s, dominio, tipo)
    except ErroNo as erro:
        return {"A": [], "AAAA": [], "erro": erro.mensagem}
    return enderecos


class DnsNo(NoBase):
    """Uma consulta por tipo, do domínio que o nó `destino` escolheu (o do alvo, ou o do site para onde ele
    redireciona). O DNS só responde o presente: no modo retroativo o motor pula o nó.

    `redirecionador`: depois de um redirect, o A e o AAAA do domínio do alvo (o redirecionador), à parte dos
    registros do destino (`{"A": [...], "AAAA": [...]}`, com `erro` se a consulta falhou); sem redirect, `None`.
    """

    nome = "dns"
    entradas = ("destino",)
    saidas = ("A", "AAAA", "MX", "NS", "TXT", "nxdomain", "redirecionador")
    as_of = "so_atual"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        destino = entradas["destino"]
        saidas: dict = {}
        nxdomain = False
        for tipo in _TIPOS:
            saidas[tipo], inexistente = await _consultar(s, destino["dominio"], tipo)
            if tipo == "A":
                nxdomain = inexistente
        saidas["nxdomain"] = nxdomain
        redirecionado_de = destino.get("redirecionado_de")
        saidas["redirecionador"] = (
            await _enderecos_do_redirecionador(s, redirecionado_de)
            if isinstance(redirecionado_de, str) and redirecionado_de
            else None
        )
        return Feito(saidas)
