"""Extração por regex dos candidatos de uma página (Tarefa 9)."""

from __future__ import annotations

import json
import time
from datetime import date, datetime

import pytest

from radar.config import Config, RedeConfig
from radar.custodia import Custodia
from radar.execucao import criar_contexto, criar_servicos
from radar.modelos import Candidato, ErroNo, Feito, Pulado
from radar.motor import Motor, NoBase
from radar.nos import nos_do_nucleo
from radar.nos.extracao import ExtracaoNo, _minusculas, cnpj_valido, converter_para_mes, extrair
from radar.rede import Rede

AGORA = datetime(2026, 10, 7, 12, 0, 0)


def candidatos(texto: str, categoria: str) -> list[Candidato]:
    return [c for c in extrair(texto, "sha256:x") if c.categoria == categoria]


def valores(texto: str, categoria: str) -> list[str]:
    return [c.valor for c in candidatos(texto, categoria)]


# ---------------------------------------------------------------------------- percentual


@pytest.mark.parametrize(
    "texto,valor,pct_mes",
    [
        ("Rendimento de 1,5% a.d. garantido", "1.5|dia", 56.3080),
        ("rendimento diário de 1%", "1|dia", 34.7849),
        ("até 30% a.m.", "30|mes", 30.0),
        ("200% em 24 meses", "200|24m", 4.6839),
        ("12% ao ano", "12|ano", 0.9489),
    ],
)
def test_percentuais(texto, valor, pct_mes):
    c = candidatos(texto, "percentual")[0]
    assert c.valor == valor and c.extra["pct_mes"] == pytest.approx(pct_mes, abs=1e-3)


def test_ate_marcado():
    assert candidatos("até 30% a.m.", "percentual")[0].extra["ate"] is True
    assert candidatos("Ganhe em até 45% ao mês", "percentual")[0].extra["ate"] is True
    assert candidatos("Rende máximo de 20% ao mês", "percentual")[0].extra["ate"] is True
    assert candidatos("Ganhe 30% a.m.", "percentual")[0].extra["ate"] is False
    # "até" de outra frase, longe do número, não conta
    assert candidatos("Saque até sexta. Rende 30% a.m.", "percentual")[0].extra["ate"] is False


def test_percentual_extra_so_tem_pct_mes_e_ate():
    extra = candidatos("1,5% a.d.", "percentual")[0].extra
    assert set(extra) == {"pct_mes", "ate"}
    assert isinstance(extra["pct_mes"], float) and extra["pct_mes"] == round(extra["pct_mes"], 4)


@pytest.mark.parametrize(
    "texto,valor",
    [
        ("1.5% ao dia", "1.5|dia"),  # ponto decimal
        ("1,50% a.d.", "1.5|dia"),  # sem zero supérfluo
        ("10,0% ao mês", "10|mes"),  # sem ",0"
        ("0,50% por mês", "0.5|mes"),
        ("30 % a.m.", "30|mes"),  # espaço antes do %
        ("5% mensal", "5|mes"),
        ("20% por ano", "20|ano"),
        ("20% anual", "20|ano"),
        ("2% /dia", "2|dia"),
        ("300% em 12 meses", "300|12m"),
        ("100% após 6 meses", "100|6m"),
        ("retorno diário de 2%", "2|dia"),
        ("rentabilidade mensal: 8%", "8|mes"),
        ("30%\nao dia", "30|dia"),  # número e unidade em blocos vizinhos
    ],
)
def test_percentual_formas(texto, valor):
    assert valores(texto, "percentual") == [valor]


def test_percentual_faixa_gera_os_dois_extremos():
    c = candidatos("Receba de 0,5% a 1,5% ao dia", "percentual")
    assert [x.valor for x in c] == ["0.5|dia", "1.5|dia"]


@pytest.mark.parametrize(
    "texto",
    [
        "100% seguro",  # sem período
        "50% de desconto no primeiro mês",
        "Saque diário. 100% garantido",  # o período é de outra frase
        "Atendimento diário\n100% online",  # idem, em outra linha
        "Saque diário, 100% garantido",  # idem, em outra oração
        "12345% ao dia",  # número fora da faixa
        "versão 2.5 do sistema",  # sem %
    ],
)
def test_percentual_sem_periodo_nao_vira_candidato(texto):
    assert candidatos(texto, "percentual") == []


def test_percentual_unidade_da_oracao_anterior_nao_vale_para_o_numero_seguinte():
    assert valores("Rende 0,8% ao dia útil, 100% seguro", "percentual") == ["0.8|dia"]


def test_percentual_repetido_guarda_a_primeira_ocorrencia():
    texto = "Rende 1% ao dia. Sim, 1% ao dia! Até 1% ao dia."
    c = candidatos(texto, "percentual")
    assert [x.valor for x in c] == ["1|dia"]
    assert c[0].posicao == texto.index("1%") and c[0].extra["ate"] is False


