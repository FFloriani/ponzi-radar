"""Máscara do modo cego (Tarefa 13): os termos que identificam o alvo viram marcadores."""

from __future__ import annotations

import pytest

from radar.pendencias.mascara import mascarar, montar_mascara

HOME = (
    '<html><head><meta charset="utf-8"><title>  Exemplo   Invest — Rendimento diário </title>'
    '<meta property="og:site_name" content="Exemplo Invest Brasil"></head><body><p>oi</p></body></html>'
)
ALVO_IDN = "investimentoseguro-ação.com.br"
ALVO_PUNYCODE = ALVO_IDN.encode("idna").decode("ascii")


def saidas_completas() -> dict[str, dict]:
    return {
        "ct": {"primeiro_certificado": "2024-01-01", "total": 2, "sans": ["exemplo.com.br", "app.exemplo.com.br"]},
        "cnpj": {
            "cnpj": "33000167000101",
            "razao_social": "Exemplo Invest Ltda",
            "nome_fantasia": None,
            "socios": [{"nome": "Fulano de Tal", "qualificacao": "Administrador", "entrada": "2020-01-01"}],
        },
    }


def sem_artefatos(ref: str) -> bytes:
    raise AssertionError(f"não devia ler artefato: {ref}")


def com_titulo(titulo: str) -> dict[str, str]:
    html = f"<html><head><title>{titulo}</title></head><body></body></html>".encode()
    return montar_mascara({"captura": {"paginas": [{"html": "sha256:aa"}]}}, {"sha256:aa": html}.__getitem__)


# --- montar_mascara ---------------------------------------------------------------------------------------


def test_mascara_completa():
    mascara = montar_mascara(saidas_completas(), sem_artefatos)
    assert mascara == {
        "Exemplo Invest Ltda": "[EMPRESA]",
        "exemplo.com.br": "[ALVO]",
        "app.exemplo.com.br": "[ALVO]",
        "33.000.167/0001-01": "[CNPJ]",
        "33000167000101": "[CNPJ]",
        "Fulano de Tal": "[PESSOA_1]",
    }


def test_sem_saidas_a_mascara_e_vazia():
    assert montar_mascara({}, sem_artefatos) == {}
    # nó que não rodou, saída sem os campos e valores que não são texto
    saidas = {"ct": {}, "cnpj": {"cnpj": None, "razao_social": None, "socios": None}, "captura": None}
    assert montar_mascara(saidas, sem_artefatos) == {}


def test_dominio_do_alvo_entra_mesmo_sem_o_ct():
    mascara = montar_mascara({"alvo": {"dominio": "exemplo.com.br"}}, sem_artefatos)
    assert mascara == {"exemplo.com.br": "[ALVO]"}


def test_dominio_idn_entra_em_punycode_e_em_unicode():
    sans = [ALVO_PUNYCODE, "www." + ALVO_PUNYCODE, "app." + ALVO_IDN]
    saidas = {"alvo": {"dominio": ALVO_PUNYCODE}, "ct": {"sans": sans}}
    mascara = montar_mascara(saidas, sem_artefatos)
    assert mascara == {
        ALVO_PUNYCODE: "[ALVO]",
        ALVO_IDN: "[ALVO]",
        "www." + ALVO_PUNYCODE: "[ALVO]",
        "www." + ALVO_IDN: "[ALVO]",
        "app." + ALVO_IDN: "[ALVO]",
        "app." + ALVO_PUNYCODE: "[ALVO]",
    }


def test_punycode_malformado_nao_derruba():
    mascara = montar_mascara({"ct": {"sans": ["xn--a-----.example.org"]}}, sem_artefatos)
    assert mascara == {"xn--a-----.example.org": "[ALVO]"}


def test_cnpj_alfanumerico_formatado_e_so_com_caracteres():
    mascara = montar_mascara({"cnpj": {"cnpj": "12ABC34501DE35"}}, sem_artefatos)
    assert mascara == {"12.ABC.345/01DE-35": "[CNPJ]", "12ABC34501DE35": "[CNPJ]"}


