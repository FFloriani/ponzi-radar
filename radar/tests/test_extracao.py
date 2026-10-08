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
from radar.cnpj_util import normalizar_cnpj
from radar.nos import extracao as modulo_extracao
from radar.nos.extracao import (
    TETO_POR_CATEGORIA,
    ExtracaoNo,
    _minusculas,
    cnpj_valido,
    converter_para_mes,
    extrair,
    extrair_atributos,
)
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


@pytest.mark.parametrize(
    "texto,valor",
    [
        ("1% de lucro diário", "1|dia"),
        ("1,2% de rendimento diário", "1.2|dia"),
        ("1% de rentabilidade diária", "1|dia"),
        ("5% de comissão mensal", "5|mes"),
        ("2% de ganhos anuais", "2|ano"),
        ("5% de lucro em 24 meses", "5|24m"),
        ("0,5% a cada dia", "0.5|dia"),
        ("2,5% a cada 24 horas", "2.5|dia"),
        ("1% dia", "1|dia"),
        ("10% mês", "10|mes"),
        ("3% am", "3|mes"),
        ("3% a/m", "3|mes"),
        ("3% a.m", "3|mes"),
        ("4% ad", "4|dia"),
        ("9% aa", "9|ano"),
        ("5% por semana", "5|semana"),
        ("5% semanal", "5|semana"),
        ("rendimento semanal de 7%", "7|semana"),
        ("10% a cada 7 dias", "10|semana"),
        ("10% a cada semana", "10|semana"),
        ("2% a cada 1 dia", "2|dia"),
        ("8% a cada 30 dias", "8|mes"),
        ("6% a cada 15 dias", "6|15d"),
        ("45% em 30 dias", "45|30d"),  # o prazo fica como está escrito: 30d, não mes
        ("20% em 7 dias", "20|7d"),
        ("100% em até 90 dias", "100|90d"),
    ],
)
def test_percentual_formas_comuns_de_promessa(texto, valor):
    assert valores(texto, "percentual") == [valor]


def test_percentual_em_n_dias_converte_para_o_mes():
    c = candidatos("45% em 30 dias", "percentual")[0]
    assert (c.valor, c.extra["pct_mes"]) == ("45|30d", 45.0)
    c = candidatos("20% em 7 dias", "percentual")[0]
    assert c.extra["pct_mes"] == converter_para_mes(20, "semana")
    c = candidatos("5% por semana", "percentual")[0]
    assert c.extra["pct_mes"] == round(((1 + 5 / 100) ** (30 / 7) - 1) * 100, 4)


@pytest.mark.parametrize(
    "texto",
    [
        "10% de comissão (nível 1)",  # a unidade não vem junto
        "5% de desconto no mês",
        "5% de taxa diária de saque, 2% de lucro",  # "taxa" não é um dos substantivos
        "30% adicional",  # "ad" colado em palavra
        "30% amanhã",
        "100% dias úteis",
    ],
)
def test_percentual_formas_novas_nao_geram_falso_positivo(texto):
    assert candidatos(texto, "percentual") == []


@pytest.mark.parametrize(
    "texto,valor",
    [
        ("Rentabilidade de 1.000% ao ano", "1000|ano"),
        ("1.5% a.d.", "1.5|dia"),
        ("10.000,00% ao mês", "10000|mes"),
        ("1.000,5% a.d.", "1000.5|dia"),
        ("1.000.000% em 12 meses", "1000000|12m"),
        ("1.500% ao mês", "1500|mes"),  # três dígitos depois do ponto: milhar
        ("0.500% ao mês", "0.5|mes"),  # zero à esquerda: decimal
        ("12.34% ao mês", "12.34|mes"),
        ("2,50% a.m.", "2.5|mes"),
    ],
)
def test_percentual_milhar_e_decimal(texto, valor):
    assert valores(texto, "percentual") == [valor]


def test_percentual_milhar_converte_com_o_valor_certo():
    c = candidatos("Rentabilidade de 1.000% ao ano", "percentual")[0]
    assert c.extra["pct_mes"] == converter_para_mes(1000, "ano")