@pytest.mark.parametrize(
    "pct,periodo,esperado",
    [
        (1.5, "dia", 56.3080),
        (1, "dia", 34.7849),
        (30, "mes", 30.0),
        (200, "24m", 4.6839),
        (12, "ano", 0.9489),
        (7.25, "mes", 7.25),
        (0, "dia", 0.0),
        (100, "1m", 100.0),
    ],
)
def test_converter_para_mes(pct, periodo, esperado):
    assert converter_para_mes(pct, periodo) == esperado


def test_converter_para_mes_arredonda_a_4_casas():
    assert converter_para_mes(1.5, "dia") == round(((1 + 1.5 / 100) ** 30 - 1) * 100, 4)
    assert converter_para_mes(12, "ano") == round(((1 + 12 / 100) ** (1 / 12) - 1) * 100, 4)
    assert converter_para_mes(33.33333333, "mes") == 33.3333  # até a identidade arredonda


@pytest.mark.parametrize("periodo", ["semana", "", "0m", "m", "-1m", "1.5m", "DIA", "12"])
def test_converter_para_mes_recusa_periodo_desconhecido(periodo):
    with pytest.raises(ValueError):
        converter_para_mes(10, periodo)


@pytest.mark.parametrize("pct", [-100.5, float("nan"), float("inf"), 1e30])
def test_converter_para_mes_recusa_pct_impossivel(pct):
    with pytest.raises(ValueError):
        converter_para_mes(pct, "dia")


# ---------------------------------------------------------------------------- cnpj


def test_cnpj_valido_e_invalido():
    cats = extrair("CNPJ 33.000.167/0001-01 e 33.000.167/0001-02", "a")
    assert [c.valor for c in cats if c.categoria == "cnpj"] == ["33000167000101"]


@pytest.mark.parametrize("cnpj", ["33000167000101", "00000000000191", "60746948000112", "00360305000104"])
def test_cnpj_valido_aceita_dv_correto(cnpj):
    assert cnpj_valido(cnpj) is True


@pytest.mark.parametrize(
    "cnpj",
    [
        "33000167000102",  # DV errado
        "33000167000111",  # só o 1º DV certo
        "33000167000001",  # só o 2º DV certo
        *(str(d) * 14 for d in range(10)),  # sequências repetidas (00000000000000 tem DV "certo")
        "3300016700010",  # 13 dígitos
        "330001670001011",  # 15 dígitos
        "",
        "33.000.167/0001-01",  # formatado: o chamador manda só dígitos
        "3300016700010a",
        "٣٣٠٠٠١٦٧٠٠٠١٠١",  # dígitos árabes-índicos não valem
    ],
)
def test_cnpj_valido_recusa(cnpj):
    assert cnpj_valido(cnpj) is False


def test_cnpj_formatado_e_so_digitos():
    assert valores("CNPJ: 33.000.167/0001-01.", "cnpj") == ["33000167000101"]
    assert valores("cnpj 33000167000101", "cnpj") == ["33000167000101"]
    assert valores("33.000.167/0001-01 e 00.360.305/0001-04", "cnpj") == ["33000167000101", "00360305000104"]


def test_cnpj_repetido_na_pagina_guarda_o_primeiro():
    texto = "33.000.167/0001-01 ... 33000167000101"
    c = candidatos(texto, "cnpj")
    assert [(x.valor, x.posicao) for x in c] == [("33000167000101", 0)]


@pytest.mark.parametrize(
    "texto",
    [
        "133000167000101",  # 15 dígitos
        "3300016700010123",
        "1.33.000.167/0001-01",  # mais um grupo na frente
        "00.000.000/0000-00",  # repetido
        "11.111.111/1111-11",
        "12.345.678/0001-96",  # DV errado (o 12.345.678/0001-95 é válido)
    ],
)
def test_cnpj_nao_sai_de_dentro_de_numero_maior_nem_invalido(texto):
    assert candidatos(texto, "cnpj") == []


# ---------------------------------------------------------------------------- termos


def test_garantido_e_investimento():
    texto = "Investimento 100% GARANTIDO, sem risco. Retorno garantida. Garantia de lucro. Invista já."
    assert valores(texto, "garantido") == ["garantido", "sem risco", "garantida", "garantia de lucro"]
    assert valores("Plano de investimento com aporte mínimo.", "investimento") == ["investimento", "aporte"]
    assert valores("Seja um investidor. Investimentos seguros.", "investimento") == ["investidor", "investimentos"]


