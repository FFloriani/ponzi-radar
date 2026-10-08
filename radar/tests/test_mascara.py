"""Máscara do modo cego (Tarefa 13): os termos que identificam o alvo viram marcadores."""

from __future__ import annotations

import pytest

from radar.pendencias.mascara import MARCADOR, mascarar, montar_mascara

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


def com_titulo(titulo: str, **saidas: dict) -> dict[str, str]:
    """A máscara de um site de domínio `exemplo.com.br`, razão social "Exemplo Invest Ltda" e esse título."""
    html = f"<html><head><title>{titulo}</title></head><body></body></html>".encode()
    base = {
        "alvo": {"dominio": "exemplo.com.br"},
        "cnpj": {"razao_social": "Exemplo Invest Ltda"},
        "captura": {"paginas": [{"html": "sha256:aa"}]},
    }
    return montar_mascara({**base, **saidas}, {"sha256:aa": html}.__getitem__)


def termos_da_empresa(mascara: dict[str, str]) -> set[str]:
    return {termo for termo, marcador in mascara.items() if marcador == "[EMPRESA]"}


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
    # o título é partido no " — ": "Exemplo Invest" tem palavra em comum com o og:site_name; "Rendimento diário", não
    assert mascara == {"Exemplo Invest": "[EMPRESA]", "Exemplo Invest Brasil": "[EMPRESA]"}


@pytest.mark.parametrize(
    ("titulo", "partes"),
    [
        ("Exemplo Invest | Exemplo Brasil", {"Exemplo Invest", "Exemplo Brasil"}),
        ("Exemplo Invest – Exemplo Rendimentos", {"Exemplo Invest", "Exemplo Rendimentos"}),
        ("Exemplo Invest — Invest Brasil", {"Exemplo Invest", "Invest Brasil"}),  # "invest" não é genérico
        ("Exemplo Invest - Exemplo", {"Exemplo Invest", "Exemplo"}),
        ("Exemplo Invest · Início", {"Exemplo Invest"}),
        ("Exemplo Invest: o melhor jeito", {"Exemplo Invest"}),
        ("A | B | Exemplo Invest | Sim", {"Exemplo Invest"}),  # partes com menos de 4 caracteres ficam de fora
        ("Pré-venda Exemplo-Invest", {"Pré-venda Exemplo-Invest"}),  # hífen colado não separa
        ("  Exemplo   Invest  ", {"Exemplo Invest"}),
        ("Bem-vindo | Home", set()),  # nenhuma palavra do site: não é o nome dele
    ],
)
def test_titulo_e_partido_nos_separadores(titulo, partes):
    assert termos_da_empresa(com_titulo(titulo)) - {"Exemplo Invest Ltda"} == partes


def test_parte_do_titulo_com_a_promessa_nao_entra():
    # a promessa no título não vira [EMPRESA]: ela tem "%" e nenhuma relação com o nome do site
    mascara = com_titulo("Exemplo Invest | Rendimento de 1,5% ao dia")
    assert termos_da_empresa(mascara) == {"Exemplo Invest Ltda", "Exemplo Invest"}
    promessa = "Rendimento de 1,5% ao dia, garantido"
    assert mascarar(promessa, mascara) == promessa


@pytest.mark.parametrize(
    ("titulo", "razao", "marca"),
    [
        ("Investimentos - Exemplo Invest", "EXEMPLO INVESTIMENTOS LTDA", "Exemplo Invest"),
        ("Participações - Exemplo", "EXEMPLO PARTICIPACOES LTDA", "Exemplo"),
        ("Serviços Digitais | Exemplo", "EXEMPLO SERVICOS DIGITAIS LTDA", "Exemplo"),
    ],
)
def test_palavra_generica_da_razao_social_nao_vira_empresa(titulo, razao, marca):
    # a razão social realista traz a palavra do setor: ela está na razão, mas não identifica ninguém
    mascara = com_titulo(titulo, cnpj={"razao_social": razao})
    assert termos_da_empresa(mascara) == {razao, marca}


