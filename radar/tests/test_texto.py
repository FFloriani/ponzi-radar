"""`radar.texto`: normalização, decodificação de bytes e texto de PDF (T13: validação de fontes; T11: índices)."""

from __future__ import annotations

from pathlib import Path

import pytest

from radar import texto as modulo
from radar.texto import codigo_md, decodificar, escapar_md, normalizar, texto_de_pdf

FIXTURES_CVM = Path(__file__).parent / "fixtures" / "cvm"
PDF_509 = (FIXTURES_CVM / "deli509.pdf").read_bytes()


# --- normalizar -------------------------------------------------------------------------------------------


def test_normalizar_tira_acento_caixa_aspas_e_espacos_repetidos():
    assert normalizar("  AÇÃO  “Garantida”\n do ‘Mês’ ") == "acao \"garantida\" do 'mes'"


def test_normalizar_remove_caracteres_de_formato_invisiveis():
    # hífen opcional, espaço de largura zero, junção de largura zero, BOM e marca de direção (categoria Cf)
    assert normalizar("so­ft​ware‍﻿‎") == "software"
    assert normalizar("Pag​amento  parado") == "pagamento parado"


# --- decodificar ------------------------------------------------------------------------------------------

LATIN1 = "Promoção: ação garantida".encode("iso-8859-1")
META_LATIN1 = b'<html><head><meta charset="iso-8859-1"></head><body>'


def test_decodificar_usa_o_charset_do_cabecalho():
    assert decodificar(LATIN1, "text/html; charset=ISO-8859-1") == "Promoção: ação garantida"
    assert decodificar("ação".encode(), "text/plain; charset=utf-8") == "ação"


def test_decodificar_sem_charset_usa_o_meta_do_html():
    corpo = META_LATIN1 + LATIN1
    for tipo in ("text/html", "application/xhtml+xml", None, ""):
        assert decodificar(corpo, tipo).endswith("Promoção: ação garantida"), tipo


def test_decodificar_o_cabecalho_vale_mais_que_o_meta():
    corpo = META_LATIN1 + "ação".encode()
    assert decodificar(corpo, "text/html; charset=utf-8").endswith("ação")


def test_decodificar_so_procura_meta_em_html():
    corpo = META_LATIN1 + LATIN1
    assert "�" in decodificar(corpo, "text/plain")  # texto puro: UTF-8 com replace


def test_decodificar_sem_nada_e_utf8_com_replace():
    assert decodificar("ação".encode(), None) == "ação"
    assert "�" in decodificar(LATIN1, None)


@pytest.mark.parametrize(
    "tipo", ["text/html; charset=inventado-9", "text/html; charset=idna", "text/html; charset=undefined"]
)
def test_decodificar_charset_que_o_python_nao_decodifica_cai_no_utf8(tipo):
    assert decodificar("ação".encode(), tipo) == "ação"


def test_decodificar_meta_com_charset_desconhecido_cai_no_utf8():
    assert decodificar(b'<meta charset="inventado-9">' + "ação".encode(), "text/html").endswith("ação")


def test_decodificar_tira_o_bom():
    assert decodificar(b"\xef\xbb\xbfola", "text/plain; charset=utf-8") == "ola"
    assert decodificar(b"\xef\xbb\xbf<p>ola</p>", None) == "<p>ola</p>"


# --- texto_de_pdf -----------------------------------------------------------------------------------------


def test_texto_de_pdf_le_o_texto():
    texto = texto_de_pdf(PDF_509)
    assert "DELIBERAÇÃO CVM Nº 509" in texto
    assert "FIDELITAS" in texto


def test_texto_de_pdf_sem_texto_extraivel_e_vazio():
    assert texto_de_pdf((FIXTURES_CVM / "sem_texto.pdf").read_bytes()) == ""


@pytest.mark.parametrize("dados", [b"", b"isto nao e um pdf", b"%PDF-1.4\nlixo sem estrutura"])
def test_texto_de_pdf_que_nao_e_pdf_e_vazio(dados):
    assert texto_de_pdf(dados) == ""