def test_contratos():
    assert valores("Sociedade em Conta de Participação", "contrato") == ["scp"]
    assert valores("firmamos contrato de mútuo com você", "contrato") == ["mutuo"]
    assert valores("aluguel de criptomoedas", "contrato") == ["locacao_cripto"]
    assert valores("Contrato SCP assinado digitalmente", "contrato") == ["scp"]
    assert valores("cessão de direitos creditórios", "contrato") == ["cessao"]
    assert valores("contrato de parceria comercial", "contrato") == ["parceria"]
    assert valores("SOCIEDADE EM CONTA DE PARTICIPAÇÃO e LOCAÇÃO DE CRIPTOATIVOS", "contrato") == [
        "scp",
        "locacao_cripto",
    ]


def test_contrato_mutuo_nao_pega_mutuo_acordo():
    assert valores("rescisão por mútuo acordo", "contrato") == []
    assert valores("o mutuário recebe o valor", "contrato") == ["mutuo"]


def test_contratos_diferentes_na_mesma_pagina_e_repetido():
    texto = "SCP. Contrato de mútuo. Sociedade em conta de participação. SCP."
    c = candidatos(texto, "contrato")
    assert [(x.valor, x.posicao) for x in c] == [("scp", 0), ("mutuo", texto.index("Contrato de mútuo"))]


def test_indicacao_saque_carencia():
    texto = (
        "Ganhe bônus de indicação até o nível 3. Taxa de saque de 5%. "
        "Carência de 12 meses, com multa de 30% no resgate."
    )
    assert valores(texto, "indicacao") == ["bônus de indicação", "nível 3"]
    assert valores(texto, "saque") == ["taxa de saque"]
    assert valores(texto, "carencia") == ["carência de 12 meses", "multa de 30%"]


def test_indicacao_outras_formas():
    texto = "Programa de afiliados: indique e ganhe! Rede multinível com comissão por indicação."
    assert valores(texto, "indicacao") == [
        "programa de afiliados",
        "indique e ganhe",
        "multinível",
        "comissão por indicação",
    ]


def test_saque_outras_formas():
    assert valores("Saque mínimo de R$ 50. Prazo de saque: 24h.", "saque") == ["saque mínimo", "prazo de saque"]
    assert valores("Os saques são liberados em D+1", "saque") == ["saques"]


def test_carencia_outras_formas():
    assert valores("Há carência. Resgate antecipado perde o bônus.", "carencia") == [
        "carência",
        "resgate antecipado",
    ]
    assert valores("período de bloqueio de 90 dias", "carencia") == ["período de bloqueio"]


def test_historico():
    assert valores("histórico de rentabilidade mês a mês", "historico_rentabilidade") == [
        "histórico de rentabilidade"
    ]
    assert valores("Veja a rentabilidade histórica do fundo", "historico_rentabilidade") == [
        "rentabilidade histórica"
    ]
    assert valores("rentabilidade mês a mês", "historico_rentabilidade") == ["rentabilidade mês a mês"]


def test_token_e_pix():
    assert valores("Compre o TOKEN da casa, moeda própria, airdrop e staking", "token") == [
        "token",
        "moeda própria",
        "airdrop",
        "staking",
    ]
    assert valores("Lançamento da ICO. Ele tinha ido embora.", "token") == ["ico"]
    assert valores("Pague com Pix ou chave Pix aleatória; veja o pixel", "pix") == ["pix", "chave pix"]


def test_termos_ignoram_caixa_e_espacos_extras():
    assert valores("TAXA   DE   SAQUE", "saque") == ["taxa de saque"]
    assert valores("Garantido GARANTIDO garantido", "garantido") == ["garantido"]


def test_termos_nao_pegam_pedaco_de_palavra():
    assert valores("reaportes e desinvestimentos", "investimento") == []
    assert valores("nãogarantido", "garantido") == []


def test_termos_com_maiusculas_acentuadas():
    assert valores("BÔNUS DE INDICAÇÃO e CARÊNCIA DE 12 MESES", "indicacao") == ["bônus de indicação"]
    assert valores("BÔNUS DE INDICAÇÃO e CARÊNCIA DE 12 MESES", "carencia") == ["carência de 12 meses"]
    assert valores("RENDIMENTO MENSAL DE 8%", "percentual") == ["8|mes"]


def test_minusculas_nao_muda_o_tamanho():
    todos = "".join(map(chr, range(0x110000)))
    assert len(_minusculas(todos)) == len(todos)


def test_posicao_e_trecho_valem_no_texto_original_com_i_pontuado():
    # "İ".lower() tem 2 caracteres em Python: o índice não pode deslocar
    texto = "İİİ Pix e Investimento İ"
    pix, investimento = extrair(texto, "a")
    assert (pix.categoria, pix.posicao) == ("pix", 4)
    assert texto[investimento.posicao :].startswith("Investimento")
    assert pix.trecho == texto


def test_frase_nao_atravessa_quebra_de_linha():
    assert valores("Taxa de\nsaque", "saque") == ["saque"]  # só o "saque" solto


# ---------------------------------------------------------------------------- carteiras e contatos