@pytest.mark.parametrize(
    ("dominio", "razao", "generico"),
    [
        ("exemploinvestimentos.com.br", "EXEMPLO INVESTIMENTOS LTDA", "Investimentos"),
        ("exemplo-investimentos.com.br", "EXEMPLO INVESTIMENTOS LTDA", "Investimentos"),
        ("exemploparticipacoes.com.br", "EXEMPLO PARTICIPACOES LTDA", "Participações"),
        ("exemploservicosdigitais.com.br", "EXEMPLO SERVICOS DIGITAIS LTDA", "Serviços Digitais"),
    ],
)
def test_palavra_do_setor_dentro_do_rotulo_do_dominio_nao_vira_empresa(dominio, razao, generico):
    # o domínio concatena a marca e a palavra do setor: "investimentos" está dentro do rótulo, mas não é o nome
    titulo = f"{generico} - Exemplo Invest"
    mascara = com_titulo(titulo, alvo={"dominio": dominio}, cnpj={"razao_social": razao})
    assert termos_da_empresa(mascara) == {razao, "Exemplo Invest"}
    # sem CNPJ só o rótulo do domínio decide, e a parte genérica continua de fora
    assert generico not in termos_da_empresa(com_titulo(titulo, alvo={"dominio": dominio}, cnpj={}))


def test_parte_generica_so_entra_quando_e_o_proprio_rotulo():
    # o domínio é a palavra genérica: aí ela é o nome do site
    site = {"alvo": {"dominio": "investimentos.com.br"}, "cnpj": {}}
    assert termos_da_empresa(com_titulo("Investimentos | Home", **site)) == {"Investimentos"}
    mais = {"alvo": {"dominio": "mais-investimentos.com.br"}, "cnpj": {}}
    assert termos_da_empresa(com_titulo("Mais Investimentos", **mais)) == {"Mais Investimentos"}
    # contém o rótulo inteiro, ou está dentro dele, mas só tem palavras genéricas e não é ele: fica de fora
    assert termos_da_empresa(com_titulo("Investimentos Brasil | Home", **site)) == set()
    maior = {"alvo": {"dominio": "investimentosbrasil.com.br"}, "cnpj": {}}
    assert termos_da_empresa(com_titulo("Investimentos", **maior)) == set()
    # palavra de menos de 4 caracteres também não é marca: "BR" não faz de "Investimentos BR" o nome do site
    br = {"alvo": {"dominio": "exemploinvestimentosbr.com.br"}, "cnpj": {}}
    assert termos_da_empresa(com_titulo("Investimentos BR - Exemplo", **br)) == {"Exemplo"}


GENERICOS = """
    Ltda Eireli Sociedade Anônima Companhia Company Grupo Holding Investimento Investimentos Participação
    Participações Serviço Serviços Digital Digitais Consultoria Assessoria Gestão Negócios Capital Financeira
    Finanças Financeiro Tecnologia Tecnologias Comércio Empreendimentos Soluções Brasil Brazil Global
    Internacional Trade Trading Cripto Crypto Banco Bank Clube Club Plataforma Oficial Site Home Início Página
    Bem-vindo Bemvindo Ganhe Ganhos Renda Rendimento Rendimentos Lucro Lucros Mais Gente
""".split()


@pytest.mark.parametrize("generico", GENERICOS)
def test_termo_generico_nao_liga_o_titulo_a_razao_social(generico):
    cnpj = {"razao_social": f"Exemplo {generico} Ltda"}
    assert generico not in termos_da_empresa(com_titulo(generico, alvo={"dominio": "outro.com.br"}, cnpj=cnpj))


