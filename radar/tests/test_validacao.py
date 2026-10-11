"""Validação de respostas, arquivamento de fonte e checagens SSRF/contato (Tarefa 13)."""

from __future__ import annotations

import ipaddress
import json
import socket
import threading
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from radar.config import Config, RedeConfig
from radar.custodia import Custodia
from radar.modelos import Contexto, ErroNo, Evidencia, Pendencia, Resposta
from radar.motor import Servicos
from radar.nos.extracao import ExtracaoNo
from radar.pendencias.definicoes import nova_pendencia
from radar.pendencias.mascara import mascarar, montar_mascara
from radar.pendencias.validacao import FonteArquivada, Validacao, arquivar_fonte, validar
from radar.rede import ErroRede, Rede
from radar.texto import normalizar, texto_de_pdf
from tests.matriz_spec import MATRIZ_SPEC

AGORA = datetime(2026, 10, 7, 12, 0, 0)
URL = "https://noticias.example.org/materia"
VALOR_A1 = {"pct_mes": 45.0, "taxa_diaria": True, "garantido": True}
TRECHO = "Rendimento de 1,5% ao dia"
PAGINA = (
    '<html lang="pt-BR"><head><meta charset="utf-8"><title>Exemplo Invest</title>{cabeca}</head><body>'
    "<h1>Exemplo Invest</h1>"
    "<p>Rendimento de 1,5% ao dia, “garantido”   pela\n empresa.</p>"
    '<script>var oculto = "texto só no script";</script></body></html>'
)
MOTIVO_NENHUM = "fonte recusada: modo_contato=nenhum não permite acessar o alvo; cite o snapshot do Wayback"
MOTIVO_FONTE_INVALIDA = "fonte inválida: use sha256:<hex> ou URL http(s)"
MOTIVO_ALVO = "fonte recusada: o alvo só é acessado pela captura; cite o sha256 da captura ou o snapshot do Wayback"
MOTIVO_ALVO_CEGO = "fonte recusada: domínio não permitido"
MOTIVO_CURTO = "trecho curto demais: cite ao menos 12 caracteres literais da fonte"
MOTIVO_HOST = "fonte recusada: host inválido"
MOTIVO_NXDOMAIN = "fonte não encontrada (domínio inexistente); cite uma URL existente ou o snapshot do Wayback"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
FIXTURES_CVM = Path(__file__).parent / "fixtures" / "cvm"
IP_PUBLICO = "93.184.216.34"


def pagina(cabeca: str = "") -> str:
    return PAGINA.replace("{cabeca}", cabeca)


async def _nao_dormir(s: float) -> None:
    return None


def contexto(
    pasta: Path, as_of: date = date(2026, 10, 7), modo_contato: str = "captura", alvo: str = "exemplo.com.br"
) -> Contexto:
    slug = alvo.replace(".", "-")
    return Contexto(
        alvo=alvo,
        slug=slug,
        url_inicial=f"https://{alvo}/",
        as_of=as_of,
        data_execucao=AGORA,
        modo_contato=modo_contato,
        modo_cego=False,
        run_id=f"{slug}/2026-10-07_120000",
        pasta=pasta,
    )


@pytest.fixture(autouse=True)
def dns(monkeypatch):
    """O DNS dos testes: todo nome resolve para um IP público, a menos que o teste diga outro em `dns[nome]`
    (um IP, uma lista ou uma exceção). Os testes não consultam a internet."""
    respostas: dict = {}

    def getaddrinfo(host, porta, *args, **kwargs):
        resposta = respostas.get(host, IP_PUBLICO)
        if isinstance(resposta, Exception):
            raise resposta
        enderecos = [resposta] if isinstance(resposta, str) else resposta
        return [
            (socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in enderecos
        ]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return respostas


@pytest.fixture
def ctx(tmp_path):
    return contexto(tmp_path)


@pytest.fixture
def ctx_retro(tmp_path):
    return contexto(tmp_path, as_of=date(2025, 6, 1))


@pytest.fixture
def ctx_nenhum(tmp_path):
    return contexto(tmp_path, modo_contato="nenhum")


@pytest.fixture
def ctx_cego(tmp_path):
    return contexto(tmp_path).model_copy(update={"modo_cego": True})


@pytest.fixture
async def serv(tmp_path):
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        yield Servicos(config=config, rede=rede, custodia=Custodia(tmp_path), matriz=MATRIZ_SPEC)
    finally:
        await rede.fechar()


# a marca da spec e a da evidência (I3): a resposta destes testes tem uma evidência só
NAO_CONFERIDA_0 = ["trecho_nao_conferido", "trecho_nao_conferido:evidencias[0]"]


def pend(ctx: Contexto, id: str = "P-A1") -> Pendencia:  # noqa: A002
    return nova_pendencia(id, ctx, [], "pend_teste", matriz=MATRIZ_SPEC)


def guardar(serv: Servicos, dados: str | bytes, ext: str = "html") -> str:
    conteudo = dados.encode("utf-8") if isinstance(dados, str) else dados
    return serv.custodia.guardar(conteudo, ext, tipo="pagina", origem="https://exemplo.com.br/")


def ev(fonte: str, trecho: str = TRECHO, data_fonte: date | None = date(2025, 1, 10)) -> Evidencia:
    return Evidencia(fonte=fonte, trecho=trecho, data_fonte=data_fonte, tipo_fonte="operador")


def confirmado(*evidencias: Evidencia, valor: dict | None = None, status: str = "confirmado") -> Resposta:
    return Resposta(status=status, valor=VALOR_A1 if valor is None else valor, evidencias=list(evidencias))


def servir(respx_mock, url: str, html: str, **kw):
    return respx_mock.get(url).mock(return_value=httpx.Response(200, html=html, **kw))


# --- trecho conferido na fonte ---------------------------------------------------------------------------


async def test_trecho_conferido_por_artefato(ctx, serv):
    ref = guardar(serv, pagina())
    # outra caixa, sem acento, aspas retas no lugar das curvas, espaços e quebra de linha diferentes
    trecho = 'RENDIMENTO  de 1,5%  ao dia, "GARANTIDO" pela empresa'
    v = await validar(confirmado(ev(ref, trecho)), pend(ctx), ctx, serv)
    assert v == Validacao(aceita=True, motivo=None, campo=None, marcas=[])


async def test_acento_do_trecho_nao_precisa_bater(ctx, serv):
    ref = guardar(serv, "<p>Atenção: saque suspenso até segunda ordem</p>")
    v = await validar(confirmado(ev(ref, "atencao: SAQUE suspenso")), pend(ctx), ctx, serv)
    assert v.aceita


async def test_trecho_ausente_rejeita(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, "Rendimento de 9,9% ao dia")), pend(ctx), ctx, serv)
    assert v == Validacao(False, "trecho não encontrado na fonte", "evidencias[0].trecho", [])


async def test_html_so_vale_o_texto_visivel(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, "texto só no script")), pend(ctx), ctx, serv)
    assert (v.aceita, v.motivo) == (False, "trecho não encontrado na fonte")


async def test_trecho_do_texto_interno_e_conferido_no_artefato_que_a_extracao_guardou(ctx, serv):
    # o texto de um script não vale citado no HTML (o teste acima), mas vale no texto interno, o artefato derivado
    html = '<script>window.t = {"saque.rendimento.bloqueado":"Saques de rendimento estão bloqueados."};</script>'
    login = {
        "url": "https://exemplo.com.br/login", "texto": guardar(serv, "Entrar", "txt"), "html": guardar(serv, html)
    }  # fmt: skip
    feito = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [login], "bloqueada": False}}, {}, serv)
    (candidato,) = feito.saidas["candidatos"]
    assert candidato["extra"] == {"origem": "texto_interno"}
    fonte = candidato["artefato"]
    assert serv.custodia.tipos(fonte) == {"texto_interno"}

    async def validar_b(fonte: str, trecho: str) -> Validacao:
        return await validar(confirmado(ev(fonte, trecho), valor=VALOR_B), pend(ctx, "P-B"), ctx, serv)

    for trecho in ("SAQUES de rendimento estao bloqueados", "saque.rendimento.bloqueado = Saques de rendimento"):
        assert await validar_b(fonte, trecho) == Validacao(True, None, None, [])
    assert (await validar_b(fonte, "Saques de rendimento liberados")).motivo == "trecho não encontrado na fonte"
    assert (await validar_b(login["html"], "Saques de rendimento estão bloqueados")).aceita is False


async def test_html_em_iso_8859_1_sem_cabecalho_de_charset(ctx, serv):
    html = '<html><head><meta charset="iso-8859-1"></head><body><p>Promoção: rendimento garantido</p></body></html>'
    ref = guardar(serv, html.encode("iso-8859-1"))
    v = await validar(confirmado(ev(ref, "promoção: rendimento garantido")), pend(ctx), ctx, serv)
    assert v.aceita


@pytest.mark.parametrize(
    ("ext", "conteudo"),
    [
        ("txt", "Saque suspenso até segunda ordem".encode()),
        ("json", json.dumps({"aviso": "Saque suspenso até segunda ordem"}, ensure_ascii=False).encode()),
        ("txt", b"Saque suspenso at\xe9 segunda ordem"),  # bytes que não são UTF-8 viram U+FFFD, sem erro
    ],
)
async def test_artefato_que_nao_e_html_e_lido_como_texto(ctx, serv, ext, conteudo):
    ref = guardar(serv, conteudo, ext)
    v = await validar(confirmado(ev(ref, "saque suspenso")), pend(ctx), ctx, serv)
    assert v.aceita


