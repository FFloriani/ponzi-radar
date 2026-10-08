"""Validação de respostas, arquivamento de fonte e checagens SSRF/contato (Tarefa 13)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from radar.config import Config, RedeConfig
from radar.custodia import Custodia
from radar.modelos import Contexto, ErroNo, Evidencia, Pendencia, Resposta
from radar.motor import Servicos
from radar.pendencias.definicoes import nova_pendencia
from radar.pendencias.validacao import FonteArquivada, Validacao, arquivar_fonte, validar
from radar.rede import Rede
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
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


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
async def serv(tmp_path):
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        yield Servicos(config=config, rede=rede, custodia=Custodia(tmp_path), matriz=MATRIZ_SPEC)
    finally:
        await rede.fechar()


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
        ("har", '{"log": {"mensagem": "Saque suspenso até segunda ordem"}}'.encode()),
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
    assert v == Validacao(True, None, None, ["trecho_nao_conferido"])


async def test_trecho_em_branco_rejeita(ctx, serv):
    ref = guardar(serv, pagina())
    resposta = confirmado(ev(ref), ev(ref, "   "))  # a segunda evidência passa pelo modelo, mas não cita nada
    v = await validar(resposta, pend(ctx), ctx, serv)
    assert (v.aceita, v.campo) == (False, "evidencias[1].trecho")
    assert v.motivo.startswith("trecho vazio")


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
    assert v == Validacao(True, None, None, ["trecho_nao_conferido"])


async def test_url_que_da_404_tambem_aceita_com_marca(ctx, serv, respx_mock):
    respx_mock.get(URL).mock(return_value=httpx.Response(404))
    v = await validar(confirmado(ev(URL)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, ["trecho_nao_conferido"])


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
    assert v == Validacao(True, None, None, ["trecho_nao_conferido"])


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


async def test_data_fonte_informada_vale_mais_que_a_detectada(tmp_path, serv, respx_mock):
    ctx = contexto(tmp_path, as_of=date(2025, 2, 15))
    servir(respx_mock, URL, pagina('<meta property="article:published_time" content="2025-03-01">'))
    v = await validar(confirmado(ev(URL, data_fonte=date(2025, 1, 5))), pend(ctx), ctx, serv)
    assert v.aceita


async def test_sem_data_marca_data_desconhecida(ctx, serv):
    ref = guardar(serv, pagina())
    v = await validar(confirmado(ev(ref, data_fonte=None)), pend(ctx), ctx, serv)
    assert v == Validacao(True, None, None, ["data_desconhecida"])


async def test_artefato_nao_tem_data_detectada(ctx_retro, serv):
    # a data detectada é a da página que `arquivar_fonte` baixou; o artefato da custódia não passa por ela
    ref = guardar(serv, pagina('<meta property="article:published_time" content="2025-03-01">'))
    v = await validar(confirmado(ev(ref, data_fonte=None)), pend(ctx_retro), ctx_retro, serv)
    assert v.marcas == ["data_desconhecida"]


async def test_marcas_sem_duplicatas_na_ordem_em_que_surgiram(ctx, serv, respx_mock):
    respx_mock.get(URL).mock(return_value=httpx.Response(503))
    respx_mock.get(URL + "-2").mock(return_value=httpx.Response(503))
    ref = guardar(serv, pagina())
    resposta = confirmado(ev(URL, data_fonte=None), ev(URL + "-2", data_fonte=None), ev(ref, data_fonte=None))
    v = await validar(resposta, pend(ctx), ctx, serv)
    assert v.aceita
    assert v.marcas == ["trecho_nao_conferido", "data_desconhecida"]


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


async def test_ip_publico_e_permitido(ctx, serv, respx_mock):
    servir(respx_mock, "http://93.184.216.34/pagina", pagina())
    fonte = await arquivar_fonte("http://93.184.216.34/pagina", ctx, serv)
    assert "Rendimento de 1,5% ao dia" in fonte.texto


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
    assert v == Validacao(True, None, None, ["trecho_nao_conferido"])


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


async def test_modo_captura_permite_o_dominio_do_alvo(ctx, serv, respx_mock):
    servir(respx_mock, "https://exemplo.com.br/termos", pagina())
    fonte = await arquivar_fonte("https://exemplo.com.br/termos", ctx, serv)
    assert fonte.texto


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
        (None, b"<p>sem content-type</p>", ".html", "sem content-type"),
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
        serv.rede._cache.clear()  # a Rede devolveria a página da rodada anterior
        assert (await arquivar_fonte(URL, ctx, serv)).data_publicacao == esperada


async def test_data_de_publicacao_com_json_ld_aninhado_fundo_nao_derruba(ctx, serv, respx_mock):
    fundo = "[" * 100_000 + "]" * 100_000
    servir(respx_mock, URL, pagina(f'<script type="application/ld+json">{fundo}</script>'))
    assert (await arquivar_fonte(URL, ctx, serv)).data_publicacao is None