BTC_BECH32 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
BTC_TAPROOT = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
BTC_LEGADO = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
BTC_P2SH = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
ETH = "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"
TRON = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def test_carteiras_e_contatos():
    texto = (
        f"Deposite em {BTC_BECH32} ou {ETH} ou {TRON}. "
        "Fale em wa.me/5511999998888 ou t.me/canal_vip. "
        "Veja instagram.com/siteoficial. Escreva para contato@site.com.br."
    )
    cats = extrair(texto, "sha256:x")
    por_categoria = {c.categoria: c for c in cats}
    assert {c.categoria for c in cats} == {"carteira", "whatsapp", "telegram", "rede_social", "email"}
    assert [(c.valor, c.extra) for c in cats if c.categoria == "carteira"] == [
        (BTC_BECH32, {"rede": "btc"}),
        (ETH, {"rede": "eth"}),
        (TRON, {"rede": "tron"}),
    ]
    assert por_categoria["whatsapp"].valor == "wa.me/5511999998888"
    assert por_categoria["telegram"].valor == "t.me/canal_vip"
    assert por_categoria["rede_social"].valor == "instagram.com/siteoficial"
    assert por_categoria["email"].valor == "contato@site.com.br"


@pytest.mark.parametrize(
    "endereco,rede",
    [
        (BTC_BECH32, "btc"),
        (BTC_BECH32.upper(), "btc"),
        (BTC_TAPROOT, "btc"),
        (BTC_LEGADO, "btc"),
        (BTC_P2SH, "btc"),
        (ETH, "eth"),
        (ETH.lower(), "eth"),
        (TRON, "tron"),
    ],
)
def test_carteira_por_rede_guarda_a_caixa_original(endereco, rede):
    c = candidatos(f"Envie para {endereco} agora.", "carteira")
    assert [(x.valor, x.extra["rede"]) for x in c] == [(endereco, rede)]


@pytest.mark.parametrize(
    "texto",
    [
        "bc1qshort",
        f"x{BTC_BECH32}",  # colado numa palavra
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb",  # checksum base58 errado
        "1" * 34,  # forma de endereço legado sem checksum
        "0x" + "a" * 39,  # curto
        "0x" + "a" * 41,  # longo demais
        "0x" + "ab12" * 16,  # hash de transação (64 hex)
        "0x" + "g" * 40,  # não é hex
        "T" + "O" * 33,  # "O" fora do alfabeto base58
        "T" + "1" * 32,  # 33 caracteres
        "T" + "1" * 34,  # 35 caracteres
        f"a{TRON}",  # colado numa palavra
    ],
)
def test_carteira_recusa(texto):
    assert candidatos(texto, "carteira") == []


def test_carteira_repetida_guarda_a_primeira():
    c = candidatos(f"{ETH} e de novo {ETH}", "carteira")
    assert [(x.valor, x.posicao) for x in c] == [(ETH, 0)]


def test_whatsapp_formas():
    texto = (
        "https://wa.me/5511999998888 "
        "https://api.whatsapp.com/send?phone=5511999998888&text=Ola "
        "https://api.whatsapp.com/send/?text=oi&phone=5521988887777 "
        "https://chat.whatsapp.com/Ab12Cd34Ef56 "
        "wa.me/message/XYZ123"
    )
    assert valores(texto, "whatsapp") == [
        "wa.me/5511999998888",  # as duas formas do mesmo número viram um só
        "wa.me/5521988887777",
        "chat.whatsapp.com/Ab12Cd34Ef56",  # o código do convite não muda de caixa
        "wa.me/message/XYZ123",
    ]


def test_telegram_formas():
    texto = "https://t.me/Canal_Vip, telegram.me/outro_canal e t.me/+AbCdEf123 e t.me/joinchat/XyZ98 e t.me/canal_vip"
    assert valores(texto, "telegram") == [
        "t.me/canal_vip",  # o @usuario não diferencia a caixa: Canal_Vip e canal_vip são o mesmo
        "t.me/outro_canal",
        "t.me/+AbCdEf123",  # o código do convite diferencia
        "t.me/joinchat/XyZ98",
    ]
    assert valores("set.me/abc cat.me/abcde", "telegram") == []


def test_rede_social_formas():
    texto = (
        "https://www.instagram.com/Site.Oficial/ "
        "facebook.com/pagina.oficial, "
        "https://m.youtube.com/@canal "
        "tiktok.com/@site "
        "https://x.com/siteoficial "
        "twitter.com/site "
        "linkedin.com/company/site-sa "
        "discord.gg/abc123 "
    )
    assert valores(texto, "rede_social") == [
        "instagram.com/Site.Oficial",
        "facebook.com/pagina.oficial",
        "youtube.com/@canal",
        "tiktok.com/@site",
        "x.com/siteoficial",
        "twitter.com/site",
        "linkedin.com/company/site-sa",
        "discord.gg/abc123",
    ]
    assert valores("max.com/filmes e instagram.com/ e box.x.com", "rede_social") == []


