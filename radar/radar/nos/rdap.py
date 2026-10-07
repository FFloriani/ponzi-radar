"""Nó `rdap`: datas de registro e expiração, registrador e CNPJ do titular do domínio."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos
from radar.nos._api import buscar_json

_URL_BR = "https://rdap.registro.br/domain/"
_URL_GERAL = "https://rdap.org/domain/"  # redireciona para o RDAP do registro do TLD
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")


def _lista(valor: Any) -> list:
    return valor if isinstance(valor, list) else []


def _data_do_evento(dados: dict, acao: str) -> str | None:
    """`AAAA-MM-DD` do evento do domínio (só o nível de cima: as entidades têm eventos próprios)."""
    for evento in _lista(dados.get("events")):
        if isinstance(evento, dict) and evento.get("eventAction") == acao:
            data = evento.get("eventDate")
            if isinstance(data, str) and _DATA.match(data):
                return data[:10]
    return None


def _entidades(dados: dict, papel: str) -> list[dict]:
    return [
        e
        for e in _lista(dados.get("entities"))
        if isinstance(e, dict) and papel in (str(r).lower() for r in _lista(e.get("roles")))
    ]


def _nome_da_entidade(entidade: dict) -> str | None:
    """Nome do vCard (`fn`) ou, sem ele, o `handle`."""
    vcard = entidade.get("vcardArray")
    if isinstance(vcard, list) and len(vcard) > 1:
        for propriedade in _lista(vcard[1]):
            if isinstance(propriedade, list) and len(propriedade) > 3 and propriedade[0] == "fn":
                if isinstance(propriedade[3], str) and propriedade[3].strip():
                    return propriedade[3].strip()
    handle = entidade.get("handle")
    return handle.strip() if isinstance(handle, str) and handle.strip() else None


def _cnpj_do_titular(dados: dict) -> str | None:
    """14 dígitos do `publicIds[type=cnpj]` do titular. CPF e qualquer outro id são ignorados."""
    for titular in _entidades(dados, "registrant"):
        for id_publico in _lista(titular.get("publicIds")):
            if isinstance(id_publico, dict) and str(id_publico.get("type", "")).lower() == "cnpj":
                digitos = re.sub(r"\D", "", str(id_publico.get("identifier", "")))
                if len(digitos) == 14:
                    return digitos
    return None


class RdapNo(NoBase):
    """Só o titular (CNPJ) é dado do presente; a data de registro é a mesma em qualquer `as_of`.

    No modo retroativo o CNPJ do titular não é lido (`None`) e fica marcado em
    `vazamento_temporal`, para a pontuação saber que a ausência vem do `as_of`.
    """

    nome = "rdap"
    entradas = ("alvo",)
    saidas = ("registro", "expiracao", "registrador", "cnpj_titular", "vazamento_temporal")
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        dominio = entradas["alvo"]["dominio"]
        base = _URL_BR if dominio.endswith(".br") else _URL_GERAL
        dados = await buscar_json(s, base + quote(dominio, safe=""), "RDAP")
        if not isinstance(dados, dict):
            raise ErroNo(f"RDAP: resposta de {dominio} não é um objeto JSON", permanente=True)
        registrador = next((_nome_da_entidade(e) for e in _entidades(dados, "registrar")), None)
        return Feito(
            {
                "registro": _data_do_evento(dados, "registration"),
                "expiracao": _data_do_evento(dados, "expiration"),
                "registrador": registrador,
                "cnpj_titular": None if ctx.retroativo else _cnpj_do_titular(dados),
                "vazamento_temporal": ["cnpj_titular"] if ctx.retroativo else [],
            }
        )
