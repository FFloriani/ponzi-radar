"""Índices da CVM e do BCB em cache local (Tarefa 11): leitura dos arquivos, validade e deliberações."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import date, datetime, timedelta

import httpx
import pytest

from radar.config import RedeConfig
from radar.indices import (
    URL_DELIBERACOES_PAGINAS,
    URL_DELIBERACOES_PARTIDA,
    URL_OLINDA,
    Deliberacao,
    DominioBCB,
    Indices,
    InstituicaoBCB,
    ProcessoCVM,
    RegistroCVM,
    vencido_desde,
)
from radar.modelos import ErroNo
from radar.rede import Rede
from tests.mocks_cvm import (
    DATAS,
    NUMEROS,
    TOTAL_PAGINAS,
    URL_SANCIONADOR,
    ZIPS_CVM,
    fixture_bytes,
    mocar_cvm,
    mocar_deliberacoes,
    mocar_olinda,
    pdf_com_texto,
)

AGORA = datetime(2026, 10, 7, 12, 0, 0)


async def _nao_dormir(s: float) -> None:
    return None


class Relogio:
    """O `agora` do `Indices`, que só anda quando o teste manda."""

    def __init__(self) -> None:
        self.t = AGORA

    def __call__(self) -> datetime:
        return self.t

    def avancar(self, **kw) -> None:
        self.t += timedelta(**kw)


@pytest.fixture
async def rede():
    r = Rede(RedeConfig(limites={"*": 0}), dormir=_nao_dormir)
    yield r
    await r.fechar()


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def indices(tmp_path, rede, relogio):
    return Indices(tmp_path, rede, 24, agora=relogio)


def _cache(tmp_path, nome: str) -> dict:
    return json.loads((tmp_path / f"{nome}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------- cadastros da CVM


async def test_cadastros_cvm_le_latin1(respx_mock, indices):
    mocar_cvm(respx_mock)
    registros = await indices.cadastros_cvm()
    assert all(isinstance(r, RegistroCVM) for r in registros)
    # o CNPJ-curinga "00.999.999/9999-99" do intermed não é CNPJ e fica de fora
    assert Counter(r.cadastro for r in registros) == {"intermed": 6, "crowdfunding": 5, "adm_cart": 2, "consultor": 3}
    abc = next(r for r in registros if r.cnpj == "33817677000176")
    assert abc.denominacao == "ABC BRASIL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A."  # latin-1 lido certo
    assert abc.nome_comercial == "ABC BRASIL DTVM"
    xp = next(r for r in registros if r.cnpj == "02332886000104")
    assert (xp.cadastro, xp.situacao, xp.dt_reg, xp.dt_cancel) == (
        "intermed", "EM FUNCIONAMENTO NORMAL", date(1997, 12, 5), None
    )
    # a mesma empresa aparece uma vez por registro: o ABN AMRO Clearing tem quatro ao longo do tempo
    abn = sorted((r.dt_reg, r.dt_cancel) for r in registros if r.cnpj == "03532415000102")
    assert abn == [
        (date(1999, 12, 22), date(2000, 5, 23)),
        (date(2000, 5, 23), date(2005, 11, 14)),
        (date(2005, 11, 25), date(2013, 9, 17)),
        (date(2013, 9, 17), None),
    ]


async def test_cadastros_cvm_le_o_arquivo_pj_e_nao_o_primeiro_do_zip(respx_mock, indices):
    # no ZIP do adm_cart o `_pf.csv` vem antes do `_pj.csv` (e tem outras colunas)
    mocar_cvm(respx_mock)
    registros = [r for r in await indices.cadastros_cvm() if r.cadastro in ("adm_cart", "consultor")]
    assert {r.denominacao for r in registros} == {
        "10B GESTORA DE RECURSOS LTDA.",
        "3G CAPITAL GESTORA DE RECURSOS LTDA",
        "1 TO 1 CAPITAL - CONSULTORIA FINANCEIRA E VMFO LTDA",
        "31 CAPITAL LTDA",
    }


async def test_cadastro_crowdfunding_sem_registro_concedido_e_cancelado(respx_mock, indices):
    # o CSV do crowdfunding não tem DT_CANCEL: quem está "Cancelado" perde o registro em DT_INI_SIT,
    # e quem "Não Concedido" ou "Em Análise" nunca teve DT_REG
    mocar_cvm(respx_mock)
    cf = {(r.cnpj, r.situacao): r for r in await indices.cadastros_cvm() if r.cadastro == "crowdfunding"}
    negado = cf[("11854914000489", "Registro Não Concedido")]
    assert (negado.dt_reg, negado.dt_cancel) == (None, None)
    assert cf[("34697721000114", "Em Análise")].dt_reg is None
    cancelado = cf[("15799453000105", "Cancelado")]
    assert (cancelado.dt_reg, cancelado.dt_cancel) == (date(2023, 6, 22), date(2025, 4, 10))
    sem_situacao = cf[("15799453000105", "")]
    assert (sem_situacao.dt_reg, sem_situacao.dt_cancel) == (None, None)
    ativo = cf[("12144966000181", "Em Funcionamento Normal")]
    assert (ativo.dt_reg, ativo.dt_cancel) == (date(2026, 9, 9), None)


async def test_nome_comercial_vazio_ou_traco_vira_none(respx_mock, indices):
    mocar_cvm(respx_mock)
    registros = await indices.cadastros_cvm()
    assert next(r for r in registros if r.cnpj == "09813848000104").nome_comercial is None  # "--" na fonte
    assert next(r for r in registros if r.cnpj == "15799453000105").nome_comercial == "Pipeline Collective"


# ------------------------------------------------------------------------------- validade do cache


async def test_ttl_nao_rebaixa_dentro_de_24h(respx_mock, indices, relogio):
    rotas = mocar_cvm(respx_mock)
    await indices.cadastros_cvm()
    relogio.avancar(hours=23)
    await indices.cadastros_cvm()
    assert [rotas[z].call_count for z in ZIPS_CVM.values()] == [1, 1, 1, 1]
    relogio.avancar(hours=2)  # 25 h depois do download
    await indices.cadastros_cvm()
    # o cache em memória da `Rede` não vale aqui: o índice vencido tem de ir à rede de novo
    assert [rotas[z].call_count for z in ZIPS_CVM.values()] == [2, 2, 2, 2]


async def test_cache_em_disco_tem_gerado_em_e_itens_e_sobrevive_a_outra_instancia(respx_mock, tmp_path, indices, relogio):
    rotas = mocar_cvm(respx_mock)
    esperado = await indices.cadastros_cvm()
    bruto = _cache(tmp_path, "cadastros_cvm")
    assert set(bruto) == {"gerado_em", "itens"}
    assert bruto["gerado_em"] == AGORA.isoformat() and len(bruto["itens"]) == len(esperado) == 16
    assert bruto["itens"][0]["dt_reg"] == "2005-11-25"  # datas em ISO
    # outro processo (outra `Rede`, outro `Indices`) lê o mesmo arquivo sem baixar nada
    outra = Rede(RedeConfig(limites={"*": 0}), dormir=_nao_dormir)
    try:
        assert await Indices(tmp_path, outra, 24, agora=relogio).cadastros_cvm() == esperado
    finally:
        await outra.fechar()
    assert all(r.call_count == 1 for r in rotas.values() if r.called)


@pytest.mark.parametrize(
    "conteudo",
    [
        "{quebrado",
        "[]",
        '{"gerado_em": "ontem", "itens": []}',
        '{"gerado_em": "2026-10-07T12:00:00", "itens": [{"cadastro": "outro"}]}',
        '{"gerado_em": "2026-10-07T12:00:00"}',
    ],
)
async def test_cache_ilegivel_ou_de_outro_formato_e_refeito(respx_mock, tmp_path, indices, conteudo):
    rotas = mocar_cvm(respx_mock)
    (tmp_path / "cadastros_cvm.json").write_text(conteudo, encoding="utf-8")
    assert len(await indices.cadastros_cvm()) == 16
    assert rotas["cad_intermed.zip"].call_count == 1
    assert len(_cache(tmp_path, "cadastros_cvm")["itens"]) == 16  # e o arquivo ficou bom


async def test_cache_gerado_no_futuro_nao_vale(respx_mock, tmp_path, indices, relogio):
    # relógio que andou para trás: um `gerado_em` à frente do agora não pode valer "para sempre"
    rotas = mocar_cvm(respx_mock)
    await indices.cadastros_cvm()
    relogio.avancar(days=-3)
    await indices.cadastros_cvm()
    assert rotas["cad_intermed.zip"].call_count == 2


async def test_chamadas_simultaneas_baixam_uma_vez(respx_mock, indices):
    rotas = mocar_cvm(respx_mock)
    a, b, c = await asyncio.gather(indices.cadastros_cvm(), indices.cadastros_cvm(), indices.cadastros_cvm())
    assert a == b == c
    assert [rotas[z].call_count for z in ZIPS_CVM.values()] == [1, 1, 1, 1]


# ------------------------------------------------------------------------------- erros


async def test_erro_de_rede_vira_erro_no_com_a_permanencia_da_rede(respx_mock, indices):
    url = next(iter(ZIPS_CVM))
    respx_mock.get(f"https://dados.cvm.gov.br/dados/{url}").mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo) as e503:
        await indices.cadastros_cvm()
    assert e503.value.permanente is False and "cadastros_cvm" in e503.value.mensagem and "503" in e503.value.mensagem
    respx_mock.reset()
    respx_mock.get(f"https://dados.cvm.gov.br/dados/{url}").mock(return_value=httpx.Response(404))
    with pytest.raises(ErroNo) as e404:
        await indices.cadastros_cvm()
    assert e404.value.permanente is True


async def test_zip_que_nao_e_zip_e_erro_permanente(respx_mock, indices):
    respx_mock.get(URL_SANCIONADOR).mock(return_value=httpx.Response(200, content=b"<html>manutencao</html>"))
    with pytest.raises(ErroNo) as e:
        await indices.sancionador()
    assert e.value.permanente is True and "sancionador" in e.value.mensagem


async def test_csv_sem_a_coluna_esperada_e_erro_permanente(respx_mock, indices):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("processo_sancionador.csv", "NUP;Outra\r\n1;2\r\n")
        z.writestr("processo_sancionador_acusado.csv", "NUP;Nome_Acusado;Situacao;Data_Situacao\r\n")
    respx_mock.get(URL_SANCIONADOR).mock(return_value=httpx.Response(200, content=buf.getvalue()))
    with pytest.raises(ErroNo) as e:
        await indices.sancionador()
    assert e.value.permanente is True and "Objeto" in e.value.mensagem


@pytest.mark.parametrize("corpo", [b"<html>502</html>", b'{"sem": "value"}', b'{"value": "x"}', b"[1]"])
async def test_olinda_com_formato_inesperado_e_erro_permanente(respx_mock, indices, corpo):
    respx_mock.get(url__startswith="https://olinda.bcb.gov.br/").mock(return_value=httpx.Response(200, content=corpo))
    with pytest.raises(ErroNo) as e:
        await indices.instituicoes_bcb()
    assert e.value.permanente is True and "instituicoes_bcb" in e.value.mensagem


# ------------------------------------------------------------------------------- BCB


async def test_instituicoes_bcb_dos_quatro_conjuntos(respx_mock, indices):
    rotas = mocar_olinda(respx_mock)
    instituicoes = await indices.instituicoes_bcb()
    assert all(isinstance(i, InstituicaoBCB) for i in instituicoes)
    assert Counter(i.conjunto for i in instituicoes) == {
        "SedesBancoComMultCE": 2, "SedesSociedades": 2, "SedesCooperativas": 2, "SedesConsorcios": 2,
    }
    turcambio = next(i for i in instituicoes if i.raiz_cnpj == "15482499")
    assert (turcambio.conjunto, turcambio.nome, turcambio.segmento) == (
        "SedesSociedades", "TURCÂMBIO - SOCIEDADE CORRETORA DE CÂMBIO LTDA.", "Sociedade Corretora de Câmbio"
    )
    # cooperativas e consórcios não têm SEGMENTO
    assert all(i.segmento is None for i in instituicoes if i.conjunto in ("SedesCooperativas", "SedesConsorcios"))
    # o $format e o $top vão na consulta, sem escapar o "$" do OData
    assert rotas["SedesSociedades"].calls[0].request.url.query == b"$format=json&$top=100000"
    assert rotas["DominiosVerificados"].call_count == 0


async def test_dominios_bcb_ignora_sem_dominio_e_repetidos(respx_mock, indices):
    mocar_olinda(respx_mock)
    dominios = await indices.dominios_bcb()
    assert all(isinstance(d, DominioBCB) for d in dominios)
    # 15 linhas na fonte, 2 "Sem domínio verificado" (DOMINIO vazio) ficam de fora
    assert len(dominios) == 13 and all(d.dominio for d in dominios)
    # o mesmo domínio vale para cada instituição do conglomerado: o par (domínio, raiz) é a chave
    assert sorted({d.raiz_cnpj for d in dominios if d.dominio == "bb.com.br"}) == [
        "00000000", "06043050", "24933830", "30822936", "31546476"
    ]
    bb = next(d for d in dominios if d.dominio == "bb.com.br" and d.raiz_cnpj == "00000000")
    assert bb.instituicao == "BANCO DO BRASIL S.A."


# ------------------------------------------------------------------------------- processo sancionador


async def test_sancionador_junta_processo_e_acusado(respx_mock, indices):
    mocar_cvm(respx_mock)
    processos = await indices.sancionador()
    assert all(isinstance(p, ProcessoCVM) for p in processos)
    assert len(processos) == 5  # uma linha por acusado
    aguia = [p for p in processos if p.acusado.startswith("ÁGUIA")]
    assert sorted((p.nup, p.data_abertura, p.fase) for p in aguia) == [
        ("19957000011202001", date(2020, 3, 10), "Julgamento"),
        ("19957000033202601", date(2026, 4, 5), "Citação e envio de defesas"),
    ]
    assert aguia[0].objeto.startswith("Apurar") and aguia[0].situacao == "Acusado envia defesa"
    # Data_Abertura em DD/MM/AAAA também vale
    figueiredo = next(p for p in processos if p.acusado == "JOSÉ ROBERTO FIGUEIREDO")
    assert figueiredo.data_abertura == date(2019, 9, 15)


# ------------------------------------------------------------------------------- deliberações


async def test_deliberacoes_paginacao_e_data(respx_mock, tmp_path, indices):
    reg = mocar_deliberacoes(respx_mock)
    deliberacoes = await indices.deliberacoes()
    assert all(isinstance(d, Deliberacao) for d in deliberacoes)
    # dos links `deliNNN.html` das duas páginas reais (os PDF e DOCX de cada uma são ignorados)
    assert [d.numero for d in deliberacoes] == sorted(NUMEROS, reverse=True)
    assert {d.numero: d.data for d in deliberacoes} == DATAS
    assert all(d.integral for d in deliberacoes) and reg.pdfs == []  # o `.htm` basta: o PDF nem é pedido
    assert reg.paginas == list(range(1, TOTAL_PAGINAS + 1))  # até "Páginas 28/28"
    assert reg.partida.call_count == 1  # a página de partida abre a sessão; as 28 do JSP vão depois
    d905 = next(d for d in deliberacoes if d.numero == 905)
    assert d905.url == "https://conteudo.cvm.gov.br/legislacao/deliberacoes/deli0900/deli905.html"
    # o texto traz o resumo do invólucro e o texto integral do `deli905.htm`, com o CNPJ e os domínios
    assert "SANTO TRADER TREINAMENTO PROFISSIONAIS LTDA." in d905.texto and "41.557.647/0001-04" in d905.texto
    assert "https://santotrader.com/" in d905.texto
    # do menu da página (fora do bloco do texto) nada entra
    assert "Atos Declaratórios" not in d905.texto and "Voltar ao topo" not in d905.texto
    assert _cache(tmp_path, "deliberacoes")["gerado_em"] == AGORA.isoformat()


async def test_deliberacoes_a_busca_usa_os_parametros_reais(respx_mock, indices):
    reg = mocar_deliberacoes(respx_mock)
    await indices.deliberacoes()
    parametros = dict(reg.jsp.calls[1].request.url.params)
    assert parametros["searchPage"] == "2"
    # o JSP decodifica o termo uma vez a mais: o "Atuação Irregular" vai com aspas, percent-encoded duas vezes
    assert reg.jsp.calls[1].request.url.query.split(b"&")[1] == b"lastName=%2522Atua%25C3%25A7%25C3%25A3o%2520Irregular%2522"
    assert (parametros["itensPagina"], parametros["ordenar"], parametros["filtro"], parametros["buscado"]) == (
        "10", "recentes", "todos", "true"
    )


async def test_deliberacoes_sem_a_sessao_da_busca_nao_vira_indice_vazio(respx_mock, tmp_path, indices):
    # o JSP responde 200 com o corpo em branco a quem chega sem o cookie da página de partida
    reg = mocar_deliberacoes(respx_mock)
    reg.partida.mock(return_value=httpx.Response(200, text="<html></html>"))  # sem Set-Cookie
    with pytest.raises(ErroNo) as e:
        await indices.deliberacoes()
    assert e.value.permanente is False and "deliberacoes" in e.value.mensagem
    assert not (tmp_path / "deliberacoes.json").exists()


def _jsp_cortado(reg, a_partir_da: int = 2) -> None:
    """A busca diz "Páginas n/28", mas a partir da página `a_partir_da` responde "Nenhum resultado encontrado"."""
    funciona = reg.jsp.side_effect
    reg.jsp.mock(
        side_effect=lambda r: httpx.Response(200, content=fixture_bytes("deliberacoes_vazia.html"))
        if int(r.url.params["searchPage"]) >= a_partir_da
        else funciona(r)
    )


async def test_pagina_sem_resultado_antes_do_total_nao_vira_indice_parcial(respx_mock, tmp_path, indices):
    # a página 1 diz "Páginas 1/28" e a 2 já é "Nenhum resultado": lista cortada, não o fim da busca
    reg = mocar_deliberacoes(respx_mock)
    _jsp_cortado(reg)
    with pytest.raises(ErroNo) as e:
        await indices.deliberacoes()
    assert e.value.permanente is False and "deliberacoes" in e.value.mensagem
    assert not (tmp_path / "deliberacoes.json").exists() and reg.involucros == []  # nada gravado nem baixado pela metade


async def test_lista_cortada_com_cache_existente_deixa_o_cache_como_estava(respx_mock, tmp_path, indices, relogio):
    reg = mocar_deliberacoes(respx_mock)
    await indices.deliberacoes()
    antes = (tmp_path / "deliberacoes.json").read_bytes()
    relogio.avancar(hours=25)
    _jsp_cortado(reg, a_partir_da=15)
    vencido = await indices.deliberacoes()  # I6: o anterior volta, marcado como vencido
    assert vencido_desde(vencido) == AGORA + timedelta(hours=24) and len(vencido) == 7
    assert (tmp_path / "deliberacoes.json").read_bytes() == antes  # com o `gerado_em` antigo: continua vencido


async def test_deliberacoes_incremental_so_baixa_os_numeros_novos(respx_mock, tmp_path, indices, relogio):
    reg = mocar_deliberacoes(respx_mock)
    await indices.deliberacoes()
    assert sorted(reg.involucros) == NUMEROS and sorted(reg.documentos) == NUMEROS
    relogio.avancar(hours=25)
    await indices.deliberacoes()
    # a busca foi refeita (índice vencido), mas as sete deliberações já guardadas não foram baixadas de novo
    assert reg.partida.call_count == 2 and reg.paginas == list(range(1, 29)) * 2
    assert sorted(reg.involucros) == NUMEROS and sorted(reg.documentos) == NUMEROS
    # uma deliberação nova na busca: some da cópia local e é a única baixada
    cache = _cache(tmp_path, "deliberacoes")
    cache["itens"] = [i for i in cache["itens"] if i["numero"] != 903]
    (tmp_path / "deliberacoes.json").write_text(json.dumps(cache), encoding="utf-8")
    relogio.avancar(hours=25)
    deliberacoes = await indices.deliberacoes()
    assert [d.numero for d in deliberacoes] == sorted(NUMEROS, reverse=True)
    assert sorted(reg.involucros) == sorted([*NUMEROS, 903]) and sorted(reg.documentos) == sorted([*NUMEROS, 903])


async def test_deliberacoes_dentro_da_validade_nao_toca_a_rede(respx_mock, indices, relogio):
    reg = mocar_deliberacoes(respx_mock)
    await indices.deliberacoes()
    chamadas = (reg.partida.call_count, len(reg.paginas), len(reg.involucros))
    relogio.avancar(hours=23)
    await indices.deliberacoes()
    assert (reg.partida.call_count, len(reg.paginas), len(reg.involucros)) == chamadas


async def test_deliberacoes_falha_no_meio_guarda_o_progresso(respx_mock, tmp_path, indices):
    reg = mocar_deliberacoes(respx_mock)
    funciona = reg.rota_involucros.side_effect
    reg.rota_involucros.mock(side_effect=lambda r: httpx.Response(503) if str(r.url).endswith("deli900.html") else funciona(r))
    with pytest.raises(ErroNo) as e:
        await indices.deliberacoes()
    assert e.value.permanente is False and "deli900" in e.value.mensagem
    parcial = _cache(tmp_path, "deliberacoes")
    assert [i["numero"] for i in parcial["itens"]] == [905, 903, 902, 901]
    assert parcial["gerado_em"] is None  # incompleto: o próximo uso refaz a busca
    # o servidor volta: só o que faltava é baixado
    reg.rota_involucros.mock(side_effect=funciona)
    antes = len(reg.involucros)
    deliberacoes = await indices.deliberacoes()
    assert [d.numero for d in deliberacoes] == sorted(NUMEROS, reverse=True)
    assert reg.involucros[antes:] == [900, 899, 895]
    assert _cache(tmp_path, "deliberacoes")["gerado_em"] == AGORA.isoformat()


async def test_deliberacao_que_responde_404_fica_de_fora_sem_derrubar_as_outras(respx_mock, indices):
    reg = mocar_deliberacoes(respx_mock)
    funciona = reg.rota_involucros.side_effect
    reg.rota_involucros.mock(side_effect=lambda r: httpx.Response(404) if str(r.url).endswith("deli902.html") else funciona(r))
    deliberacoes = await indices.deliberacoes()
    assert [d.numero for d in deliberacoes] == [905, 903, 901, 900, 899, 895]


async def test_deliberacao_sem_texto_integral_fica_com_o_resumo(respx_mock, indices):
    # sem `.htm` e com o PDF fora do ar (404), só o resumo do invólucro
    reg = mocar_deliberacoes(respx_mock)
    reg.rota_pdfs.mock(return_value=httpx.Response(404))
    listagem = (
        '<span>2 resultados encontrados</span><article><h3><a href="/legislacao/deliberacoes/deli0500/deli509.html">'
        'Deliberação CVM 509</a></h3></article><article><h3><a href="/legislacao/deliberacoes/deli0800/Deli863.html">'
        'Deliberação CVM 863</a></h3></article><span>Páginas 1/1</span>'
    )
    reg.jsp.mock(return_value=httpx.Response(200, text=listagem))
    sem_documento = fixture_bytes("deli509.html")
    outro = fixture_bytes("deli509.html").replace(b"509", b"863")
    reg.rota_involucros.mock(
        side_effect=lambda r: httpx.Response(200, content=sem_documento if r.url.path.endswith("deli509.html") else outro)
    )
    deliberacoes = await indices.deliberacoes()
    d509 = next(d for d in deliberacoes if d.numero == 509)
    assert d509.data == date(2006, 9, 29)  # do carimbo do invólucro; o texto só tem "(Publicada no DOU de 03.10.06)"
    assert d509.integral is False and "Fidelitas Investimentos Ltda." in d509.texto
    assert "Atos Declaratórios" not in d509.texto
    # `Deli863.html` (D maiúsculo, como o site publica duas deliberações) também entra
    assert {d.numero for d in deliberacoes} == {509, 863}
    assert next(d for d in deliberacoes if d.numero == 863).url.endswith("/deli0800/Deli863.html")


async def test_deliberacao_sem_carimbo_usa_a_primeira_data_do_documento_e_nunca_a_do_resumo(respx_mock, indices):
    reg = mocar_deliberacoes(respx_mock)
    listagem = (
        '<span>Páginas 1/1</span><h3><a href="/legislacao/deliberacoes/deli0800/deli801.html">x</a></h3>'
        '<h3><a href="/legislacao/deliberacoes/deli0800/deli802.html">y</a></h3>'
    )
    reg.jsp.mock(return_value=httpx.Response(200, text=listagem))
    resumo = "nos termos da Lei nº 6.385, de 7 de dezembro de 1976, e da Resolução CVM nº 20, de 25 de fevereiro de 2021"

    def involucro(request: httpx.Request) -> httpx.Response:
        com_documento = request.url.path.endswith("deli801.html")
        link = '<a href="/legislacao/deliberacoes/anexos/0800/deli801.htm">[HTML]</a>' if com_documento else ""
        return httpx.Response(
            200, text=f'<article class="contentTextoGeral"><p>Atuação irregular {resumo}.</p>{link}</article>'
        )

    reg.rota_involucros.mock(side_effect=involucro)
    reg.rota_documentos.mock(
        return_value=httpx.Response(200, text="<p>DELIBERAÇÃO CVM Nº 801, de 3 de MARÇO de 2020</p><p>Lei de 1º de janeiro de 1999</p>")
    )
    deliberacoes = {d.numero: d for d in await indices.deliberacoes()}
    assert deliberacoes[801].data == date(2020, 3, 3)
    # sem carimbo e sem documento a data é desconhecida: o resumo cita leis e resoluções, não a deliberação
    assert deliberacoes[802].data is None


async def test_deliberacoes_exige_o_bloco_do_texto_na_pagina(respx_mock, indices):
    # uma página sem o `<article class="contentTextoGeral">` (layout novo) não vira deliberação de texto vazio
    reg = mocar_deliberacoes(respx_mock)
    reg.rota_involucros.mock(return_value=httpx.Response(200, text="<html><body>Nova cara</body></html>"))
    with pytest.raises(ErroNo) as e:
        await indices.deliberacoes()
    assert e.value.permanente is True and "deliberacoes" in e.value.mensagem



# ---------------------- erros que não podem apagar deliberações novas em silêncio (cache já existente)


async def _cache_sem_as_mais_novas(respx_mock, tmp_path, indices, relogio):
    """Um índice completo no disco do qual saíram 905 e 903, vencido (25 h depois): elas são as 'novas' da renovação."""
    reg = mocar_deliberacoes(respx_mock)
    await indices.deliberacoes()
    cache = _cache(tmp_path, "deliberacoes")
    cache["itens"] = [i for i in cache["itens"] if i["numero"] not in (905, 903)]
    (tmp_path / "deliberacoes.json").write_text(json.dumps(cache), encoding="utf-8")
    relogio.avancar(hours=25)
    return reg


@pytest.mark.parametrize("quebra", ["403", "layout"])
@pytest.mark.parametrize("numero", [905, 903])
async def test_erro_numa_deliberacao_nova_nao_a_descarta_em_silencio(respx_mock, tmp_path, indices, relogio, quebra, numero):
    reg = await _cache_sem_as_mais_novas(respx_mock, tmp_path, indices, relogio)
    funciona = reg.rota_involucros.side_effect
    resposta = {"403": lambda: httpx.Response(403), "layout": lambda: httpx.Response(200, text="<html>Nova cara</html>")}[quebra]
    reg.rota_involucros.mock(side_effect=lambda r: resposta() if str(r.url).endswith(f"deli{numero}.html") else funciona(r))
    # I6: há um índice anterior completo, então ele volta vencido (com o progresso) em vez de derrubar o nó
    vencido = await indices.deliberacoes()
    assert vencido_desde(vencido) == AGORA + timedelta(hours=24)
    progresso = ([905] if numero == 903 else []) + [902, 901, 900, 899, 895]
    assert [d.numero for d in vencido] == progresso
    cache = _cache(tmp_path, "deliberacoes")
    # o progresso fica (a 905 entra se a 903 é que falhou) e o índice continua vencido: a próxima chamada tenta de novo
    assert [i["numero"] for i in cache["itens"]] == progresso
    assert cache["gerado_em"] == AGORA.isoformat()
    reg.rota_involucros.mock(side_effect=funciona)
    assert [d.numero for d in await indices.deliberacoes()] == sorted(NUMEROS, reverse=True)


async def test_404_numa_deliberacao_nova_e_o_unico_erro_que_a_pula(respx_mock, tmp_path, indices, relogio):
    reg = await _cache_sem_as_mais_novas(respx_mock, tmp_path, indices, relogio)
    funciona = reg.rota_involucros.side_effect
    reg.rota_involucros.mock(side_effect=lambda r: httpx.Response(404) if str(r.url).endswith("deli905.html") else funciona(r))
    assert [d.numero for d in await indices.deliberacoes()] == [903, 902, 901, 900, 899, 895]


# ---------------------- renovação: invólucros recentes sem texto integral são baixados de novo


async def test_renovacao_baixa_de_novo_so_o_que_e_recente_e_nao_tem_texto_integral(respx_mock, tmp_path, indices, relogio):
    reg = mocar_deliberacoes(respx_mock)
    await indices.deliberacoes()
    cache = _cache(tmp_path, "deliberacoes")
    for item in cache["itens"]:
        if item["numero"] == 905:  # recente (< 180 dias) e só com o resumo: o anexo pode ter saído depois
            item.update(data="2026-08-01", integral=False, texto="Deliberação CVM 905 só o resumo")
        elif item["numero"] == 903:  # só com o resumo, mas de mais de 180 dias: não se baixa de novo
            item.update(integral=False, texto="Deliberação CVM 903 só o resumo")
        elif item["numero"] == 902:  # sem data conhecida e só com o resumo: também volta
            item.update(data=None, integral=False, texto="Deliberação CVM 902 só o resumo")
        elif item["numero"] == 901:  # recente, mas já integral: nunca volta
            item.update(data="2026-09-01")
    (tmp_path / "deliberacoes.json").write_text(json.dumps(cache), encoding="utf-8")
    antes = len(reg.involucros)
    relogio.avancar(hours=25)
    deliberacoes = {d.numero: d for d in await indices.deliberacoes()}
    assert sorted(reg.involucros[antes:]) == [902, 905]
    assert deliberacoes[905].integral and "SANTO TRADER" in deliberacoes[905].texto
    assert deliberacoes[905].data == date(2025, 11, 25)  # a data volta a ser a do carimbo
    assert deliberacoes[902].integral and deliberacoes[902].data == date(2025, 8, 22)
    assert not deliberacoes[903].integral and deliberacoes[903].texto == "Deliberação CVM 903 só o resumo"
    assert deliberacoes[901].integral


async def test_renovacao_com_404_no_involucro_mantem_o_que_ja_havia(respx_mock, tmp_path, indices, relogio):
    reg = mocar_deliberacoes(respx_mock)
    await indices.deliberacoes()
    cache = _cache(tmp_path, "deliberacoes")
    for item in cache["itens"]:
        if item["numero"] == 905:
            item.update(data="2026-08-01", integral=False, texto="só o resumo")
    (tmp_path / "deliberacoes.json").write_text(json.dumps(cache), encoding="utf-8")
    relogio.avancar(hours=25)
    funciona = reg.rota_involucros.side_effect
    reg.rota_involucros.mock(side_effect=lambda r: httpx.Response(404) if str(r.url).endswith("deli905.html") else funciona(r))
    d905 = next(d for d in await indices.deliberacoes() if d.numero == 905)
    assert (d905.texto, d905.integral, d905.data) == ("só o resumo", False, date(2026, 8, 1))


# ---------------------- texto integral pelo PDF do anexo


def _listagem(*numeros: int) -> str:
    links = "".join(
        f'<article><h3><a href="/legislacao/deliberacoes/deli{n // 100:02d}00/deli{n}.html">Deliberação CVM {n}</a></h3></article>'
        for n in numeros
    )
    return f"<span>{len(numeros)} resultados encontrados</span>{links}<span>Páginas 1/1</span>"


async def test_deliberacao_antiga_ganha_o_texto_integral_do_pdf(respx_mock, indices):
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(586, 509)))
    d = {x.numero: x for x in await indices.deliberacoes()}
    assert reg.pdfs == [586, 509] and reg.documentos == []  # sem `.htm` no invólucro, vai para o PDF
    assert all(x.integral for x in d.values())
    d509 = d[509]
    texto = " ".join(d509.texto.split())
    assert texto.startswith("Deliberação CVM 509 Fri Sep 29 00:00:00 BRT 2006 Atuação irregular")  # o resumo vem antes
    # o PDF traz o que o resumo não tem: o CNPJ (com o espaço que a extração deixa depois do hífen)
    assert "FIDELITAS INVESTIMENTOS LTDA., CNPJ nº 06.151.776/0001- 99" in texto
    assert d509.data == date(2006, 9, 29)
    assert "http://www.fginfocls.com" in " ".join(d[586].texto.split()) and d[586].data == date(2009, 8, 11)


async def test_doc_e_docx_nao_sao_baixados(respx_mock, indices):
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(801)))
    chamadas = []
    respx_mock.get(url__regex=r".*\.(doc|docx)$").mock(side_effect=lambda r: chamadas.append(str(r.url)) or httpx.Response(200))
    reg.rota_involucros.mock(
        return_value=httpx.Response(
            200,
            text='<article class="contentTextoGeral"><p>Resumo.</p>'
            '<a href="/export/sites/cvm/legislacao/deliberacoes/anexos/0800/deli801.doc">[DOC]</a>'
            '<a href="/legislacao/deliberacoes/anexos/0800/deli801.docx">[DOCX]</a></article>',
        )
    )
    (d,) = await indices.deliberacoes()
    assert d.integral is False and d.texto.startswith("Resumo.") and chamadas == [] and reg.pdfs == []


@pytest.mark.parametrize(
    "resposta",
    [
        pytest.param(lambda: httpx.Response(404), id="pdf-ausente"),
        pytest.param(lambda: httpx.Response(200, content=fixture_bytes("sem_texto.pdf")), id="pdf-sem-texto-extraivel"),
        pytest.param(lambda: httpx.Response(200, content=pdf_com_texto("1")), id="pdf-so-com-o-numero-da-pagina"),
        pytest.param(lambda: httpx.Response(200, content=b"<html>erro</html>"), id="nao-e-pdf"),
        pytest.param(lambda: httpx.Response(200, content=fixture_bytes("deli509.pdf")[:3000]), id="pdf-cortado"),
        pytest.param(lambda: httpx.Response(200, content=b""), id="vazio"),
    ],
)
async def test_pdf_ausente_ou_sem_texto_extraivel_fica_so_com_o_resumo(respx_mock, indices, resposta):
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(509)))
    reg.rota_pdfs.mock(side_effect=lambda r: resposta())
    (d,) = await indices.deliberacoes()
    assert d.integral is False and "Fidelitas Investimentos Ltda." in d.texto
    assert "CNPJ" not in d.texto and d.data == date(2006, 9, 29)  # a data vem do carimbo mesmo assim


async def test_pdf_grande_demais_nao_e_lido(respx_mock, indices, monkeypatch):
    import radar.texto as modulo  # o limite mora em `texto_de_pdf`, que os índices usam

    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(509)))
    monkeypatch.setattr(modulo, "_MAX_BYTES_PDF", 1000)
    (d,) = await indices.deliberacoes()
    assert d.integral is False and reg.pdfs == [509]


async def test_htm_ausente_cai_no_pdf(respx_mock, indices):
    # o invólucro liga um `.htm` que deu 404 (e também o PDF): vale o PDF
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(509)))
    reg.rota_involucros.mock(
        return_value=httpx.Response(
            200,
            content=fixture_bytes("deli509.html").replace(
                b"<p>(Publicada", b'<a href="/legislacao/deliberacoes/anexos/0500/deli509.htm">[HTML]</a><p>(Publicada'
            ),
        )
    )
    reg.rota_documentos.mock(return_value=httpx.Response(404))
    (d,) = await indices.deliberacoes()
    assert d.integral and "06.151.776/0001" in d.texto and reg.documentos == [] and reg.pdfs == [509]


@pytest.mark.parametrize("status", [403, 503])
async def test_anexo_de_deliberacao_antiga_com_erro_fica_so_com_o_resumo(respx_mock, tmp_path, indices, status):
    # I6: um anexo antigo que nunca responde não trava a renovação do índice
    reg = mocar_deliberacoes(respx_mock)
    reg.jsp.mock(return_value=httpx.Response(200, text=_listagem(586, 509)))
    funciona = reg.rota_pdfs.side_effect
    reg.rota_pdfs.mock(side_effect=lambda r: httpx.Response(status) if str(r.url).endswith("deli509.pdf") else funciona(r))
    d586, d509 = await indices.deliberacoes()
    assert d586.integral and not d509.integral and "509" in d509.texto
    cache = _cache(tmp_path, "deliberacoes")
    assert [i["numero"] for i in cache["itens"]] == [586, 509] and cache["gerado_em"] == AGORA.isoformat()


@pytest.mark.parametrize(("status", "permanente"), [(403, True), (503, False)])
async def test_anexo_de_deliberacao_recente_com_erro_derruba_o_indice(respx_mock, tmp_path, indices, relogio, status, permanente):
    # a recente (menos de 180 dias) é a que traz CNPJ e domínio: sem o texto dela o índice não vale
    relogio.t = datetime(2025, 12, 1, 12, 0, 0)
    reg = mocar_deliberacoes(respx_mock)
    funciona = reg.rota_documentos.side_effect
    reg.rota_documentos.mock(side_effect=lambda r: httpx.Response(status) if str(r.url).endswith("deli905.htm") else funciona(r))
    with pytest.raises(ErroNo) as e:
        await indices.deliberacoes()
    assert e.value.permanente is permanente and "deli905" in e.value.mensagem
    assert _cache(tmp_path, "deliberacoes")["gerado_em"] is None


async def test_cache_de_antes_do_campo_integral_nao_vale(respx_mock, tmp_path, indices):
    # um cache gravado sem `integral` não vale: o índice é refeito do zero
    reg = mocar_deliberacoes(respx_mock)
    antigo = {"gerado_em": AGORA.isoformat(), "itens": [{"numero": 905, "data": "2025-11-25", "url": "u", "texto": "t"}]}
    (tmp_path / "deliberacoes.json").write_text(json.dumps(antigo), encoding="utf-8")
    assert len(await indices.deliberacoes()) == 7 and sorted(reg.involucros) == NUMEROS


def test_urls_da_spec():
    assert URL_DELIBERACOES_PARTIDA == (
        "https://conteudo.cvm.gov.br/legislacao/index.html?numero=&lastNameShow=%22Atua%C3%A7%C3%A3o+Irregular%22"
        "&lastName=%2522Atua%25C3%25A7%25C3%25A3o%2520Irregular%2522&buscado=true&pasta=deliberacoes&filtro=todos"
        "&contCategoriasCheck=1&vimDaCategoria=%2Flegislacao%2Fdeliberacoes%2F&tags="
    )
    assert URL_OLINDA == (
        "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata/{conjunto}"
        "?$format=json&$top=100000"
    )
    assert URL_DELIBERACOES_PAGINAS.endswith("/system/modules/br.com.squadra.legislacao/elements/resultadoLegislacao.jsp")


# ---------------------- índice vencido quando a renovação falha (I6)


async def test_renovacao_que_falha_devolve_o_indice_vencido(respx_mock, tmp_path, indices, relogio):
    rotas = mocar_cvm(respx_mock)
    frescos = await indices.cadastros_cvm()
    assert vencido_desde(frescos) is None
    relogio.avancar(hours=25)
    for rota in rotas.values():
        rota.mock(return_value=httpx.Response(503))
    vencidos = await indices.cadastros_cvm()
    assert vencidos == frescos and vencido_desde(vencidos) == AGORA + timedelta(hours=24)
    # o arquivo continua o de antes: a próxima chamada tenta renovar de novo
    assert _cache(tmp_path, "cadastros_cvm")["gerado_em"] == AGORA.isoformat()


async def test_sem_indice_anterior_a_falha_continua_erro(respx_mock, indices):
    respx_mock.get(URL_SANCIONADOR).mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo):
        await indices.sancionador()