def test_email_formas():
    texto = "Fale: Contato@Site.com.br, suporte+vip@sub.exemplo.com; (a.b_c-d@x.io) logo@2x.png"
    assert valores(texto, "email") == ["contato@site.com.br", "suporte+vip@sub.exemplo.com", "a.b_c-d@x.io"]
    assert valores("sem@dominio e @mencao e a@b.c", "email") == []


# ---------------------------------------------------------------------------- trecho e posição


def test_trecho_e_posicao():
    achado = "33.000.167/0001-01"
    antes, depois = "a" * 300, "z" * 300
    texto = f"{antes} {achado} {depois}"
    c = candidatos(texto, "cnpj")[0]
    assert c.posicao == texto.index(achado)
    assert texto[c.posicao : c.posicao + len(achado)] == achado
    assert achado in c.trecho
    assert c.trecho == texto[c.posicao - 120 : c.posicao + len(achado) + 120]
    assert len(c.trecho) == 120 + len(achado) + 120


def test_trecho_corta_nos_limites_do_texto():
    texto = "CNPJ 33.000.167/0001-01 fim"
    c = candidatos(texto, "cnpj")[0]
    assert c.trecho == texto
    inicio = "33.000.167/0001-01" + "z" * 300
    assert candidatos(inicio, "cnpj")[0].trecho == inicio[: 18 + 120]
    fim = "a" * 300 + "33.000.167/0001-01"
    assert candidatos(fim, "cnpj")[0].trecho == fim[300 - 120 :]


def test_trecho_de_toda_categoria_e_um_recorte_do_texto_que_comeca_120_antes():
    preenchimento = "lorem ipsum dolor sit amet " * 15
    texto = (
        f"{preenchimento}Rende 1,5% ao dia, garantido. {preenchimento}"
        f"bônus de indicação nível 3, taxa de saque, carência de 12 meses. {preenchimento}"
        f"{BTC_BECH32} {ETH} {TRON} {preenchimento}wa.me/5511999998888 t.me/canal_vip "
        f"instagram.com/site contato@site.com.br 33.000.167/0001-01 Pix token {preenchimento}"
    )
    cs = extrair(texto, "sha256:abc")
    assert {c.categoria for c in cs} >= {
        "percentual", "garantido", "indicacao", "saque", "carencia", "carteira", "whatsapp",
        "telegram", "rede_social", "email", "cnpj", "pix", "token",
    }
    for c in cs:
        assert c.artefato == "sha256:abc"
        assert c.trecho in texto
        # o trecho é o recorte [posicao - 120, fim do achado + 120] do texto
        inicio = max(0, c.posicao - 120)
        assert texto.startswith(c.trecho, inicio), c
        assert c.posicao < len(texto) and 0 <= c.posicao - inicio <= 120
    # a posição é o índice do início do achado
    por_categoria = {c.categoria: c for c in cs}
    for categoria, achado in [
        ("percentual", "1,5% ao dia"),
        ("cnpj", "33.000.167/0001-01"),
        ("email", "contato@site.com.br"),
    ]:
        c = por_categoria[categoria]
        assert texto[c.posicao : c.posicao + len(achado)] == achado
        assert c.trecho == texto[c.posicao - 120 : c.posicao + len(achado) + 120]


def test_resultado_ordenado_por_posicao():
    texto = "Pix garantido; token e saque; 33.000.167/0001-01"
    posicoes = [c.posicao for c in extrair(texto, "a")]
    assert posicoes == sorted(posicoes)


def test_texto_sem_nada_nao_gera_candidato():
    assert extrair("", "a") == []
    assert extrair("Bem-vindo ao nosso site institucional. Veja o catálogo de produtos.", "a") == []


def test_extrair_devolve_candidatos_do_modelo():
    c = extrair("rendimento diário de 1%", "sha256:y")[0]
    assert isinstance(c, Candidato)
    assert c.model_dump()["extra"]["pct_mes"] == pytest.approx(34.7849, abs=1e-3)


# ---------------------------------------------------------------------------- texto hostil (R-T9-redos)

_VARIADO = (
    "Rendimento de 1,5% a.d. garantido, bônus de indicação até o nível 3, taxa de saque e carência de 12 meses. "
    "CNPJ 33.000.167/0001-01, SCP e contrato de mútuo. Fale em wa.me/5511999998888, t.me/canal_vip, "
    "instagram.com/site e contato@site.com.br. Pague via Pix. Investimento com token próprio. "
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit 123.456.789/0001-00 0x1234 bc1 T9 1.5 2,5 \n"
)