def test_invest_nao_e_generico():
    cnpj = {"razao_social": "Exemplo Invest Ltda"}
    assert "Invest" in termos_da_empresa(com_titulo("Invest", alvo={"dominio": "outro.com.br"}, cnpj=cnpj))


@pytest.mark.parametrize(
    ("titulo", "dominio", "marca"),
    [
        ("Exemplo Invest | Home", "exemploinvest.com.br", "Exemplo Invest"),
        ("Brais Company", "braiscompany.com", "Brais Company"),
        ("Plano Bacana - Início", "planobacana.com.br", "Plano Bacana"),
        ("Seguro-Bacana!", "seguro-bacana.com.br", "Seguro-Bacana!"),
    ],
)
def test_marca_do_titulo_entra_quando_o_dominio_a_concatena(titulo, dominio, marca):
    # sem CNPJ nem og:site_name, a única ligação do título com o site é o rótulo do domínio
    assert termos_da_empresa(com_titulo(titulo, alvo={"dominio": dominio}, cnpj={})) == {marca}


def test_digito_so_vale_quando_a_parte_e_o_rotulo_do_dominio():
    assert termos_da_empresa(com_titulo("Invest4U - Home", alvo={"dominio": "invest4u.com"}, cnpj={})) == {"Invest4U"}
    assert "Exemplo 2024" in termos_da_empresa(com_titulo("Exemplo 2024 | Exemplo Invest"))  # contém o rótulo
    # pela razão social, a parte com número não entra
    cnpj = {"razao_social": "Alfa Beta Ltda"}
    mascara = com_titulo("Alfa 2024 | Beta", alvo={"dominio": "outro.com"}, cnpj=cnpj)
    assert termos_da_empresa(mascara) == {"Alfa Beta Ltda", "Beta"}


@pytest.mark.parametrize(
    "titulo",
    [
        "Exemplo 100% | Exemplo Invest",
        "Exemplo % | Exemplo Invest",
        "Exemplo+ 5% | Exemplo Invest",
        "Exemplo% | Exemplo Invest",
    ],
)
def test_parte_do_titulo_com_porcento_nunca_entra(titulo):
    # nem quando ela contém o rótulo do domínio inteiro
    assert termos_da_empresa(com_titulo(titulo)) == {"Exemplo Invest Ltda", "Exemplo Invest"}


def test_palavra_em_comum_com_o_og_site_name_o_nome_fantasia_ou_a_razao_social():
    # cada uma das três referências basta, sozinha
    titulo = "Marca Fantasia"
    razao = {"razao_social": "Nada Haver Ltda"}
    assert termos_da_empresa(com_titulo(titulo, alvo={"dominio": "outro.com"}, cnpj=razao)) == {"Nada Haver Ltda"}
    fantasia = {**razao, "nome_fantasia": "Fantasia Real"}
    assert "Marca Fantasia" in termos_da_empresa(com_titulo(titulo, alvo={"dominio": "outro.com"}, cnpj=fantasia))
    outra_razao = {"razao_social": "Marca Registrada Ltda"}
    assert "Marca Fantasia" in termos_da_empresa(com_titulo(titulo, alvo={"dominio": "outro.com"}, cnpj=outra_razao))
    html = b'<head><title>Marca Fantasia</title><meta name="og:site_name" content="Fantasia Brasil"></head>'
    por_og = montar_mascara({"captura": {"paginas": [{"html": "sha256:aa"}]}}, {"sha256:aa": html}.__getitem__)
    assert set(por_og) == {"Marca Fantasia", "Fantasia Brasil"}


def test_palavras_genericas_do_og_site_name_nao_ligam_o_titulo():
    html = (
        b"<head><title>Ganhe mais todos os dias</title>"
        b'<meta property="og:site_name" content="Exemplo - ganhe mais com a gente"></head>'
    )
    saidas = {"alvo": {"dominio": "exemplo.com.br"}, "captura": {"paginas": [{"html": "sha256:aa"}]}}
    mascara = montar_mascara(saidas, {"sha256:aa": html}.__getitem__)
    assert termos_da_empresa(mascara) == {"Exemplo - ganhe mais com a gente"}