async def test_artefato_png_aceita_sem_conferir(ctx, serv):
    ref = guardar(serv, PNG, "png")
    v = await validar(confirmado(ev(ref, "qualquer coisa que está na imagem")), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


@pytest.mark.parametrize(
    "trecho",
    ["", "   ", "a", "%", "1", "ais", "ab cd", "12345 78901", "Rendimentodiariogarantido", "Rendimento\u00ad\u200b"],
)
async def test_trecho_curto_demais_rejeita(ctx, serv, trecho):
    # 12 caracteres e 2 palavras, depois de normalizar: o que passa disso na página não prova nada
    ref = guardar(serv, f"<p>{TRECHO} 1 % ais a ab cd 12345 78901 Rendimentodiariogarantido</p>")
    v = await validar(confirmado(ev(ref), ev(ref, trecho)), pend(ctx), ctx, serv)
    assert v == Validacao(False, MOTIVO_CURTO, "evidencias[1].trecho", [])


async def test_trecho_com_12_caracteres_e_2_palavras_vale(ctx, serv):
    ref = guardar(serv, "<p>chaves 123456 78901 fim</p>")
    assert (await validar(confirmado(ev(ref, "123456 78901")), pend(ctx), ctx, serv)).aceita


async def test_trecho_curto_vale_tambem_para_fonte_que_nao_se_confere(ctx, serv):
    ref = guardar(serv, PNG, "png")
    v = await validar(confirmado(ev(ref, "ais")), pend(ctx), ctx, serv)
    assert (v.aceita, v.motivo) == (False, MOTIVO_CURTO)


async def test_trecho_curto_demais_vem_depois_da_fonte(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, "ais"), ev("rdap")), pend(ctx), ctx, serv)
    assert (v.motivo, v.campo) == (MOTIVO_FONTE_INVALIDA, "evidencias[1].fonte")


async def test_fonte_har_nao_e_citavel(ctx, serv):
    ref = guardar(serv, '{"log": {"mensagem": "Saque suspenso até segunda ordem"}}'.encode(), "har")
    v = await validar(confirmado(ev(ref, "saque suspenso")), pend(ctx), ctx, serv)
    motivo = "fonte .har não é citável: cite o html ou o texto da página"
    assert v == Validacao(False, motivo, "evidencias[0].fonte", [])


async def test_artefato_bin_aceita_sem_conferir(ctx, serv):
    ref = guardar(serv, b"\x00\x01 Saque suspenso\xff", "bin")
    v = await validar(confirmado(ev(ref, "saque suspenso")), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


async def test_campo_aponta_a_evidencia_que_falhou(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref), ev(ref, "frase que não existe")), pend(ctx), ctx, serv)
    assert (v.aceita, v.campo) == (False, "evidencias[1].trecho")


# --- fonte: forma, custódia e URL ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fonte",
    ["cnpj", "rdap", "", "sha256:abc", "ftp://exemplo.org/a", "www.exemplo.org/pagina", "md5:" + "a" * 32],
)
async def test_fonte_invalida(ctx, serv, fonte):
    v = await validar(confirmado(ev(fonte)), pend(ctx), ctx, serv)
    assert v == Validacao(False, MOTIVO_FONTE_INVALIDA, "evidencias[0].fonte", [])


async def test_fonte_invalida_aponta_o_indice(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref), ev("cnpj")), pend(ctx), ctx, serv)
    assert (v.motivo, v.campo) == (MOTIVO_FONTE_INVALIDA, "evidencias[1].fonte")


async def test_ref_sha256_fora_da_custodia(ctx, serv):
    v = await validar(confirmado(ev("sha256:" + "0" * 64)), pend(ctx), ctx, serv)
    assert v == Validacao(False, "fonte não encontrada na custódia", "evidencias[0].fonte", [])


async def test_url_conferida_aceita(ctx, serv, respx_mock):
    servir(respx_mock, URL, pagina())
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, [])


async def test_url_com_trecho_ausente_rejeita(ctx, serv, respx_mock):
    servir(respx_mock, URL, pagina())
    v = await validar(confirmado(ev(URL, "frase que a página não tem")), pend(ctx), ctx, serv)
    assert (v.aceita, v.motivo, v.campo) == (False, "trecho não encontrado na fonte", "evidencias[0].trecho")


async def test_url_inacessivel_aceita_com_marca(ctx, serv, respx_mock):
    rota = respx_mock.get(URL).mock(return_value=httpx.Response(503))
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert rota.call_count == 4  # as quatro tentativas da Rede
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


@pytest.mark.parametrize("status", [404, 410])
async def test_url_que_nao_existe_rejeita(ctx, serv, respx_mock, status):
    respx_mock.get(URL).mock(return_value=httpx.Response(status))
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(
        False,
        f"fonte não encontrada (HTTP {status}); cite uma URL existente ou o snapshot do Wayback",
        "evidencias[0].fonte",
        [],
    )


@pytest.mark.parametrize("status", [403, 429, 500, 502])
async def test_outro_erro_http_aceita_com_marca(ctx, serv, respx_mock, status):
    respx_mock.get(URL).mock(return_value=httpx.Response(status))
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


async def test_falha_de_transporte_aceita_com_marca(ctx, serv, respx_mock):
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("sem rota"))
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


async def test_mesma_url_em_duas_evidencias_baixa_uma_vez(ctx, serv, respx_mock):
    rota = servir(respx_mock, URL, pagina())
    resposta = confirmado(ev(URL), ev(URL, "Exemplo Invest"))
    assert (await validar(resposta, pend(ctx), ctx, serv)).aceita
    assert rota.call_count == 1


async def test_url_de_imagem_aceita_sem_conferir(ctx, serv, respx_mock):
    respx_mock.get("https://exemplo.org/print.png").mock(
        return_value=httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    )
    v = await validar(confirmado(ev("https://exemplo.org/print.png")), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


# --- data ------------------------------------------------------------------------------------------------


async def test_retroativo_data_posterior_rejeita(ctx_retro, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, data_fonte=date(2025, 6, 2))), pend(ctx_retro), ctx_retro, serv)
    assert v == Validacao(False, "data_fonte posterior ao as_of", "evidencias[0].data_fonte", [])


async def test_retroativo_data_no_dia_do_as_of_vale(ctx_retro, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, data_fonte=date(2025, 6, 1))), pend(ctx_retro), ctx_retro, serv)
    assert v.aceita


async def test_execucao_atual_nao_confere_a_data(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, data_fonte=date(2027, 1, 1))), pend(ctx), ctx, serv)
    assert v.aceita


async def test_data_detectada_da_pagina(ctx_retro, serv, respx_mock):
    cabeca = '<meta property="article:published_time" content="2025-03-01T08:00:00-03:00">'
    servir(respx_mock, URL, pagina(cabeca))
    # sem data_fonte: vale a data da página, que é anterior ao as_of, e a evidência não fica sem data
    v = await validar(confirmado(ev(URL, data_fonte=None)), pend(ctx_retro), ctx_retro, serv)
    assert v == Validacao(True, None, None, [])


async def test_data_detectada_posterior_ao_as_of_rejeita(tmp_path, serv, respx_mock):
    ctx = contexto(tmp_path, as_of=date(2025, 2, 15))
    cabeca = '<meta property="article:published_time" content="2025-03-01">'
    servir(respx_mock, URL, pagina(cabeca))
    v = await validar(confirmado(ev(URL, data_fonte=None)), pend(ctx), ctx, serv)
    assert (v.aceita, v.motivo, v.campo) == (False, "data_fonte posterior ao as_of", "evidencias[0].data_fonte")


@pytest.mark.parametrize(
    "cabeca",
    [
        '<meta property="article:published_time" content="2025-03-01">',
        '<meta name="date" content="2025-03-01">',
        '<script type="application/ld+json">{"datePublished":"2025-03-01"}</script>',
    ],
)
async def test_data_detectada_forte_posterior_rejeita_mesmo_com_data_fonte_anterior(tmp_path, serv, respx_mock, cabeca):
    # a página se diz publicada depois do as_of: a data_fonte que o Claude declarou não a salva
    ctx = contexto(tmp_path, as_of=date(2025, 2, 15))
    servir(respx_mock, URL, pagina(cabeca))
    v = await validar(confirmado(ev(URL, data_fonte=date(2025, 1, 5))), pend(ctx), ctx, serv)
    assert v == Validacao(False, "data_fonte posterior ao as_of", "evidencias[0].data_fonte", [])


async def test_data_detectada_forte_anterior_e_data_fonte_anterior_aceita(tmp_path, serv, respx_mock):
    ctx = contexto(tmp_path, as_of=date(2025, 2, 15))
    servir(respx_mock, URL, pagina('<meta property="article:published_time" content="2025-01-01">'))
    v = await validar(confirmado(ev(URL, data_fonte=date(2025, 1, 5))), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, [])


async def test_time_posterior_nao_derruba_a_data_fonte_informada(tmp_path, serv, respx_mock):
    # o <time> costuma ser a data de um evento: só vale quando falta a data_fonte
    ctx = contexto(tmp_path, as_of=date(2025, 2, 15))
    servir(respx_mock, URL, pagina('<time datetime="2025-03-01">lançamento</time>'))
    v = await validar(confirmado(ev(URL, data_fonte=date(2025, 1, 5))), pend(ctx), ctx, serv)
    assert v.aceita


async def test_time_sozinho_vale_quando_falta_a_data_fonte(tmp_path, serv, respx_mock):
    ctx = contexto(tmp_path, as_of=date(2025, 2, 15))
    servir(respx_mock, URL, pagina('<time datetime="2025-03-01">lançamento</time>'))
    v = await validar(confirmado(ev(URL, data_fonte=None)), pend(ctx), ctx, serv)
    assert (v.aceita, v.motivo) == (False, "data_fonte posterior ao as_of")