def test_termos_curtos_nao_entram():
    saidas = {
        "ct": {"sans": ["a.b", "abc.io"]},
        "cnpj": {"razao_social": "ABC", "nome_fantasia": "Sol", "socios": [{"nome": "Li"}, {"nome": "Ana"}]},
    }
    assert montar_mascara(saidas, sem_artefatos) == {"abc.io": "[ALVO]"}


def test_socios_seguem_a_ordem_do_quadro():
    saidas = {"cnpj": {"socios": [{"nome": "Maria Souza"}, {"nome": "Li"}, {"nome": "João Pereira"}, {"nome": None}]}}
    # a numeração é a posição no quadro: o sócio de nome curto não desloca os seguintes
    assert montar_mascara(saidas, sem_artefatos) == {"Maria Souza": "[PESSOA_1]", "João Pereira": "[PESSOA_3]"}


def test_termo_repetido_so_entra_uma_vez_sem_diferenciar_caixa():
    saidas = {
        "alvo": {"dominio": "exemplo.com.br"},
        "ct": {"sans": ["EXEMPLO.com.br"]},
        "cnpj": {"razao_social": "Exemplo Invest Ltda", "nome_fantasia": "EXEMPLO INVEST LTDA"},
    }
    assert montar_mascara(saidas, sem_artefatos) == {"exemplo.com.br": "[ALVO]", "Exemplo Invest Ltda": "[EMPRESA]"}


def test_titulo_e_og_site_name_da_pagina_inicial():
    artefatos = {"sha256:aa": HOME.encode("utf-8")}
    saidas = {"captura": {"paginas": [{"url": "https://exemplo.com.br/", "html": "sha256:aa"}, {"html": "sha256:bb"}]}}
    # só a página inicial é lida: pedir a "sha256:bb" daria KeyError
    mascara = montar_mascara(saidas, artefatos.__getitem__)
    # o título é partido no " — ": cada parte vale sozinha
    assert mascara == {
        "Exemplo Invest": "[EMPRESA]",
        "Rendimento diário": "[EMPRESA]",
        "Exemplo Invest Brasil": "[EMPRESA]",
    }


@pytest.mark.parametrize(
    ("titulo", "partes"),
    [
        ("Exemplo Invest | Investimentos Seguros", {"Exemplo Invest", "Investimentos Seguros"}),
        ("Exemplo Invest – Rendimento diário", {"Exemplo Invest", "Rendimento diário"}),
        ("Exemplo Invest — Rendimento diário", {"Exemplo Invest", "Rendimento diário"}),
        ("Exemplo Invest - Rendimento diário", {"Exemplo Invest", "Rendimento diário"}),
        ("Exemplo Invest · Início", {"Exemplo Invest", "Início"}),
        ("Exemplo Invest: o melhor jeito", {"Exemplo Invest", "o melhor jeito"}),
        ("A | B | Exemplo Invest | Sim", {"Exemplo Invest"}),  # partes com menos de 4 caracteres ficam de fora
        ("Pré-venda Exemplo-Invest", {"Pré-venda Exemplo-Invest"}),  # hífen colado não separa
        ("  Exemplo   Invest  ", {"Exemplo Invest"}),
    ],
)
def test_titulo_e_partido_nos_separadores(titulo, partes):
    assert set(com_titulo(titulo)) == partes


@pytest.mark.parametrize("atributo", ["property", "name"])
def test_og_site_name_por_property_ou_por_name(atributo):
    html = f'<head><meta {atributo}="og:site_name" content="Exemplo Invest Brasil"></head>'.encode()
    mascara = montar_mascara({"captura": {"paginas": [{"html": "sha256:aa"}]}}, {"sha256:aa": html}.__getitem__)
    assert mascara == {"Exemplo Invest Brasil": "[EMPRESA]"}


def test_pagina_inicial_do_wayback_quando_nao_ha_captura():
    artefatos = {"sha256:aa": HOME.encode("utf-8")}
    saidas = {"wayback_snapshot": {"paginas": [{"url": "http://exemplo.com.br/", "html": "sha256:aa"}]}}
    assert "Exemplo Invest Brasil" in montar_mascara(saidas, artefatos.__getitem__)