@pytest.mark.parametrize(
    "absurdo",
    [
        "10.000.000.000.000% ao dia",
        "999.999.999.999.999% ao dia",
        "rendimento diário de 10.000.000.000.000%",  # a unidade vem antes
        "999.999.999.999.999% a cada 24 horas",
    ],
)
def test_percentual_grande_demais_e_descartado_e_o_resto_segue(absurdo):
    # (1 + p/100) ** 30 estoura o float: `converter_para_mes` levanta ValueError
    with pytest.raises(ValueError):
        converter_para_mes(1e15, "dia")
    assert candidatos(absurdo, "percentual") == []
    texto = f"Rende 1% ao dia e {absurdo}. CNPJ 33.000.167/0001-01 e 2% ao mês, garantido."
    cs = extrair(texto, "a")
    assert [c.valor for c in cs if c.categoria == "percentual"] == ["1|dia", "2|mes"]
    assert {c.categoria for c in cs} >= {"cnpj", "garantido"}


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


def test_converter_para_mes_semana_e_dias():
    assert converter_para_mes(5, "semana") == round(((1 + 5 / 100) ** (30 / 7) - 1) * 100, 4)
    assert converter_para_mes(10, "7d") == converter_para_mes(10, "semana")
    assert converter_para_mes(1.5, "1d") == converter_para_mes(1.5, "dia")
    assert converter_para_mes(45, "30d") == 45.0  # 30 dias é um mês
    assert converter_para_mes(20, "15d") == 44.0  # 1,2 ao quadrado


@pytest.mark.parametrize(
    "periodo", ["semanas", "SEMANA", "", "0m", "m", "-1m", "1.5m", "DIA", "12", "0d", "d", "-1d", "1.5d", "7D"]
)
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


CNPJ_ALFA = "12ABC34501DE35"  # o exemplo da Receita (IN RFB 2.229/2024): base 12ABC34501DE, DV 35


@pytest.mark.parametrize("cnpj", [CNPJ_ALFA, "AB1C2D3E4F5G13", "Z9Y8X7W6V5U429", "0A0A0A0A0A0A90"])
def test_cnpj_alfanumerico_valido(cnpj):
    assert cnpj_valido(cnpj) is True


@pytest.mark.parametrize(
    "cnpj",
    [
        "12ABC34501DE34",  # DV errado
        "12ABC34501DE53",  # DVs trocados
        "12ABC34501DEAB",  # os dois últimos têm de ser dígitos
        "12abc34501de35",  # só maiúsculas: quem normaliza é o chamador
        "12ABC34501DE3",  # 13
        "12ABC34501DE355",  # 15
        "12.ABC.345/01DE-35",  # com pontuação
        "12ABC34501D_35",
        "12ABC34501DÉ35",
        "ÂBC12345678935",
    ],
)
def test_cnpj_alfanumerico_recusa(cnpj):
    assert cnpj_valido(cnpj) is False


def test_cnpj_alfanumerico_na_pagina():
    assert valores("CNPJ 12.ABC.345/01DE-35 - Empresa", "cnpj") == [CNPJ_ALFA]
    assert valores("cnpj 12ABC34501DE35.", "cnpj") == [CNPJ_ALFA]
    assert valores("CNPJ: 12.abc.345/01de-35", "cnpj") == [CNPJ_ALFA]  # entrada em minúsculas, valor em maiúsculas
    assert valores("12ABC34501DE35 e 12.ABC.345/01DE-35", "cnpj") == [CNPJ_ALFA]
    assert valores("33.000.167/0001-01 e 12ABC34501DE35", "cnpj") == ["33000167000101", CNPJ_ALFA]


def test_cnpj_alfanumerico_posicao_e_trecho():
    texto = "Sede: CNPJ 12.ABC.345/01DE-35."
    (c,) = candidatos(texto, "cnpj")
    assert texto[c.posicao :].startswith("12.ABC.345/01DE-35")
    assert c.trecho == texto


@pytest.mark.parametrize(
    "texto",
    [
        "12.ABC.345/01DE-34",  # DV errado
        "12ABC34501DEAB",  # os dois últimos não são dígitos
        "CNPJ12ABC34501DE35",  # colado em palavra
        "12ABC34501DE35X",
        "X12ABC34501DE35",
        "12ABC34501DE355",  # 15
        "pedido123456ab",  # palavra de 14 que não passa no DV
        "AAAAAAAAAAAA00",
    ],
)
def test_cnpj_alfanumerico_nao_sai_de_onde_nao_deve(texto):
    assert candidatos(texto, "cnpj") == []