def _hostil_grande() -> str:
    corpo = _VARIADO * (2_000_000 // len(_VARIADO) + 1)
    return corpo[:2_000_000]


PATOLOGICOS = {
    "digitos": "1" * 100_000,
    "percentuais": "%" * 100_000,
    "pontos": "a." * 100_000,
    "digitos_com_percentual": "1%" * 50_000,
    "decimais": "1,1" * 40_000,
    "cnpj_parcial": "12.345.678/" * 20_000,
    "cnpj_colado": "33.000.167/0001-01" * 8_000,
    "bech32": "bc1" * 50_000,
    "bech32_longo": "bc1" + "q" * 100_000,
    "hex": "0x" * 50_000,
    "hex_longo": "0x" + "a" * 100_000,
    "tron": "T" * 100_000,
    "tron_repetido": "T" + "1" * 33 + "T" * 50_000,
    "arrobas": "@" * 100_000,
    "emails_vazios": "a@" * 50_000,
    "email_pontilhado": "a@" + "a." * 50_000,
    "local_longo": "a" * 100_000 + "@x.com",
    "wa": "wa.me/" * 30_000,
    "telegram": "t.me/" * 30_000,
    "social": "instagram.com/" * 10_000,
    "espacos": "a" + " " * 100_000 + "garantido",
    "hifens": "-" * 100_000,
    "quebras": "\n" * 100_000,
    "palavra_longa": "garantid" * 20_000,
    "frase_repetida": "taxa de " * 20_000,
    "ate": "até " * 50_000,
    "carencia": "carência de " * 20_000,
    "multa": "multa de 3" * 20_000,
    "acentos": "ção" * 60_000,
    "unicode": "İ" * 50_000 + "ǅ" * 50_000,
}


def test_texto_hostil_grande_termina_rapido():
    texto = _hostil_grande() + "".join(PATOLOGICOS.values())
    assert len(texto) > 2_000_000
    inicio = time.perf_counter()
    cs = extrair(texto, "sha256:x")
    assert time.perf_counter() - inicio < 5
    # e continua achando o que importa
    assert any(c.categoria == "cnpj" and c.valor == "33000167000101" for c in cs)
    assert any(c.categoria == "percentual" and c.valor == "1.5|dia" for c in cs)


@pytest.mark.parametrize("nome", sorted(PATOLOGICOS))
def test_sequencia_patologica_termina_rapido(nome):
    texto = PATOLOGICOS[nome]
    inicio = time.perf_counter()
    extrair(texto, "sha256:x")
    assert time.perf_counter() - inicio < 5


REPETIDOS = {
    "termo": "garantido ",
    "sigla": "scp ",
    "pix": "pix ",
    "percentual": "1%a.d. ",
    "percentual_com_unidade_antes": "diário 1% ",
    "faixa": "1% a 2% ao dia ",
    "ate": "até 1% a.m. ",
    "email": "a@b.co ",
    "cnpj": "33.000.167/0001-01 ",
    "btc_legado": "1" + "2" * 33 + " ",  # forma de endereço legado, checksum errado
    "tron": "T" + "1" * 33 + " ",
    "whatsapp": "wa.me/5511 ",
    "rede_social": "x.com/a ",
    "nivel": "nível 3 ",
}


@pytest.mark.parametrize("nome", sorted(REPETIDOS))
def test_achado_curto_repetido_e_linear(nome):
    unidade = REPETIDOS[nome]
    texto = unidade * (400_000 // len(unidade))
    inicio = time.perf_counter()
    extrair(texto, "sha256:x")
    assert time.perf_counter() - inicio < 5


def test_texto_hostil_deduplica_e_nao_explode_o_resultado():
    texto = "garantido " * 200_000
    cs = extrair(texto, "sha256:x")
    assert [(c.categoria, c.valor, c.posicao) for c in cs] == [("garantido", "garantido", 0)]


# ---------------------------------------------------------------------------- nó


def guardar_texto(custodia: Custodia, texto: str) -> str:
    return custodia.guardar(texto.encode("utf-8"), "txt", tipo="texto", origem="https://alvo.com.br/")


@pytest.fixture
async def serv(tmp_path):
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede)
    try:
        yield criar_servicos(config, tmp_path, rede)
    finally:
        await rede.fechar()


@pytest.fixture
def ctx(tmp_path):
    return criar_contexto("https://alvo.com.br/", date(2026, 10, 7), "captura", False, tmp_path, AGORA)


def pagina(serv, url: str, texto: str) -> dict:
    return {"url": url, "status": 200, "texto": guardar_texto(serv.custodia, texto)}


def test_atributos_do_no():
    no = ExtracaoNo()
    assert no.nome == "extracao"
    assert no.exige_um_de == ("captura", "wayback_snapshot")
    assert no.opcionais == ("captura", "wayback_snapshot")
    assert no.entradas == ()
    assert no.as_of == "exato" and no.toca_alvo is False
    assert no.saidas == ("candidatos", "fonte")


def test_no_esta_no_nucleo_depois_do_wayback_snapshot():
    nomes = [n.nome for n in nos_do_nucleo()]
    assert nomes[-2:] == ["wayback_snapshot", "extracao"]
    assert isinstance(nos_do_nucleo()[-1], ExtracaoNo)


async def test_no_usa_a_captura(ctx, serv):
    home = pagina(serv, "https://alvo.com.br/", "Rendimento de 1,5% a.d. garantido")
    sub = pagina(serv, "https://alvo.com.br/termos", "Carência de 12 meses. CNPJ 33.000.167/0001-01")
    entradas = {"captura": {"paginas": [home, sub], "terceiros": [], "bloqueada": False, "falhas": []}}
    resultado = await ExtracaoNo().executar(ctx, entradas, {}, serv)
    assert isinstance(resultado, Feito)
    assert resultado.saidas["fonte"] == "captura"
    cs = resultado.saidas["candidatos"]
    assert [(c["categoria"], c["valor"], c["artefato"]) for c in cs] == [
        ("percentual", "1.5|dia", home["texto"]),
        ("garantido", "garantido", home["texto"]),
        ("carencia", "carência de 12 meses", sub["texto"]),
        ("cnpj", "33000167000101", sub["texto"]),
    ]
    assert cs[0]["posicao"] == len("Rendimento de ") and cs[0]["extra"]["ate"] is False
    # o que o nó devolve é o que os dependentes recebem: dicionários do Candidato, serializáveis em JSON
    assert json.loads(json.dumps(cs)) == cs
    assert [Candidato.model_validate(c) for c in cs][0].categoria == "percentual"


async def test_no_usa_o_wayback_quando_ele_esta_nas_entradas(ctx, serv):
    wayback = {
        "paginas": [
            {"url": "http://alvo.com.br/", "timestamp": "20190606235936", "texto": guardar_texto(serv.custodia, "SCP")}
        ],
        "falhas": [],
        "truncado": False,
    }
    captura = {"paginas": [pagina(serv, "https://alvo.com.br/", "contrato de mútuo")], "bloqueada": False}
    resultado = await ExtracaoNo().executar(ctx, {"captura": captura, "wayback_snapshot": wayback}, {}, serv)
    assert resultado.saidas["fonte"] == "wayback_snapshot"
    assert [c["valor"] for c in resultado.saidas["candidatos"]] == ["scp"]


async def test_no_cai_no_wayback_quando_a_captura_foi_bloqueada(ctx, serv):
    bloqueada = {"paginas": [{"url": "https://alvo.com.br/", "status": 403, "screenshot": "sha256:" + "0" * 64}],
                 "terceiros": [], "bloqueada": True, "falhas": []}
    wayback = {"paginas": [pagina(serv, "http://alvo.com.br/", "Pix")], "falhas": [], "truncado": False}
    resultado = await ExtracaoNo().executar(ctx, {"captura": bloqueada, "wayback_snapshot": wayback}, {}, serv)
    assert resultado.saidas["fonte"] == "wayback_snapshot"
    assert [c["valor"] for c in resultado.saidas["candidatos"]] == ["pix"]


async def test_no_ignora_a_captura_bloqueada_mesmo_com_texto(ctx, serv):
    entradas = {"captura": {"paginas": [pagina(serv, "https://alvo.com.br/", "Pix")], "bloqueada": True}}
    with pytest.raises(ErroNo) as erro:
        await ExtracaoNo().executar(ctx, entradas, {}, serv)
    assert erro.value.mensagem == "sem texto de página" and erro.value.permanente is True


async def test_no_cai_na_captura_se_o_wayback_nao_trouxe_texto(ctx, serv):
    wayback = {"paginas": [], "falhas": [], "truncado": False}
    captura = {"paginas": [pagina(serv, "https://alvo.com.br/", "Pix")], "bloqueada": False}
    resultado = await ExtracaoNo().executar(ctx, {"captura": captura, "wayback_snapshot": wayback}, {}, serv)
    assert resultado.saidas["fonte"] == "captura"


@pytest.mark.parametrize(
    "entradas",
    [
        {},
        {"captura": {"paginas": [], "bloqueada": False}},
        {"captura": {"paginas": [{"url": "https://alvo.com.br/", "status": 403}], "bloqueada": True}},
        {"wayback_snapshot": {"paginas": [], "falhas": [], "truncado": False}},
        {"wayback_snapshot": {"paginas": [{"url": "http://alvo.com.br/"}], "falhas": []}},
    ],
)
async def test_no_sem_texto_de_pagina_e_erro_permanente(ctx, serv, entradas):
    with pytest.raises(ErroNo) as erro:
        await ExtracaoNo().executar(ctx, entradas, {}, serv)
    assert erro.value.mensagem == "sem texto de página" and erro.value.permanente is True


async def test_no_mantem_o_mesmo_achado_em_paginas_diferentes(ctx, serv):
    p1 = pagina(serv, "https://alvo.com.br/", "Pix aqui. Pix ali.")
    p2 = pagina(serv, "https://alvo.com.br/termos", "Também Pix. xx Pix")
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p1, p2], "bloqueada": False}}, {}, serv)
    cs = resultado.saidas["candidatos"]
    assert [(c["valor"], c["artefato"], c["posicao"]) for c in cs] == [
        ("pix", p1["texto"], 0),
        ("pix", p2["texto"], len("Também ")),
    ]


