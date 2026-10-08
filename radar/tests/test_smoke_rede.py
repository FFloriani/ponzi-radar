"""Smoke tests ao vivo (Tarefa 18): cada fonte real ainda responde no formato que o nó espera.

Só rodam com `-m rede` (o `addopts` do pyproject tira `rede` da suíte padrão):
`.venv/Scripts/python -m pytest -m rede -v`. Consultam a Petrobras (`petrobras.com.br`, CNPJ 33000167000101), domínio
antigo e empresa estável, pela `Rede` de verdade (limites e timeouts padrão). As asserções são de formato e de fatos
que não mudam (data de registro, abertura, razão social, CNAE), não de contagens que crescem.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import pytest

from radar.config import Config
from radar.custodia import Custodia
from radar.execucao import criar_indices
from radar.indices import _LINK_DELIBERACAO, _PAGINAS, _PARAMS_BUSCA, URL_DELIBERACOES_PAGINAS, URL_DELIBERACOES_PARTIDA
from radar.modelos import Contexto, Feito
from radar.motor import Servicos
from radar.nos._api import buscar_json
from radar.nos.cnpj import _FONTES, _empresa
from radar.nos.ct import CtNo
from radar.nos.dns import DnsNo
from radar.nos.rdap import RdapNo
from radar.nos.wayback import WaybackIndiceNo
from radar.rede import Rede

pytestmark = pytest.mark.rede

DOMINIO = "petrobras.com.br"
CNPJ = "33000167000101"
ENTRADAS = {"alvo": {"dominio": DOMINIO, "slug": "petrobras-com-br", "url_inicial": f"https://{DOMINIO}/"}}
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
_CAMPOS_DE_CPF = ("cnpj_cpf_do_socio", "cpf_representante_legal", "nome_representante_legal")


def contexto(pasta: Path, as_of: date | None = None) -> Contexto:
    agora = datetime.now()
    return Contexto(
        alvo=DOMINIO,
        slug="petrobras-com-br",
        url_inicial=f"https://{DOMINIO}/",
        as_of=as_of or agora.date(),
        data_execucao=agora,
        modo_contato="nenhum",
        modo_cego=False,
        run_id=f"petrobras-com-br/{agora:%Y-%m-%d_%H%M%S}",
        pasta=pasta,
    )


@pytest.fixture
async def servicos(tmp_path):
    config = Config(casos_dir=tmp_path / "casos")
    rede = Rede(config.rede)
    try:
        yield Servicos(
            config=config, rede=rede, custodia=Custodia(tmp_path / "execucao"), indices=criar_indices(config, rede)
        )
    finally:
        await rede.fechar()


async def _rodar(no, ctx: Contexto, s: Servicos) -> dict:
    resultado = await no.executar(ctx, ENTRADAS, {}, s)
    assert isinstance(resultado, Feito), resultado
    return resultado.saidas


# ---------------------------------------------------------------------------- domínio


async def test_rdap_registro_br(tmp_path, servicos):
    saidas = await _rodar(RdapNo(), contexto(tmp_path), servicos)
    assert saidas["registro"] == "1996-06-14"
    assert _DATA.fullmatch(saidas["expiracao"])
    assert saidas["cnpj_titular"] == CNPJ


async def test_dns_sobre_https(tmp_path, servicos):
    saidas = await _rodar(DnsNo(), contexto(tmp_path), servicos)
    assert saidas["nxdomain"] is False
    assert saidas["A"] and saidas["NS"] and saidas["MX"]


async def test_crt_sh(tmp_path, servicos):
    saidas = await _rodar(CtNo(), contexto(tmp_path), servicos)
    assert saidas["total"] > 0
    assert _DATA.fullmatch(saidas["primeiro_certificado"])
    assert any(nome.endswith(DOMINIO) for nome in saidas["sans"])


async def test_wayback_cdx(tmp_path, servicos):
    # o as_of antigo deixa a listagem pequena (~230 capturas até 1997; até 2000 já passa das 10 mil do limite)
    saidas = await _rodar(WaybackIndiceNo(), contexto(tmp_path, date(1998, 1, 1)), servicos)
    assert saidas["total"] > 0 and saidas["truncado"] is False
    assert "1996-01-01" <= saidas["primeiro"] <= saidas["ultimo"] <= "1998-01-01"
    assert sum(saidas["por_mes"].values()) == saidas["total"]


# ---------------------------------------------------------------------------- CNPJ


@pytest.mark.parametrize("fonte", [fonte for fonte, _, _ in _FONTES])
async def test_api_de_cnpj(servicos, fonte):
    _, rotulo, modelo = next(f for f in _FONTES if f[0] == fonte)
    dados = await buscar_json(servicos, modelo.format(cnpj=CNPJ), rotulo)
    assert {"cnpj", "razao_social", "data_inicio_atividade", "cnae_fiscal", "qsa"} <= set(dados)
    empresa = _empresa(dados, rotulo, CNPJ)
    assert empresa["razao_social"] == "PETROLEO BRASILEIRO S A PETROBRAS"
    assert (empresa["abertura"], empresa["cnae"]) == ("1966-09-28", 600001)
    assert empresa["situacao"] == "ATIVA"
    assert empresa["socios"] and all(set(socio) == {"nome", "qualificacao", "entrada"} for socio in empresa["socios"])
    assert not any(campo in str(empresa) for campo in _CAMPOS_DE_CPF)


# ---------------------------------------------------------------------------- índices (BCB e CVM)


async def test_olinda_bcb(servicos):
    instituicoes = await servicos.indices.instituicoes_bcb()
    assert {i.conjunto for i in instituicoes} == {
        "SedesBancoComMultCE", "SedesSociedades", "SedesCooperativas", "SedesConsorcios"
    }  # fmt: skip
    assert any(i.raiz_cnpj == "00000000" for i in instituicoes)  # Banco do Brasil
    dominios = await servicos.indices.dominios_bcb()
    assert any(d.dominio == "bb.com.br" and d.raiz_cnpj == "00000000" for d in dominios)


async def test_zip_da_cvm_cadastros(servicos):
    registros = await servicos.indices.cadastros_cvm()
    assert {r.cadastro for r in registros} == {"intermed", "crowdfunding", "adm_cart", "consultor"}
    assert all(len(r.cnpj) == 14 for r in registros)
    assert any(r.dt_reg is not None for r in registros)


async def test_zip_da_cvm_sancionador(servicos):
    processos = await servicos.indices.sancionador()
    assert processos
    assert any(p.data_abertura is not None for p in processos)
    assert all(p.nup and p.acusado for p in processos)


async def test_deliberacoes_pagina_1(servicos):
    rede, indices = servicos.rede, servicos.indices
    await rede.get(URL_DELIBERACOES_PARTIDA, usar_cache=False)  # abre a sessão que o JSP exige
    resposta = await rede.get(URL_DELIBERACOES_PAGINAS, params={"searchPage": "1", **_PARAMS_BUSCA}, usar_cache=False)
    marcador = _PAGINAS.search(resposta.texto)
    assert marcador is not None and marcador[1] == "1" and int(marcador[2]) >= 1
    links = {int(achado[2]): achado[1] for achado in _LINK_DELIBERACAO.finditer(resposta.texto)}
    assert links
    numero = max(links)  # a mais recente
    deliberacao = await indices._baixar_deliberacao(numero, urljoin(URL_DELIBERACOES_PARTIDA, links[numero]))
    assert deliberacao is not None and deliberacao.numero == numero
    assert deliberacao.data is not None and deliberacao.texto