def test_cnpj_numerico_colado_em_palavra_continua_valendo():
    assert valores("CNPJ33.000.167/0001-01", "cnpj") == ["33000167000101"]


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("33.000.167/0001-01", "33000167000101"),
        ("33000167000101", "33000167000101"),
        (" 33.000.167/0001-01 ", "33000167000101"),
        ("12.ABC.345/01DE-35", CNPJ_ALFA),
        ("12.abc.345/01de-35", CNPJ_ALFA),
        ("12abc34501de35", CNPJ_ALFA),
        ("33.000.167/0001-02", None),
        ("12.ABC.345/01DE-34", None),
        ("123.456.789-09", None),  # CPF
        ("00.000.000/0000-00", None),
        ("", None),
        ("abc", None),
        ("12ABC34501DE35!", None),
        ("٣٣٠٠٠١٦٧٠٠٠١٠١", None),
    ],
)
def test_normalizar_cnpj(entrada, esperado):
    assert normalizar_cnpj(entrada) == esperado


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


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Veja os rendimentos mês a mês", ["mês a mês"]),
        ("resultados mês a mês de 2025", ["mês a mês"]),
        ("Confira o histórico de resultados", ["histórico de resultados"]),
        ("histórico de performance", ["histórico de performance"]),
        ("Histórico de Operações", ["histórico de operações"]),
        ("histórico de rendimentos", ["histórico de rendimentos"]),
        ("tabela de rentabilidade 2025: Jan 12,3% Fev 12,1%", ["tabela de rentabilidade"]),
        ("Tabela de Retornos", ["tabela de retornos"]),
        ("rentabilidade mensal dos últimos 12 meses", ["rentabilidade mensal dos últimos 12 meses"]),
        ("rentabilidade dos ultimos 6 meses", ["rentabilidade dos ultimos 6 meses"]),
        ("sem relação: o mês passado, a cada mês", []),
    ],
)
def test_historico_de_rentabilidade_formas(texto, esperado):
    assert valores(texto, "historico_rentabilidade") == esperado


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Indique amigos e receba comissão", ["indique amigos"]),
        ("Indique e receba", ["indique e receba"]),
        ("Convide amigos e ganhe", ["convide amigos"]),
        ("Convide e ganhe", ["convide e ganhe"]),
        ("bônus binário", ["bônus binário"]),
        ("Sistema binário de ganhos", ["binário"]),
        ("matriz forçada", ["matriz forçada"]),
        ("matriz 3x7", ["matriz 3x7"]),
        ("Matriz 2 x 10", ["matriz 2 x 10"]),
        ("matrizes de dados", []),
    ],
)
def test_indicacao_formas_de_rede(texto, esperado):
    assert valores(texto, "indicacao") == esperado


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Indique seus amigos e ganhe 10%", ["indique"]),
        ("Indique alguém", ["indique"]),
        ("Indique 3 amigos", ["indique"]),
        ("Convide seus amigos", ["convide"]),
        ("Indiquem seus amigos", ["indiquem"]),
        ("Convidem a família", ["convidem"]),
        ("você pode indicar amigos", ["indicar amigos"]),
        ("Indique amigos", ["indique amigos"]),  # a frase fixa vale mais que a palavra solta
        ("indicado para iniciantes, convidados e indicar", []),  # pedaço de outra palavra não conta
        ("reindique, desconvide", []),
    ],
)
def test_indicacao_indique_e_convide_soltos(texto, esperado):
    assert valores(texto, "indicacao") == esperado


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Taxa de liberação de 10%", ["taxa de liberação"]),
        ("taxa de desbloqueio", ["taxa de desbloqueio"]),
        ("Liberação do saque em D+1", ["liberação do saque"]),
        ("taxa de liberacao", ["taxa de liberacao"]),  # sem acento
    ],
)
def test_saque_taxas_de_liberacao(texto, esperado):
    assert valores(texto, "saque") == esperado


def test_carencia_lock():
    assert valores("Lock de 30 dias e lock-up de 6 meses", "carencia") == ["lock", "lock-up"]
    assert valores("block, locked e unlock", "carencia") == []