def test_palavra_curta_em_comum_nao_basta():
    # "alfa" tem 4 caracteres e vale; "sa" e "de" (menos de 4) não
    cnpj = {"razao_social": "Alfa de Sa Ltda"}
    assert "Banco de Sa" not in termos_da_empresa(com_titulo("Banco de Sa", cnpj=cnpj))
    assert "Alfa Ltda" in termos_da_empresa(com_titulo("Alfa Ltda", cnpj=cnpj))


def test_parte_que_esta_dentro_do_rotulo_ou_que_o_contem_entra():
    site = {"alvo": {"dominio": "exemploinvest.com.br"}, "cnpj": {}}
    assert termos_da_empresa(com_titulo("Exemplo | Invest", **site)) == {"Exemplo", "Invest"}  # pedaços do rótulo
    assert termos_da_empresa(com_titulo("Inv | Exe", **site)) == set()  # menos de 4 caracteres
    # menos de 4 caracteres colados, mesmo com 5 no total: "a.b.c" está dentro de "abcdef" mas não vale
    assert termos_da_empresa(com_titulo("A.B.C", alvo={"dominio": "abcdef.com.br"}, cnpj={})) == set()
    contem = com_titulo("Exemplo Invest Brasil Oficial | Home", alvo={"dominio": "exemploinvest.com.br"}, cnpj={})
    assert termos_da_empresa(contem) == {"Exemplo Invest Brasil Oficial"}  # contém o rótulo inteiro


@pytest.mark.parametrize(
    ("titulo", "dominio", "marca"),
    [
        ("XP Investimentos", "xp.com.br", "XP Investimentos"),
        ("BTG Pactual | Home", "btg.com.br", "BTG Pactual"),
        ("MMM Global", "mmm.com.br", "MMM Global"),
        ("Invest-XP", "xp.com.br", "Invest-XP"),
        ("B3 Investimentos", "b3.com.br", "B3 Investimentos"),
    ],
)
def test_rotulo_curto_vale_quando_e_uma_palavra_inteira_da_parte(titulo, dominio, marca):
    # com 3 caracteres ou menos o rótulo só vale como palavra inteira; aí as outras palavras podem ser genéricas
    assert termos_da_empresa(com_titulo(titulo, alvo={"dominio": dominio}, cnpj={})) == {marca}


def test_rotulo_curto_dentro_de_uma_palavra_nao_vale():
    # "ab" está dentro de "Abacate", mas não é uma palavra da parte
    assert termos_da_empresa(com_titulo("Abacate Verde", alvo={"dominio": "ab.com.br"}, cnpj={})) == set()
    assert termos_da_empresa(com_titulo("Expert Invest", alvo={"dominio": "xp.com.br"}, cnpj={})) == set()
    # a promessa continua de fora, mesmo com o rótulo como palavra
    assert termos_da_empresa(com_titulo("XP rende 1% ao dia", alvo={"dominio": "xp.com.br"}, cnpj={})) == set()


def test_rotulo_curto_dos_sans_tambem_vale():
    ct = {"sans": ["www.xp.com.br", "app.xp.com.br"]}
    assert termos_da_empresa(com_titulo("XP Investimentos", alvo={}, ct=ct, cnpj={})) == {"XP Investimentos"}


def test_rotulo_do_dominio_vem_do_registravel_e_dos_sans_sem_o_sufixo():
    # o sufixo público não conta: "museum" é o TLD de outro.museum
    sem = com_titulo("Museum Tickets", alvo={"dominio": "outro.museum"}, cnpj={})
    assert termos_da_empresa(sem) == set()
    sans = {"sans": ["www.planobacana.com.br", "planobacana.com.br"]}
    com_sans = com_titulo("Plano Bacana", alvo={}, ct=sans, cnpj={})
    assert termos_da_empresa(com_sans) == {"Plano Bacana"}
    # só o rótulo registrável: "investimentos" em investimentos.outro.com.br é um serviço do site, não o nome
    subdominio = {"sans": ["investimentos.outro.com.br"]}
    assert termos_da_empresa(com_titulo("Investimentos", alvo={}, ct=subdominio, cnpj={})) == set()