async def test_execucao_atual_nao_confere_a_data_detectada(ctx, serv, respx_mock):
    servir(respx_mock, URL, pagina('<meta property="article:published_time" content="2027-03-01">'))
    assert (await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)).aceita


async def test_sem_data_marca_data_desconhecida(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, data_fonte=None)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, ["data_desconhecida", "data_desconhecida:evidencias[0]"])


async def test_artefato_nao_tem_data_detectada(ctx_retro, serv):
    # a data detectada é a da página que `arquivar_fonte` baixou; o artefato da custódia não passa por ela
    ref = guardar(serv, pagina('<meta property="article:published_time" content="2025-03-01">'))
    v = await validar(confirmado(ev(ref, data_fonte=None)), pend(ctx_retro), ctx_retro, serv)
    assert v.marcas == ["data_desconhecida", "data_desconhecida:evidencias[0]"]


async def test_marcas_sem_duplicatas_na_ordem_em_que_surgiram(ctx, serv, respx_mock):
    respx_mock.get(URL).mock(return_value=httpx.Response(503))
    respx_mock.get(URL + "-2").mock(return_value=httpx.Response(503))
    ref = guardar(serv, pagina())
    resposta = confirmado(ev(URL, data_fonte=None), ev(URL + "-2", data_fonte=None), ev(ref, data_fonte=None))
    v = await validar(resposta, pend(ctx), ctx, serv)
    assert v.aceita
    # a marca agregada da spec e, depois dela, uma por evidência (I3)
    assert v.marcas == [
        "trecho_nao_conferido", "trecho_nao_conferido:evidencias[0]", "trecho_nao_conferido:evidencias[1]",
        "data_desconhecida", "data_desconhecida:evidencias[0]", "data_desconhecida:evidencias[1]",
        "data_desconhecida:evidencias[2]",
    ]  # fmt: skip


VALOR_B = {"indicacao": "indicacao_remunerada", "token_proprio": False, "carencia_com_multa": True,
           "taxa_para_sacar": False}  # fmt: skip


async def test_itens_da_evidencia_precisam_ser_da_pendencia(ctx, serv):
    ref = guardar(serv, pagina())
    boa = ev(ref).model_copy(update={"itens": ["B1", "B3"]})
    v = await validar(confirmado(boa, valor=VALOR_B), pend(ctx, "P-B"), ctx, serv)
    assert v.aceita, v
    fora = ev(ref).model_copy(update={"itens": ["B3", "A1"]})
    v = await validar(confirmado(boa, fora, valor=VALOR_B), pend(ctx, "P-B"), ctx, serv)
    assert (v.aceita, v.campo) == (False, "evidencias[1].itens")
    assert v.motivo == "item fora da pendência: A1 (a P-B cobre B1, B2, B3, B4)"


async def test_itens_numa_pendencia_sem_itens_rejeita(ctx, serv):
    ref = guardar(serv, pagina())
    evidencia = ev(ref).model_copy(update={"itens": ["A1"]})
    v = await validar(confirmado(evidencia, valor={"cnpj": "33000167000101"}), pend(ctx, "P-CNPJ"), ctx, serv)
    assert (v.aceita, v.campo) == (False, "evidencias[0].itens")
    assert v.motivo == "item fora da pendência: A1 (a P-CNPJ não cobre item da matriz)"


async def test_itens_vazio_ou_ausente_vale(ctx, serv):
    ref = guardar(serv, pagina())
    for itens in (None, []):
        evidencia = ev(ref).model_copy(update={"itens": itens})
        assert (await validar(confirmado(evidencia, valor=VALOR_B), pend(ctx, "P-B"), ctx, serv)).aceita


# --- esquema do valor ------------------------------------------------------------------------------------


async def test_valor_fora_do_esquema(ctx, serv):
    ref = guardar(serv, pagina())
    valor = {"pct_mes": "alto", "taxa_diaria": True, "garantido": True}
    v = await validar(confirmado(ev(ref), valor=valor), pend(ctx), ctx, serv)
    assert v.aceita is False
    assert v.campo == "valor"
    assert v.motivo.startswith("valor fora do esquema: ")
    assert "pct_mes" in v.motivo
    assert "\n" not in v.motivo  # resumido, sem o texto longo do pydantic


async def test_valor_com_campo_a_mais_ou_a_menos(ctx, serv):
    ref = guardar(serv, pagina())
    for valor in ({**VALOR_A1, "extra": 1}, {"pct_mes": 1.0}):
        v = await validar(confirmado(ev(ref), valor=valor), pend(ctx), ctx, serv)
        assert (v.aceita, v.campo) == (False, "valor")


async def test_corrigido_tambem_valida_o_valor(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref), valor={}, status="corrigido"), pend(ctx), ctx, serv)
    assert (v.aceita, v.campo) == (False, "valor")


async def test_valor_certo_aceita(ctx, serv):
    ref = guardar(serv, pagina())
    assert (await validar(confirmado(ev(ref)), pend(ctx), ctx, serv)).aceita


async def test_pendencia_desconhecida(ctx, serv):
    ref = guardar(serv, pagina())
    with pytest.raises(ValueError, match="pendência desconhecida: P-ZZ"):
        await validar(confirmado(ev(ref)), pend(ctx).model_copy(update={"id": "P-ZZ"}), ctx, serv)


# --- P-E: tipos, modificadores e índices de evidência ----------------------------------------------------


def valor_e(sinais=(("atraso_pagamento", 0),), modificadores=(("midia_de_massa", 0),)) -> dict:
    return {
        "sinais": [{"tipo": t, "data": "2025-05-01", "evidencia": i} for t, i in sinais],
        "modificadores": [{"id": m, "evidencia": i} for m, i in modificadores],
    }


async def test_pe_aceita_sinais_e_modificadores_da_matriz(ctx, serv):
    ref = guardar(serv, pagina())
    valor = valor_e(sinais=(("atraso_pagamento", 0), ("prova_aportes_novos", 1)))
    v = await validar(confirmado(ev(ref), ev(ref), valor=valor), pend(ctx, "P-E"), ctx, serv)
    assert v == Validacao(True, None, None, [])


async def test_pe_tipo_desconhecido(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref), valor=valor_e(sinais=(("x", 0),))), pend(ctx, "P-E"), ctx, serv)
    assert (v.aceita, v.motivo, v.campo) == (False, "tipo de sinal desconhecido: x", "valor")


async def test_pe_modificador_desconhecido(ctx, serv):
    ref = guardar(serv, pagina())
    # `retorno_alto` existe na matriz, mas sai da A1: a P-E não o responde
    for desconhecido in ("retorno_alto", "inventado"):
        valor = valor_e(modificadores=((desconhecido, 0),))
        v = await validar(confirmado(ev(ref), valor=valor), pend(ctx, "P-E"), ctx, serv)
        assert (v.aceita, v.motivo, v.campo) == (False, f"modificador desconhecido: {desconhecido}", "valor")


async def test_pe_indice_de_evidencia_invalido(ctx, serv):
    ref = guardar(serv, pagina())
    casos = (
        (valor_e(sinais=(("atraso_pagamento", 1),)), 1),
        (valor_e(modificadores=(("midia_de_massa", 3),)), 3),
    )
    for valor, indice in casos:
        v = await validar(confirmado(ev(ref), valor=valor), pend(ctx, "P-E"), ctx, serv)
        assert (v.aceita, v.motivo, v.campo) == (False, f"índice de evidência inválido: {indice}", "valor")


async def test_pe_indice_negativo_e_erro_de_esquema(ctx, serv):
    ref = guardar(serv, pagina())
    valor = valor_e(sinais=(("atraso_pagamento", -1),))
    v = await validar(confirmado(ev(ref), valor=valor), pend(ctx, "P-E"), ctx, serv)
    assert v.motivo.startswith("valor fora do esquema: ")


async def test_pe_sem_matriz_nao_valida_em_silencio(ctx, serv):
    serv.matriz = None
    ref = guardar(serv, pagina())
    with pytest.raises(ValueError, match="matriz"):
        await validar(confirmado(ev(ref), valor=valor_e()), pend(ctx, "P-E"), ctx, serv)


# --- nao_encontrado e inconclusivo -----------------------------------------------------------------------


async def test_nao_encontrado_sem_evidencias_aceita(ctx, serv):
    resposta = Resposta(status="nao_encontrado", onde_procurou=["rodapé", "RDAP"])
    assert await validar(resposta, pend(ctx), ctx, serv) == Validacao(True, None, None, [])


async def test_inconclusivo_sem_evidencias_aceita(ctx, serv):
    assert (await validar(Resposta(status="inconclusivo"), pend(ctx, "P-E"), ctx, serv)).aceita


async def test_nao_encontrado_com_evidencia_valida_a_evidencia(ctx, serv):
    ref = guardar(serv, pagina())
    base = {"status": "nao_encontrado", "onde_procurou": ["site"]}
    v = await validar(Resposta(**base, evidencias=[ev("rdap")]), pend(ctx), ctx, serv)
    assert (v.motivo, v.campo) == (MOTIVO_FONTE_INVALIDA, "evidencias[0].fonte")
    v = await validar(Resposta(**base, evidencias=[ev(ref, "frase que não existe")]), pend(ctx), ctx, serv)
    assert (v.motivo, v.campo) == ("trecho não encontrado na fonte", "evidencias[0].trecho")
    assert (await validar(Resposta(**base, evidencias=[ev(ref)]), pend(ctx), ctx, serv)).aceita


# --- ordem: esquema, fonte, trecho, data -----------------------------------------------------------------


async def test_o_esquema_vem_antes_da_fonte(ctx, serv):
    valor = {"pct_mes": "alto", "taxa_diaria": True, "garantido": True}
    v = await validar(confirmado(ev("cnpj"), valor=valor), pend(ctx), ctx, serv)
    assert v.campo == "valor"