def test_texto_de_pdf_grande_demais_nao_e_lido(monkeypatch):
    monkeypatch.setattr(modulo, "_MAX_BYTES_PDF", 1000)
    assert texto_de_pdf(PDF_509) == ""


def test_texto_de_pdf_le_so_as_primeiras_paginas(monkeypatch):
    completo = texto_de_pdf(PDF_509)
    monkeypatch.setattr(modulo, "_MAX_PAGINAS_PDF", 1)
    primeira = texto_de_pdf(PDF_509)
    assert 0 < len(primeira) < len(completo)
    assert completo.startswith(primeira)


def test_texto_de_pdf_sanea_substituto_solto(monkeypatch):
    """O `pypdf` pode devolver um substituto UTF-16 solto (CMap malformado); ele não pode chegar ao JSON do cache."""

    class Pagina:
        def extract_text(self) -> str:
            return "texto com substituto solto \ud800 e mais texto valido para passar do minimo de caracteres. " * 3

    class Leitor:
        def __init__(self, fluxo) -> None:
            self.pages = [Pagina()]

    monkeypatch.setattr(modulo, "PdfReader", Leitor)
    texto = texto_de_pdf(b"%PDF-1.4")
    texto.encode("utf-8")  # não levanta UnicodeEncodeError
    assert "substituto solto" in texto
    assert "\ud800" not in texto


# --- escapar_md e codigo_md (T15: o dossiê em Markdown) ------------------------------------------------------


@pytest.mark.parametrize(
    "entrada,saida",
    [
        ("a | b", r"a \| b"),
        ("linha 1\nlinha 2\r\nlinha 3\N{LINE SEPARATOR}linha 4", "linha 1 linha 2 linha 3 linha 4"),
        ("  muitos   espaços\t aqui ", "muitos espaços aqui"),
        ("<b>x</b> & y", r"\<b\>x\</b\> \& y"),
        ("[a](http://x)", r"\[a\](http://x)"),
        ("*a* _b_ `c` ~d~ # e", r"\*a\* \_b\_ \`c\` \~d\~ \# e"),
        # o sublinhado entre letras ou dígitos é de identificador e fica; o solto vira texto
        ("atraso_pagamento a_b_c ação_x 1_2", "atraso_pagamento a_b_c ação_x 1_2"),
        ("_x x_ __y__ (_z)", r"\_x x\_ \_\_y\_\_ (\_z)"),
        ("barra \\ invertida", "barra \\\\ invertida"),
        ("CPF 123.456.789-09 e CNPJ 12.345.678/0001-95", "CPF (CPF omitido) e CNPJ 12.345.678/0001-95"),
        ("cpf: 12345678909 e fone 11987654321", "(CPF omitido) e fone 11987654321"),
        (
            "sem\x00controle\x07 e\N{RIGHT-TO-LEFT OVERRIDE}bidi\N{LEFT-TO-RIGHT ISOLATE} e\N{ZERO WIDTH SPACE}sp",
            "semcontrole ebidi esp",
        ),
        (None, ""),
        (3, "3"),
    ],
)
def test_escapar_md(entrada, saida):
    assert escapar_md(entrada) == saida


def test_escapar_md_corta_depois_de_mascarar_o_cpf():
    assert escapar_md("x" * 300, 160) == "x" * 159 + "…"
    assert escapar_md("curto", 160) == "curto"
    # o CPF que cairia no corte não sobra pela metade
    texto = "a" * 150 + " CPF 123.456.789-09"
    assert "123." not in escapar_md(texto, 160) and "(CPF omitido)" in escapar_md(texto, 200)


def test_codigo_md_para_celula_de_tabela():
    assert codigo_md("https://x.example/a_b*c") == "`https://x.example/a_b*c`"
    assert codigo_md("a|b") == "`a\\|b`"
    assert codigo_md("com `crase`") == "`` com `crase` ``"
    assert codigo_md("duas ``crases`` aqui") == "```duas ``crases`` aqui```"
    assert codigo_md("a\nb\N{LINE SEPARATOR}c") == "`a b c`"
    assert codigo_md("") == "" and codigo_md(None) == ""