def test_historico():
    # "mês a mês" também vale sozinho: o termo mais longo vem primeiro e os dois são achados distintos
    assert valores("histórico de rentabilidade mês a mês", "historico_rentabilidade") == [
        "histórico de rentabilidade",
        "mês a mês",
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


# ---------------------------------------------------------------------------- atributos do HTML (R-T9-href)

HTML_CONTATOS = f"""<!doctype html>
<html><body>
<a href="https://wa.me/5511999998888">Fale conosco</a>
<a class="x" HREF="mailto:Contato@Site.com.br?subject=Oi">E-mail</a>
<a href='https://t.me/Canal_Vip'>Telegram</a>
<a href="https://www.instagram.com/siteoficial/"><img src="/i.png"></a>
<form action="https://api.whatsapp.com/send?phone=5521988887777&amp;text=Oi"></form>
<a href="bitcoin:{BTC_BECH32}?amount=1">Pagar</a>
<script>var s = "<a href='https://wa.me/111'>";</script>
<img src="data:image/png;base64,AAAA">
</body></html>"""


def atributos(html: str, categoria: str | None = None) -> list[str]:
    return [c.valor for c in extrair_atributos(html, "sha256:h") if categoria in (None, c.categoria)]


def test_atributos_de_link_viram_candidatos_de_contato():
    cs = extrair_atributos(HTML_CONTATOS, "sha256:h")
    assert [(c.categoria, c.valor) for c in cs] == [
        ("whatsapp", "wa.me/5511999998888"),
        ("email", "contato@site.com.br"),  # mailto:
        ("telegram", "t.me/canal_vip"),
        ("rede_social", "instagram.com/siteoficial"),
        ("whatsapp", "wa.me/5521988887777"),  # action=
        ("carteira", BTC_BECH32),
    ]
    assert {c.artefato for c in cs} == {"sha256:h"}
    assert cs[-1].extra == {"rede": "btc"}


def test_atributos_posicao_e_o_offset_do_valor_no_html():
    posicoes = {c.valor: c.posicao for c in extrair_atributos(HTML_CONTATOS, "sha256:h")}
    assert posicoes["wa.me/5511999998888"] == HTML_CONTATOS.index("https://wa.me/5511999998888")
    assert posicoes["contato@site.com.br"] == HTML_CONTATOS.index("mailto:Contato@Site.com.br")
    assert posicoes["t.me/canal_vip"] == HTML_CONTATOS.index("https://t.me/Canal_Vip")
    assert posicoes["instagram.com/siteoficial"] == HTML_CONTATOS.index("https://www.instagram.com/")
    assert posicoes[BTC_BECH32] == HTML_CONTATOS.index("bitcoin:")
    # com `&amp;` o valor lido não aparece igual na tag: o offset cai no início da tag
    assert posicoes["wa.me/5521988887777"] == HTML_CONTATOS.index("<form")


def test_atributos_trecho_e_recorte_do_html_em_volta_do_valor():
    primeiro = extrair_atributos(HTML_CONTATOS, "sha256:h")[0]
    valor = "https://wa.me/5511999998888"
    i = primeiro.posicao
    assert primeiro.trecho == HTML_CONTATOS[max(0, i - 120) : i + len(valor) + 120]
    assert valor in primeiro.trecho


def test_atributos_offset_vale_com_varias_linhas_acentos_e_crlf():
    html = (
        "<p>Atenção — fale conosco</p>\r\n<p>ação</p>\n\n<div>\n  <a\n   href=\"https://t.me/canal_vip\">x</a>"
        "<img\n src='https://wa.me/5511999998888' /></div>"
    )
    cs = extrair_atributos(html, "h")
    assert [(c.valor, c.posicao) for c in cs] == [
        ("t.me/canal_vip", html.index("https://t.me/canal_vip")),
        ("wa.me/5511999998888", html.index("https://wa.me/5511999998888")),
    ]


def test_atributos_ignoram_script_data_uri_e_repetidos():
    html = """<script>var s = "<a href='https://wa.me/111'>";</script>
<img src="data:image/png;base64,bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4">
<a href="https://wa.me/5511999998888">1</a><a href="https://wa.me/5511999998888">2</a>"""
    cs = extrair_atributos(html, "h")
    assert [(c.valor, c.posicao) for c in cs] == [
        ("wa.me/5511999998888", html.index("https://wa.me/5511999998888"))
    ]


def test_atributos_numa_tag_so_os_20_primeiros_href_src_e_action():
    valores_do_html = [f"https://wa.me/{i:012d}" for i in range(30)]
    html = "<a " + " ".join(f'{("href", "src", "action")[i % 3]}="{v}"' for i, v in enumerate(valores_do_html)) + ">"
    cs = extrair_atributos(html, "h")
    assert [c.valor for c in cs] == [f"wa.me/{i:012d}" for i in range(20)]
    # e o offset de cada um continua certo, um depois do outro
    assert [c.posicao for c in cs] == [html.index(v) for v in valores_do_html[:20]]
    # os 20 contam só os que têm valor novo; a mesma tag com outros atributos não gasta a conta
    html = '<a id=1 class=x title=y href="https://t.me/canal_vip" data-a=1 data-b=2>x</a>'
    assert atributos(html) == ["t.me/canal_vip"]


def test_atributos_so_href_src_e_action():
    html = (
        '<a data-href="https://wa.me/1111111111" title="https://wa.me/2222222222" '
        'onclick="window.open(\'https://wa.me/3333333333\')" href="https://wa.me/5511999998888">x</a>'
        '<iframe src="https://t.me/canal_vip"></iframe>'
    )
    assert atributos(html) == ["wa.me/5511999998888", "t.me/canal_vip"]


def test_atributos_so_rodam_as_regex_de_contato_e_carteira():
    html = (
        '<a href="https://alvo.com.br/promo?rende=1,5%25+ao+dia&garantido=sim">garantido 1,5% ao dia</a>'
        '<a href="https://alvo.com.br/saque/bonus-de-indicacao/33.000.167/0001-01">x</a>'
    )
    assert extrair_atributos(html, "h") == []


def test_atributos_ignoram_pixel_e_botao_de_compartilhar():
    html = (
        '<img src="https://www.facebook.com/tr?id=123&ev=PageView">'
        '<a href="https://www.facebook.com/sharer/sharer.php?u=x">'
        '<a href="https://twitter.com/intent/tweet?text=x">'
        '<a href="https://www.youtube.com/watch?v=abc">'
        '<iframe src="https://www.youtube.com/embed/abc"></iframe>'
        '<a href="https://www.facebook.com/paginaoficial">'
    )
    assert atributos(html) == ["facebook.com/paginaoficial"]
    assert valores("facebook.com/tr e twitter.com/intent/tweet", "rede_social") == []


def test_atributos_html_sem_atributo_de_interesse_ou_vazio():
    assert extrair_atributos("", "h") == []
    assert extrair_atributos("<p>sem links</p><a name=x>", "h") == []
    assert extrair_atributos('<a href="">x</a><a href>y</a>', "h") == []


def test_atributos_html_com_valor_enorme_nao_estoura():
    html = '<a href="https://wa.me/5511999998888' + "9" * 5000 + '">x</a>'
    assert atributos(html) == []  # número com mais de 15 dígitos não é telefone


def test_atributos_html_com_muitas_tags_so_le_as_primeiras(monkeypatch):
    monkeypatch.setattr(modulo_extracao, "_TAGS_MAXIMAS", 10)
    link = '<a href="https://wa.me/5511999998888">x</a>'
    outro = '<a href="https://wa.me/5521988887777">x</a>'
    assert atributos(link + "<p>x</p>" * 5 + outro) == ["wa.me/5511999998888"]  # o outro é o 13º "<"
    assert atributos(link + "<p>x</p>" * 3 + outro) == ["wa.me/5511999998888", "wa.me/5521988887777"]


def test_html_dentro_dos_limites_nao_e_cortado():
    html = "<p>x</p>" * 100_000 + '<a href="https://wa.me/5511999998888">x</a>'  # 200 mil tags, 0,9 MB
    assert atributos(html) == ["wa.me/5511999998888"]


def test_atributos_html_acima_do_maximo_so_le_o_comeco(monkeypatch):
    monkeypatch.setattr(modulo_extracao, "_HTML_MAXIMO", 200)
    link = '<a href="https://wa.me/5511999998888">x</a>'
    enchimento = "<p>x</p>" * 100
    assert atributos(link + enchimento) == ["wa.me/5511999998888"]
    assert atributos(enchimento + link) == []


# ---------------------------------------------------------------------------- teto por categoria (R-T9-teto)


def _emails(n: int) -> str:
    return " ".join(f"u{i}@b.co" for i in range(n))


def test_teto_guarda_os_primeiros_por_posicao():
    cs = extrair(_emails(250) + " Pix", "a")
    emails = [c.valor for c in cs if c.categoria == "email"]
    assert emails == [f"u{i}@b.co" for i in range(TETO_POR_CATEGORIA)]
    assert TETO_POR_CATEGORIA == 100
    assert [c.valor for c in cs if c.categoria == "pix"] == ["pix"]  # outra categoria não é afetada


def test_teto_nao_corta_exatamente_no_limite():
    assert len(extrair(_emails(TETO_POR_CATEGORIA), "a")) == TETO_POR_CATEGORIA
    assert len(extrair(_emails(TETO_POR_CATEGORIA + 1), "a")) == TETO_POR_CATEGORIA


def test_teto_2mb_de_emails_distintos():
    texto = "".join(f"u{i}@b.co " for i in range(250_000))
    assert len(texto) > 2_000_000
    inicio = time.perf_counter()
    cs = extrair(texto, "sha256:x")
    assert time.perf_counter() - inicio < 5
    assert len(cs) == TETO_POR_CATEGORIA and {c.categoria for c in cs} == {"email"}


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


def test_nenhuma_regex_do_modulo_tem_repeticao_sem_limite():
    """A regra do docstring do módulo: nada de `*`, `+` ou `{n,}`; só `{n,m}` (e `?`)."""
    import re
    from re import _constants, _parser  # o `re` não expõe a árvore da regex em API pública

    def filhos(av):
        if isinstance(av, _parser.SubPattern):
            yield av
        elif isinstance(av, tuple | list):
            for x in av:
                yield from filhos(x)

    def ilimitadas(sub):
        for op, av in sub:
            if op in (_constants.MAX_REPEAT, _constants.MIN_REPEAT, _constants.POSSESSIVE_REPEAT):
                if av[1] == _constants.MAXREPEAT:
                    yield op
            for f in filhos(av):
                yield from ilimitadas(f)

    def padroes(valor):
        if isinstance(valor, re.Pattern):
            yield valor
        elif isinstance(valor, tuple | list):
            for x in valor:
                yield from padroes(x)

    todos = [(nome, p) for nome, valor in vars(modulo_extracao).items() for p in padroes(valor)]
    assert len(todos) >= 30  # a varredura achou as regex do módulo
    assert [(nome, p.pattern) for nome, p in todos if list(ilimitadas(_parser.parse(p.pattern, p.flags)))] == []


def test_texto_denso_em_percentuais_termina_rapido():
    texto = "diário " + "1%" * 1_000_000
    assert len(texto) > 2_000_000
    inicio = time.perf_counter()
    cs = extrair(texto, "sha256:x")
    assert time.perf_counter() - inicio < 5
    assert [(c.valor, c.posicao) for c in cs] == [("1|dia", len("diário "))]  # só o primeiro vê a unidade


@pytest.mark.parametrize(
    "unidade",
    ["1%a", "1% a ", "1%\n", "5%a.d.", "1,5%ao dia ", "1.000%", "diário 1%", "1% de lucro ", "1% a 3% ao dia "],
)
def test_texto_denso_em_percentuais_variados_termina_rapido(unidade):
    texto = unidade * (2_000_000 // len(unidade))
    inicio = time.perf_counter()
    extrair(texto, "sha256:x")
    assert time.perf_counter() - inicio < 5


HTMLS_HOSTIS = {
    # cada um no tamanho em que o `_recortar_html` ainda deixa passar (ou além dele)
    "menores_que": "<" * 6_000_000,
    "tags": "<p>oi</p>" * 220_000,
    "tags_alem_do_limite": "<p>" * 600_000,
    "tags_com_atributo": "<a href=x>" * 400_000,
    "links_distintos": "".join(f'<a href="https://wa.me/{i:012d}">x</a>' for i in range(60_000)),
    "emails_distintos": "".join(f'<a href="mailto:u{i}@b.co">x</a>' for i in range(60_000)),
    "aspas_abertas": '<a href="' * 450_000,
    "atributos": "<a " + 'x="1" ' * 700_000 + ">",
    "valor_gigante": '<a href="' + "a" * 5_000_000 + '">',
    "entidades_no_valor": '<a href="' + "&amp;" * 800_000 + '">',
    "sem_fechar": "<a href=x" * 400_000,
    "comentarios": "<!--x-->" * 500_000,
    "script": "<script>" + "x" * 5_000_000,
    "href_vazio": "<a href>" * 400_000,
    "base64": '<img src="data:image/png;base64,' + "QUJD" * 1_000_000 + '">',
    # 80 mil `href` distintos numa tag só (1 MB): custava 22 s quando cada um buscava o offset na tag inteira
    "href_distintos_numa_tag": "<a " + "".join(f'href="u{i}" ' for i in range(80_000)) + ">",
    "href_e_src_distintos_numa_tag": "<img " + "".join(f"src=s{i} href=h{i} " for i in range(60_000)) + ">",
}


@pytest.mark.parametrize("nome", sorted(HTMLS_HOSTIS))
def test_html_hostil_termina_rapido(nome):
    inicio = time.perf_counter()
    cs = extrair_atributos(HTMLS_HOSTIS[nome], "sha256:h")
    assert time.perf_counter() - inicio < 5
    assert len(cs) <= 5 * TETO_POR_CATEGORIA  # whatsapp, telegram, rede_social, email e carteira


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
    assert no.saidas == ("candidatos", "fonte", "truncado")


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
    assert resultado.saidas == {"candidatos": [], "fonte": "captura", "truncado": {}}


async def test_no_le_texto_utf8_com_byte_invalido(ctx, serv):
    ref = serv.custodia.guardar(b"Pix \xff\xfe garantido", "txt", tipo="texto", origem="x")
    entradas = {"captura": {"paginas": [{"url": "u", "texto": ref}], "bloqueada": False}}
    resultado = await ExtracaoNo().executar(ctx, entradas, {}, serv)
    assert [c["valor"] for c in resultado.saidas["candidatos"]] == ["pix", "garantido"]


async def test_no_artefato_ausente_da_custodia_levanta(ctx, serv):
    entradas = {"captura": {"paginas": [{"url": "u", "texto": "sha256:" + "0" * 64}], "bloqueada": False}}
    with pytest.raises(FileNotFoundError):
        await ExtracaoNo().executar(ctx, entradas, {}, serv)


def guardar_html(serv, url: str, html: str) -> str:
    return serv.custodia.guardar(html.encode("utf-8"), "html", tipo="pagina", origem=url)


def pagina_com_html(serv, url: str, texto: str, html: str) -> dict:
    return {**pagina(serv, url, texto), "html": guardar_html(serv, url, html)}


async def test_no_le_tambem_os_atributos_do_html(ctx, serv):
    html = '<html><body><a href="https://wa.me/5511999998888">Fale conosco</a></body></html>'
    p = pagina_com_html(serv, "https://alvo.com.br/", "Fale conosco", html)
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p], "bloqueada": False}}, {}, serv)
    (c,) = resultado.saidas["candidatos"]
    assert (c["categoria"], c["valor"]) == ("whatsapp", "wa.me/5511999998888")
    # o candidato do atributo aponta para o HTML guardado, no offset do atributo
    assert c["artefato"] == p["html"] and c["artefato"] != p["texto"]
    assert c["posicao"] == html.index("https://wa.me/5511999998888")
    assert c["trecho"] == html[max(0, c["posicao"] - 120) : c["posicao"] + len("https://wa.me/5511999998888") + 120]
    assert resultado.saidas["truncado"] == {}