def test_captura_bloqueada_nao_tem_html_e_o_wayback_vale():
    artefatos = {"sha256:aa": HOME.encode("utf-8")}
    saidas = {
        "captura": {"paginas": [{"url": "https://exemplo.com.br/", "status": 403, "screenshot": "sha256:ff"}]},
        "wayback_snapshot": {"paginas": [{"html": "sha256:aa"}]},
    }
    assert "Exemplo Invest Brasil" in montar_mascara(saidas, artefatos.__getitem__)


def test_pagina_sem_titulo_nem_og_site_name():
    artefatos = {"sha256:aa": b"<html><body>so texto</body></html>"}
    saidas = {"captura": {"paginas": [{"html": "sha256:aa"}]}}
    assert montar_mascara(saidas, artefatos.__getitem__) == {}


def test_titulo_de_pagina_em_iso_8859_1():
    html = '<html><head><meta charset="iso-8859-1"><title>Promoção Investimentos</title></head></html>'
    saidas = {"wayback_snapshot": {"paginas": [{"html": "sha256:aa"}]}}
    mascara = montar_mascara(saidas, {"sha256:aa": html.encode("iso-8859-1")}.__getitem__)
    assert mascara == {"Promoção Investimentos": "[EMPRESA]"}


# --- mascarar ---------------------------------------------------------------------------------------------


def test_mascarar_do_termo_mais_longo_para_o_mais_curto_sem_diferenciar_caixa():
    mascara = montar_mascara(saidas_completas(), sem_artefatos)
    texto = (
        "Acesse https://app.exemplo.com.br/login ou EXEMPLO.COM.BR. CNPJ 33.000.167/0001-01 (33000167000101). "
        "Sócio: FULANO DE TAL, da exemplo invest ltda."
    )
    assert mascarar(texto, mascara) == (
        "Acesse https://[ALVO]/login ou [ALVO]. CNPJ [CNPJ] ([CNPJ]). Sócio: [PESSOA_1], da [EMPRESA]."
    )


def test_formato_da_receita_contra_texto_com_acento_e_caixa_mista():
    mascara = {"EXEMPLO PARTICIPACOES E INVESTIMENTOS S.A.": "[EMPRESA]", "JOAO DA SILVA": "[PESSOA_1]"}
    texto = 'A Exemplo Participações e Investimentos S/A (a "Exemplo") é de João da Silva e de JOÃO DA SILVA.'
    assert mascarar(texto, mascara) == 'A [EMPRESA] (a "Exemplo") é de [PESSOA_1] e de [PESSOA_1].'


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Exemplo Invest S.A. fim", "[EMPRESA] fim"),
        ("EXEMPLO INVEST S A fim", "[EMPRESA] fim"),
        ("exemplo invest s/a fim", "[EMPRESA] fim"),
        ("Exemplo Invest SA fim", "[EMPRESA] fim"),
        ("Exemplo Invest S.A fim", "[EMPRESA] fim"),
        ("Exemplo  Invest S.A. fim", "[EMPRESA] fim"),
        ("Exemplo\nInvest\nS.A. fim", "[EMPRESA] fim"),
        ("Exemplo-Invest S.A. fim", "[EMPRESA] fim"),
        ("Exem­plo Invest​ S.A. fim", "[EMPRESA] fim"),
        ("Exemplo Invest S.A.", "[EMPRESA]"),
    ],
)
def test_s_a_espacos_e_separadores_variam(texto, esperado):
    assert mascarar(texto, {"Exemplo Invest S.A.": "[EMPRESA]"}) == esperado


def test_o_ponto_so_e_absorvido_quando_o_termo_termina_nele():
    assert mascarar("A Exemplo Invest. Fim", {"Exemplo Invest": "[EMPRESA]"}) == "A [EMPRESA]. Fim"


@pytest.mark.parametrize(
    "cnpj",
    [
        "33.000.167/0001-01",
        "33000167000101",
        "33 000 167 0001 01",
        "33.000.167.0001.01",
        "33-000-167-0001-01",
        "33.000.167/0001 01",
        "33 000 167\n0001 01",
        "33 . 000 . 167 / 0001 - 01",
    ],
)
def test_cnpj_em_qualquer_formatacao(cnpj):
    mascara = montar_mascara({"cnpj": {"cnpj": "33000167000101"}}, sem_artefatos)
    assert mascarar(f"CNPJ {cnpj}, aberto", mascara) == "CNPJ [CNPJ], aberto"


