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


async def test_deliberacoes_para_na_pagina_sem_resultados(respx_mock, indices):
    reg = mocar_deliberacoes(respx_mock)
    pagina1 = fixture_bytes("deliberacoes_pagina1.html")
    reg.jsp.mock(
        side_effect=lambda r: httpx.Response(
            200, content=pagina1 if r.url.params["searchPage"] == "1" else fixture_bytes("deliberacoes_vazia.html")
        )
    )
    deliberacoes = await indices.deliberacoes()
    # a página 1 só tem o HTML de 905, 903 e 902 (o de 901 vem na 2); a 2 já é "Nenhum resultado encontrado"
    assert [d.numero for d in deliberacoes] == [905, 903, 902]
    assert reg.involucros == [905, 903, 902]


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
    funciona = reg.rota_documentos.side_effect
    reg.rota_documentos.mock(side_effect=lambda r: httpx.Response(503) if str(r.url).endswith("deli900.htm") else funciona(r))
    with pytest.raises(ErroNo) as e:
        await indices.deliberacoes()
    assert e.value.permanente is False and "deli900" in e.value.mensagem
    parcial = _cache(tmp_path, "deliberacoes")
    assert [i["numero"] for i in parcial["itens"]] == [905, 903, 902, 901]
    assert parcial["gerado_em"] is None  # incompleto: o próximo uso refaz a busca
    # o servidor volta: só o que faltava é baixado
    reg.rota_documentos.mock(side_effect=funciona)
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


async def test_deliberacao_sem_o_documento_integral_fica_com_o_resumo(respx_mock, indices):
    # 89 das 97 deliberações (as de antes de 2024) só têm o resumo no HTML; o texto integral é PDF/DOC
    reg = mocar_deliberacoes(respx_mock)
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
    assert "Fidelitas Investimentos Ltda." in d509.texto
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