async def test_no_texto_e_atributo_do_mesmo_achado_ficam_so_com_o_do_texto(ctx, serv):
    html = '<a href="https://wa.me/5511999998888">x</a><a href="https://t.me/canal_vip">y</a>'
    p = pagina_com_html(serv, "https://alvo.com.br/", "Fale no wa.me/5511999998888", html)
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p], "bloqueada": False}}, {}, serv)
    assert [(c["categoria"], c["valor"], c["artefato"]) for c in resultado.saidas["candidatos"]] == [
        ("whatsapp", "wa.me/5511999998888", p["texto"]),  # a ocorrência do texto vale; a do atributo some
        ("telegram", "t.me/canal_vip", p["html"]),
    ]


async def test_no_o_wayback_tambem_traz_o_html(ctx, serv):
    html = '<a href="mailto:contato@site.com.br">e-mail</a>'
    p = {**pagina_com_html(serv, "http://alvo.com.br/", "e-mail", html), "timestamp": "20190606235936"}
    wayback = {"paginas": [p], "falhas": [], "truncado": False}
    resultado = await ExtracaoNo().executar(ctx, {"wayback_snapshot": wayback}, {}, serv)
    assert resultado.saidas["fonte"] == "wayback_snapshot"
    assert [(c["valor"], c["artefato"]) for c in resultado.saidas["candidatos"]] == [
        ("contato@site.com.br", p["html"])
    ]


