"""Nó `dns`: registros A, AAAA, MX, NS e TXT por DNS sobre HTTPS (Cloudflare)."""

from __future__ import annotations

from urllib.parse import quote

from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos
from radar.nos._api import buscar_json

_URL = "https://cloudflare-dns.com/dns-query"
# número do tipo de registro no DNS: a resposta de um A pode trazer CNAMEs (5) que não são endereços
_TIPOS = {"A": 1, "AAAA": 28, "MX": 15, "NS": 2, "TXT": 16}
_NXDOMAIN = 3
# RCODE do DoH: 0 (NOERROR) e 3 (NXDOMAIN) são respostas de verdade; o resto é falha de resolução
_STATUS_VALIDOS = (0, _NXDOMAIN)
_NOMES_STATUS = {1: "FORMERR", 2: "SERVFAIL", 4: "NOTIMP", 5: "REFUSED"}


class DnsNo(NoBase):
    """Uma consulta por tipo, do domínio que o nó `destino` escolheu (o do alvo, ou o do site para onde ele
    redireciona). O DNS só responde o presente: no modo retroativo o motor pula o nó."""

    nome = "dns"
    entradas = ("destino",)
    saidas = ("A", "AAAA", "MX", "NS", "TXT", "nxdomain")
    as_of = "so_atual"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        dominio = quote(entradas["destino"]["dominio"], safe="")
        saidas: dict = {}
        nxdomain = False
        for tipo, codigo in _TIPOS.items():
            dados = await buscar_json(
                s,
                f"{_URL}?name={dominio}&type={tipo}",
                f"DNS {tipo}",
                headers={"accept": "application/dns-json"},
            )
            if not isinstance(dados, dict):
                raise ErroNo(f"DNS {tipo}: resposta não é um objeto JSON", permanente=True)
            status = dados.get("Status")
            if status not in _STATUS_VALIDOS:
                # SERVFAIL, REFUSED, FORMERR...: o resolvedor não conseguiu responder. Lista vazia
                # aqui seria "sem registros", e isso o DNS não disse
                nome = _NOMES_STATUS.get(status) if isinstance(status, int) else None
                raise ErroNo(
                    f"DNS {tipo}: Status {status} ({nome or 'desconhecido'}) "
                    f"para {entradas['destino']['dominio']}: falha de resolução, não ausência de registros",
                    permanente=False,
                )
            registros = dados.get("Answer")
            saidas[tipo] = [
                r["data"]
                for r in (registros if isinstance(registros, list) else [])
                if isinstance(r, dict) and r.get("type") == codigo and isinstance(r.get("data"), str)
            ]
            if tipo == "A":
                nxdomain = dados.get("Status") == _NXDOMAIN
        saidas["nxdomain"] = nxdomain
        return Feito(saidas)
