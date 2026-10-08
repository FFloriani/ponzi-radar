"""As respostas gravadas da CVM e do BCB (`tests/fixtures/cvm/`) servidas por respx, sem rede."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx

from radar.indices import (
    CONJUNTOS_BCB,
    URL_CVM,
    URL_DELIBERACOES_PAGINAS,
    URL_DELIBERACOES_PARTIDA,
    URL_OLINDA,
)

FIXTURES = Path(__file__).parent / "fixtures" / "cvm"

ZIPS_CVM = {
    "INTERMED/CAD/DADOS/cad_intermed.zip": "cad_intermed.zip",
    "CROWDFUNDING/CAD/DADOS/cad_crowdfunding.zip": "cad_crowdfunding.zip",
    "ADM_CART/CAD/DADOS/cad_adm_cart.zip": "cad_adm_cart.zip",
    "CONSULTOR_VLMOB/CAD/DADOS/cad_consultor_vlmob.zip": "cad_consultor_vlmob.zip",
}
URL_SANCIONADOR = URL_CVM + "PROCESSO/SANCIONADOR/DADOS/processo_sancionador.zip"
URL_INVOLUCRO = r"https://conteudo\.cvm\.gov\.br/legislacao/deliberacoes/deli\d+/[Dd]eli(\d+)\.html"
URL_DOCUMENTO = r"https://conteudo\.cvm\.gov\.br/legislacao/deliberacoes/anexos/\d+/deli(\d+)\.htm"
TOTAL_PAGINAS = 28  # "Páginas 1/28": o que a busca real respondia em 07/10/2026
SESSAO = "JSESSIONID=SESSAO-DE-TESTE"

# datas reais das deliberações das duas primeiras páginas da busca
DATAS = {
    905: date(2025, 11, 25),
    903: date(2025, 10, 28),
    902: date(2025, 8, 22),
    901: date(2025, 8, 18),
    900: date(2025, 7, 8),
    899: date(2025, 7, 1),
    895: date(2024, 9, 11),
}
NUMEROS = sorted(DATAS)


def fixture_bytes(nome: str) -> bytes:
    return (FIXTURES / nome).read_bytes()


def mocar_cvm(respx_mock) -> dict:
    """Os quatro cadastros e o processo sancionador, pelo nome do arquivo."""
    rotas = {}
    for caminho, arquivo in {**ZIPS_CVM, URL_SANCIONADOR.removeprefix(URL_CVM): "processo_sancionador.zip"}.items():
        rotas[arquivo] = respx_mock.get(URL_CVM + caminho).mock(
            return_value=httpx.Response(200, content=fixture_bytes(arquivo), headers={"content-type": "application/zip"})
        )
    return rotas


def mocar_olinda(respx_mock) -> dict:
    rotas = {}
    for conjunto in (*CONJUNTOS_BCB, "DominiosVerificados"):
        rotas[conjunto] = respx_mock.get(URL_OLINDA.format(conjunto=conjunto)).mock(
            return_value=httpx.Response(200, content=fixture_bytes(f"olinda_{conjunto}.json"))
        )
    return rotas


def _involucro_sintetico(numero: int) -> bytes:
    data = DATAS[numero]
    carimbo = data.strftime("%a %b %d 18:00:00 BRT %Y")
    return (
        '<html><body><div id="main"><article class="contentTextoGeral">'
        f'<h2>Deliberação CVM {numero}</h2><section class="pull-left contentArticle">'
        f"<p><b>{carimbo}</b></p>"
        "<p>Atuação irregular no mercado de valores mobiliários por parte de pessoas não autorizadas pela CVM.</p>"
        f'<p><a href="/legislacao/deliberacoes/anexos/{numero // 100 * 100:04d}/deli{numero}.htm">[HTML]</a></p>'
        "</section></article></div></body></html>"
    ).encode()


def _documento_sintetico(numero: int) -> bytes:
    data = DATAS[numero]
    return (
        f"<html><head><meta charset='utf-8'></head><body><p>DELIBERAÇÃO CVM Nº {numero}, de {data.day} de julho de {data.year}</p>"
        f"<p>a CVM apurou indícios de que EMPRESA FICTÍCIA {numero} LTDA., CNPJ nº 00.000.000/0001-91, "
        f"por meio do sítio https://golpe{numero}.example/ oferece contratos de investimento.</p></body></html>"
    ).encode()


def mocar_deliberacoes(respx_mock, *, exigir_sessao: bool = True) -> SimpleNamespace:
    """A busca de "Atuação Irregular", as páginas 1 e 2 reais e as deliberações das duas.

    Como o servidor real, o JSP responde vazio a quem não passou antes pela página de partida (sem o cookie da
    sessão). As páginas 3 a 28 só trazem o marcador "Páginas n/28", sem artigos. `.requisicoes` guarda o que foi
    pedido: `paginas` (searchPage), `involucros` e `documentos` (números).
    """
    reg = SimpleNamespace(paginas=[], involucros=[], documentos=[], partida=None, jsp=None)

    def jsp(request: httpx.Request) -> httpx.Response:
        if exigir_sessao and SESSAO not in request.headers.get("cookie", ""):
            return httpx.Response(200, text="\n" * 40)  # o corpo vazio da resposta real sem sessão
        pagina = int(request.url.params["searchPage"])
        reg.paginas.append(pagina)
        if pagina in (1, 2):
            corpo = fixture_bytes(f"deliberacoes_pagina{pagina}.html")
        elif pagina <= TOTAL_PAGINAS:
            corpo = f"<span>273 resultados encontrados</span><span>Páginas {pagina}/{TOTAL_PAGINAS}</span>".encode()
        else:
            corpo = fixture_bytes("deliberacoes_vazia.html")
        return httpx.Response(200, content=corpo, headers={"content-type": "text/html;charset=UTF-8"})

    def involucro(request: httpx.Request) -> httpx.Response:
        numero = int(re.fullmatch(URL_INVOLUCRO, str(request.url)).group(1))
        reg.involucros.append(numero)
        corpo = fixture_bytes("deli905.html") if numero == 905 else _involucro_sintetico(numero)
        return httpx.Response(200, content=corpo, headers={"content-type": "text/html;charset=UTF-8"})

    def documento(request: httpx.Request) -> httpx.Response:
        numero = int(re.fullmatch(URL_DOCUMENTO, str(request.url)).group(1))
        reg.documentos.append(numero)
        corpo = fixture_bytes("deli905.htm") if numero == 905 else _documento_sintetico(numero)
        return httpx.Response(200, content=corpo, headers={"content-type": "text/html;charset=UTF-8"})

    reg.partida = respx_mock.get(URL_DELIBERACOES_PARTIDA).mock(
        return_value=httpx.Response(200, text="<html></html>", headers={"set-cookie": f"{SESSAO}; Path=/; HttpOnly"})
    )
    reg.jsp = respx_mock.get(URL_DELIBERACOES_PAGINAS).mock(side_effect=jsp)
    reg.rota_involucros = respx_mock.get(url__regex=URL_INVOLUCRO).mock(side_effect=involucro)
    reg.rota_documentos = respx_mock.get(url__regex=URL_DOCUMENTO).mock(side_effect=documento)
    return reg
