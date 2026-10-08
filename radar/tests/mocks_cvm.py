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
URL_PDF = r"https://conteudo\.cvm\.gov\.br/export/sites/cvm/legislacao/deliberacoes/anexos/\d+/deli(\d+)\.pdf"
# invólucros reais gravados (os outros números ganham um invólucro sintético) e os PDFs reais que existem
INVOLUCROS_REAIS = {905: "deli905.html", 509: "deli509.html", 586: "deli586.html"}
PDFS = {509: "deli509.pdf", 586: "deli586.pdf"}
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
    reg = SimpleNamespace(paginas=[], involucros=[], documentos=[], pdfs=[], partida=None, jsp=None)

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
        corpo = fixture_bytes(INVOLUCROS_REAIS[numero]) if numero in INVOLUCROS_REAIS else _involucro_sintetico(numero)
        return httpx.Response(200, content=corpo, headers={"content-type": "text/html;charset=UTF-8"})

    def documento(request: httpx.Request) -> httpx.Response:
        numero = int(re.fullmatch(URL_DOCUMENTO, str(request.url)).group(1))
        reg.documentos.append(numero)
        corpo = fixture_bytes("deli905.htm") if numero == 905 else _documento_sintetico(numero)
        return httpx.Response(200, content=corpo, headers={"content-type": "text/html;charset=UTF-8"})

    def pdf(request: httpx.Request) -> httpx.Response:
        numero = int(re.fullmatch(URL_PDF, str(request.url)).group(1))
        reg.pdfs.append(numero)
        if numero not in PDFS:
            return httpx.Response(404)
        return httpx.Response(200, content=fixture_bytes(PDFS[numero]), headers={"content-type": "application/pdf"})

    reg.partida = respx_mock.get(URL_DELIBERACOES_PARTIDA).mock(
        return_value=httpx.Response(200, text="<html></html>", headers={"set-cookie": f"{SESSAO}; Path=/; HttpOnly"})
    )
    reg.jsp = respx_mock.get(URL_DELIBERACOES_PAGINAS).mock(side_effect=jsp)
    reg.rota_involucros = respx_mock.get(url__regex=URL_INVOLUCRO).mock(side_effect=involucro)
    reg.rota_documentos = respx_mock.get(url__regex=URL_DOCUMENTO).mock(side_effect=documento)
    reg.rota_pdfs = respx_mock.get(url__regex=URL_PDF).mock(side_effect=pdf)
    return reg


def pdf_com_texto(texto: str) -> bytes:
    """Um PDF válido de uma página com `texto` (só ASCII, sem parênteses nem barras), para os casos que os PDFs reais não têm."""
    conteudo = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode()
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = bytearray(b"%PDF-1.4\n")
    deslocamentos = []
    for numero, objeto in enumerate(objetos, 1):
        deslocamentos.append(len(saida))
        saida += b"%d 0 obj\n" % numero + objeto + b"\nendobj\n"
    inicio_xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for deslocamento in deslocamentos:
        saida += b"%010d 00000 n \n" % deslocamento
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, inicio_xref)
    return bytes(saida)