async def test_no_pagina_sem_achado_e_pagina_vazia_nao_derrubam(ctx, serv):
    p1 = pagina(serv, "https://alvo.com.br/", "")
    p2 = pagina(serv, "https://alvo.com.br/a", "nada de interessante")
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p1, p2], "bloqueada": False}}, {}, serv)
    assert resultado.saidas == {"candidatos": [], "fonte": "captura"}


async def test_no_le_texto_utf8_com_byte_invalido(ctx, serv):
    ref = serv.custodia.guardar(b"Pix \xff\xfe garantido", "txt", tipo="texto", origem="x")
    entradas = {"captura": {"paginas": [{"url": "u", "texto": ref}], "bloqueada": False}}
    resultado = await ExtracaoNo().executar(ctx, entradas, {}, serv)
    assert [c["valor"] for c in resultado.saidas["candidatos"]] == ["pix", "garantido"]


async def test_no_artefato_ausente_da_custodia_levanta(ctx, serv):
    entradas = {"captura": {"paginas": [{"url": "u", "texto": "sha256:" + "0" * 64}], "bloqueada": False}}
    with pytest.raises(FileNotFoundError):
        await ExtracaoNo().executar(ctx, entradas, {}, serv)


# --- dentro do motor: as dependências, a normalização das saídas e a retomada


