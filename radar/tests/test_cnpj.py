"""Nó `cnpj`: escolha do CNPJ, consulta à BrasilAPI e ao minhareceita.org e P-CNPJ (Tarefa 10)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from radar.cnpj_util import cnpj_valido
from radar.config import Config, RedeConfig
from radar.custodia import Custodia
from radar.execucao import criar_contexto, criar_servicos
from radar.modelos import (
    Aguardando,
    Candidato,
    Contexto,
    ErroNo,
    Evidencia,
    Feito,
    Pendencia,
    Resposta,
)
from radar.motor import Motor, NoBase, Servicos
from radar.nos import nos_do_nucleo
from radar.nos.cnpj import CnpjNo
from radar.nos.extracao import ExtracaoNo
from radar.pendencias.definicoes import nova_pendencia
from radar.rede import Rede

FIXTURES = Path(__file__).parent / "fixtures" / "api"
AGORA = datetime(2026, 10, 7, 12, 0, 0)


def _com_dv(base12: str) -> str:
    """Os 14 caracteres do CNPJ de raiz+ordem `base12` (conta dos dígitos verificadores, independente de `cnpj_util`)."""

    def dv(texto: str, pesos: tuple[int, ...]) -> int:
        resto = sum((ord(c) - 48) * p for c, p in zip(texto, pesos, strict=True)) % 11
        return 0 if resto < 2 else 11 - resto

    d1 = dv(base12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    d2 = dv(base12 + str(d1), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return f"{base12}{d1}{d2}"


PETROBRAS = "33000167000101"  # raiz 33000167, matriz
PETROBRAS_FILIAL = _com_dv("330001670002")  # mesma raiz, ordem 0002
BANCO_DO_BRASIL = "00000000000191"  # raiz 00000000
CAIXA = "00360305000104"  # raiz 00360305
ALFANUMERICO = "12ABC34501DE35"
assert all(cnpj_valido(c) for c in (PETROBRAS, PETROBRAS_FILIAL, BANCO_DO_BRASIL, CAIXA, ALFANUMERICO))

URL_BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/"
URL_MINHARECEITA = "https://minhareceita.org/"
CAMPOS_PROIBIDOS = ("cnpj_cpf_do_socio", "cpf_representante_legal", "nome_representante_legal")


def fixture(nome: str) -> dict:
    return json.loads((FIXTURES / f"{nome}_{PETROBRAS}.json").read_text(encoding="utf-8"))


def contexto(pasta: Path, as_of: date) -> Contexto:
    return Contexto(
        alvo="exemplo.com.br",
        slug="exemplo-com-br",
        url_inicial="https://exemplo.com.br/",
        as_of=as_of,
        data_execucao=AGORA,
        modo_contato="captura",
        modo_cego=False,
        run_id="exemplo-com-br/2026-10-07_120000",
        pasta=pasta,
    )


@pytest.fixture
def ctx_hoje(tmp_path):
    return contexto(tmp_path, date(2026, 10, 7))


@pytest.fixture
def ctx_2019(tmp_path):
    return contexto(tmp_path, date(2019, 6, 6))


async def _nao_dormir(s: float) -> None:
    return None


@pytest.fixture
async def serv(tmp_path):
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    yield Servicos(config=config, rede=rede, custodia=Custodia(tmp_path))
    await rede.fechar()


def candidato(cnpj: str, posicao: int = 0) -> dict:
    """Como a `extracao` entrega: o `Candidato` como dicionário."""
    return Candidato(
        categoria="cnpj", valor=cnpj, trecho=f"CNPJ {cnpj}", artefato="sha256:abc", posicao=posicao
    ).model_dump()


def entradas(*cnpjs: str, titular: str | None = None, rdap: bool = True, extras: list[dict] | None = None) -> dict:
    """Entradas do nó: candidatos `cnpj` da extração (mais `extras`) e, se `rdap`, o `cnpj_titular`."""
    lista = [candidato(c, i * 10) for i, c in enumerate(cnpjs)] + (extras or [])
    pronto = {"extracao": {"candidatos": lista, "fonte": "captura", "truncado": {}}}
    if rdap:
        pronto["rdap"] = {"cnpj_titular": titular, "vazamento_temporal": []}
    return pronto


def mocar_brasilapi(respx_mock, cnpj: str = PETROBRAS, corpo: dict | None = None):
    return respx_mock.get(URL_BRASILAPI + cnpj).mock(
        return_value=httpx.Response(200, json=corpo if corpo is not None else fixture("brasilapi"))
    )


def resposta(status: str, valor: dict | None = None) -> Resposta:
    if status in ("confirmado", "corrigido"):
        evidencias = [Evidencia(fonte="https://exemplo.com.br/termos", trecho="CNPJ 33.000.167/0001-01", tipo_fonte="operador")]
        return Resposta(status=status, valor=valor or {}, evidencias=evidencias)
    if status == "nao_encontrado":
        return Resposta(status=status, valor=valor or {}, onde_procurou=["rodapé", "termos de uso"])
    return Resposta(status=status, valor=valor or {})


# ---------------------------------------------------------------------------- um candidato


async def test_um_candidato_brasilapi(respx_mock, ctx_hoje, serv):
    rota = mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert isinstance(r, Feito)
    assert r.saidas == {
        "cnpj": PETROBRAS,
        "razao_social": "PETROLEO BRASILEIRO S A PETROBRAS",
        "nome_fantasia": "PETROBRAS - EDISE",
        "abertura": "1966-09-28",
        "cnae": 600001,
        "cnae_descricao": "Extração de petróleo e gás natural",
        "capital_social": 205431960000.0,
        "situacao": "ATIVA",
        "socios": [
            {"nome": "MAGDA MARIA DE REGINA CHAMBRIARD", "qualificacao": "Presidente", "entrada": "2024-06-07"},
            {"nome": "ANGELICA GARCIA COBAS LAUREANO", "qualificacao": "Diretor", "entrada": "2025-07-29"},
            {"nome": "CLARICE COPPETTI", "qualificacao": "Diretor", "entrada": "2023-04-17"},
        ],
        "fonte": "brasilapi",
        "vazamento_temporal": [],
    }
    assert isinstance(r.saidas["cnae"], int) and isinstance(r.saidas["capital_social"], float)
    assert rota.call_count == 1


async def test_json_bruto_vai_para_a_custodia(respx_mock, ctx_hoje, serv):
    mocar_brasilapi(respx_mock)
    await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    registros = [json.loads(linha) for linha in (ctx_hoje.pasta / "custodia.log").read_text(encoding="utf-8").splitlines()]
    assert [(r["origem"], r["tipo"]) for r in registros] == [(URL_BRASILAPI + PETROBRAS, "api")]
    assert json.loads(serv.custodia.ler(f"sha256:{registros[0]['sha256']}")) == fixture("brasilapi")


async def test_fallback_minhareceita(respx_mock, ctx_hoje, serv):
    principal = respx_mock.get(URL_BRASILAPI + PETROBRAS).mock(return_value=httpx.Response(503))
    reserva = respx_mock.get(URL_MINHARECEITA + PETROBRAS).mock(
        return_value=httpx.Response(200, json=fixture("minhareceita"))
    )
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert principal.call_count == 4  # as novas tentativas da Rede, depois o fallback
    assert reserva.call_count == 1
    assert r.saidas["fonte"] == "minhareceita"
    assert r.saidas["razao_social"] == "PETROLEO BRASILEIRO S A PETROBRAS"
    assert r.saidas["abertura"] == "1966-09-28"
    assert [s["nome"] for s in r.saidas["socios"]][0] == "MAGDA MARIA DE REGINA CHAMBRIARD"


@pytest.mark.parametrize(
    "falha",
    [
        httpx.Response(404),
        httpx.Response(200, content=b"<html>manutencao</html>"),  # não é JSON
        httpx.Response(200, json=[1, 2]),  # JSON que não é um objeto
    ],
)
async def test_qualquer_erro_da_brasilapi_cai_no_minhareceita(respx_mock, ctx_hoje, serv, falha):
    respx_mock.get(URL_BRASILAPI + PETROBRAS).mock(return_value=falha)
    respx_mock.get(URL_MINHARECEITA + PETROBRAS).mock(return_value=httpx.Response(200, json=fixture("minhareceita")))
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert r.saidas["fonte"] == "minhareceita"


async def test_as_duas_apis_falham(respx_mock, ctx_hoje, serv):
    respx_mock.get(URL_BRASILAPI + PETROBRAS).mock(return_value=httpx.Response(503))
    respx_mock.get(URL_MINHARECEITA + PETROBRAS).mock(return_value=httpx.Response(404))
    with pytest.raises(ErroNo) as e:
        await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert e.value.permanente is False
    mensagem = e.value.mensagem
    assert mensagem.startswith("APIs de CNPJ indisponíveis: ")
    brasilapi, _, minhareceita = mensagem.removeprefix("APIs de CNPJ indisponíveis: ").partition("; ")
    assert "BrasilAPI" in brasilapi and "503" in brasilapi
    assert "minhareceita" in minhareceita and "404" in minhareceita


async def test_cnpj_alfanumerico_vai_como_esta_para_as_apis(respx_mock, ctx_hoje, serv):
    corpo = {**fixture("brasilapi"), "cnpj": ALFANUMERICO}
    rota = mocar_brasilapi(respx_mock, ALFANUMERICO, corpo)
    r = await CnpjNo().executar(ctx_hoje, entradas(ALFANUMERICO), {}, serv)
    assert rota.call_count == 1
    assert r.saidas["cnpj"] == ALFANUMERICO


async def test_apis_sem_suporte_ao_alfanumerico_viram_erro_nao_permanente(respx_mock, ctx_hoje, serv):
    respx_mock.get(URL_BRASILAPI + ALFANUMERICO).mock(return_value=httpx.Response(400))
    respx_mock.get(URL_MINHARECEITA + ALFANUMERICO).mock(return_value=httpx.Response(400))
    with pytest.raises(ErroNo) as e:
        await CnpjNo().executar(ctx_hoje, entradas(ALFANUMERICO), {}, serv)
    assert e.value.permanente is False and "400" in e.value.mensagem


# ---------------------------------------------------------------------------- sócios sem CPF


async def test_sem_cpf_nas_saidas(respx_mock, ctx_hoje, serv):
    corpo = fixture("brasilapi")
    # a fixture é a resposta real: ela tem os campos que não podem sair
    assert all(c in socio for socio in corpo["qsa"] for c in CAMPOS_PROIBIDOS)
    corpo["qsa"][0]["nome_representante_legal"] = "REPRESENTANTE SECRETO"
    mocar_brasilapi(respx_mock, corpo=corpo)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert len(r.saidas["socios"]) == 3
    assert all(set(s) == {"nome", "qualificacao", "entrada"} for s in r.saidas["socios"])
    texto = json.dumps(r.saidas, ensure_ascii=False)
    assert not any(campo in texto for campo in CAMPOS_PROIBIDOS)
    assert "***" not in texto and "REPRESENTANTE SECRETO" not in texto


async def test_socios_ausentes_ou_malformados(respx_mock, ctx_hoje, serv):
    corpo = fixture("brasilapi")
    corpo["qsa"] = [
        "lixo",
        {"nome_socio": "  ", "qualificacao_socio": "Sócio", "data_entrada_sociedade": "2020-01-01"},  # sem nome
        {"nome_socio": "FULANO DE TAL", "qualificacao_socio": None, "data_entrada_sociedade": "01/02/2020"},
        {"nome_socio": "BELTRANO", "qualificacao_socio": "Administrador", "data_entrada_sociedade": "2020-02-30"},
    ]
    mocar_brasilapi(respx_mock, corpo=corpo)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert r.saidas["socios"] == [
        {"nome": "FULANO DE TAL", "qualificacao": None, "entrada": None},
        {"nome": "BELTRANO", "qualificacao": "Administrador", "entrada": None},
    ]


async def test_resposta_sem_qsa(respx_mock, ctx_hoje, serv):
    corpo = fixture("brasilapi")
    del corpo["qsa"]
    mocar_brasilapi(respx_mock, corpo=corpo)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert r.saidas["socios"] == []


# ---------------------------------------------------------------------------- campos da empresa


async def test_campos_ausentes_ou_em_outro_formato(respx_mock, ctx_hoje, serv):
    corpo = {
        "razao_social": "EMPRESA FICTICIA LTDA",
        "nome_fantasia": "",
        "data_inicio_atividade": "2025-13-45",
        "cnae_fiscal": "6422100",
        "capital_social": "1500.50",
    }
    mocar_brasilapi(respx_mock, corpo=corpo)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert r.saidas == {
        "cnpj": PETROBRAS,
        "razao_social": "EMPRESA FICTICIA LTDA",
        "nome_fantasia": None,
        "abertura": None,
        "cnae": 6422100,
        "cnae_descricao": None,
        "capital_social": 1500.5,
        "situacao": None,
        "socios": [],
        "fonte": "brasilapi",
        "vazamento_temporal": [],
    }


@pytest.mark.parametrize("capital", [True, "muito", None, [1]])
async def test_capital_social_invalido_vira_none(respx_mock, ctx_hoje, serv, capital):
    mocar_brasilapi(respx_mock, corpo={**fixture("brasilapi"), "capital_social": capital})
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert r.saidas["capital_social"] is None


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
async def test_capital_social_nao_finito_vira_none(respx_mock, ctx_hoje, serv, literal):
    # o `json` do Python aceita esses literais, que não são JSON de verdade
    corpo = b'{"razao_social": "X", "capital_social": ' + literal.encode() + b"}"
    respx_mock.get(URL_BRASILAPI + PETROBRAS).mock(return_value=httpx.Response(200, content=corpo))
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert r.saidas["capital_social"] is None


@pytest.mark.parametrize("cnae", [True, "60000A", 6000.5, None, "", [1]])
async def test_cnae_invalido_vira_none(respx_mock, ctx_hoje, serv, cnae):
    mocar_brasilapi(respx_mock, corpo={**fixture("brasilapi"), "cnae_fiscal": cnae})
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {}, serv)
    assert r.saidas["cnae"] is None


async def test_retroativo_marca_situacao_e_socios(respx_mock, ctx_2019, serv):
    mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_2019, entradas(PETROBRAS), {}, serv)
    assert r.saidas["vazamento_temporal"] == ["situacao", "socios"]
    assert r.saidas["abertura"] == "1966-09-28"  # a abertura é exata em qualquer as_of


# ---------------------------------------------------------------------------- escolha do CNPJ


async def test_varios_cnpjs_sem_titular_abre_pendencia(respx_mock, ctx_hoje, serv):
    rota = mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS, BANCO_DO_BRASIL), {}, serv)
    assert isinstance(r, Aguardando) and len(r.pendencias) == 1
    p = r.pendencias[0]
    assert isinstance(p, Pendencia)
    assert (p.id, p.no_origem) == ("P-CNPJ", "cnpj")
    assert [c.valor for c in p.candidatos] == [PETROBRAS, BANCO_DO_BRASIL]
    assert all(isinstance(c, Candidato) and c.categoria == "cnpj" for c in p.candidatos)
    assert p.restricoes == {"as_of": "2026-10-07", "modo_cego": False}
    assert rota.call_count == 0  # nenhuma consulta enquanto a dúvida não é resolvida


async def test_varios_cnpjs_com_titular_rdap(respx_mock, ctx_hoje, serv):
    rota = mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(BANCO_DO_BRASIL, PETROBRAS, CAIXA, titular=PETROBRAS), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS
    assert rota.call_count == 1


async def test_titular_vale_mesmo_que_o_site_cite_so_outros_cnpjs(respx_mock, ctx_hoje, serv):
    """O titular entra na conta ao lado dos CNPJs do site e, havendo mais de uma raiz, é ele que vale."""
    rota = mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(BANCO_DO_BRASIL, CAIXA, titular=PETROBRAS), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS
    assert rota.call_count == 1


async def test_so_o_titular_do_rdap(respx_mock, ctx_hoje, serv):
    rota = mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(titular=PETROBRAS), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS
    assert rota.call_count == 1


async def test_titular_e_extracao_com_o_mesmo_cnpj_contam_uma_vez(respx_mock, ctx_hoje, serv):
    mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS, PETROBRAS, titular=PETROBRAS), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS


async def test_nenhum_candidato_abre_pendencia_sem_candidatos(ctx_hoje, serv):
    r = await CnpjNo().executar(ctx_hoje, entradas(), {}, serv)
    assert isinstance(r, Aguardando)
    assert [(p.id, p.candidatos) for p in r.pendencias] == [("P-CNPJ", [])]


async def test_sem_a_entrada_rdap(respx_mock, ctx_hoje, serv):
    """O `rdap` é opcional: com erro dele, o nó segue só com a extração."""
    mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS, rdap=False), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS
    r = await CnpjNo().executar(ctx_hoje, entradas(rdap=False), {}, serv)
    assert isinstance(r, Aguardando)


async def test_ignora_candidatos_de_outras_categorias_e_cnpj_invalido(respx_mock, ctx_hoje, serv):
    outro = Candidato(categoria="whatsapp", valor="wa.me/5511999998888", trecho="x", artefato="a", posicao=1).model_dump()
    sem_dv = candidato("33000167000102")  # dígito verificador errado
    mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS, extras=[outro, sem_dv]), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS


async def test_titular_invalido_no_rdap_e_ignorado(respx_mock, ctx_hoje, serv):
    mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS, titular="33000167000102"), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS


# ---------------------------------------------------------------------------- raiz de 8 caracteres


@pytest.mark.parametrize("ordem", [(PETROBRAS, PETROBRAS_FILIAL), (PETROBRAS_FILIAL, PETROBRAS)])
async def test_matriz_e_filial_da_mesma_raiz_sao_um_candidato_e_vale_a_matriz(respx_mock, ctx_hoje, serv, ordem):
    rota = mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(*ordem), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS
    assert rota.call_count == 1


async def test_so_filial_da_raiz_usa_o_primeiro_encontrado(respx_mock, ctx_hoje, serv):
    outra_filial = _com_dv("330001670003")
    rota = respx_mock.get(URL_BRASILAPI + outra_filial).mock(return_value=httpx.Response(200, json=fixture("brasilapi")))
    r = await CnpjNo().executar(ctx_hoje, entradas(outra_filial, PETROBRAS_FILIAL), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == outra_filial
    assert rota.call_count == 1


async def test_titular_filial_e_matriz_no_site_vale_a_matriz(respx_mock, ctx_hoje, serv):
    """Uma raiz só: a empresa é uma, e a abertura da matriz é a da empresa (a da filial seria mais recente)."""
    mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS, titular=PETROBRAS_FILIAL), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS


async def test_duas_raizes_com_filiais_pedem_um_candidato_por_raiz(ctx_hoje, serv):
    banco_filial = _com_dv("000000000002")
    r = await CnpjNo().executar(
        ctx_hoje, entradas(PETROBRAS_FILIAL, BANCO_DO_BRASIL, PETROBRAS, banco_filial), {}, serv
    )
    assert isinstance(r, Aguardando)
    # um por raiz, na ordem em que cada raiz apareceu, com a matriz quando ela foi achada
    assert [c.valor for c in r.pendencias[0].candidatos] == [PETROBRAS, BANCO_DO_BRASIL]


async def test_titular_filial_com_outras_raizes_usa_a_matriz_da_raiz_do_titular(respx_mock, ctx_hoje, serv):
    mocar_brasilapi(respx_mock)
    r = await CnpjNo().executar(
        ctx_hoje, entradas(BANCO_DO_BRASIL, PETROBRAS, titular=PETROBRAS_FILIAL), {}, serv
    )
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS


async def test_titular_filial_sem_matriz_conhecida_vale_a_propria_filial(respx_mock, ctx_hoje, serv):
    rota = respx_mock.get(URL_BRASILAPI + PETROBRAS_FILIAL).mock(return_value=httpx.Response(200, json=fixture("brasilapi")))
    r = await CnpjNo().executar(ctx_hoje, entradas(BANCO_DO_BRASIL, titular=PETROBRAS_FILIAL), {}, serv)
    assert isinstance(r, Feito) and r.saidas["cnpj"] == PETROBRAS_FILIAL
    assert rota.call_count == 1


# ---------------------------------------------------------------------------- resposta à P-CNPJ


@pytest.mark.parametrize("status", ["confirmado", "corrigido"])
@pytest.mark.parametrize("escrito", [BANCO_DO_BRASIL, "00.000.000/0001-91"])
async def test_resposta_confirmada_ou_corrigida_vale_mais_que_os_candidatos(respx_mock, ctx_hoje, serv, status, escrito):
    rota = mocar_brasilapi(respx_mock, BANCO_DO_BRASIL)
    sobra = mocar_brasilapi(respx_mock, PETROBRAS)
    r = await CnpjNo().executar(
        ctx_hoje, entradas(PETROBRAS, CAIXA, titular=PETROBRAS), {"P-CNPJ": resposta(status, {"cnpj": escrito})}, serv
    )
    assert isinstance(r, Feito) and r.saidas["cnpj"] == BANCO_DO_BRASIL
    assert rota.call_count == 1 and sobra.call_count == 0


async def test_resposta_com_cnpj_alfanumerico_em_minusculas(respx_mock, ctx_hoje, serv):
    mocar_brasilapi(respx_mock, ALFANUMERICO)
    r = await CnpjNo().executar(
        ctx_hoje, entradas(), {"P-CNPJ": resposta("confirmado", {"cnpj": "12.abc.345/01de-35"})}, serv
    )
    assert r.saidas["cnpj"] == ALFANUMERICO


@pytest.mark.parametrize("status", ["nao_encontrado", "inconclusivo"])
async def test_resposta_sem_cnpj(ctx_hoje, serv, status):
    r = await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {"P-CNPJ": resposta(status)}, serv)
    assert r == Feito({"cnpj": None, "motivo": "não encontrado"})


@pytest.mark.parametrize(
    "valor",
    [
        {"cnpj": "33000167000102"},  # dígito verificador errado
        {"cnpj": "11111111111111"},
        {"cnpj": "123"},
        {"cnpj": 33000167000101},  # número, não texto
        {"cnpj": None},
        {"outro": PETROBRAS},
        {},
    ],
)
@pytest.mark.parametrize("status", ["confirmado", "corrigido"])
async def test_resposta_com_cnpj_invalido(ctx_hoje, serv, status, valor):
    with pytest.raises(ErroNo) as e:
        await CnpjNo().executar(ctx_hoje, entradas(PETROBRAS), {"P-CNPJ": resposta(status, valor)}, serv)
    assert e.value.mensagem == "P-CNPJ: CNPJ inválido na resposta" and e.value.permanente is True


# ---------------------------------------------------------------------------- P-CNPJ (provisória)


def test_nova_pendencia_p_cnpj(ctx_hoje):
    c = Candidato.model_validate(candidato(PETROBRAS))
    p = nova_pendencia("P-CNPJ", ctx_hoje, [c, candidato(CAIXA)], "cnpj")
    assert isinstance(p, Pendencia)
    assert (p.id, p.itens, p.no_origem, p.conteudo_do_alvo) == ("P-CNPJ", [], "cnpj", "")
    assert [x.valor for x in p.candidatos] == [PETROBRAS, CAIXA]
    assert p.formato_resposta == {"cnpj": "string de 14 caracteres"}
    assert p.restricoes == {"as_of": "2026-10-07", "modo_cego": False}
    assert "CNPJ" in p.pergunta and p.criterios


def test_nova_pendencia_provisoria_so_conhece_a_p_cnpj(ctx_hoje):
    with pytest.raises(ValueError, match="P-A1"):
        nova_pendencia("P-A1", ctx_hoje, [], "pend_a1")


def test_nova_pendencia_restricoes_acompanham_o_contexto(ctx_2019):
    p = nova_pendencia("P-CNPJ", ctx_2019.model_copy(update={"modo_cego": True}), [], "cnpj")
    assert p.restricoes == {"as_of": "2019-06-06", "modo_cego": True}


# ---------------------------------------------------------------------------- declaração e motor


def test_declaracao_do_no():
    no = CnpjNo()
    assert (no.nome, no.entradas, no.opcionais, no.exige_um_de) == ("cnpj", ("extracao",), ("rdap",), ())
    assert no.toca_alvo is False and no.as_of == "exato"
    assert no.saidas == (
        "cnpj", "razao_social", "nome_fantasia", "abertura", "cnae", "cnae_descricao",
        "capital_social", "situacao", "socios", "fonte", "vazamento_temporal",
    )


def test_no_esta_no_nucleo_depois_da_extracao():
    nos = nos_do_nucleo()
    assert [n.nome for n in nos][-2:] == ["extracao", "cnpj"]
    assert isinstance(nos[-2], ExtracaoNo) and isinstance(nos[-1], CnpjNo)


class _Fixo(NoBase):
    """Nó de mentira: devolve sempre as mesmas saídas."""

    def __init__(self, nome: str, saidas: dict) -> None:
        super().__init__(nome=nome)
        self._saidas = saidas

    async def executar(self, ctx, entradas, respostas, s):
        return Feito(self._saidas)


async def _motor(tmp_path, rede, candidatos: list[str], titular: str | None, as_of: date | None = None) -> Motor:
    ctx = criar_contexto("https://exemplo.com.br/", as_of, "nenhum", False, tmp_path, AGORA)
    config = Config(rede=RedeConfig(limites={"*": 0}))
    extracao = {"candidatos": [candidato(c) for c in candidatos], "fonte": "captura", "truncado": {}}
    nos = [_Fixo("rdap", {"cnpj_titular": titular}), _Fixo("extracao", extracao), CnpjNo()]
    return Motor(ctx, nos, criar_servicos(config, ctx.pasta, rede))


async def test_pendencia_p_cnpj_ida_e_volta_pelo_motor(respx_mock, tmp_path):
    rede = Rede(Config(rede=RedeConfig(limites={"*": 0})).rede, dormir=_nao_dormir)
    try:
        motor = await _motor(tmp_path, rede, [PETROBRAS, BANCO_DO_BRASIL], None)
        await motor.executar()
        assert motor.status()["cnpj"] == "aguardando"
        assert [(p.id, p.no_origem) for p in motor.pendencias_abertas()] == [("P-CNPJ", "cnpj")]

        mocar_brasilapi(respx_mock, BANCO_DO_BRASIL)
        await motor.responder("P-CNPJ", resposta("corrigido", {"cnpj": BANCO_DO_BRASIL}))
        assert motor.status()["cnpj"] == "feito"
        assert motor.saidas("cnpj")["cnpj"] == BANCO_DO_BRASIL

        # corrige a resposta: o nó roda de novo com a nova resposta ativa
        ativo = next(j for j in motor._julgamentos if j["ativa"])["id"]
        await motor.responder("P-CNPJ", resposta("nao_encontrado").model_copy(update={"substitui": ativo}))
        assert motor.saidas("cnpj") == {"cnpj": None, "motivo": "não encontrado"}
    finally:
        await rede.fechar()


async def test_api_fora_do_ar_deixa_o_no_em_erro(respx_mock, tmp_path):
    respx_mock.get(URL_BRASILAPI + PETROBRAS).mock(return_value=httpx.Response(503))
    respx_mock.get(URL_MINHARECEITA + PETROBRAS).mock(return_value=httpx.Response(503))
    rede = Rede(Config(rede=RedeConfig(limites={"*": 0})).rede, dormir=_nao_dormir)
    try:
        motor = await _motor(tmp_path, rede, [PETROBRAS], None)
        await motor.executar()
        assert motor.status()["cnpj"] == "erro"
        assert motor.saidas("cnpj") is None
    finally:
        await rede.fechar()