async def test_no_html_com_byte_invalido_e_html_ausente_da_custodia(ctx, serv):
    ref = serv.custodia.guardar(b'<a href="https://wa.me/5511999998888\xff">x</a>', "html", tipo="pagina", origem="x")
    p = {**pagina(serv, "https://alvo.com.br/", "x"), "html": ref}
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p], "bloqueada": False}}, {}, serv)
    assert [c["valor"] for c in resultado.saidas["candidatos"]] == ["wa.me/5511999998888"]
    ausente = {**pagina(serv, "https://alvo.com.br/", "x"), "html": "sha256:" + "0" * 64}
    with pytest.raises(FileNotFoundError):
        await ExtracaoNo().executar(ctx, {"captura": {"paginas": [ausente], "bloqueada": False}}, {}, serv)


async def test_no_teto_marca_o_truncado_por_pagina(ctx, serv):
    cheia = pagina(serv, "https://alvo.com.br/", _emails(250) + " Pix")
    exata = pagina(serv, "https://alvo.com.br/exata", _emails(TETO_POR_CATEGORIA))
    uma_so = pagina(serv, "https://alvo.com.br/uma", "Pix")
    entradas = {"captura": {"paginas": [cheia, exata, uma_so], "bloqueada": False}}
    resultado = await ExtracaoNo().executar(ctx, entradas, {}, serv)
    por_pagina = {}
    for c in resultado.saidas["candidatos"]:
        por_pagina.setdefault(c["artefato"], []).append(c["categoria"])
    assert por_pagina[cheia["texto"]].count("email") == TETO_POR_CATEGORIA
    assert por_pagina[exata["texto"]].count("email") == TETO_POR_CATEGORIA
    assert resultado.saidas["truncado"] == {"https://alvo.com.br/": ["email"]}  # só a que estourou