class _Fixo(NoBase):
    """Nó de mentira que devolve sempre o mesmo resultado (ou levanta, se for ErroNo)."""

    def __init__(self, nome: str, resultado):
        super().__init__(nome=nome)
        self._resultado = resultado

    async def executar(self, ctx, entradas, respostas, s):
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return self._resultado


async def _rodar(ctx, serv, captura, wayback) -> Motor:
    motor = Motor(ctx, [_Fixo("captura", captura), _Fixo("wayback_snapshot", wayback), ExtracaoNo()], serv)
    await motor.executar()
    return motor


async def test_no_no_motor_com_captura_feita(ctx, serv):
    home = pagina(serv, "https://alvo.com.br/", "Rende 2% ao dia, até 30% a.m. CNPJ 33.000.167/0001-01")
    motor = await _rodar(ctx, serv, Feito({"paginas": [home], "bloqueada": False}), Pulado("captura ok"))
    assert motor.status() == {"captura": "feito", "wayback_snapshot": "pulado", "extracao": "feito"}
    saidas = motor.saidas("extracao")
    assert saidas["fonte"] == "captura"
    assert [c["valor"] for c in saidas["candidatos"]] == ["2|dia", "30|mes", "33000167000101"]
    assert saidas["candidatos"][1]["extra"] == {"pct_mes": 30.0, "ate": True}
    gravado = json.loads((ctx.pasta / "evidencias.json").read_text(encoding="utf-8"))
    assert gravado["extracao"] == saidas


async def test_no_no_motor_com_captura_em_erro_e_wayback_feito(ctx, serv):
    wayback = Feito({"paginas": [pagina(serv, "http://alvo.com.br/", "SCP")], "falhas": [], "truncado": False})
    motor = await _rodar(ctx, serv, ErroNo("captura falhou: HTTP 503", permanente=False), wayback)
    assert motor.status() == {"captura": "erro", "wayback_snapshot": "feito", "extracao": "feito"}
    assert motor.saidas("extracao")["fonte"] == "wayback_snapshot"


async def test_no_no_motor_sem_nenhuma_fonte_fica_bloqueado(ctx, serv):
    motor = await _rodar(ctx, serv, Pulado("modo_contato=nenhum"), ErroNo("sem snapshot", permanente=True))
    assert motor.status() == {"captura": "pulado", "wayback_snapshot": "erro", "extracao": "bloqueado"}


async def test_no_no_motor_captura_bloqueada_sem_wayback_e_erro(ctx, serv):
    bloqueada = Feito({"paginas": [{"url": "https://alvo.com.br/", "status": 403}], "bloqueada": True})
    motor = await _rodar(ctx, serv, bloqueada, Pulado("captura ok"))
    assert motor.status()["extracao"] == "erro"
    estado = json.loads((ctx.pasta / "estado.json").read_text(encoding="utf-8"))
    assert estado["nos"]["extracao"]["motivo"] == "sem texto de página"