def test_rotulo_do_dominio_idn_vale_nas_duas_grafias():
    titulo = "Investimentoseguro Ação"
    assert titulo in termos_da_empresa(com_titulo(titulo, alvo={"dominio": ALVO_PUNYCODE}, cnpj={}))
    assert titulo in termos_da_empresa(com_titulo(titulo, alvo={}, ct={"sans": ["www." + ALVO_IDN]}, cnpj={}))
    # sem acento também: o rótulo é comparado dobrado
    assert "Investimentoseguro Acao" in termos_da_empresa(
        com_titulo("Investimentoseguro Acao", alvo={"dominio": ALVO_PUNYCODE}, cnpj={})
    )


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
    saidas = {
        # a palavra em comum com o título só aparece se o título foi decodificado do ISO-8859-1
        "cnpj": {"razao_social": "Promocao Investimentos Ltda"},
        "wayback_snapshot": {"paginas": [{"html": "sha256:aa"}]},
    }
    mascara = montar_mascara(saidas, {"sha256:aa": html.encode("iso-8859-1")}.__getitem__)
    assert mascara == {"Promocao Investimentos Ltda": "[EMPRESA]", "Promoção Investimentos": "[EMPRESA]"}


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


# --- CNPJs candidatos (I9) ---------------------------------------------------------------------------------


def _candidato_cnpj(valor: str) -> dict:
    return {"categoria": "cnpj", "valor": valor, "trecho": f"CNPJ {valor}", "artefato": "sha256:aa", "posicao": 0}


def test_cnpjs_candidatos_da_extracao_e_do_rdap_tem_token_proprio():
    # a P-CNPJ abre antes de o nó `cnpj` achar a empresa: os CNPJs da página e o titular do domínio já identificam
    saidas = {
        "rdap": {"cnpj_titular": "00000000000191"},
        "extracao": {"candidatos": [
            _candidato_cnpj("33000167000101"), _candidato_cnpj("00360305000104"), _candidato_cnpj("00000000000191"),
            {"categoria": "email", "valor": "a@b.com", "trecho": "a@b.com", "artefato": "x", "posicao": 0},
        ]},
    }  # fmt: skip
    assert montar_mascara(saidas, sem_artefatos) == {
        "00.000.000/0001-91": "[CNPJ_1]", "00000000000191": "[CNPJ_1]",
        "33.000.167/0001-01": "[CNPJ_2]", "33000167000101": "[CNPJ_2]",
        "00.360.305/0001-04": "[CNPJ_3]", "00360305000104": "[CNPJ_3]",
    }  # fmt: skip


def test_cnpj_confirmado_e_cnpj_e_os_outros_candidatos_ganham_numero():
    saidas = {
        **saidas_completas(),
        "extracao": {"candidatos": [_candidato_cnpj("33000167000101"), _candidato_cnpj("00360305000104")]},
    }
    mascara = montar_mascara(saidas, sem_artefatos)
    assert mascara["33000167000101"] == "[CNPJ]" and mascara["00360305000104"] == "[CNPJ_1]"
    assert mascarar("CNPJ 00.360.305/0001-04 e 33000167000101", mascara) == "CNPJ [CNPJ_1] e [CNPJ]"


def test_marcador_numerado_de_cnpj_e_marcador():
    assert MARCADOR.fullmatch("[CNPJ_12]") and MARCADOR.fullmatch("[cnpj]") and not MARCADOR.fullmatch("[CNPJ_]")
