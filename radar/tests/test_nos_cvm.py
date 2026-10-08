"""Nós `registros`, `cvm_sancionador` e `cvm_alertas` (Tarefa 11)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from radar.config import Config, RedeConfig
from radar.custodia import Custodia, verificar
from radar.execucao import carregar_execucao, criar_contexto, criar_servicos
from radar.indices import Deliberacao, IndiceVencido, Indices, ProcessoCVM
from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import Motor, NoBase, Servicos
from radar.nos.alvo import AlvoNo
from radar.nos.cvm import CvmAlertasNo, CvmSancionadorNo, RegistrosNo, casar_deliberacoes
from radar.rede import Rede
from tests.mocks_cvm import mocar_cvm, mocar_deliberacoes, mocar_olinda

AGORA = datetime(2026, 10, 7, 12, 0, 0)
HOJE = date(2026, 10, 7)

TURCAMBIO = "15482499000198"  # raiz 15482499, em SedesSociedades (o CNPJ de exemplo da spec tem DV errado)
XP = "02332886000104"  # intermed, registro de 1997 sem cancelamento
ABN_AMRO = "03532415000102"  # intermed, quatro registros ao longo do tempo
POWER_WATER = "11854914000489"  # crowdfunding, "Registro Não Concedido"
PIPELINE = "15799453000105"  # crowdfunding, registrado em 2023-06-22 e cancelado em 2025-04-10
BANCO_DO_BRASIL = "00000000000191"
SANTO_TRADER = "41557647000104"  # citado na deliberação 905


async def _nao_dormir(s: float) -> None:
    return None


def contexto(pasta: Path, as_of: date = HOJE, alvo: str = "exemplo.com.br") -> Contexto:
    slug = alvo.replace(".", "-")
    return Contexto(
        alvo=alvo,
        slug=slug,
        url_inicial=f"https://{alvo}/",
        as_of=as_of,
        data_execucao=AGORA,
        modo_contato="nenhum",
        modo_cego=False,
        run_id=f"{slug}/2026-10-07_120000",
        pasta=pasta,
    )


def entrada_alvo(dominio: str = "exemplo.com.br") -> dict:
    return {"alvo": {"dominio": dominio, "slug": dominio.replace(".", "-"), "url_inicial": f"https://{dominio}/"}}


def entrada_cnpj(cnpj: str | None, razao_social: str = "EMPRESA SEM REGISTRO LTDA", **extra) -> dict:
    if cnpj is None:
        return {"cnpj": {"cnpj": None, "motivo": "não encontrado"}}
    return {"cnpj": {"cnpj": cnpj, "razao_social": razao_social, "nome_fantasia": None, "socios": [], **extra}}


@pytest.fixture
async def rede():
    r = Rede(Config(rede=RedeConfig(limites={"*": 0})).rede, dormir=_nao_dormir)
    yield r
    await r.fechar()


@pytest.fixture
def serv(tmp_path, rede):
    indices = Indices(tmp_path / "_indices", rede, 24, agora=lambda: AGORA)
    return Servicos(config=Config(), rede=rede, custodia=Custodia(tmp_path / "execucao"), indices=indices)


def entradas_custodia(serv) -> list[dict]:
    log = serv.custodia.pasta / "custodia.log"
    if not log.exists():
        return []
    return [json.loads(linha) for linha in log.read_text(encoding="utf-8").split("\n") if linha]


def corpo_da_custodia(serv, entrada: dict) -> dict:
    return json.loads(serv.custodia.ler(f"sha256:{entrada['sha256']}"))


def sem_artefato(saidas: dict) -> dict:
    return {chave: valor for chave, valor in saidas.items() if chave != "artefato"}


# ------------------------------------------------------------------------------------ registros


def test_registros_declaracao():
    no = RegistrosNo()
    assert (no.nome, no.entradas, no.as_of, no.toca_alvo) == ("registros", ("alvo", "cnpj"), "filtravel", False)
    assert no.saidas == (
        "cvm", "bcb", "bcb_dominio", "registrado", "motivo", "vazamento_temporal", "indices_vencidos"
    )  # fmt: skip


async def test_bcb_raiz_8_digitos(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    ctx = contexto(tmp_path)
    r = await RegistrosNo().executar(ctx, {**entrada_alvo(), **entrada_cnpj(TURCAMBIO)}, {}, serv)
    assert isinstance(r, Feito)
    # o CNPJ de 14 caracteres casa pela raiz de 8 do Olinda (SedesSociedades)
    assert [(i["conjunto"], i["raiz_cnpj"]) for i in r.saidas["bcb"]] == [("SedesSociedades", "15482499")]
    assert r.saidas["bcb"][0]["nome"].startswith("TURCÂMBIO")
    assert (r.saidas["cvm"], r.saidas["bcb_dominio"]) == ([], [])
    assert (r.saidas["registrado"], r.saidas["motivo"]) == (True, None)


async def test_registro_cvm_vigente(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    r = await RegistrosNo().executar(contexto(tmp_path), {**entrada_alvo(), **entrada_cnpj(XP)}, {}, serv)
    assert [(c["cadastro"], c["dt_reg"], c["dt_cancel"]) for c in r.saidas["cvm"]] == [("intermed", "1997-12-05", None)]
    assert r.saidas["cvm"][0]["denominacao"] == "XP INVESTIMENTOS CCTVM S.A."
    assert (r.saidas["bcb"], r.saidas["registrado"]) == ([], True)


@pytest.mark.parametrize(
    ("as_of", "registros", "registrado"),
    [
        (date(1999, 1, 1), [], False),  # antes do primeiro registro
        (date(2005, 11, 20), [], False),  # entre o cancelamento de 2005-11-14 e o registro de 2005-11-25
        (date(2005, 11, 25), [("2005-11-25", "2013-09-17")], True),  # no dia do registro já vale
        (date(2010, 6, 1), [("2005-11-25", "2013-09-17")], True),  # cancelado só em 2013: em 2010 ainda valia
        (date(2013, 9, 16), [("2005-11-25", "2013-09-17")], True),
        (date(2013, 9, 17), [("2013-09-17", None)], True),  # no dia do cancelamento o antigo não vale mais
        (HOJE, [("2013-09-17", None)], True),
    ],
)
async def test_registro_cvm_cancelado_antes_do_as_of_nao_conta(respx_mock, tmp_path, serv, as_of, registros, registrado):
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    ctx = contexto(tmp_path, as_of)
    r = await RegistrosNo().executar(ctx, {**entrada_alvo(), **entrada_cnpj(ABN_AMRO)}, {}, serv)
    assert sorted((c["dt_reg"], c["dt_cancel"]) for c in r.saidas["cvm"]) == registros
    assert r.saidas["registrado"] is registrado


async def test_registro_negado_ou_em_analise_nao_e_registro(respx_mock, tmp_path, serv):
    # "Registro Não Concedido" não tem DT_REG: a data ausente não pode virar "registrado antes do as_of"
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    ctx = contexto(tmp_path)
    negado = await RegistrosNo().executar(ctx, {**entrada_alvo(), **entrada_cnpj(POWER_WATER)}, {}, serv)
    assert (negado.saidas["cvm"], negado.saidas["registrado"]) == ([], False)
    em_analise = await RegistrosNo().executar(ctx, {**entrada_alvo(), **entrada_cnpj("34697721000114")}, {}, serv)
    assert (em_analise.saidas["cvm"], em_analise.saidas["registrado"]) == ([], False)


@pytest.mark.parametrize(
    ("as_of", "registrado"),
    [(date(2023, 6, 21), False), (date(2023, 6, 22), True), (date(2025, 4, 9), True), (date(2025, 4, 10), False), (HOJE, False)],
)
async def test_crowdfunding_cancelado_vale_ate_a_data_da_situacao(respx_mock, tmp_path, serv, as_of, registrado):
    # a linha sem situação e sem DT_REG do mesmo CNPJ não conta em nenhuma data
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    r = await RegistrosNo().executar(contexto(tmp_path, as_of), {**entrada_alvo(), **entrada_cnpj(PIPELINE)}, {}, serv)
    assert r.saidas["registrado"] is registrado
    assert len(r.saidas["cvm"]) == (1 if registrado else 0)


async def test_dominio_verificado_bcb(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    ctx = contexto(tmp_path, alvo="bb.com.br")
    r = await RegistrosNo().executar(ctx, {**entrada_alvo("bb.com.br"), **entrada_cnpj(BANCO_DO_BRASIL)}, {}, serv)
    assert {d["raiz_cnpj"] for d in r.saidas["bcb_dominio"]} == {"00000000", "06043050", "24933830", "30822936", "31546476"}
    assert all(d["dominio"] == "bb.com.br" for d in r.saidas["bcb_dominio"])
    assert (r.saidas["registrado"], r.saidas["motivo"]) == (True, None)
    # igualdade exata: o domínio parecido não casa
    outro = contexto(tmp_path, alvo="bb.com.br.golpe.com")
    r2 = await RegistrosNo().executar(outro, {**entrada_alvo("bb.com.br.golpe.com"), **entrada_cnpj(PIPELINE)}, {}, serv)
    assert r2.saidas["bcb_dominio"] == []


async def test_sem_cnpj_olha_so_o_dominio(respx_mock, tmp_path, serv):
    rotas = mocar_cvm(respx_mock)
    olinda = mocar_olinda(respx_mock)
    ctx = contexto(tmp_path, alvo="bb.com.br")
    r = await RegistrosNo().executar(ctx, {**entrada_alvo("bb.com.br"), **entrada_cnpj(None)}, {}, serv)
    assert (r.saidas["cvm"], r.saidas["bcb"]) == ([], [])
    assert len(r.saidas["bcb_dominio"]) == 5 and r.saidas["registrado"] is True
    assert r.saidas["motivo"] == "sem CNPJ"
    # sem CNPJ não há o que procurar nos cadastros: só o índice de domínios foi baixado
    assert not any(rota.called for rota in rotas.values())
    assert [c for c, rota in olinda.items() if rota.called] == ["DominiosVerificados"]
    # sem CNPJ e com domínio desconhecido: não registrado
    ctx2 = contexto(tmp_path, alvo="golpe.com")
    r2 = await RegistrosNo().executar(ctx2, {**entrada_alvo("golpe.com"), **entrada_cnpj(None)}, {}, serv)
    assert (r2.saidas["registrado"], r2.saidas["motivo"]) == (False, "sem CNPJ")


async def test_registros_retroativo_marca_o_bcb_como_vazamento_temporal(respx_mock, tmp_path, serv):
    # o Olinda só lista as instituições em funcionamento hoje: não dá para filtrar por data
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    entradas = {**entrada_alvo(), **entrada_cnpj(TURCAMBIO)}
    hoje = await RegistrosNo().executar(contexto(tmp_path), entradas, {}, serv)
    assert hoje.saidas["vazamento_temporal"] == []
    antes = await RegistrosNo().executar(contexto(tmp_path, date(2019, 6, 6)), entradas, {}, serv)
    assert antes.saidas["vazamento_temporal"] == ["bcb", "bcb_dominio"]


async def test_registros_guarda_na_custodia_o_que_consultou(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    await RegistrosNo().executar(contexto(tmp_path), {**entrada_alvo(), **entrada_cnpj(TURCAMBIO)}, {}, serv)
    entradas = entradas_custodia(serv)
    assert [(e["tipo"], e["origem"]) for e in entradas] == [
        ("indice", "cadastros_cvm"), ("indice", "instituicoes_bcb"), ("indice", "dominios_bcb")
    ]
    bcb = corpo_da_custodia(serv, entradas[1])
    assert bcb["consulta"]["cnpj"] == TURCAMBIO and bcb["consulta"]["as_of"] == "2026-10-07"
    assert [i["raiz_cnpj"] for i in bcb["correspondencias"]] == ["15482499"]
    assert corpo_da_custodia(serv, entradas[0])["correspondencias"] == []
    assert verificar(serv.custodia.pasta) == []


@pytest.mark.parametrize("no", [RegistrosNo, CvmSancionadorNo, CvmAlertasNo])
async def test_sem_servico_de_indices_o_no_cai_em_erro(tmp_path, no):
    serv = Servicos(config=Config(), rede=object(), custodia=Custodia(tmp_path))
    with pytest.raises(ErroNo) as e:
        await no().executar(contexto(tmp_path), {**entrada_alvo(), **entrada_cnpj(XP)}, {}, serv)
    assert e.value.mensagem == "serviço de índices não configurado" and e.value.permanente is True


async def test_registros_indice_em_erro_derruba_o_no(respx_mock, tmp_path, serv):
    mocar_olinda(respx_mock)
    respx_mock.get(url__startswith="https://dados.cvm.gov.br/").mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo) as e:
        await RegistrosNo().executar(contexto(tmp_path), {**entrada_alvo(), **entrada_cnpj(XP)}, {}, serv)
    assert e.value.permanente is False and "cadastros_cvm" in e.value.mensagem


# ------------------------------------------------------------------------------------ cvm_sancionador


def test_sancionador_declaracao():
    no = CvmSancionadorNo()
    assert (no.nome, no.entradas, no.as_of, no.toca_alvo) == ("cvm_sancionador", ("cnpj",), "filtravel", False)
    assert no.saidas == ("processos", "motivo", "artefato", "indices_vencidos")


async def test_sancionador_por_razao_social(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    # acento e pontuação não atrapalham: "ÁGUIA AGENTE AUTÔNOMO DE INVESTIMENTOS LTDA." na CVM, sem eles na Receita
    entradas = entrada_cnpj("33000167000101", "AGUIA AGENTE AUTONOMO DE INVESTIMENTOS LTDA")
    r = await CvmSancionadorNo().executar(contexto(tmp_path), entradas, {}, serv)
    assert [(p["nup"], p["data_abertura"], p["vinculo"]) for p in r.saidas["processos"]] == [
        ("19957000033202601", "2026-04-05", "razao_social"),
        ("19957000011202001", "2020-03-10", "razao_social"),
    ]
    p = r.saidas["processos"][1]
    assert p["acusado"] == "ÁGUIA AGENTE AUTÔNOMO DE INVESTIMENTOS LTDA." and p["fase"] == "Julgamento"
    assert p["situacao"] == "Acusado envia defesa" and p["objeto"].startswith("Apurar responsabilidade")
    assert r.saidas["motivo"] is None


async def test_sancionador_so_conta_processo_aberto_ate_o_as_of(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    entradas = entrada_cnpj("33000167000101", "AGUIA AGENTE AUTONOMO DE INVESTIMENTOS LTDA")
    for as_of, esperados in [
        (date(2020, 3, 9), []),
        (date(2020, 3, 10), ["19957000011202001"]),
        (date(2026, 4, 4), ["19957000011202001"]),
        (date(2026, 4, 5), ["19957000033202601", "19957000011202001"]),
    ]:
        r = await CvmSancionadorNo().executar(contexto(tmp_path, as_of), entradas, {}, serv)
        assert [p["nup"] for p in r.saidas["processos"]] == esperados, as_of


async def test_sancionador_por_socio(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    socios = [
        {"nome": "Carlos Alberto Pereira Neto", "qualificacao": "Sócio-Administrador", "entrada": "2015-01-10"},
        {"nome": "ALGUÉM SEM PROCESSO", "qualificacao": None, "entrada": None},
    ]
    entradas = entrada_cnpj("33000167000101", "OUTRA EMPRESA LTDA", socios=socios)
    r = await CvmSancionadorNo().executar(contexto(tmp_path), entradas, {}, serv)
    assert [(p["nup"], p["acusado"], p["vinculo"], p["data_abertura"]) for p in r.saidas["processos"]] == [
        ("19957000022201801", "CARLOS ALBERTO PEREIRA NETO", "socio", "2018-06-20")
    ]
    # a data em DD/MM/AAAA da fonte também filtra
    entradas2 = entrada_cnpj("33000167000101", "OUTRA EMPRESA LTDA", socios=[{"nome": "José Roberto Figueiredo"}])
    dentro = await CvmSancionadorNo().executar(contexto(tmp_path, date(2019, 9, 15)), entradas2, {}, serv)
    fora = await CvmSancionadorNo().executar(contexto(tmp_path, date(2019, 9, 14)), entradas2, {}, serv)
    assert [p["data_abertura"] for p in dentro.saidas["processos"]] == ["2019-09-15"] and fora.saidas["processos"] == []


async def test_sancionador_sem_correspondencia_e_sem_cnpj(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    nada = await CvmSancionadorNo().executar(contexto(tmp_path), entrada_cnpj("33000167000101"), {}, serv)
    (entrada,) = entradas_custodia(serv)
    assert nada.saidas == {"processos": [], "motivo": None, "artefato": f"sha256:{entrada['sha256']}"}
    sem = await CvmSancionadorNo().executar(contexto(tmp_path), entrada_cnpj(None), {}, serv)
    assert sem.saidas == {"processos": [], "motivo": "sem CNPJ"}  # sem nome para procurar, nada vai para a custódia
    assert len(entradas_custodia(serv)) == 1


async def test_sancionador_guarda_na_custodia(respx_mock, tmp_path, serv):
    mocar_cvm(respx_mock)
    entradas = entrada_cnpj("33000167000101", "AGUIA AGENTE AUTONOMO DE INVESTIMENTOS LTDA")
    r = await CvmSancionadorNo().executar(contexto(tmp_path), entradas, {}, serv)
    (entrada,) = entradas_custodia(serv)
    assert (entrada["tipo"], entrada["origem"]) == ("indice", "sancionador")
    # a ref do JSON é a fonte citável dos candidatos da P-D1
    assert r.saidas["artefato"] == f"sha256:{entrada['sha256']}"
    corpo = corpo_da_custodia(serv, entrada)
    assert len(corpo["correspondencias"]) == 2 and corpo["consulta"]["cnpj"] == "33000167000101"
    # a consulta guarda quantos processos foram olhados, não os nomes dos sócios
    assert corpo["consulta"]["processos_consultados"] == 5


# ------------------------------------------------------------------------------------ casar_deliberacoes


def delib(numero: int, texto: str, data: date | None = date(2025, 1, 10), integral: bool = True) -> Deliberacao:
    return Deliberacao(numero=numero, data=data, url=f"https://cvm.example/deli{numero}.html", texto=texto, integral=integral)


def tipos(correspondencias: list[dict]) -> list[tuple[str, int]]:
    return [(c["tipo"], c["numero"]) for c in correspondencias]


def test_casar_por_dominio_cnpj_nome_e_data():
    d = delib(
        1,
        "a CVM apurou que GOLPE INVESTIMENTOS LTDA., CNPJ nº 33.000.167/0001-01, por meio de https://www.golpe-invest.com/ "
        "oferece contratos. Contato: ajuda@golpe-invest.com.",
    )
    esperado = [("cnpj", 1), ("dominio", 1), ("nome", 1)]
    achados = casar_deliberacoes([d], "33000167000101", "golpe-invest.com", ["Golpe Investimentos Ltda"], HOJE)
    assert tipos(achados) == esperado
    cnpj, dominio, nome = achados
    assert set(cnpj) == {"tipo", "valor", "numero", "data", "url", "trecho"}
    assert (cnpj["data"], cnpj["url"], cnpj["valor"]) == ("2025-01-10", "https://cvm.example/deli1.html", "33000167000101")
    assert "33.000.167/0001-01" in cnpj["trecho"] and "golpe-invest.com" in dominio["trecho"]
    assert dominio["valor"] == "golpe-invest.com" and "GOLPE INVESTIMENTOS LTDA." in nome["trecho"]
    # a deliberação de depois do as_of fica de fora, a do próprio dia entra
    assert casar_deliberacoes([d], "33000167000101", "golpe-invest.com", ["Golpe Investimentos Ltda"], date(2025, 1, 9)) == []
    assert tipos(casar_deliberacoes([d], "33000167000101", None, [], date(2025, 1, 10))) == [("cnpj", 1)]


def test_deliberacao_sem_data_nao_conta():
    # sem data não dá para saber se já existia no as_of; o critério é o mesmo da `cvm_alertas` exata
    d = delib(2, "CNPJ 33.000.167/0001-01", data=None)
    assert casar_deliberacoes([d], "33000167000101", None, [], HOJE) == []


@pytest.mark.parametrize(
    "texto",
    [
        "CNPJ nº 33.000.167/0001-01,",
        "CNPJ: 33000167000101.",
        "(33.000.167/000101)",
        "33.000.16700 01-01 e 33.000.167/0001-01",
        "CNPJ nº 33.000.167/0001- 01, com o espaço que a extração do PDF deixa depois do hífen",
        "inscrita no CNPJ 33.000.167/\n0001-01 (quebra de linha no meio)",
        "inscrita sob o 33000167000101",
    ],
)
def test_cnpj_formatado_ou_so_os_caracteres(texto):
    assert tipos(casar_deliberacoes([delib(3, texto)], "33000167000101", None, [], HOJE)) == [("cnpj", 3)]


@pytest.mark.parametrize(
    "texto",
    [
        "processo 1933000167000101",  # dígitos de um número vizinho
        "33000167000101999",
        "33.000.167/0001-011",
        "A33000167000101",
        "33.000.167/0002-82",  # outra filial: o CNPJ é o de 14 caracteres
        "33.000.167",
    ],
)
def test_cnpj_nao_casa_dentro_de_outro_numero(texto):
    assert casar_deliberacoes([delib(4, texto)], "33000167000101", None, [], HOJE) == []


def test_cnpj_alfanumerico():
    d = delib(5, "a empresa de CNPJ 12.ABC.345/01DE-35 e a de 12abc34501de35")
    achados = casar_deliberacoes([d], "12ABC34501DE35", None, [], HOJE)
    assert tipos(achados) == [("cnpj", 5)] and "12.ABC.345/01DE-35" in achados[0]["trecho"]
    assert casar_deliberacoes([delib(5, "12.ABC.345/01DE-36")], "12ABC34501DE35", None, [], HOJE) == []


@pytest.mark.parametrize(
    ("texto", "casa"),
    [
        ("ofertas em https://santotrader.com/ e redes", True),
        ("site SantoTrader.COM, canal no YouTube", True),
        ("https://www.santotrader.com/planos", True),  # subdomínio é o mesmo domínio registrável
        ("escreva para contato@santotrader.com.", True),  # o ponto final da frase não é parte do domínio
        ("santotrader.com", True),
        ("https://santotrader.com.br/", False),  # outro domínio
        ("https://santotrader.company/", False),
        ("https://notsantotrader.com/", False),
        ("https://meu-santotrader.com/", False),
        ("santotraderXcom", False),
    ],
)
def test_dominio_exato_sem_diferenciar_maiusculas(texto, casa):
    achados = casar_deliberacoes([delib(6, texto)], None, "santotrader.com", [], HOJE)
    assert tipos(achados) == ([("dominio", 6)] if casa else [])


def test_nome_precisa_de_oito_caracteres_e_ignora_acento_e_pontuacao():
    d = delib(7, "indícios de que a ÁGUIA AGENTE AUTÔNOMO DE INVESTIMENTOS S.A. e a XP Trader oferecem")
    assert tipos(casar_deliberacoes([d], None, None, ["Aguia Agente Autonomo de Investimentos S A"], HOJE)) == [("nome", 7)]
    assert casar_deliberacoes([d], None, None, ["Água Agente Financeiro"], HOJE) == []  # outro nome
    assert tipos(casar_deliberacoes([d], None, None, ["XP Trader"], HOJE)) == [("nome", 7)]  # 9 caracteres: basta
    assert casar_deliberacoes([d], None, None, ["Trader"], HOJE) == []  # 6: curto demais
    assert casar_deliberacoes([d], None, None, [None, "", "   "], HOJE) == []


def test_nome_respeita_limite_de_palavra():
    d = delib(8, "a SUPERINVESTIMENTOS BRASIL LTDA e o INVESTIMENTOS BRASILEIRO")
    assert casar_deliberacoes([d], None, None, ["Investimentos Brasil"], HOJE) == []
    d2 = delib(8, "a Investimentos Brasil Ltda.")
    assert tipos(casar_deliberacoes([d2], None, None, ["Investimentos Brasil"], HOJE)) == [("nome", 8)]


def test_uma_correspondencia_por_deliberacao_tipo_e_valor():
    d = delib(9, "GOLPE LTDA " * 3 + "golpe.com " * 3 + "33.000.167/0001-01 33000167000101")
    achados = casar_deliberacoes([d], "33000167000101", "golpe.com", ["golpe ltda", "GOLPE   Ltda", "Golpe Brasil Ltda"], HOJE)
    assert tipos(achados) == [("cnpj", 9), ("dominio", 9), ("nome", 9)]


def test_ordem_das_correspondencias_e_trecho_de_120_caracteres():
    antigo = delib(10, "x" * 300 + " 33.000.167/0001-01 " + "y" * 300, data=date(2020, 5, 5))
    novo = delib(11, "CNPJ 33000167000101", data=date(2024, 2, 2))
    achados = casar_deliberacoes([antigo, novo], "33000167000101", None, [], HOJE)
    assert tipos(achados) == [("cnpj", 11), ("cnpj", 10)]  # da mais nova para a mais antiga
    # 120 caracteres de cada lado do CNPJ, com os espaços colapsados nas pontas
    assert achados[1]["trecho"] == "x" * 119 + " 33.000.167/0001-01 " + "y" * 119


def test_sem_nada_para_procurar():
    assert casar_deliberacoes([delib(12, "qualquer texto")], None, None, [], HOJE) == []
    assert casar_deliberacoes([], "33000167000101", "golpe.com", ["Golpe Brasil"], HOJE) == []


# ------------------------------------------------------------------------------------ cvm_alertas


def test_alertas_declaracao():
    no = CvmAlertasNo()
    assert (no.nome, no.entradas, no.opcionais, no.as_of, no.toca_alvo) == (
        "cvm_alertas", ("alvo",), ("cnpj",), "exato", False
    )
    assert no.saidas == ("correspondencias", "cobertura", "artefato", "indices_vencidos")


async def test_alertas_casa_por_cnpj_dominio_e_nome(respx_mock, tmp_path, serv):
    mocar_deliberacoes(respx_mock)
    ctx = contexto(tmp_path, alvo="santotrader.com")
    entradas = {
        **entrada_alvo("santotrader.com"),
        **entrada_cnpj(SANTO_TRADER, "SANTO TRADER TREINAMENTO PROFISSIONAIS LTDA.", nome_fantasia="Santo Trader"),
    }
    r = await CvmAlertasNo().executar(ctx, entradas, {}, serv)
    achados = r.saidas["correspondencias"]
    # a razão social (44 caracteres) e o nome fantasia ("Santo Trader", 12) casam: dois valores de nome
    assert tipos(achados) == [("cnpj", 905), ("dominio", 905), ("nome", 905), ("nome", 905)]
    assert {c["data"] for c in achados} == {"2025-11-25"}
    assert achados[0]["url"] == "https://conteudo.cvm.gov.br/legislacao/deliberacoes/deli0900/deli905.html"
    assert "41.557.647/0001-04" in achados[0]["trecho"]
    assert "https://santotrader.com/" in achados[1]["trecho"]
    assert sorted(c["valor"] for c in achados if c["tipo"] == "nome") == ["santo trader", "santo trader treinamento profissionais ltda"]
    assert r.saidas["cobertura"] == {"com_texto_integral": 7, "so_resumo": 0}


async def test_alertas_sem_cnpj_casa_so_por_dominio(respx_mock, tmp_path, serv):
    mocar_deliberacoes(respx_mock)
    ctx = contexto(tmp_path, alvo="santotrader.com")
    sem_entrada = await CvmAlertasNo().executar(ctx, entrada_alvo("santotrader.com"), {}, serv)
    assert tipos(sem_entrada.saidas["correspondencias"]) == [("dominio", 905)]
    nao_achou = await CvmAlertasNo().executar(ctx, {**entrada_alvo("santotrader.com"), **entrada_cnpj(None)}, {}, serv)
    assert tipos(nao_achou.saidas["correspondencias"]) == [("dominio", 905)]
    outro = await CvmAlertasNo().executar(contexto(tmp_path, alvo="limpo.com.br"), entrada_alvo("limpo.com.br"), {}, serv)
    assert sem_artefato(outro.saidas) == {"correspondencias": [], "cobertura": {"com_texto_integral": 7, "so_resumo": 0}}


@pytest.mark.parametrize("plataforma", ["instagram.com", "youtube.com"])
async def test_alertas_nao_casam_dominio_de_plataforma(respx_mock, tmp_path, serv, plataforma):
    # a 905 real (SantoTrader) cita www.instagram.com/oliversantotrader e www.youtube.com/@SANTOTRADER: o domínio
    # de uma plataforma não identifica o esquema, e um perfil dela não pode herdar o alerta de outro golpe (C1)
    mocar_deliberacoes(respx_mock)
    ctx = contexto(tmp_path, alvo=plataforma)
    r = await CvmAlertasNo().executar(ctx, entrada_alvo(plataforma), {}, serv)
    assert r.saidas["correspondencias"] == []


def test_casar_deliberacoes_ignora_dominio_de_plataforma():
    d = delib(13, "divulgação em https://www.instagram.com/golpe e em https://golpe-invest.com/")
    assert casar_deliberacoes([d], None, "instagram.com", [], HOJE) == []
    assert tipos(casar_deliberacoes([d], None, "golpe-invest.com", [], HOJE)) == [("dominio", 13)]


async def test_alertas_filtra_pela_data_do_ato(respx_mock, tmp_path, serv):
    mocar_deliberacoes(respx_mock)
    entradas = {**entrada_alvo("santotrader.com"), **entrada_cnpj(SANTO_TRADER)}
    antes = await CvmAlertasNo().executar(contexto(tmp_path, date(2025, 11, 24), "santotrader.com"), entradas, {}, serv)
    no_dia = await CvmAlertasNo().executar(contexto(tmp_path, date(2025, 11, 25), "santotrader.com"), entradas, {}, serv)
    assert antes.saidas["correspondencias"] == []
    assert tipos(no_dia.saidas["correspondencias"]) == [("cnpj", 905), ("dominio", 905)]
    # a cobertura conta só o que existia no as_of: a 905, de 25/11, ainda não
    assert antes.saidas["cobertura"] == {"com_texto_integral": 6, "so_resumo": 0}
    assert no_dia.saidas["cobertura"] == {"com_texto_integral": 7, "so_resumo": 0}


def _listagem(*numeros: int) -> str:
    links = "".join(
        f'<article><h3><a href="/legislacao/deliberacoes/deli{n // 100:02d}00/deli{n}.html">Deliberação CVM {n}</a></h3></article>'
        for n in numeros
    )
    return f"<span>{len(numeros)} resultados encontrados</span>{links}<span>Páginas 1/1</span>"


async def test_alertas_cobertura_diz_quantas_so_tem_o_resumo(respx_mock, tmp_path, serv):
    # sem o PDF (404), a 509 só tem o resumo: "0 correspondências" nela não prova nada sobre CNPJ e domínio
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(905, 509)))
    reg.rota_pdfs.mock(return_value=httpx.Response(404))
    ctx = contexto(tmp_path, alvo="limpo.com.br")
    r = await CvmAlertasNo().executar(ctx, entrada_alvo("limpo.com.br"), {}, serv)
    assert sem_artefato(r.saidas) == {"correspondencias": [], "cobertura": {"com_texto_integral": 1, "so_resumo": 1}}


async def test_alertas_acha_o_cnpj_no_texto_do_pdf_de_uma_deliberacao_antiga(respx_mock, tmp_path, serv):
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(905, 586, 509)))
    ctx = contexto(tmp_path, alvo="fginfocls.com")
    # o CNPJ da Fidelitas aparece no PDF da 509 como "06.151.776/0001- 99" (o resumo do invólucro não o traz)
    entradas = {**entrada_alvo("fginfocls.com"), **entrada_cnpj("06151776000199", "FIDELITAS INVESTIMENTOS LTDA.")}
    r = await CvmAlertasNo().executar(ctx, entradas, {}, serv)
    assert [(c["tipo"], c["numero"], c["data"]) for c in r.saidas["correspondencias"]] == [
        ("dominio", 586, "2009-08-11"), ("cnpj", 509, "2006-09-29"), ("nome", 509, "2006-09-29")
    ]
    assert r.saidas["cobertura"] == {"com_texto_integral": 3, "so_resumo": 0}


async def test_alertas_guarda_na_custodia(respx_mock, tmp_path, serv):
    mocar_deliberacoes(respx_mock)
    ctx = contexto(tmp_path, alvo="santotrader.com")
    r = await CvmAlertasNo().executar(ctx, entrada_alvo("santotrader.com"), {}, serv)
    (entrada,) = entradas_custodia(serv)
    assert (entrada["tipo"], entrada["origem"]) == ("indice", "deliberacoes")
    # a ref do JSON é a fonte citável das deliberações da P-C4
    assert r.saidas["artefato"] == f"sha256:{entrada['sha256']}"
    corpo = corpo_da_custodia(serv, entrada)
    assert corpo["consulta"] == {
        "dominio": "santotrader.com",
        "cnpj": None,
        "as_of": "2026-10-07",
        "cobertura": {"com_texto_integral": 7, "so_resumo": 0},
    }
    assert [c["numero"] for c in corpo["correspondencias"]] == [905]


# ------------------------------------------------------------------------------------ pelo motor


class _CnpjFalso(NoBase):
    """Faz o papel do nó `cnpj` (já testado na Tarefa 10) com uma saída fixa."""

    nome = "cnpj"
    entradas = ("alvo",)

    def __init__(self, saidas: dict) -> None:
        super().__init__()
        self._saidas = saidas

    async def executar(self, ctx, entradas, respostas, s):
        return Feito(self._saidas)


async def _rodar(tmp_path, cnpj: dict, as_of: date | None = None):
    ctx = criar_contexto("https://www.santotrader.com/", as_of, "nenhum", False, tmp_path, AGORA)
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        indices = Indices(tmp_path / "_indices", rede, 24, agora=lambda: AGORA)
        nos = [AlvoNo(), _CnpjFalso(cnpj), RegistrosNo(), CvmSancionadorNo(), CvmAlertasNo()]
        motor = Motor(ctx, nos, criar_servicos(config, ctx.pasta, rede, indices=indices))
        await motor.executar()
    finally:
        await rede.fechar()
    return ctx, motor


async def test_nos_pelo_motor(respx_mock, tmp_path):
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    mocar_deliberacoes(respx_mock)
    cnpj = {
        "cnpj": SANTO_TRADER,
        "razao_social": "SANTO TRADER TREINAMENTO PROFISSIONAIS LTDA.",
        "nome_fantasia": None,
        "socios": [{"nome": "FULANO DE TAL", "qualificacao": "Administrador", "entrada": "2020-01-01"}],
    }
    ctx, motor = await _rodar(tmp_path, cnpj)
    assert motor.status() == {
        "alvo": "feito", "cnpj": "feito", "registros": "feito", "cvm_sancionador": "feito", "cvm_alertas": "feito"
    }
    ex = carregar_execucao(ctx.pasta)
    registros = ex.saidas["registros"]
    assert (registros["registrado"], registros["motivo"], registros["cvm"], registros["bcb"]) == (False, None, [], [])
    assert sem_artefato(ex.saidas["cvm_sancionador"]) == {"processos": [], "motivo": None}
    assert tipos(ex.saidas["cvm_alertas"]["correspondencias"]) == [("cnpj", 905), ("dominio", 905), ("nome", 905)]
    # os índices ficam em cache compartilhado; na custódia da execução só a prova das consultas
    origens = [e["origem"] for e in entradas_custodia_de(ctx.pasta)]
    assert sorted(origens) == sorted(
        ["cadastros_cvm", "instituicoes_bcb", "dominios_bcb", "sancionador", "deliberacoes"]
    )
    assert not list((ctx.pasta / "artefatos").glob("*.zip"))
    assert verificar(ctx.pasta) == []
    assert {p.name for p in (tmp_path / "_indices").iterdir()} == {
        "cadastros_cvm.json", "instituicoes_bcb.json", "dominios_bcb.json", "sancionador.json", "deliberacoes.json"
    }


def entradas_custodia_de(pasta: Path) -> list[dict]:
    return [json.loads(linha) for linha in (pasta / "custodia.log").read_text(encoding="utf-8").split("\n") if linha]


async def test_nos_pelo_motor_com_indice_fora_do_ar_nao_derruba_os_outros(respx_mock, tmp_path):
    mocar_cvm(respx_mock)
    mocar_olinda(respx_mock)
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(503))
    cnpj = {"cnpj": SANTO_TRADER, "razao_social": "SANTO TRADER TREINAMENTO PROFISSIONAIS LTDA.", "nome_fantasia": None, "socios": []}
    ctx, motor = await _rodar(tmp_path, cnpj)
    assert motor.status()["cvm_alertas"] == "erro"
    assert motor.status()["registros"] == motor.status()["cvm_sancionador"] == "feito"
    ex = carregar_execucao(ctx.pasta)
    assert "cvm_alertas" not in ex.saidas and "503" in ex.status["cvm_alertas"]["motivo"]


# ------------------------------------------------------------------------------------ índice vencido (I6)


class _IndicesVencidos:
    """Índices que respondem com a cópia anterior porque a renovação falhou."""

    def __init__(self, desde: datetime) -> None:
        self.desde = desde

    async def cadastros_cvm(self):
        return IndiceVencido([], self.desde)

    async def instituicoes_bcb(self):
        return []

    async def dominios_bcb(self):
        return IndiceVencido([], self.desde)

    async def sancionador(self):
        return IndiceVencido([], self.desde)

    async def deliberacoes(self):
        return IndiceVencido([], self.desde)


async def test_nos_da_cvm_registram_o_indice_vencido(tmp_path, rede):
    desde = datetime(2026, 10, 6, 12, 0, 0)
    serv = Servicos(config=Config(), rede=rede, custodia=Custodia(tmp_path / "execucao"), indices=_IndicesVencidos(desde))
    ctx = contexto(tmp_path)
    entradas = {**entrada_alvo(), **entrada_cnpj(BANCO_DO_BRASIL)}
    registros = await RegistrosNo().executar(ctx, entradas, {}, serv)
    assert registros.saidas["indices_vencidos"] == {
        "cadastros_cvm": "2026-10-06T12:00:00", "dominios_bcb": "2026-10-06T12:00:00"
    }
    sancionador = await CvmSancionadorNo().executar(ctx, entradas, {}, serv)
    assert sancionador.saidas["indices_vencidos"] == {"sancionador": "2026-10-06T12:00:00"}
    alertas = await CvmAlertasNo().executar(ctx, entradas, {}, serv)
    assert alertas.saidas["indices_vencidos"] == {"deliberacoes": "2026-10-06T12:00:00"}


async def test_indice_em_dia_nao_acrescenta_a_chave(respx_mock, tmp_path, serv):
    mocar_deliberacoes(respx_mock)
    r = await CvmAlertasNo().executar(contexto(tmp_path), entrada_alvo(), {}, serv)
    assert "indices_vencidos" not in r.saidas


# ------------------------------------------------------------------------------------ nome curto (I7)


class _IndicesComProcessos:
    async def sancionador(self):
        def processo(nup: str, acusado: str) -> ProcessoCVM:
            return ProcessoCVM(nup=nup, objeto="Apurar oferta irregular", data_abertura=date(2020, 1, 10),
                               fase="Julgamento", acusado=acusado, situacao="Acusado envia defesa")  # fmt: skip

        return [processo("1", "JOÃO SILVA"), processo("2", "CARLOS ALBERTO PEREIRA NETO"), processo("3", "EMPRESA X LTDA")]


async def test_sancionador_marca_o_nome_curto_de_socio(tmp_path, rede):
    # nome de sócio com menos de 3 palavras casa com muita gente: o processo entra, marcado como possível homônimo
    serv = Servicos(config=Config(), rede=rede, custodia=Custodia(tmp_path / "execucao"), indices=_IndicesComProcessos())
    socios = [{"nome": "João Silva"}, {"nome": "Carlos Alberto Pereira Neto"}]
    entradas = entrada_cnpj("33000167000101", "EMPRESA X LTDA", socios=socios)
    r = await CvmSancionadorNo().executar(contexto(tmp_path), entradas, {}, serv)
    assert [(p["nup"], p["vinculo"], p["nome_curto"]) for p in r.saidas["processos"]] == [
        ("3", "razao_social", False), ("2", "socio", False), ("1", "socio", True)
    ]  # mesma data de abertura: pela ordem do NUP, do maior para o menor