async def test_no_teto_conta_texto_e_atributos_juntos(ctx, serv):
    texto = _emails(60)
    html = "".join(f'<a href="mailto:h{i}@b.co">x</a>' for i in range(60))
    p = pagina_com_html(serv, "https://alvo.com.br/", texto, html)
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p], "bloqueada": False}}, {}, serv)
    emails = [c for c in resultado.saidas["candidatos"] if c["categoria"] == "email"]
    assert len(emails) == TETO_POR_CATEGORIA
    assert [c["artefato"] for c in emails] == [p["texto"]] * 60 + [p["html"]] * 40  # o texto primeiro
    assert resultado.saidas["truncado"] == {"https://alvo.com.br/": ["email"]}


async def test_no_teto_lista_as_categorias_na_ordem_da_tabela(ctx, serv):
    texto = _emails(150) + " " + " ".join(f"x.com/u{i}" for i in range(150)) + " " + " ".join(
        f"wa.me/{i:012d}" for i in range(150)
    )
    p = pagina(serv, "https://alvo.com.br/", texto)
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p], "bloqueada": False}}, {}, serv)
    assert resultado.saidas["truncado"] == {"https://alvo.com.br/": ["whatsapp", "rede_social", "email"]}


async def test_no_2mb_de_emails_distintos_no_no(ctx, serv):
    texto = "".join(f"u{i}@b.co " for i in range(250_000))
    p = pagina(serv, "https://alvo.com.br/", texto)
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p], "bloqueada": False}}, {}, serv)
    assert len(resultado.saidas["candidatos"]) == TETO_POR_CATEGORIA
    assert resultado.saidas["truncado"] == {"https://alvo.com.br/": ["email"]}
    assert len(json.dumps(resultado.saidas)) < 100_000  # e não 60 MB


async def test_no_percentual_absurdo_nao_derruba_o_no(ctx, serv):
    p = pagina(serv, "https://alvo.com.br/", "Rende 10.000.000.000.000% ao dia e 1% ao mês. Pix")
    resultado = await ExtracaoNo().executar(ctx, {"captura": {"paginas": [p], "bloqueada": False}}, {}, serv)
    assert [c["valor"] for c in resultado.saidas["candidatos"]] == ["1|mes", "pix"]


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