async def test_a_fonte_de_toda_evidencia_vem_antes_do_trecho(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, "frase que não existe"), ev("rdap")), pend(ctx), ctx, serv)
    assert (v.motivo, v.campo) == (MOTIVO_FONTE_INVALIDA, "evidencias[1].fonte")


async def test_o_trecho_de_toda_evidencia_vem_antes_da_data(ctx_retro, serv):
    ref = guardar(serv, pagina())
    primeira = ev(ref, data_fonte=date(2026, 1, 1))  # data posterior, mas o trecho certo
    segunda = ev(ref, "frase que não existe", date(2025, 1, 1))
    v = await validar(confirmado(primeira, segunda), pend(ctx_retro), ctx_retro, serv)
    assert (v.motivo, v.campo) == ("trecho não encontrado na fonte", "evidencias[1].trecho")


# --- SSRF e modo_contato=nenhum --------------------------------------------------------------------------

URLS_RECUSADAS = [
    "http://localhost/painel",
    "http://LOCALHOST:8080/",
    "http://localhost./x",
    "http://api.localhost/x",
    "http://127.0.0.1/x",
    "http://127.1/x",
    "http://2130706433/x",
    "http://0x7f000001/x",
    "http://0/x",
    "http://10.1.2.3/x",
    "http://172.16.0.9/x",
    "http://192.168.0.10:8080/x",
    "http://169.254.169.254/latest/meta-data/",
    "http://0.0.0.0/x",
    "http://224.0.0.1/x",
    "http://240.0.0.1/x",
    "http://100.64.0.1/x",
    "http://100.127.255.254/x",
    "http://[::1]/x",
    "http://[::]/x",
    "http://[fe80::1]/x",
    "http://[fc00::1]/x",
    "http://[ff02::1]/x",
    "http://[::ffff:127.0.0.1]/x",
    "http://[::ffff:10.0.0.1]/x",
    "http:///x",
]


@pytest.mark.parametrize("url", URLS_RECUSADAS)
async def test_arquivar_fonte_recusa_destino_interno(ctx, serv, url, respx_mock):
    # nenhuma rota registrada: se a recusa não vier antes da rede, o respx derruba o teste
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(url, ctx, serv)
    assert erro.value.permanente is True
    assert erro.value.mensagem.startswith("fonte recusada: ")
    assert respx_mock.calls.call_count == 0


async def test_arquivar_fonte_recusa_esquema_que_nao_e_http(ctx, serv):
    for url in ("ftp://exemplo.org/a", "file:///etc/passwd", "javascript:alert(1)", "exemplo.org/a"):
        with pytest.raises(ErroNo, match=r"^fonte recusada: "):
            await arquivar_fonte(url, ctx, serv)


async def test_validar_converte_a_recusa_em_rejeicao(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref), ev("http://169.254.169.254/latest/meta-data/")), pend(ctx), ctx, serv)
    assert v.aceita is False
    assert v.campo == "evidencias[1].fonte"
    assert v.motivo.startswith("fonte recusada: ")


async def test_ip_publico_e_permitido(ctx, serv, respx_mock, dns):
    dns[IP_PUBLICO] = AssertionError("IP literal não se resolve")
    servir(respx_mock, f"http://{IP_PUBLICO}/pagina", pagina())
    fonte = await arquivar_fonte(f"http://{IP_PUBLICO}/pagina", ctx, serv)
    assert "Rendimento de 1,5% ao dia" in fonte.texto


async def test_host_punycode_invalido_e_recusado(ctx, serv, respx_mock):
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte("https://xn--a-----.example.org/x", ctx, serv)
    assert erro.value.mensagem == MOTIVO_HOST
    v = await validar(confirmado(ev("https://xn--a-----.example.org/x")), pend(ctx), ctx, serv)
    assert (v.aceita, v.campo) == (False, "evidencias[0].fonte")


@pytest.mark.parametrize(
    "url",
    [
        "https://web.archive.org/save/https://outro.example.org/",
        "https://web.archive.org//save/https://outro.example.org/",
        "https://WEB.ARCHIVE.ORG/save",
        "https://exemplo-com-br.translate.goog/pagina?_x_tr_sl=pt",
        "https://translate.goog/x",
    ],
)
async def test_servico_que_visita_o_alvo_e_recusado(ctx, serv, url, respx_mock):
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(url, ctx, serv)
    assert (erro.value.mensagem, erro.value.permanente) == ("fonte recusada: serviço que visita o alvo", True)
    assert respx_mock.calls.call_count == 0


async def test_wayback_de_snapshot_e_permitido(ctx, serv, respx_mock):
    url = "https://web.archive.org/web/20250101000000/http://outro.example.org/termos"
    servir(respx_mock, url, pagina())
    assert (await validar(confirmado(ev(url)), pend(ctx), ctx, serv)).aceita


@pytest.mark.parametrize(
    "enderecos",
    [
        ["10.0.0.5"],
        ["127.0.0.1"],
        [IP_PUBLICO, "192.168.1.9"],
        ["100.64.0.9"],
        ["::1"],
        ["fe80::1%eth0"],
        ["::ffff:10.0.0.1"],
    ],
)
async def test_nome_que_resolve_para_ip_interno_e_recusado(ctx, serv, dns, respx_mock, enderecos):
    dns["127.0.0.1.nip.io"] = enderecos
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte("https://127.0.0.1.nip.io/pagina", ctx, serv)
    assert erro.value.permanente is True
    assert erro.value.mensagem.startswith("fonte recusada: ")
    assert respx_mock.calls.call_count == 0
    v = await validar(confirmado(ev("https://127.0.0.1.nip.io/pagina")), pend(ctx), ctx, serv)
    assert (v.aceita, v.campo) == (False, "evidencias[0].fonte")


async def test_nome_que_resolve_para_ip_publico_e_permitido(ctx, serv, dns, respx_mock):
    dns["noticias.example.org"] = [IP_PUBLICO, "2606:2800:220:1:248:1893:25c8:1946"]
    servir(respx_mock, URL, pagina())
    assert (await arquivar_fonte(URL, ctx, serv)).texto


@pytest.mark.parametrize("codigo", sorted({socket.EAI_NONAME, getattr(socket, "EAI_NODATA", socket.EAI_NONAME)}))
async def test_dominio_inexistente_rejeita(ctx, serv, dns, respx_mock, codigo):
    dns["noticias.example.org"] = socket.gaierror(codigo, "Name or service not known")
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(URL, ctx, serv)
    assert (erro.value.mensagem, erro.value.permanente) == (MOTIVO_NXDOMAIN, True)
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(False, MOTIVO_NXDOMAIN, "evidencias[0].fonte", [])
    assert respx_mock.calls.call_count == 0


@pytest.mark.parametrize(
    "erro",
    [socket.gaierror(socket.EAI_AGAIN, "Temporary failure"), TimeoutError("lento"), OSError("sem rede")],
)
async def test_outro_erro_de_dns_segue_para_a_rede(ctx, serv, dns, respx_mock, erro):
    # quem falha é a Rede, com ErroRede: na `validar` vira trecho_nao_conferido
    dns["noticias.example.org"] = erro
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("sem rota"))
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


@pytest.mark.parametrize(
    "host", ["a..example.org", "a" * 64 + ".example.org", ("a" * 63 + ".") * 4 + "org", ".example.org"]
)
async def test_host_com_rotulo_vazio_ou_longo_demais_e_recusado(ctx, serv, respx_mock, host):
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(f"https://{host}/x", ctx, serv)
    assert (erro.value.mensagem, erro.value.permanente) == (MOTIVO_HOST, True)
    v = await validar(confirmado(ev(f"https://{host}/x")), pend(ctx), ctx, serv)
    assert v == Validacao(False, MOTIVO_HOST, "evidencias[0].fonte", [])
    assert respx_mock.calls.call_count == 0


@pytest.mark.parametrize(
    "erro",
    [UnicodeEncodeError("idna", "x", 0, 1, "label empty"), UnicodeError("label too long"), ValueError("embedded null")],
)
async def test_erro_de_codificacao_do_dns_vira_host_invalido(ctx, serv, dns, respx_mock, erro):
    dns["estranho.example.org"] = erro
    v = await validar(confirmado(ev("https://estranho.example.org/x")), pend(ctx), ctx, serv)
    assert v == Validacao(False, MOTIVO_HOST, "evidencias[0].fonte", [])
    assert respx_mock.calls.call_count == 0


@pytest.mark.parametrize("destino", ["https://a..example.org/x", "https://estranho.example.org/x"])
async def test_redirect_para_host_invalido_e_recusado(ctx, serv, dns, respx_mock, destino):
    # o redirect vem de um servidor público: o terceiro é que dispararia a exceção
    dns["estranho.example.org"] = UnicodeEncodeError("idna", "x", 0, 1, "label empty")
    respx_mock.get("https://curto.example.org/a").mock(return_value=httpx.Response(302, headers={"location": destino}))
    v = await validar(confirmado(ev("https://curto.example.org/a")), pend(ctx), ctx, serv)
    assert v == Validacao(False, MOTIVO_HOST, "evidencias[0].fonte", [])


