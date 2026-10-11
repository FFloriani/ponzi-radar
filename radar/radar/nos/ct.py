"""Nó `ct`: certificados do domínio nos logs de Certificate Transparency (crt.sh)."""

from __future__ import annotations

import re
from urllib.parse import quote

from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos
from radar.nos._api import buscar_json

_URL = "https://crt.sh/"
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")


class CtNo(NoBase):
    """Certificados do domínio que o nó `destino` escolheu (o do alvo, ou o do site para onde ele redireciona). Só conta
    o que já existia no `as_of`: `not_before[:10] <= as_of`."""

    nome = "ct"
    entradas = ("destino",)
    saidas = ("primeiro_certificado", "total", "sans")
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        dominio = quote(entradas["destino"]["dominio"], safe="")
        certificados = await buscar_json(s, f"{_URL}?q={dominio}&output=json", "crt.sh")
        if not isinstance(certificados, list):
            raise ErroNo("crt.sh: resposta não é uma lista de certificados", permanente=True)
        limite = ctx.as_of.isoformat()
        datas: list[str] = []
        sans: set[str] = set()
        for certificado in certificados:
            if not isinstance(certificado, dict):
                continue
            inicio = certificado.get("not_before")
            # sem data válida não dá para saber se já existia no as_of: fica de fora
            if not isinstance(inicio, str) or not _DATA.match(inicio) or inicio[:10] > limite:
                continue
            datas.append(inicio[:10])
            nomes = certificado.get("name_value")
            for nome in nomes.split("\n") if isinstance(nomes, str) else []:
                nome = nome.strip().lower().removeprefix("*.")
                if nome:
                    sans.add(nome)
        return Feito(
            {
                "primeiro_certificado": min(datas) if datas else None,
                "total": len(datas),
                "sans": sorted(sans),
            }
        )