@pytest.mark.parametrize("cnpj", ["12.ABC.345/01DE-35", "12ABC34501DE35", "12.abc.345/01de-35", "12 ABC 345 01DE 35"])
def test_cnpj_alfanumerico_em_qualquer_formatacao(cnpj):
    mascara = montar_mascara({"cnpj": {"cnpj": "12ABC34501DE35"}}, sem_artefatos)
    assert mascarar(f"CNPJ: {cnpj}.", mascara) == "CNPJ: [CNPJ]."


def test_cnpj_dentro_de_numero_maior_nao_e_mascarado():
    mascara = montar_mascara({"cnpj": {"cnpj": "33000167000101"}}, sem_artefatos)
    for texto in ("1233000167000101", "330001670001019", "x33000167000101", "protocolo 33000167000101a"):
        assert mascarar(texto, mascara) == texto


def test_dominio_idn_em_punycode_e_em_unicode():
    saidas = {"alvo": {"dominio": ALVO_PUNYCODE}, "ct": {"sans": ["www." + ALVO_PUNYCODE]}}
    mascara = montar_mascara(saidas, sem_artefatos)
    sem_acento = "investimentoseguro-acao.com.br"
    texto = f"{ALVO_IDN} / {ALVO_PUNYCODE} / www.{ALVO_IDN} / WWW.{ALVO_PUNYCODE.upper()} / {sem_acento}"
    assert mascarar(texto, mascara) == "[ALVO] / [ALVO] / [ALVO] / [ALVO] / [ALVO]"


def test_so_troca_palavra_inteira():
    mascara = {"Home": "[EMPRESA]", "Silva": "[PESSOA_1]", "exemplo.com.br": "[ALVO]"}
    texto = "Homenagem à Home de Silvana e do Silva; meuexemplo.com.br não é exemplo.com.br."
    esperado = "Homenagem à [EMPRESA] de Silvana e do [PESSOA_1]; meuexemplo.com.br não é [ALVO]."
    assert mascarar(texto, mascara) == esperado


def test_o_resto_do_texto_fica_como_estava():
    # a troca mexe só no trecho achado: acentos, caixa e espaços do resto continuam
    texto = "Ação:  João da Silva — açúcar\nÇÃO"
    assert mascarar(texto, {"JOAO DA SILVA": "[PESSOA_1]"}) == "Ação:  [PESSOA_1] — açúcar\nÇÃO"


def test_acento_decomposto_no_texto():
    mascara = {"João da Silva": "[PESSOA_1]", "Jose": "[PESSOA_2]"}
    # "a" + til combinante no meio do termo e acento combinante colado ao fim dele
    assert mascarar("João da Silva e José foram", mascara) == "[PESSOA_1] e [PESSOA_2] foram"


def test_o_marcador_nao_e_mascarado_de_novo():
    # uma empresa chamada "Alvo": o "[ALVO]" que acabou de entrar não pode virar "[[EMPRESA]]"
    mascara = {"exemplo.com.br": "[ALVO]", "Alvo": "[EMPRESA]"}
    assert mascarar("exemplo.com.br e a Alvo", mascara) == "[ALVO] e a [EMPRESA]"


def test_mascarar_trata_o_termo_como_texto_e_nao_como_regex():
    mascara = {"Invest S.A.": "[EMPRESA]", "a+b (c)": "[PESSOA_1]"}
    texto = "Invest S.A. e Invest SxAx; a+b (c) e aab c"
    assert mascarar(texto, mascara) == "[EMPRESA] e Invest SxAx; [PESSOA_1] e aab c"


def test_texto_ascii_e_texto_com_acento_trocam_igual():
    mascara = {"Exemplo Invest": "[EMPRESA]"}
    assert mascarar("exemplo INVEST!", mascara) == "[EMPRESA]!"
    assert mascarar("ção exemplo INVEST!", mascara) == "ção [EMPRESA]!"


@pytest.mark.parametrize("texto", ["", "nada a esconder"])
def test_mascarar_sem_mascara_devolve_o_texto(texto):
    assert mascarar(texto, {}) == texto
