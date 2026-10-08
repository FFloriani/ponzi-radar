"""Máscara do modo cego (Tarefa 13): os termos que identificam o alvo viram marcadores."""

from __future__ import annotations

import pytest

from radar.pendencias.mascara import mascarar, montar_mascara

HOME = (
    '<html><head><meta charset="utf-8"><title>  Exemplo   Invest — Rendimento diário </title>'
    '<meta property="og:site_name" content="Exemplo Invest Brasil"></head><body><p>oi</p></body></html>'
)


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
    assert mascara == {"Exemplo Invest — Rendimento diário": "[EMPRESA]", "Exemplo Invest Brasil": "[EMPRESA]"}


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


def test_mascarar_do_termo_mais_longo_para_o_mais_curto_sem_diferenciar_caixa():
    mascara = montar_mascara(saidas_completas(), sem_artefatos)
    texto = (
        "Acesse https://app.exemplo.com.br/login ou EXEMPLO.COM.BR. CNPJ 33.000.167/0001-01 (33000167000101). "
        "Sócio: FULANO DE TAL, da exemplo invest ltda."
    )
    assert mascarar(texto, mascara) == (
        "Acesse https://[ALVO]/login ou [ALVO]. CNPJ [CNPJ] ([CNPJ]). Sócio: [PESSOA_1], da [EMPRESA]."
    )


def test_o_marcador_nao_e_mascarado_de_novo():
    # uma empresa chamada "Alvo": o "[ALVO]" que acabou de entrar não pode virar "[[EMPRESA]]"
    mascara = {"exemplo.com.br": "[ALVO]", "Alvo": "[EMPRESA]"}
    assert mascarar("exemplo.com.br e a Alvo", mascara) == "[ALVO] e a [EMPRESA]"


def test_mascarar_trata_o_termo_como_texto_e_nao_como_regex():
    mascara = {"Invest S.A.": "[EMPRESA]"}
    assert mascarar("Invest S.A. e Invest SxAx", mascara) == "[EMPRESA] e Invest SxAx"


@pytest.mark.parametrize("texto", ["", "nada a esconder"])
def test_mascarar_sem_mascara_devolve_o_texto(texto):
    assert mascarar(texto, {}) == texto