async def test_host_invalido_e_recusado_mesmo_com_proxy(tmp_path, respx_mock):
    config = Config(rede=RedeConfig(proxy="http://127.0.0.1:3128", limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        s = Servicos(config=config, rede=rede, custodia=Custodia(tmp_path), matriz=MATRIZ_SPEC)
        with pytest.raises(ErroNo) as erro:
            await arquivar_fonte("https://a..example.org/x", contexto(tmp_path), s)
        assert erro.value.mensagem == MOTIVO_HOST
    finally:
        await rede.fechar()


async def test_redirect_para_nome_que_resolve_para_ip_interno_e_recusado(ctx, serv, dns, respx_mock):
    dns["interno.example.org"] = "10.9.8.7"
    respx_mock.get("https://curto.example.org/a").mock(
        return_value=httpx.Response(302, headers={"location": "https://interno.example.org/admin"})
    )
    with pytest.raises(ErroNo, match=r"^fonte recusada: "):
        await arquivar_fonte("https://curto.example.org/a", ctx, serv)


async def test_com_proxy_configurado_o_dns_fica_com_o_proxy(tmp_path, dns, respx_mock):
    dns["noticias.example.org"] = AssertionError("com proxy quem resolve é o proxy")
    config = Config(rede=RedeConfig(proxy="http://127.0.0.1:3128", limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        s = Servicos(config=config, rede=rede, custodia=Custodia(tmp_path), matriz=MATRIZ_SPEC)
        servir(respx_mock, URL, pagina())
        assert (await arquivar_fonte(URL, contexto(tmp_path), s)).texto
    finally:
        await rede.fechar()


async def test_redirect_para_destino_interno_e_recusado(ctx, serv, respx_mock):
    respx_mock.get("https://curto.example.org/a").mock(
        return_value=httpx.Response(302, headers={"location": "http://127.0.0.1:8080/admin"})
    )
    v = await validar(confirmado(ev("https://curto.example.org/a")), pend(ctx), ctx, serv)
    assert (v.aceita, v.campo) == (False, "evidencias[0].fonte")
    assert v.motivo.startswith("fonte recusada: ")


async def test_redirect_para_destino_publico_e_seguido(ctx, serv, respx_mock):
    respx_mock.get("https://curto.example.org/a").mock(
        return_value=httpx.Response(301, headers={"location": "/b"})
    )
    respx_mock.get("https://curto.example.org/b").mock(
        return_value=httpx.Response(302, headers={"location": "https://destino.example.org/materia"})
    )
    servir(respx_mock, "https://destino.example.org/materia", pagina())
    fonte = await arquivar_fonte("https://curto.example.org/a", ctx, serv)
    assert "Rendimento de 1,5% ao dia" in fonte.texto
    registros = [json.loads(linha) for linha in (ctx.pasta / "custodia.log").read_text(encoding="utf-8").splitlines()]
    assert [(r["tipo"], r["origem"]) for r in registros] == [("fonte", "https://curto.example.org/a")]


async def test_redirect_em_laco_nao_prende(ctx, serv, respx_mock):
    respx_mock.get("https://laco.example.org/a").mock(
        return_value=httpx.Response(302, headers={"location": "https://laco.example.org/a"})
    )
    v = await validar(confirmado(ev("https://laco.example.org/a")), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


@pytest.mark.parametrize(
    "url", ["https://exemplo.com.br/termos", "https://app.Exemplo.com.br:8443/termos", "http://exemplo.com.br./"]
)
async def test_modo_nenhum_recusa_o_dominio_do_alvo(ctx_nenhum, serv, url):
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(url, ctx_nenhum, serv)
    assert erro.value.mensagem == MOTIVO_NENHUM
    assert erro.value.permanente is True
    v = await validar(confirmado(ev(url)), pend(ctx_nenhum), ctx_nenhum, serv)
    assert v == Validacao(False, MOTIVO_NENHUM, "evidencias[0].fonte", [])


async def test_modo_nenhum_recusa_redirect_para_o_alvo(ctx_nenhum, serv, respx_mock):
    respx_mock.get("https://curto.example.org/a").mock(
        return_value=httpx.Response(302, headers={"location": "https://www.exemplo.com.br/"})
    )
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte("https://curto.example.org/a", ctx_nenhum, serv)
    assert erro.value.mensagem == MOTIVO_NENHUM


async def test_modo_nenhum_permite_o_wayback(ctx_nenhum, serv, respx_mock):
    url = "https://web.archive.org/web/20250101000000/http://exemplo.com.br/termos"
    servir(respx_mock, url, pagina())
    v = await validar(confirmado(ev(url)), pend(ctx_nenhum), ctx_nenhum, serv)
    assert v.aceita


@pytest.mark.parametrize(
    "url", ["https://exemplo.com.br/termos", "https://app.Exemplo.com.br:8443/termos", "http://exemplo.com.br./"]
)
async def test_qualquer_modo_recusa_o_dominio_do_alvo(ctx, serv, url, respx_mock):
    # só o nó captura toca o alvo: nem no modo captura a fonte pode ser uma página dele
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(url, ctx, serv)
    assert (erro.value.mensagem, erro.value.permanente) == (MOTIVO_ALVO, True)
    v = await validar(confirmado(ev(url)), pend(ctx), ctx, serv)
    assert v == Validacao(False, MOTIVO_ALVO, "evidencias[0].fonte", [])
    assert respx_mock.calls.call_count == 0


async def test_redirect_para_o_alvo_e_recusado_no_modo_captura(ctx, serv, respx_mock):
    respx_mock.get("https://curto.example.org/a").mock(
        return_value=httpx.Response(302, headers={"location": "https://exemplo.com.br/"})
    )
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte("https://curto.example.org/a", ctx, serv)
    assert erro.value.mensagem == MOTIVO_ALVO


async def test_modo_cego_recusa_o_alvo_com_mensagem_neutra(tmp_path, serv):
    for modo in ("captura", "nenhum"):
        ctx = contexto(tmp_path, modo_contato=modo).model_copy(update={"modo_cego": True})
        v = await validar(confirmado(ev("https://app.exemplo.com.br/termos")), pend(ctx), ctx, serv)
        assert v == Validacao(False, MOTIVO_ALVO_CEGO, "evidencias[0].fonte", [])


@pytest.mark.parametrize(
    "url",
    ["https://meuexemplo.com.br/", "https://exemplo.com.br.outro.org/", "https://exemplo.org/", "https://exemplo.com/"],
)
async def test_dominio_parecido_com_o_alvo_e_permitido(ctx, serv, respx_mock, url):
    servir(respx_mock, url, pagina())
    assert (await arquivar_fonte(url, ctx, serv)).texto


ALVO_IDN = "investimentoseguro-ação.com.br"
ALVO_PUNYCODE = ALVO_IDN.encode("idna").decode("ascii")


@pytest.mark.parametrize("modo", ["captura", "nenhum"])
@pytest.mark.parametrize("host", [ALVO_IDN, ALVO_PUNYCODE, "www." + ALVO_IDN, "app." + ALVO_PUNYCODE, ALVO_IDN.upper()])
async def test_alvo_idn_e_recusado_nas_duas_grafias(tmp_path, serv, respx_mock, modo, host):
    ctx = contexto(tmp_path, modo_contato=modo, alvo=ALVO_PUNYCODE)
    esperado = MOTIVO_ALVO if modo == "captura" else MOTIVO_NENHUM
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(f"https://{host}/termos", ctx, serv)
    assert erro.value.mensagem == esperado
    v = await validar(confirmado(ev(f"https://{host}/termos")), pend(ctx), ctx, serv)
    assert v == Validacao(False, esperado, "evidencias[0].fonte", [])
    assert respx_mock.calls.call_count == 0


# --- destino depois de um redirect (melhorias do aceite) --------------------------------------------------

DESTINO = "phinvestimentos.com"


@pytest.mark.parametrize(
    "url", [f"https://{DESTINO}/login", f"https://app.{DESTINO}:8443/termos", f"http://WWW.{DESTINO.upper()}./"]
)
async def test_dominio_do_destino_e_recusado_como_o_do_alvo(ctx, serv, respx_mock, url):
    # o destino do redirect é o site analisado: só a captura o visita
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(url, ctx, serv, dominio_destino=DESTINO)
    assert (erro.value.mensagem, erro.value.permanente) == (MOTIVO_ALVO, True)
    v = await validar(confirmado(ev(url)), pend(ctx), ctx, serv, dominio_destino=DESTINO)
    assert v == Validacao(False, MOTIVO_ALVO, "evidencias[0].fonte", [])
    assert respx_mock.calls.call_count == 0


async def test_com_destino_o_alvo_continua_recusado(ctx, serv, respx_mock):
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte("https://exemplo.com.br/termos", ctx, serv, dominio_destino=DESTINO)
    assert erro.value.mensagem == MOTIVO_ALVO
    assert respx_mock.calls.call_count == 0


async def test_redirect_para_o_destino_e_recusado(ctx, serv, respx_mock):
    respx_mock.get("https://curto.example.org/a").mock(
        return_value=httpx.Response(302, headers={"location": f"https://www.{DESTINO}/login"})
    )
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte("https://curto.example.org/a", ctx, serv, dominio_destino=DESTINO)
    assert erro.value.mensagem == MOTIVO_ALVO
    v = await validar(confirmado(ev("https://curto.example.org/a")), pend(ctx), ctx, serv, dominio_destino=DESTINO)
    assert v == Validacao(False, MOTIVO_ALVO, "evidencias[0].fonte", [])


async def test_destino_recusado_com_a_mensagem_do_modo(tmp_path, serv):
    url = f"https://{DESTINO}/login"
    cego = contexto(tmp_path).model_copy(update={"modo_cego": True})
    nenhum = contexto(tmp_path, modo_contato="nenhum")
    for ctx_, esperado in ((cego, MOTIVO_ALVO_CEGO), (nenhum, MOTIVO_NENHUM)):
        v = await validar(confirmado(ev(url)), pend(ctx_), ctx_, serv, dominio_destino=DESTINO)
        assert v == Validacao(False, esperado, "evidencias[0].fonte", [])


@pytest.mark.parametrize("dominio_destino", [None, "", "  "])
async def test_sem_destino_o_dominio_dele_e_fonte_comum(ctx, serv, respx_mock, dominio_destino):
    servir(respx_mock, f"https://{DESTINO}/noticia", pagina())
    assert (await arquivar_fonte(f"https://{DESTINO}/noticia", ctx, serv, dominio_destino=dominio_destino)).texto


async def test_dominio_parecido_com_o_destino_e_permitido(ctx, serv, respx_mock):
    for url in (f"https://meu{DESTINO}/", f"https://{DESTINO}.outro.org/"):
        servir(respx_mock, url, pagina())
        assert (await arquivar_fonte(url, ctx, serv, dominio_destino=DESTINO)).texto


@pytest.mark.parametrize("dado", [ALVO_IDN, ALVO_PUNYCODE])
@pytest.mark.parametrize("host", [ALVO_IDN, ALVO_PUNYCODE, "www." + ALVO_PUNYCODE])
async def test_destino_idn_e_recusado_nas_duas_grafias(ctx, serv, respx_mock, dado, host):
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(f"https://{host}/termos", ctx, serv, dominio_destino=dado)
    assert erro.value.mensagem == MOTIVO_ALVO
    assert respx_mock.calls.call_count == 0


# --- arquivar_fonte --------------------------------------------------------------------------------------


async def test_arquivar_fonte_guarda_na_custodia_e_devolve_o_texto(ctx, serv, respx_mock):
    servir(respx_mock, URL, pagina('<meta property="article:published_time" content="2025-03-01">'))
    fonte = await arquivar_fonte(URL, ctx, serv)
    assert isinstance(fonte, FonteArquivada)
    assert fonte.data_publicacao == date(2025, 3, 1)
    assert "Rendimento de 1,5% ao dia, “garantido” pela empresa." in fonte.texto
    assert "texto só no script" not in fonte.texto
    caminho = serv.custodia.caminho(fonte.ref)
    assert caminho.suffix == ".html"
    assert "texto só no script" in caminho.read_text(encoding="utf-8")  # o artefato é a página inteira
    registro = json.loads((ctx.pasta / "custodia.log").read_text(encoding="utf-8").splitlines()[-1])
    assert (registro["tipo"], registro["origem"], f"sha256:{registro['sha256']}") == ("fonte", URL, fonte.ref)


async def test_arquivar_fonte_usa_o_user_agent_de_navegador(ctx, serv, respx_mock):
    rota = servir(respx_mock, URL, pagina())
    await arquivar_fonte(URL, ctx, serv)
    assert rota.calls.last.request.headers["user-agent"] == serv.config.rede.ua_navegador


@pytest.mark.parametrize(
    ("tipo", "corpo", "ext", "texto"),
    [
        ("text/plain; charset=utf-8", "Saque suspenso até".encode(), ".txt", "Saque suspenso até"),
        ("application/json", '{"aviso": "ok"}'.encode(), ".json", '{"aviso": "ok"}'),
        ("application/ld+json", b"{}", ".json", "{}"),
        ("text/html; charset=iso-8859-1", "<p>Promoção</p>".encode("iso-8859-1"), ".html", "Promoção"),
        ("image/png", PNG, ".png", ""),
        ("image/webp", b"RIFF....WEBP", ".webp", ""),
        ("image/avif", b"....ftypavif", ".img", ""),
        ("application/pdf", b"%PDF-1.4", ".pdf", None),
        ("application/octet-stream", b"%PDF-1.7\n%\xe2\xe3", ".pdf", None),  # a assinatura vale mais que o tipo
        ("text/html", b"%PDF-1.7\n%\xe2\xe3", ".pdf", None),
        (None, b"%PDF-1.4", ".pdf", None),
        ("application/octet-stream", b"\x00\x01\x02", ".bin", None),
        ("application/x-desconhecido", b"\xff\xfe\x00\x00", ".bin", None),
        ("application/zip", b"PK\x03\x04\x14\x00\x00\x00", ".bin", None),
        (None, b"<p>sem content-type</p>", ".html", "sem content-type"),
        ("application/octet-stream", b"<p>sem tipo</p>", ".html", "sem tipo"),
        (None, "\ufeff \n<html><body>ola mundo</body></html>".encode(), ".html", "ola mundo"),
        ("application/octet-stream", "só texto simples".encode(), ".txt", "só texto simples"),
        (None, "texto em latin-1: ação".encode("iso-8859-1"), ".bin", None),
        ("application/octet-stream", b"texto com \x00 nul", ".bin", None),
        ("text/csv", b"a,b", ".txt", "a,b"),
        ("image/svg+xml", b"<svg/>", ".xml", "<svg/>"),
    ],
)
async def test_arquivar_fonte_extensao_e_texto_pelo_content_type(ctx, serv, respx_mock, tipo, corpo, ext, texto):
    headers = {"content-type": tipo} if tipo else {}
    respx_mock.get(URL).mock(return_value=httpx.Response(200, content=corpo, headers=headers))
    fonte = await arquivar_fonte(URL, ctx, serv)
    assert serv.custodia.caminho(fonte.ref).suffix == ext
    if texto is not None:
        assert fonte.texto == texto
    assert fonte.data_publicacao is None


@pytest.mark.parametrize(
    ("cabeca", "esperada"),
    [
        ('<meta property="article:published_time" content="2025-03-01T10:00:00-03:00">', date(2025, 3, 1)),
        ('<meta name="date" content="2024-12-31">', date(2024, 12, 31)),
        ('<meta name="DATE" content=" 2024-11-30 10:00 ">', date(2024, 11, 30)),
        (
            '<script type="application/ld+json">{"@type":"Article","datePublished":"2023-05-06T08:00:00Z"}</script>',
            date(2023, 5, 6),
        ),
        (
            '<script type="application/ld+json">{"@graph":[{"@type":"WebSite"},'
            '{"@type":"Article","datePublished":"2022-02-03"}]}</script>',
            date(2022, 2, 3),
        ),
        (
            '<script type="application/ld+json">[{"@type":"WebSite"},{"datePublished":"2022-02-04"}]</script>',
            date(2022, 2, 4),
        ),
        ('<time datetime="2021-07-08T10:00">8 de julho</time>', date(2021, 7, 8)),
        ("", None),
        ('<meta property="article:published_time" content="ontem">', None),
        ('<meta property="article:published_time" content="2025-13-45">', None),
        ('<script type="application/ld+json">{"datePublished": </script>', None),
        ('<script>var datePublished = "2020-01-01"</script>', None),
        ('<time datetime="amanhã">amanhã</time>', None),
    ],
)
async def test_arquivar_fonte_detecta_a_data_de_publicacao(ctx, serv, respx_mock, cabeca, esperada):
    servir(respx_mock, URL, pagina(cabeca))
    assert (await arquivar_fonte(URL, ctx, serv)).data_publicacao == esperada


async def test_data_de_publicacao_prioridade_entre_as_fontes(ctx, serv, respx_mock):
    time = '<time datetime="2021-01-04">x</time>'
    json_ld = '<script type="application/ld+json">{"datePublished":"2021-01-03"}</script>'
    meta_date = '<meta name="date" content="2021-01-02">'
    article = '<meta property="article:published_time" content="2021-01-01">'
    esperadas = [
        (article + meta_date + json_ld + time, date(2021, 1, 1)),
        (meta_date + json_ld + time, date(2021, 1, 2)),
        (json_ld + time, date(2021, 1, 3)),
        (time, date(2021, 1, 4)),
    ]
    for cabeca, esperada in esperadas:
        respx_mock.get(URL).mock(return_value=httpx.Response(200, html=pagina(cabeca)))
        assert (await arquivar_fonte(URL, ctx, serv)).data_publicacao == esperada


async def test_data_de_publicacao_com_json_ld_aninhado_fundo_nao_derruba(ctx, serv, respx_mock):
    fundo = "[" * 100_000 + "]" * 100_000
    servir(respx_mock, URL, pagina(f'<script type="application/ld+json">{fundo}</script>'))
    assert (await arquivar_fonte(URL, ctx, serv)).data_publicacao is None


async def test_arquivar_fonte_nao_usa_o_cache_da_rede(ctx, serv, respx_mock):
    # a fonte arquivada precisa ser a página de agora, não a que a Rede guardou antes
    rota = servir(respx_mock, URL, pagina())
    await arquivar_fonte(URL, ctx, serv)
    await arquivar_fonte(URL, ctx, serv)
    assert rota.call_count == 2


# --- teto de tamanho --------------------------------------------------------------------------------------


async def test_corpo_acima_de_10_mb_nao_e_guardado_e_fica_sem_conferir(ctx, serv, respx_mock):
    grande = httpx.Response(200, content=b"x" * 10_000_001, headers={"content-type": "text/plain"})
    respx_mock.get(URL).mock(return_value=grande)
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)
    assert not (ctx.pasta / "custodia.log").exists()
    with pytest.raises(ErroRede, match="10 MB"):
        await arquivar_fonte(URL, ctx, serv)


async def test_corpo_de_exatos_10_mb_e_guardado(ctx, serv, respx_mock):
    corpo = httpx.Response(200, content=b"x" * 10_000_000, headers={"content-type": "text/plain"})
    respx_mock.get(URL).mock(return_value=corpo)
    fonte = await arquivar_fonte(URL, ctx, serv)
    assert len(serv.custodia.ler(fonte.ref)) == 10_000_000


# --- modo cego: o trecho pode citar os marcadores ---------------------------------------------------------

PAGINA_CEGA = "<p>Exemplo Invest paga 1% ao mês aos clientes, com cadastro em exemplo.com.br</p>"
MASCARA = {"Exemplo Invest": "[EMPRESA]", "exemplo.com.br": "[ALVO]"}


async def test_modo_cego_aceita_o_trecho_com_marcador(ctx_cego, serv):
    ref = guardar(serv, PAGINA_CEGA)
    for trecho in ("[EMPRESA] paga 1% ao mês", "[empresa] PAGA 1% ao mes", "com cadastro em [ALVO]"):
        v = await validar(confirmado(ev(ref, trecho)), pend(ctx_cego), ctx_cego, serv, MASCARA)
        assert v == Validacao(True, None, None, []), trecho


async def test_modo_cego_continua_aceitando_o_texto_sem_mascara(ctx_cego, serv):
    ref = guardar(serv, PAGINA_CEGA)
    v = await validar(confirmado(ev(ref, "Exemplo Invest paga 1% ao mês")), pend(ctx_cego), ctx_cego, serv, MASCARA)
    assert v.aceita


async def test_modo_cego_marcador_que_nao_esta_na_fonte_rejeita(ctx_cego, serv):
    ref = guardar(serv, PAGINA_CEGA)
    for trecho in ("[PESSOA_1] paga 1% ao mês", "[ALVO] paga 1% ao mês"):
        v = await validar(confirmado(ev(ref, trecho)), pend(ctx_cego), ctx_cego, serv, MASCARA)
        assert (v.aceita, v.motivo, v.campo) == (False, "trecho não encontrado na fonte", "evidencias[0].trecho")


async def test_marcador_sem_mascara_ou_fora_do_modo_cego_rejeita(ctx, ctx_cego, serv):
    ref = guardar(serv, PAGINA_CEGA)
    resposta = confirmado(ev(ref, "[EMPRESA] paga 1% ao mês"))
    assert not (await validar(resposta, pend(ctx_cego), ctx_cego, serv)).aceita  # sem máscara
    assert not (await validar(resposta, pend(ctx), ctx, serv, MASCARA)).aceita  # execução aberta


async def test_modo_cego_com_url(ctx_cego, serv, respx_mock):
    servir(respx_mock, URL, PAGINA_CEGA)
    v = await validar(confirmado(ev(URL, "[EMPRESA] paga 1% ao mês")), pend(ctx_cego), ctx_cego, serv, MASCARA)
    assert v.aceita


# --- PDF --------------------------------------------------------------------------------------------------

PDF_509 = (FIXTURES_CVM / "deli509.pdf").read_bytes()


async def test_pdf_confere_o_trecho_sem_os_espacos(ctx, serv):
    # a extração parte palavras ("COSTA F ERREIRA"): o trecho certo só casa quando os espaços saem dos dois lados
    trecho = "Frederick Domingos Costa Ferreira, CPF nº 636.126.311-87"
    assert normalizar(trecho) not in normalizar(texto_de_pdf(PDF_509))
    ref = guardar(serv, PDF_509, "pdf")
    v = await validar(confirmado(ev(ref, trecho)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, [])


async def test_pdf_com_trecho_ausente_rejeita(ctx, serv):
    ref = guardar(serv, PDF_509, "pdf")
    v = await validar(confirmado(ev(ref, "Fidelitas Investimentos pagou 10% ao dia")), pend(ctx), ctx, serv)
    assert (v.aceita, v.motivo, v.campo) == (False, "trecho não encontrado na fonte", "evidencias[0].trecho")


async def test_pdf_sem_texto_extraivel_aceita_com_marca(ctx, serv):
    ref = guardar(serv, (FIXTURES_CVM / "sem_texto.pdf").read_bytes(), "pdf")
    v = await validar(confirmado(ev(ref, "qualquer trecho que o pdf tenha")), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, ["trecho_nao_conferido", "trecho_nao_conferido:evidencias[0]"])


async def test_pdf_que_nao_e_pdf_aceita_com_marca(ctx, serv):
    ref = guardar(serv, b"isto nao e um pdf de verdade", "pdf")
    v = await validar(confirmado(ev(ref, "qualquer trecho que o pdf tenha")), pend(ctx), ctx, serv)
    assert v.marcas == ["trecho_nao_conferido", "trecho_nao_conferido:evidencias[0]"]


@pytest.mark.parametrize("tipo", ["application/pdf", "application/octet-stream", None])
async def test_url_de_pdf(ctx, serv, respx_mock, tipo):
    headers = {"content-type": tipo} if tipo else {}
    respx_mock.get("https://cvm.example.org/deli509.pdf").mock(
        return_value=httpx.Response(200, content=PDF_509, headers=headers)
    )
    fonte = await arquivar_fonte("https://cvm.example.org/deli509.pdf", ctx, serv)
    assert serv.custodia.caminho(fonte.ref).suffix == ".pdf"
    assert "DELIBERAÇÃO CVM" in fonte.texto
    trecho = "Frederick Domingos Costa Ferreira, CPF nº 636.126.311-87"
    v = await validar(confirmado(ev("https://cvm.example.org/deli509.pdf", trecho)), pend(ctx), ctx, serv)
    assert v.aceita


async def test_pdf_no_modo_cego(ctx_cego, serv):
    ref = guardar(serv, PDF_509, "pdf")
    mascara = {"FIDELITAS INVESTIMENTOS LTDA": "[EMPRESA]"}
    trecho = "[EMPRESA]., CNPJ nº 06.151.776/0001- 99"
    v = await validar(confirmado(ev(ref, trecho)), pend(ctx_cego), ctx_cego, serv, mascara)
    assert v.aceita


async def test_html_sem_content_type_com_charset_no_meta(ctx, serv, respx_mock):
    corpo = '<html><head><meta charset="iso-8859-1"></head><body><p>Promoção garantida hoje</p></body></html>'
    headers = {"content-type": "application/octet-stream"}
    respx_mock.get(URL).mock(return_value=httpx.Response(200, content=corpo.encode("iso-8859-1"), headers=headers))
    assert (await arquivar_fonte(URL, ctx, serv)).texto == "Promoção garantida hoje"


@pytest.mark.parametrize("tipo", [None, "application/octet-stream", "application/x-desconhecido"])
async def test_html_sem_tipo_e_conferido_e_o_trecho_fabricado_rejeitado(ctx, serv, respx_mock, tipo):
    headers = {"content-type": tipo} if tipo else {}
    respx_mock.get(URL).mock(return_value=httpx.Response(200, content=pagina().encode(), headers=headers))
    assert await validar(confirmado(ev(URL)), pend(ctx), ctx, serv) == Validacao(True, None, None, [])
    falso = await validar(confirmado(ev(URL, "Rendimento de 9,9% ao dia")), pend(ctx), ctx, serv)
    assert (falso.aceita, falso.motivo) == (False, "trecho não encontrado na fonte")


async def test_binario_sem_tipo_aceita_sem_conferir(ctx, serv, respx_mock):
    respx_mock.get(URL).mock(return_value=httpx.Response(200, content=b"\x00\x01\x02\x03"))
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, NAO_CONFERIDA_0)


# --- PDF: o mínimo é medido sem espaços --------------------------------------------------------------------


async def test_pdf_trecho_curto_demais_sem_os_espacos(ctx, serv):
    ref = guardar(serv, PDF_509, "pdf")
    for trecho in ("d e l i b e r a", "d e l i b e r a c a o", "c v m  n o  5 0 9"):
        v = await validar(confirmado(ev(ref, trecho)), pend(ctx), ctx, serv)
        assert v == Validacao(False, MOTIVO_CURTO, "evidencias[0].trecho", []), trecho
    assert (await validar(confirmado(ev(ref, "DELIBERAÇÃO CVM")), pend(ctx), ctx, serv)).aceita


async def test_html_com_espacos_no_trecho_curto_continua_valendo_pelo_tamanho_normal(ctx, serv):
    # só o PDF mede sem espaços: aqui "d e l i b e r a" tem 15 caracteres e 8 palavras
    ref = guardar(serv, "<p>texto d e l i b e r a texto</p>")
    assert (await validar(confirmado(ev(ref, "d e l i b e r a")), pend(ctx), ctx, serv)).aceita


# --- marcadores não contam para o mínimo ------------------------------------------------------------------


@pytest.mark.parametrize(
    "trecho",
    ["[EMPRESA] [ALVO]", "[CNPJ] [PESSOA_1]", "[EMPRESA] paga", "[empresa]  [alvo] [pessoa_12]", "[EMPRESA] [ALVO] x"],
)
async def test_marcadores_nao_contam_para_o_minimo(ctx, ctx_cego, serv, trecho):
    ref = guardar(serv, PAGINA_CEGA)
    for contexto_ in (ctx_cego, ctx):
        v = await validar(confirmado(ev(ref, trecho)), pend(contexto_), contexto_, serv, MASCARA)
        assert v == Validacao(False, MOTIVO_CURTO, "evidencias[0].trecho", []), trecho


async def test_marcador_mais_texto_suficiente_vale(ctx_cego, serv):
    ref = guardar(serv, PAGINA_CEGA)
    v = await validar(confirmado(ev(ref, "[EMPRESA] paga 1% ao mês")), pend(ctx_cego), ctx_cego, serv, MASCARA)
    assert v.aceita


async def test_mascarar_roda_fora_do_loop(ctx_cego, serv, monkeypatch):
    import radar.pendencias.validacao as modulo

    threads: list[int] = []
    original = modulo.mascarar

    def espiao(texto, mascara):
        threads.append(threading.get_ident())
        return original(texto, mascara)

    monkeypatch.setattr(modulo, "mascarar", espiao)
    ref = guardar(serv, PAGINA_CEGA)
    v = await validar(confirmado(ev(ref, "[EMPRESA] paga 1% ao mês")), pend(ctx_cego), ctx_cego, serv, MASCARA)
    assert v.aceita
    assert threads and threads[0] != threading.get_ident()


# --- título: a máscara não apaga a promessa nem atribui a outra empresa ------------------------------------


def mascara_do_site(
    serv: Servicos, titulo: str, razao: str = "Exemplo Invest Ltda", dominio: str = "exemplo.com.br"
) -> dict[str, str]:
    html = f"<html><head><title>{titulo}</title></head><body><p>oi</p></body></html>"
    saidas = {
        "alvo": {"dominio": dominio},
        "cnpj": {"razao_social": razao},
        "captura": {"paginas": [{"html": guardar(serv, html)}]},
    }
    return montar_mascara(saidas, serv.custodia.ler)


async def test_titulo_com_a_promessa_nao_apaga_a_promessa_no_modo_cego(ctx_cego, serv):
    mascara = mascara_do_site(serv, "Exemplo Invest | Rendimento de 1,5% ao dia")
    promessa = "Rendimento de 1,5% ao dia, garantido"
    assert mascarar(promessa, mascara) == promessa
    ref = guardar(serv, f"<p>{promessa}, na Exemplo Invest</p>")
    v = await validar(confirmado(ev(ref, promessa)), pend(ctx_cego), ctx_cego, serv, mascara)
    assert v.aceita


async def test_titulo_generico_nao_atribui_a_fala_a_outra_empresa(ctx_cego, serv):
    mascara = mascara_do_site(serv, "Investimentos - Exemplo Invest")
    ref = guardar(serv, "<p>Outra Empresa Investimentos não possui registro na CVM</p>")
    v = await validar(
        confirmado(ev(ref, "[EMPRESA] não possui registro na CVM")), pend(ctx_cego), ctx_cego, serv, mascara
    )
    assert v == Validacao(False, "trecho não encontrado na fonte", "evidencias[0].trecho", [])


@pytest.mark.parametrize(
    ("titulo", "razao", "marca", "outra_empresa"),
    [
        (
            "Investimentos - Exemplo Invest",
            "EXEMPLO INVESTIMENTOS LTDA",
            "Exemplo Invest",
            "Outra Empresa Investimentos",
        ),
        ("Participações - Exemplo", "EXEMPLO PARTICIPACOES LTDA", "Exemplo", "Outra Empresa Participações"),
        ("Serviços Digitais | Exemplo", "EXEMPLO SERVICOS DIGITAIS LTDA", "Exemplo", "Outra Empresa Serviços Digitais"),
    ],
)
async def test_palavra_do_setor_na_razao_social_nao_atribui_a_fala_a_outra_empresa(
    ctx_cego, serv, titulo, razao, marca, outra_empresa
):
    mascara = mascara_do_site(serv, titulo, razao)
    ref = guardar(serv, f"<p>{outra_empresa} não possui registro na CVM</p>")
    falsa = confirmado(ev(ref, "[EMPRESA] não possui registro na CVM"))
    v = await validar(falsa, pend(ctx_cego), ctx_cego, serv, mascara)
    assert v == Validacao(False, "trecho não encontrado na fonte", "evidencias[0].trecho", [])
    # a empresa de verdade continua podendo ser citada pelo marcador
    ref = guardar(serv, f"<p>{marca} não possui registro na CVM</p>")
    verdadeira = confirmado(ev(ref, "[EMPRESA] não possui registro na CVM"))
    assert (await validar(verdadeira, pend(ctx_cego), ctx_cego, serv, mascara)).aceita


@pytest.mark.parametrize(
    ("dominio", "razao", "generico"),
    [
        ("exemploinvestimentos.com.br", "EXEMPLO INVESTIMENTOS LTDA", "Investimentos"),
        ("exemplo-investimentos.com.br", "EXEMPLO INVESTIMENTOS LTDA", "Investimentos"),
        ("exemploparticipacoes.com.br", "EXEMPLO PARTICIPACOES LTDA", "Participações"),
        ("exemploservicosdigitais.com.br", "EXEMPLO SERVICOS DIGITAIS LTDA", "Serviços Digitais"),
    ],
)
async def test_palavra_do_setor_no_dominio_nao_atribui_a_fala_a_outra_empresa(
    ctx_cego, serv, dominio, razao, generico
):
    # o domínio traz a palavra do setor colada à marca: ela não pode virar [EMPRESA] pelo rótulo do domínio
    mascara = mascara_do_site(serv, f"{generico} - Exemplo Invest", razao, dominio)
    ref = guardar(serv, f"<p>Outra Empresa {generico} não possui registro na CVM</p>")
    falsa = confirmado(ev(ref, "[EMPRESA] não possui registro na CVM"))
    v = await validar(falsa, pend(ctx_cego), ctx_cego, serv, mascara)
    assert v == Validacao(False, "trecho não encontrado na fonte", "evidencias[0].trecho", [])
    ref = guardar(serv, "<p>Exemplo Invest não possui registro na CVM</p>")
    verdadeira = confirmado(ev(ref, "[EMPRESA] não possui registro na CVM"))
    assert (await validar(verdadeira, pend(ctx_cego), ctx_cego, serv, mascara)).aceita


# --- autocitação -------------------------------------------------------------------------------------------


async def test_julgamento_nao_e_fonte(ctx, serv):
    julgamento = b'{"id": "P-A1#1", "mensagem": "Saque suspenso hoje"}'
    ref = serv.custodia.guardar(julgamento, "json", tipo="julgamento", origem="P-A1#1")
    v = await validar(confirmado(ev(ref, "Saque suspenso hoje")), pend(ctx), ctx, serv)
    assert v == Validacao(False, "fonte inválida: julgamento não é fonte", "evidencias[0].fonte", [])


async def test_conteudo_registrado_tambem_como_julgamento_nao_e_fonte(ctx, serv):
    conteudo = b"Saque suspenso hoje por ordem judicial"
    ref = serv.custodia.guardar(conteudo, "txt", tipo="pagina", origem="https://exemplo.org/")
    assert (await validar(confirmado(ev(ref, "Saque suspenso hoje")), pend(ctx), ctx, serv)).aceita
    serv.custodia.guardar(conteudo, "txt", tipo="julgamento", origem="P-A1#1")
    v = await validar(confirmado(ev(ref, "Saque suspenso hoje")), pend(ctx), ctx, serv)
    assert (v.aceita, v.motivo) == (False, "fonte inválida: julgamento não é fonte")


async def test_artefato_de_outro_tipo_continua_fonte(ctx, serv):
    ref = serv.custodia.guardar(b"Saque suspenso hoje", "txt", tipo="texto", origem="https://exemplo.org/")
    assert (await validar(confirmado(ev(ref, "Saque suspenso hoje")), pend(ctx), ctx, serv)).aceita


# --- IP do alvo --------------------------------------------------------------------------------------------

IPV6_PUBLICO = "2606:2800:220:1:248:1893:25c8:1946"
# o `dns` entrega as formas que o DoH devolve; a comparação é pelo endereço, não pelo texto
IPS_DO_ALVO = {f" {IP_PUBLICO} ", "2606:2800:0220:0001:0248:1893:25C8:1946"}


@pytest.mark.parametrize(
    "url",
    [
        f"http://{IP_PUBLICO}/x",
        f"http://{int(ipaddress.ip_address(IP_PUBLICO))}/x",  # a mesma notação antiga que o resolvedor aceita
        f"http://[{IPV6_PUBLICO}]/x",
    ],
)
async def test_ip_literal_do_alvo_e_recusado(ctx, serv, respx_mock, url):
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte(url, ctx, serv, IPS_DO_ALVO)
    assert (erro.value.mensagem, erro.value.permanente) == (MOTIVO_ALVO, True)
    v = await validar(confirmado(ev(url)), pend(ctx), ctx, serv, ips_do_alvo=IPS_DO_ALVO)
    assert v == Validacao(False, MOTIVO_ALVO, "evidencias[0].fonte", [])
    assert respx_mock.calls.call_count == 0


async def test_ip_do_alvo_usa_a_mensagem_do_modo(tmp_path, serv):
    url = f"http://{IP_PUBLICO}/x"
    cego = contexto(tmp_path).model_copy(update={"modo_cego": True})
    nenhum = contexto(tmp_path, modo_contato="nenhum")
    for ctx_, esperado in ((cego, MOTIVO_ALVO_CEGO), (nenhum, MOTIVO_NENHUM)):
        v = await validar(confirmado(ev(url)), pend(ctx_), ctx_, serv, ips_do_alvo=IPS_DO_ALVO)
        assert v == Validacao(False, esperado, "evidencias[0].fonte", [])


async def test_outro_ip_ou_sem_ips_do_alvo_e_permitido(ctx, serv, respx_mock):
    servir(respx_mock, f"http://{IP_PUBLICO}/x", pagina())
    servir(respx_mock, "http://8.8.8.8/x", pagina())
    assert (await arquivar_fonte("http://8.8.8.8/x", ctx, serv, IPS_DO_ALVO)).texto
    assert (await arquivar_fonte(f"http://{IP_PUBLICO}/x", ctx, serv)).texto
    assert (await arquivar_fonte(f"http://{IP_PUBLICO}/x", ctx, serv, set())).texto
    # entrada que não é IP não derruba nem vale
    assert (await arquivar_fonte(f"http://{IP_PUBLICO}/x", ctx, serv, {"não é um ip"})).texto


async def test_redirect_para_o_ip_do_alvo_e_recusado(ctx, serv, respx_mock):
    respx_mock.get("https://curto.example.org/a").mock(
        return_value=httpx.Response(302, headers={"location": f"http://{IP_PUBLICO}/x"})
    )
    with pytest.raises(ErroNo) as erro:
        await arquivar_fonte("https://curto.example.org/a", ctx, serv, IPS_DO_ALVO)
    assert erro.value.mensagem == MOTIVO_ALVO
