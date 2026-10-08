"""Pontuação (Tarefa 14): a matriz, os itens A1–D4 e os dois eixos (spec 8)."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from radar.execucao import ExecucaoSalva
from radar.modelos import Contexto, Evidencia, Item, Resposta, Sinal
from radar.pendencias.definicoes import validos_da_matriz
from radar.pontuacao import (
    CAMINHO_MATRIZ,
    CLASSES,
    Eixo1,
    Eixo2,
    ModificadorAplicado,
    carregar_matriz,
    itens_da_execucao,
    pontos_a1,
    pontuar_eixo1,
    pontuar_eixo2,
    sinais_da_execucao,
)

MATRIZ = carregar_matriz()
IDS = ("A1", "A2", "A3", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4", "D1", "D2", "D3", "D4")
AGORA = datetime(2026, 10, 7, 12, 0, 0)
HOJE = AGORA.date()
RETRO = date(2019, 7, 1)
PETROBRAS = "33000167000101"


@pytest.fixture
def matriz():
    return MATRIZ


# ---------------------------------------------------------------------------- itens montados à mão (eixo 1)


def itens(abertos=(), inconclusivos=(), **pts) -> dict[str, Item]:
    """Os ids de `pts` confirmados com esses pontos, os de `abertos` nao_verificado e os de `inconclusivos`
    inconclusivo; os outros ficam nao_se_aplica com 0."""
    resultado = {}
    for id_ in IDS:
        if id_ in pts:
            estado, pontos = "confirmado", pts[id_]
        elif id_ in abertos:
            estado, pontos = "nao_verificado", 0
        elif id_ in inconclusivos:
            estado, pontos = "inconclusivo", 0
        else:
            estado, pontos = "nao_se_aplica", 0
        resultado[id_] = Item(id=id_, estado=estado, pontos=pontos, maximo=MATRIZ.itens[id_].max, origem="claude")
    return resultado


GAS = dict(A1=3, A2=2, A3=2, B1=2, B3=1, C1=3, C2=2, C3=2, D4=1)
ATLAS_2019 = dict(A1=3, A3=2, C1=3)
BOI_GORDO = dict(A1=2, C1=3, D4=1)


# ---------------------------------------------------------------------------- execução montada à mão


def ev(tipo_fonte: str = "imprensa", trecho: str = "trecho literal citado da fonte", **extra) -> dict:
    return {"fonte": "https://noticia.example/materia", "trecho": trecho, "tipo_fonte": tipo_fonte, **extra}


def resp(status: str = "confirmado", valor: dict | None = None, evidencias: list[dict] | None = None) -> dict:
    """A saída de um nó `pend_*` com essa resposta (como o motor grava)."""
    if evidencias is None:
        evidencias = [ev()] if status in ("confirmado", "corrigido") else []
    resposta = Resposta(
        status=status,
        valor=valor or {},
        evidencias=evidencias,
        onde_procurou=["site e imprensa"] if status == "nao_encontrado" else [],
    )
    return {"resposta": resposta.model_dump(mode="json")}


def julgamento(pendencia: str, status: str, valor: dict | None = None) -> dict:
    return {
        "id": f"{pendencia}#1",
        "pendencia": pendencia,
        "resposta": resp(status, valor)["resposta"],
        "em": "2026-10-07T12:00:00.000+00:00",
        "substitui": None,
        "ativa": True,
    }


def base() -> dict[str, dict]:
    """Uma execução em modo atual: empresa e domínio antigos, CNAE da seção K, sem registro, sem alerta.

    As pendências dão A1=3 (5% ao mês) e A3=2; o resto é negativo, a P-A2 não foi gerada e a P-E não achou nada.
    """
    return {
        "rdap": {
            "registro": "2015-03-02", "expiracao": "2027-03-02", "registrador": "Registro.br",
            "cnpj_titular": PETROBRAS, "vazamento_temporal": [],
        },
        "dns": {"A": ["203.0.113.7"], "AAAA": [], "MX": [], "NS": ["ns1.exemplo.com.br"], "TXT": [], "nxdomain": False},
        "captura": {"paginas": [], "terceiros": [], "bloqueada": False, "falhas": []},
        "cnpj": {
            "cnpj": PETROBRAS, "razao_social": "EXEMPLO INVESTIMENTOS LTDA", "abertura": "2014-01-10",
            "cnae": 6619302, "vazamento_temporal": [],
        },
        "registros": {
            "cvm": [], "bcb": [], "bcb_dominio": [], "registrado": False, "motivo": None, "vazamento_temporal": [],
        },
        "cvm_alertas": {"correspondencias": [], "cobertura": {"com_texto_integral": 10, "so_resumo": 5}},
        "pend_a1": resp(valor={"pct_mes": 5.0, "taxa_diaria": False, "garantido": True}),
        "pend_a3": resp(valor={"origem_verificavel": False, "custodiante_independente": False}),
        "pend_b": resp(
            valor={"indicacao": "nenhuma", "token_proprio": False, "carencia_com_multa": False, "taxa_para_sacar": False}
        ),
        "pend_c": resp(
            valor={"contrato_atipico": False, "tipo_contrato": None, "conta_pf_ou_terceiro": False, "offshore_alegado": False}
        ),
        "pend_c4": resp(valor={"alerta_vigente": False, "alertas": []}),
        "pend_d1": resp(valor={"historico_fraude": False, "pessoas": []}),
        "pend_d4": resp(valor={"credibilidade_emprestada": False, "tipos": []}),
        "pend_e": resp("nao_encontrado"),
    }  # fmt: skip


_STATUS_BASE = {"pend_a2": ("pulado", "sem histórico de rentabilidade")}
# no retroativo o DNS e a captura são `so_atual` e o `cnpj` marca tudo menos `cnpj` e `abertura`
_VAZAMENTO_CNPJ = ["razao_social", "nome_fantasia", "cnae", "cnae_descricao", "capital_social", "situacao", "socios", "fonte"]


def execucao(
    saidas: dict | None = None,
    status: dict | None = None,
    *,
    as_of: date = HOJE,
    pendencias: dict | None = None,
    julgamentos: list | None = None,
) -> ExecucaoSalva:
    """A `base()` com `saidas` trocadas ou acrescentadas (o nó fica `feito`). `status`: `{nó: status}` ou
    `{nó: (status, motivo)}` tira o nó do `feito` e apaga a saída dele."""
    todas = {**base(), **(saidas or {})}
    pedidos = {**{n: s for n, s in _STATUS_BASE.items() if n not in (saidas or {})}, **(status or {})}
    estados = {no: {"status": "feito", "motivo": None} for no in todas}
    for no, pedido in pedidos.items():
        st, motivo = pedido if isinstance(pedido, tuple) else (pedido, None)
        if motivo is None and st in ("erro", "bloqueado", "pulado"):
            motivo = f"motivo de {st}"
        estados[no] = {"status": st, "motivo": motivo}
        todas.pop(no, None)
    ctx = Contexto(
        alvo="exemplo.com.br",
        slug="exemplo-com-br",
        url_inicial="https://exemplo.com.br/",
        as_of=as_of,
        data_execucao=AGORA,
        modo_contato="captura",
        modo_cego=False,
        run_id="exemplo-com-br/2026-10-07_120000",
        pasta=Path("casos/exemplo-com-br/2026-10-07_120000"),
    )
    return ExecucaoSalva(
        ctx=ctx, status=estados, saidas=todas, pendencias=pendencias or {}, julgamentos=julgamentos or []
    )


def retroativa(saidas: dict | None = None, status: dict | None = None, **kw) -> ExecucaoSalva:
    """Execução com `as_of` em 2019: DNS e captura pulados, `cnpj` e `registros` com vazamento temporal."""
    padrao = {
        "cnpj": {**base()["cnpj"], "vazamento_temporal": list(_VAZAMENTO_CNPJ)},
        "registros": {**base()["registros"], "vazamento_temporal": ["bcb", "bcb_dominio"]},
        "rdap": {**base()["rdap"], "cnpj_titular": None, "vazamento_temporal": ["cnpj_titular"]},
    }
    return execucao(
        {**padrao, **(saidas or {})},
        {"dns": ("pulado", "só atual"), "captura": ("pulado", "só atual"), **(status or {})},
        as_of=RETRO,
        **kw,
    )


def item(ex: ExecucaoSalva, id_: str) -> Item:
    return itens_da_execucao(ex, MATRIZ)[id_]


# ---------------------------------------------------------------------------- matriz


def test_carrega_a_matriz_da_spec(matriz):
    assert matriz.versao == "2026-10-07"
    assert matriz.hash == hashlib.sha256(CAMINHO_MATRIZ.read_bytes()).hexdigest()
    assert list(matriz.itens) == list(IDS)
    assert sum(i.max for i in matriz.itens.values()) == 34
    assert [f.classe for f in matriz.faixas] == list(CLASSES[:4])
    assert [r.id for r in matriz.regras_corte] == ["R1", "R2", "R3"]
    assert list(matriz.janelas) == [f"E{n}" for n in range(8)]
    assert matriz.itens["A1"].limites_pct_mes == [1.2, 3.0, 10.0]
    assert matriz.itens["B1"].valores == {"indicacao_remunerada": 2, "recrutar_para_sacar": 3}
    assert matriz.itens["D3"].meses_limite == 12


def test_matriz_serve_a_pe_por_duck_typing(matriz):
    # `validos_da_matriz` lê `estagios` (dict[str, str]) e `modificadores` (dict[str, dict], com ["origem"])
    assert type(matriz.estagios) is dict and all(type(v) is str for v in matriz.estagios.values())
    assert type(matriz.modificadores) is dict and all(type(v) is dict for v in matriz.modificadores.values())
    validos = validos_da_matriz(matriz)
    assert len(validos["tipos_validos"].split("|")) == 27 + 1
    assert len(validos["modificadores_validos"].split("|")) == 10


def test_carregar_matriz_de_outro_caminho(tmp_path):
    texto = CAMINHO_MATRIZ.read_text(encoding="utf-8").replace('versao: "2026-10-07"', 'versao: "teste"')
    caminho = tmp_path / "matriz.yaml"
    caminho.write_text(texto, encoding="utf-8")
    outra = carregar_matriz(caminho)
    assert outra.versao == "teste"
    assert outra.hash == hashlib.sha256(caminho.read_bytes()).hexdigest() != MATRIZ.hash


@pytest.mark.parametrize(
    "de,para",
    [
        ("{item: B4, op: \">\", valor: 0}", "{item: Z9, op: \">\", valor: 0}"),  # regra com item desconhecido
        ('classe: "provável", condicoes', 'classe: "talvez", condicoes'),  # classe fora da ordem
        ("atraso_pagamento: E4", "atraso_pagamento: E9"),  # estágio sem janela
        ("{de: 5,  ate: 9,", "{de: 6,  ate: 9,"),  # faixas com buraco
        ("reciclagem dos líderes\"", "reciclagem dos líderes\"\n  E9: \"depois\""),  # janelas fora de E0..En
        ("recrutar_para_sacar: 3}", "recrutar_para_sacar: 4}"),  # B1 acima do máximo
        ("10.0], taxa_diaria: 4}", "10.0], taxa_diaria: 5}"),  # taxa diária acima do máximo do A1
        ("[1.2, 3.0, 10.0]", "[1.2, 1.2, 10.0]"),  # limites não estritamente crescentes
        ("[1.2, 3.0, 10.0]", "[3.0, 1.2, 10.0]"),
        ("[1.2, 3.0, 10.0]", "[1.2, 3.0]"),  # a fronteira do A1 é definida para três limites
    ],
)
def test_matriz_incoerente_recusada(tmp_path, de, para):
    texto = CAMINHO_MATRIZ.read_text(encoding="utf-8")
    assert de in texto
    caminho = tmp_path / "matriz.yaml"
    caminho.write_text(texto.replace(de, para, 1), encoding="utf-8")
    with pytest.raises(ValidationError):
        carregar_matriz(caminho)


# ---------------------------------------------------------------------------- A1


# R-T14-fronteira-a1: 1 se pct <= 1,2; 2 se 1,2 < pct < 3,0; 3 se 3,0 <= pct <= 10,0; 4 se pct > 10,0 ou taxa
# diária (a R1 do relatório diz "3% ao mês ou mais (A1 >= 3)" e a tabela, "de 3% a 10% = 3")
@pytest.mark.parametrize(
    "pct,diaria,esperado",
    [(None, False, 0), (1.2, False, 1), (1.21, False, 2), (2.99, False, 2), (3.0, False, 3), (3.01, False, 3),
     (10.0, False, 3), (10.01, False, 4), (0.5, True, 4), (0, False, 0), (-1.0, False, 0), (None, True, 4)],
)  # fmt: skip
def test_pontos_a1(pct, diaria, esperado, matriz):
    assert pontos_a1(pct, diaria, matriz) == esperado


# ---------------------------------------------------------------------------- eixo 1


@pytest.mark.parametrize(
    "pts,total,classe",
    [
        (GAS, 18, "característico"),  # GAS
        (ATLAS_2019, 8, "provável"),  # Atlas jul/2019 (R1)
        (dict(A1=3, A3=2, C1=3, C4=3), 11, "provável"),  # Atlas set/2019
        (dict(A1=3, A3=2, C1=3, C4=3, B2=2), 13, "provável"),  # Atlas 2020
        (BOI_GORDO, 6, "suspeito"),  # Boi Gordo
        (dict(A1=1, A2=2, A3=2, B1=2, D4=1), 8, "suspeito"),  # Madoff
        (dict(A3=2, B4=3, C1=3, C3=2), 10, "característico"),  # Aglobal (R2)
    ],
)
def test_casos_ouro(pts, total, classe, matriz):
    e = pontuar_eixo1(itens(**pts), matriz, sinais=[])
    assert (e.minimo, e.maximo, e.classe) == (total, total, classe)
    assert e.pode_chegar_a is None and e.regras_pendentes == []


def test_regras_disparadas(matriz):
    assert pontuar_eixo1(itens(**ATLAS_2019), matriz, sinais=[]).regras_disparadas == ["R1"]
    assert pontuar_eixo1(itens(A3=2, B4=3, C1=3, C3=2), matriz, sinais=[]).regras_disparadas == ["R2"]
    assert pontuar_eixo1(itens(**BOI_GORDO), matriz, sinais=[]).regras_disparadas == []
    # GAS: a faixa já é "característico", mas a R1 também disparou
    assert pontuar_eixo1(itens(**GAS), matriz, sinais=[]).regras_disparadas == ["R1"]


def test_sem_nada(matriz):
    assert pontuar_eixo1(itens(), matriz, sinais=[]) == Eixo1(
        minimo=0, maximo=0, classe="sem sinal estrutural forte", pode_chegar_a=None,
        regras_disparadas=[], regras_pendentes=[],
    )  # fmt: skip


def test_intervalo_com_nao_verificado(matriz):
    e = pontuar_eixo1(itens(abertos=("D1",), **GAS), matriz, sinais=[])
    assert (e.minimo, e.maximo, e.classe, e.pode_chegar_a) == (18, 21, "característico", None)


def test_inconclusivo_conta_como_aberto(matriz):
    e = pontuar_eixo1(itens(inconclusivos=("D1",), **GAS), matriz, sinais=[])
    assert (e.minimo, e.maximo) == (18, 21)


def test_pode_chegar_a(matriz):
    e = pontuar_eixo1(itens(abertos=("B2", "C4"), **ATLAS_2019), matriz, sinais=[])
    assert (e.minimo, e.classe, e.maximo, e.pode_chegar_a) == (8, "provável", 13, None)
    e = pontuar_eixo1(itens(abertos=("B2", "C4", "D1", "B4"), **ATLAS_2019), matriz, sinais=[])
    assert (e.minimo, e.classe, e.maximo, e.pode_chegar_a) == (8, "provável", 19, "característico")


def test_regra_pendente(matriz):
    e = pontuar_eixo1(itens(abertos=("B4",), **BOI_GORDO), matriz, sinais=[])
    assert "R2 dispara se B4 se confirmar" in e.regras_pendentes
    # a R1 não fica pendente: A1=2 está confirmado e não chega a 3
    assert not any(r.startswith("R1") for r in e.regras_pendentes)
    assert e.regras_disparadas == []


def test_regra_pendente_por_item_faltante(matriz):
    e = pontuar_eixo1(itens(abertos=("C1",), A1=3, A3=2), matriz, sinais=[])
    assert e.regras_pendentes == ["R1 dispara se C1 se confirmar"]
    e = pontuar_eixo1(itens(inconclusivos=("A1",), C1=3), matriz, sinais=[])
    assert e.regras_pendentes == ["R1 dispara se A1 se confirmar"]
    # as duas condições da R1 em aberto: falta mais de um item, nenhuma frase
    e = pontuar_eixo1(itens(abertos=("A1", "C1")), matriz, sinais=[])
    assert e.regras_pendentes == []
    # item nao_se_aplica não fica pendente
    assert pontuar_eixo1(itens(A1=3), matriz, sinais=[]).regras_pendentes == []


def test_r3_classe_fixa_pelo_sinal(matriz):
    prova = Sinal(tipo="prova_aportes_novos", estagio=None, data=date(2020, 1, 5), tipo_fonte="oficial")
    e = pontuar_eixo1(itens(**BOI_GORDO), matriz, sinais=[prova])
    assert e.classe == "confirmado" and e.regras_disparadas == ["R3"]
    assert e.pode_chegar_a is None
    outro = Sinal(tipo="atraso_pagamento", estagio="E4", data=None, tipo_fonte="relato")
    assert pontuar_eixo1(itens(**BOI_GORDO), matriz, sinais=[outro]).classe == "suspeito"


def test_sinais_e_anterior_sao_obrigatorios(matriz):
    # sem os sinais a R3 sumiria em silêncio; sem a anterior, o E6 por duas falhas de captura
    with pytest.raises(TypeError):
        pontuar_eixo1(itens(**BOI_GORDO), matriz)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        pontuar_eixo1(itens(**BOI_GORDO), matriz, [])  # type: ignore[misc]  # só por nome
    with pytest.raises(TypeError):
        sinais_da_execucao(execucao(), matriz)  # type: ignore[call-arg]
    assert sinais_da_execucao(execucao(), matriz, None) == ([], [])  # None explícito vale


# ---------------------------------------------------------------------------- itens: estados das pendências


def test_devolve_os_15_itens_em_ordem(matriz):
    resultado = itens_da_execucao(execucao(), matriz)
    assert list(resultado) == list(IDS)
    assert all(i.id == id_ and i.maximo == matriz.itens[id_].max for id_, i in resultado.items())


def test_execucao_base(matriz):
    resultado = itens_da_execucao(execucao(), matriz)
    estados = {id_: (i.estado, i.pontos) for id_, i in resultado.items()}
    assert estados == {
        "A1": ("confirmado", 3), "A2": ("nao_se_aplica", 0), "A3": ("confirmado", 2),
        "B1": ("nao_se_aplica", 0), "B2": ("nao_se_aplica", 0), "B3": ("nao_se_aplica", 0),
        "B4": ("nao_se_aplica", 0), "C1": ("confirmado", 3), "C2": ("nao_se_aplica", 0),
        "C3": ("nao_se_aplica", 0), "C4": ("nao_se_aplica", 0), "D1": ("nao_se_aplica", 0),
        "D2": ("nao_verificado", 0), "D3": ("nao_se_aplica", 0), "D4": ("nao_se_aplica", 0),
    }  # fmt: skip
    e = pontuar_eixo1(resultado, matriz, sinais=[])
    assert (e.minimo, e.maximo, e.classe, e.regras_disparadas) == (8, 10, "provável", ["R1"])


def test_nao_encontrado(matriz):
    a1 = item(execucao({"pend_a1": resp("nao_encontrado")}), "A1")
    assert (a1.estado, a1.pontos, a1.origem) == ("nao_encontrado", 0, "claude")


def test_inconclusivo(matriz):
    d1 = item(execucao({"pend_d1": resp("inconclusivo")}), "D1")
    assert (d1.estado, d1.pontos) == ("inconclusivo", 0)


def test_no_pulado_nao_se_aplica(matriz):
    a2 = item(execucao(), "A2")
    assert (a2.estado, a2.pontos, a2.origem) == ("nao_se_aplica", 0, "nenhuma")
    assert "sem histórico de rentabilidade" in a2.nota


@pytest.mark.parametrize("status", ["aguardando", "pendente", "executando"])
def test_pendencia_sem_resposta_nao_verificado(status, matriz):
    ex = execucao(status={"pend_a1": status}, pendencias={"P-A1": {"candidatos": [], "aberta": status == "aguardando"}})
    a1 = item(ex, "A1")
    assert (a1.estado, a1.pontos, a1.origem) == ("nao_verificado", 0, "nenhuma")
    assert "P-A1" in a1.nota


def test_pendencia_aberta_nao_verificado(matriz):
    # a pendência marcada aberta vale mais que a saída, que seria de uma rodada anterior
    ex = execucao(pendencias={"P-D4": {"candidatos": [], "aberta": True}})
    assert item(ex, "D4").estado == "nao_verificado"


@pytest.mark.parametrize("no,id_,status", [("pend_d1", "D1", "erro"), ("pend_c4", "C4", "bloqueado")])
def test_no_em_erro_nao_verificado(no, id_, status, matriz):
    resultado = item(execucao(status={no: status}), id_)
    assert (resultado.estado, resultado.pontos) == ("nao_verificado", 0)
    assert f"motivo de {status}" in resultado.nota


def test_no_ausente_nao_verificado(matriz):
    ex = execucao()
    del ex.status["pend_b"], ex.saidas["pend_b"]
    assert {item(ex, b).estado for b in ("B1", "B2", "B3", "B4")} == {"nao_verificado"}


def test_corrigido_vale_como_confirmado(matriz):
    ex = execucao({"pend_d1": resp("corrigido", {"historico_fraude": True, "pessoas": []})})
    assert (item(ex, "D1").estado, item(ex, "D1").pontos) == ("confirmado", 3)


def test_valor_invalido_nao_verificado(matriz):
    saida = resp(valor={"historico_fraude": True, "pessoas": []})
    saida["resposta"]["valor"] = {"historico": True}
    d1 = item(execucao({"pend_d1": saida}), "D1")
    assert d1.estado == "nao_verificado" and "inválid" in d1.nota


def test_d2_sempre_nao_verificado(matriz):
    d2 = item(execucao(), "D2")
    assert (d2.estado, d2.pontos, d2.maximo, d2.origem) == ("nao_verificado", 0, 2, "nenhuma")


# ---------------------------------------------------------------------------- itens: valores → pontos

B_NEGATIVO = {"indicacao": "nenhuma", "token_proprio": False, "carencia_com_multa": False, "taxa_para_sacar": False}


@pytest.mark.parametrize(
    "no,valor,id_,estado,pontos",
    [
        ("pend_a1", {"pct_mes": 0.8, "taxa_diaria": False, "garantido": False}, "A1", "confirmado", 1),
        ("pend_a1", {"pct_mes": 34.78, "taxa_diaria": True, "garantido": False}, "A1", "confirmado", 4),
        ("pend_a1", {"pct_mes": None, "taxa_diaria": False, "garantido": True}, "A1", "nao_se_aplica", 0),
        ("pend_a2", {"serie_lisa": True}, "A2", "confirmado", 2),
        ("pend_a2", {"serie_lisa": False}, "A2", "nao_se_aplica", 0),
        ("pend_a3", {"origem_verificavel": True, "custodiante_independente": False}, "A3", "nao_se_aplica", 0),
        ("pend_a3", {"origem_verificavel": False, "custodiante_independente": True}, "A3", "nao_se_aplica", 0),
        ("pend_a3", {"origem_verificavel": False, "custodiante_independente": False}, "A3", "confirmado", 2),
        ("pend_b", {**B_NEGATIVO, "indicacao": "indicacao_remunerada"}, "B1", "confirmado", 2),
        ("pend_b", {**B_NEGATIVO, "indicacao": "recrutar_para_sacar"}, "B1", "confirmado", 3),
        ("pend_b", B_NEGATIVO, "B1", "nao_se_aplica", 0),
        ("pend_b", {**B_NEGATIVO, "token_proprio": True}, "B2", "confirmado", 2),
        ("pend_b", {**B_NEGATIVO, "carencia_com_multa": True}, "B3", "confirmado", 1),
        ("pend_b", {**B_NEGATIVO, "taxa_para_sacar": True}, "B4", "confirmado", 3),
        ("pend_c", {"contrato_atipico": True, "tipo_contrato": "locação de criptoativos",
                    "conta_pf_ou_terceiro": False, "offshore_alegado": False}, "C2", "confirmado", 2),
        ("pend_c4", {"alerta_vigente": True, "alertas": [
            {"regulador": "FCA", "data": "2019-05-01", "url": "https://www.fca.org.uk/news/warnings/x"}]},
         "C4", "confirmado", 3),
        ("pend_d1", {"historico_fraude": True, "pessoas": [{"pessoa": "Fulano", "vinculo": "sócio"}]},
         "D1", "confirmado", 3),
        ("pend_d4", {"credibilidade_emprestada": True, "tipos": ["influenciador"]}, "D4", "confirmado", 1),
    ],
)  # fmt: skip
def test_valor_vira_pontos(no, valor, id_, estado, pontos, matriz):
    resultado = item(execucao({no: resp(valor=valor)}), id_)
    assert (resultado.estado, resultado.pontos) == (estado, pontos)
    assert resultado.evidencias and resultado.evidencias[0].trecho == "trecho literal citado da fonte"


def test_b_os_quatro_subitens_de_uma_resposta(matriz):
    valor = {"indicacao": "recrutar_para_sacar", "token_proprio": True, "carencia_com_multa": False, "taxa_para_sacar": True}
    resultado = itens_da_execucao(execucao({"pend_b": resp(valor=valor)}), matriz)
    assert [(resultado[b].estado, resultado[b].pontos) for b in ("B1", "B2", "B3", "B4")] == [
        ("confirmado", 3), ("confirmado", 2), ("nao_se_aplica", 0), ("confirmado", 3),
    ]  # fmt: skip


# ---------------------------------------------------------------------------- itens: origem


def _candidatos(*categorias: str) -> list[dict]:
    return [{"categoria": c, "valor": "x", "trecho": "x", "artefato": "sha256:0", "posicao": 0} for c in categorias]


def test_origem(matriz):
    ex = execucao(pendencias={"P-A1": {"candidatos": _candidatos("percentual"), "aberta": False}})
    assert item(ex, "A1").origem == "regex_confirmada"
    # candidato só de "garantido" não é a extração do retorno: quem achou o número foi o Claude
    ex = execucao(pendencias={"P-A1": {"candidatos": _candidatos("garantido"), "aberta": False}})
    assert item(ex, "A1").origem == "claude"
    assert item(execucao(), "A1").origem == "claude"
    # P-B: a categoria de cada subitem, com os quatro confirmados
    b_todos = resp(
        valor={"indicacao": "indicacao_remunerada", "token_proprio": True, "carencia_com_multa": True, "taxa_para_sacar": True}
    )
    ex = execucao({"pend_b": b_todos}, pendencias={"P-B": {"candidatos": _candidatos("indicacao", "saque"), "aberta": False}})
    resultado = itens_da_execucao(ex, matriz)
    assert [resultado[b].origem for b in ("B1", "B2", "B3", "B4")] == ["regex_confirmada", "claude", "claude", "regex_confirmada"]
    candidatos = {"P-B": {"candidatos": _candidatos("token", "carencia", "saque"), "aberta": False}}
    resultado = itens_da_execucao(execucao({"pend_b": b_todos}, pendencias=candidatos), matriz)
    assert [resultado[b].origem for b in ("B1", "B2", "B3", "B4")] == ["claude", *["regex_confirmada"] * 3]


@pytest.mark.parametrize(
    "saida",
    [
        resp(valor={"pct_mes": None, "taxa_diaria": False, "garantido": True}),  # nao_se_aplica
        resp("nao_encontrado"),
        resp("inconclusivo"),
    ],
)
def test_regex_confirmada_so_com_item_confirmado(saida, matriz):
    # a regex achou candidato, mas o Claude não confirmou o item: a origem do estado é o julgamento dele
    ex = execucao({"pend_a1": saida}, pendencias={"P-A1": {"candidatos": _candidatos("percentual"), "aberta": False}})
    assert item(ex, "A1").origem == "claude"


def test_regex_confirmada_so_com_item_confirmado_b_e_c3(matriz):
    # B1 "nenhuma" com candidato de indicação
    ex = execucao(pendencias={"P-B": {"candidatos": _candidatos("indicacao"), "aberta": False}})
    assert item(ex, "B1").origem == "claude"
    # C3 que não marcou, com candidato de pix
    ex = execucao(pendencias={"P-C": {"candidatos": _candidatos("pix"), "aberta": False}})
    assert item(ex, "C3").origem == "claude"
    # a P-C4 não tem candidato de regex (alerta_cvm_nome vem do índice da CVM)
    ex = execucao(pendencias={"P-C4": {"candidatos": _candidatos("alerta_cvm_nome"), "aberta": False}})
    assert item(ex, "C4").origem == "claude"
    assert item(execucao(), "C1").origem == "coletor"
    assert item(execucao(), "D3").origem == "coletor"


# ---------------------------------------------------------------------------- C1, C3, D3


def test_c1_c3_d3_deterministicos(matriz):
    # empresa aberta há 4 meses, CNAE de comércio, sem registro e com oferta (A1=3): os três marcam
    ex = execucao(
        {
            "cnpj": {**base()["cnpj"], "abertura": "2026-06-01", "cnae": 4751201},
            "rdap": {**base()["rdap"], "registro": "2026-05-20"},
        }
    )
    resultado = itens_da_execucao(ex, matriz)
    assert [(resultado[i].estado, resultado[i].pontos, resultado[i].origem) for i in ("C1", "C3", "D3")] == [
        ("confirmado", 3, "coletor"), ("confirmado", 2, "coletor"), ("confirmado", 1, "coletor"),
    ]  # fmt: skip
    assert "4751201" in resultado["C3"].nota
    assert "2026-05-20" in resultado["D3"].nota


def test_c1_registrado(matriz):
    ex = execucao({"registros": {**base()["registros"], "cvm": [{"cnpj": PETROBRAS}], "registrado": True}})
    c1 = item(ex, "C1")
    assert (c1.estado, c1.pontos, c1.origem) == ("nao_se_aplica", 0, "coletor")


@pytest.mark.parametrize("status", ["erro", "bloqueado", "pendente"])
def test_c1_registros_sem_resultado(status, matriz):
    assert item(execucao(status={"registros": status}), "C1").estado == "nao_verificado"


def test_c1_depende_da_oferta(matriz):
    sem_retorno = resp(valor={"pct_mes": None, "taxa_diaria": False, "garantido": False})
    # A1 zerado e A3 não gerada: não há oferta de investimento
    ex = execucao({"pend_a1": sem_retorno}, {"pend_a3": ("pulado", "sem oferta de investimento")})
    assert item(ex, "C1").estado == "nao_se_aplica"
    # A1 zerado e A3=2: há oferta
    assert (item(execucao({"pend_a1": sem_retorno}), "C1").pontos) == 3
    # A1 sem resposta e A3 negativo: não se sabe
    a3_neg = resp(valor={"origem_verificavel": True, "custodiante_independente": True})
    ex = execucao({"pend_a3": a3_neg}, {"pend_a1": "aguardando"})
    assert item(ex, "C1").estado == "nao_verificado"


@pytest.mark.parametrize("status", ["erro", "bloqueado", "pendente"])
def test_c1_sem_oferta_dispensa_os_registros(status, matriz):
    # A1 e A3 verificados sem pontos: não há oferta de investimento, e o registro não importa
    sem_retorno = resp(valor={"pct_mes": None, "taxa_diaria": False, "garantido": False})
    ex = execucao({"pend_a1": sem_retorno}, {"pend_a3": ("pulado", "sem oferta de investimento"), "registros": status})
    c1 = item(ex, "C1")
    assert (c1.estado, c1.pontos) == ("nao_se_aplica", 0)


def test_c1_sem_cnpj(matriz):
    ex = execucao(
        {
            "cnpj": {"cnpj": None, "motivo": "não encontrado"},
            "registros": {**base()["registros"], "motivo": "sem CNPJ"},
        },
        julgamentos=[julgamento("P-CNPJ", "nao_encontrado")],
    )
    assert (item(ex, "C1").estado, item(ex, "C1").pontos) == ("confirmado", 3)


def test_c3_pela_pc(matriz):
    valor = {"contrato_atipico": False, "tipo_contrato": None, "conta_pf_ou_terceiro": True, "offshore_alegado": False}
    c3 = item(execucao({"pend_c": resp(valor=valor)}), "C3")
    assert (c3.estado, c3.pontos, c3.origem) == ("confirmado", 2, "claude")
    valor = {**valor, "conta_pf_ou_terceiro": False, "offshore_alegado": True}
    assert item(execucao({"pend_c": resp(valor=valor)}), "C3").pontos == 2


def test_c3_sem_cnpj(matriz):
    sem = {"cnpj": {"cnpj": None, "motivo": "não encontrado"}}
    c3 = item(execucao(sem, julgamentos=[julgamento("P-CNPJ", "nao_encontrado")]), "C3")
    assert (c3.estado, c3.pontos, c3.origem) == ("confirmado", 2, "coletor")
    # P-CNPJ inconclusiva: não se sabe se há CNPJ
    c3 = item(execucao(sem, julgamentos=[julgamento("P-CNPJ", "inconclusivo")]), "C3")
    assert c3.estado == "inconclusivo"


@pytest.mark.parametrize(
    "cnae,estado",
    [
        (6619302, "nao_se_aplica"),  # 66: seção K
        (6422100, "nao_se_aplica"),  # 64
        (6550200, "nao_se_aplica"),  # 65
        (4751201, "confirmado"),  # 47: comércio
        (6201501, "confirmado"),  # 62: TI
        (650000, "confirmado"),  # 0650000 (fictício): a seção é "06", não "65" — o zero à esquerda conta
        (None, "nao_verificado"),
        (0, "nao_verificado"),  # código 0000000 não existe: desconhecido, não "fora da seção K"
        (-4751201, "nao_verificado"),
        (47512010, "nao_verificado"),  # mais de 7 dígitos
    ],
)
def test_c3_cnae(cnae, estado, matriz):
    ex = execucao({"cnpj": {**base()["cnpj"], "cnae": cnae}})
    assert item(ex, "C3").estado == estado


def test_c3_cnae_sem_oferta_nao_conta(matriz):
    sem_retorno = resp(valor={"pct_mes": None, "taxa_diaria": False, "garantido": False})
    ex = execucao(
        {"pend_a1": sem_retorno, "cnpj": {**base()["cnpj"], "cnae": 4751201}},
        {"pend_a3": ("pulado", "sem oferta de investimento")},
    )
    assert item(ex, "C3").estado == "nao_se_aplica"


def test_c3_cnpj_em_erro(matriz):
    assert item(execucao(status={"cnpj": "erro"}), "C3").estado == "nao_verificado"


def test_c3_pc_inconclusiva(matriz):
    assert item(execucao({"pend_c": resp("inconclusivo")}), "C3").estado == "inconclusivo"
    assert item(execucao({"pend_c": resp("nao_encontrado")}), "C3").estado == "nao_encontrado"


@pytest.mark.parametrize(
    "registro,abertura,estado",
    [
        ("2026-04-07", "2014-01-10", "confirmado"),  # domínio de 6 meses
        ("2015-03-02", "2026-02-01", "confirmado"),  # CNPJ de 8 meses
        ("2015-03-02", "2014-01-10", "nao_se_aplica"),
        ("2025-10-07", "2014-01-10", "nao_se_aplica"),  # 12 meses exatos: não é "menos de 12"
        ("2025-10-08", "2014-01-10", "confirmado"),
        (None, "2014-01-10", "nao_verificado"),  # data do domínio desconhecida
        ("2015-03-02", None, "nao_verificado"),
        ("2026-11-01", "2014-01-10", "nao_verificado"),  # registro depois do as_of: não diz nada do as_of
    ],
)
def test_d3(registro, abertura, estado, matriz):
    ex = execucao({"rdap": {**base()["rdap"], "registro": registro}, "cnpj": {**base()["cnpj"], "abertura": abertura}})
    d3 = item(ex, "D3")
    assert d3.estado == estado
    assert d3.pontos == (1 if estado == "confirmado" else 0)


def test_d3_nos_em_erro(matriz):
    assert item(execucao(status={"rdap": "erro", "cnpj": "erro"}), "D3").estado == "nao_verificado"
    # domínio antigo, mas o CNPJ pode ser novo
    assert item(execucao(status={"cnpj": "erro"}), "D3").estado == "nao_verificado"
    # domínio novo basta
    ex = execucao({"rdap": {**base()["rdap"], "registro": "2026-09-01"}}, {"cnpj": "erro"})
    assert item(ex, "D3").estado == "confirmado"


def test_d3_sem_cnpj_vale_o_dominio(matriz):
    ex = execucao({"cnpj": {"cnpj": None, "motivo": "não encontrado"}}, julgamentos=[julgamento("P-CNPJ", "nao_encontrado")])
    assert item(ex, "D3").estado == "nao_se_aplica"


# ---------------------------------------------------------------------------- C4


def _correspondencia(tipo: str) -> dict:
    return {
        "tipo": tipo, "valor": {"cnpj": PETROBRAS, "dominio": "exemplo.com.br", "nome": "exemplo investimentos"}[tipo],
        "numero": 8123, "data": "2019-09-02", "url": "https://conteudo.cvm.gov.br/deliberacoes/8123.html",
        "trecho": "a CVM determina a suspensão da oferta de EXEMPLO INVESTIMENTOS LTDA",
    }  # fmt: skip


@pytest.mark.parametrize("tipo", ["cnpj", "dominio"])
def test_c4_pelo_coletor(tipo, matriz):
    ex = execucao({"cvm_alertas": {**base()["cvm_alertas"], "correspondencias": [_correspondencia(tipo)]}})
    c4 = item(ex, "C4")  # a P-C4 da base diz "sem alerta": a correspondência exata vale sozinha
    assert (c4.estado, c4.pontos, c4.origem) == ("confirmado", 3, "coletor")
    assert c4.evidencias == [
        Evidencia(
            fonte="https://conteudo.cvm.gov.br/deliberacoes/8123.html",
            trecho="a CVM determina a suspensão da oferta de EXEMPLO INVESTIMENTOS LTDA",
            data_fonte=date(2019, 9, 2),
            tipo_fonte="oficial",
        )
    ]


def test_c4_so_por_nome_vai_para_a_pc4(matriz):
    alertas = {**base()["cvm_alertas"], "correspondencias": [_correspondencia("nome")]}
    c4 = item(execucao({"cvm_alertas": alertas}), "C4")
    assert (c4.estado, c4.origem) == ("nao_se_aplica", "claude")
    confirmado = resp(valor={"alerta_vigente": True, "alertas": []})
    c4 = item(execucao({"cvm_alertas": alertas, "pend_c4": confirmado}), "C4")
    assert (c4.estado, c4.pontos, c4.origem) == ("confirmado", 3, "claude")


def test_c4_cvm_alertas_em_erro(matriz):
    ex = execucao(status={"cvm_alertas": "erro", "pend_c4": ("bloqueado", "dependência com erro: cvm_alertas")})
    assert item(ex, "C4").estado == "nao_verificado"


# ---------------------------------------------------------------------------- vazamento temporal (retroativo)


def test_retroativo_base(matriz):
    resultado = itens_da_execucao(retroativa(), matriz)
    # C1 marca: sem registro na CVM no as_of e nada no BCB (o BCB vazado só pesa quando sustenta o registro)
    assert (resultado["C1"].estado, resultado["C1"].pontos) == ("confirmado", 3)
    # a ausência no BCB sustenta a conclusão, e a lista consultada é a de hoje: a nota diz isso
    assert "(lista do BCB é a de hoje)" in resultado["C1"].nota
    # em modo atual, não
    assert "lista do BCB" not in item(execucao(), "C1").nota
    # o CNAE de hoje é da seção K, mas não conta: o do as_of é desconhecido e a P-C é negativa
    assert (resultado["C3"].estado, resultado["C3"].pontos) == ("nao_verificado", 0)
    # D3 usa as datas de registro e de abertura, que valem em qualquer as_of: 2015 e 2014, anos antes de 2019
    assert resultado["D3"].estado == "nao_se_aplica"


def test_retroativo_c1_so_pelo_bcb(matriz):
    registros = {
        "cvm": [], "bcb": [{"raiz_cnpj": PETROBRAS[:8]}], "bcb_dominio": [], "registrado": True,
        "motivo": None, "vazamento_temporal": ["bcb", "bcb_dominio"],
    }  # fmt: skip
    c1 = item(retroativa({"registros": registros}), "C1")
    assert (c1.estado, c1.pontos) == ("nao_verificado", 0)
    assert "vazamento temporal" in c1.nota and "(lista do BCB é a de hoje)" in c1.nota
    # com registro na CVM no as_of, o BCB de hoje não faz falta (e a nota não fala dele)
    registros = {**registros, "cvm": [{"cnpj": PETROBRAS}]}
    c1 = item(retroativa({"registros": registros}), "C1")
    assert c1.estado == "nao_se_aplica" and "lista do BCB" not in c1.nota
    # em modo atual o BCB vale
    assert item(execucao({"registros": {**registros, "cvm": [], "vazamento_temporal": []}}), "C1").estado == "nao_se_aplica"


def test_retroativo_c3_cnae_de_hoje_nao_conta(matriz):
    cnpj = {**base()["cnpj"], "cnae": 4751201, "vazamento_temporal": list(_VAZAMENTO_CNPJ)}
    c3 = item(retroativa({"cnpj": cnpj}), "C3")
    assert (c3.estado, c3.pontos) == ("nao_verificado", 0)
    assert "vazamento temporal" in c3.nota
    # pela P-C conta
    valor = {"contrato_atipico": False, "tipo_contrato": None, "conta_pf_ou_terceiro": True, "offshore_alegado": False}
    c3 = item(retroativa({"cnpj": cnpj, "pend_c": resp(valor=valor)}), "C3")
    assert (c3.estado, c3.pontos) == ("confirmado", 2)


def test_campo_vazado_de_qualquer_no_nao_conta(matriz):
    # o mesmo vale para campos que hoje não vazam, se um nó os marcar
    rdap = {**base()["rdap"], "registro": "2026-09-01", "vazamento_temporal": ["registro"]}
    assert item(execucao({"rdap": rdap}), "D3").estado == "nao_verificado"
    registros = {**base()["registros"], "vazamento_temporal": ["registrado"]}
    assert item(execucao({"registros": registros}), "C1").estado == "nao_verificado"


# ---------------------------------------------------------------------------- eixo 2


def _pe(sinais: list[dict], modificadores: list[dict] | None = None, evidencias: list[dict] | None = None, status="confirmado"):
    return resp(status, {"sinais": sinais, "modificadores": modificadores or []}, evidencias or [ev("relato"), ev("imprensa")])


def test_eixo2_maior_estagio(matriz):
    sinais_pe = [
        {"tipo": "atraso_pagamento", "data": "2019-08-01", "evidencia": 1},
        {"tipo": "saques_funcionando", "data": "2019-01-10", "evidencia": 0},
    ]
    sinais, modificadores = sinais_da_execucao(execucao({"pend_e": _pe(sinais_pe)}), matriz, None)
    assert [(s.tipo, s.estagio, s.tipo_fonte) for s in sinais] == [
        ("atraso_pagamento", "E4", "imprensa"), ("saques_funcionando", "E1", "relato"),
    ]  # fmt: skip
    assert sinais[0].data == date(2019, 8, 1) and sinais[0].evidencia.tipo_fonte == "imprensa"
    e = pontuar_eixo2(sinais, modificadores, matriz)
    assert (e.estagio, e.sinal.tipo, e.janela) == ("E4", "atraso_pagamento", matriz.janelas["E4"])


def test_eixo2_sinal_mais_antigo_do_maior_estagio(matriz):
    sinais = [
        Sinal(tipo="limite_saque", estagio="E4", data=date(2019, 9, 1), tipo_fonte="operador"),
        Sinal(tipo="atraso_pagamento", estagio="E4", data=date(2019, 8, 1), tipo_fonte="relato"),
        Sinal(tipo="saques_funcionando", estagio="E1", data=date(2019, 1, 1), tipo_fonte="relato"),
        Sinal(tipo="pico_reclamacoes", estagio="E4", data=None, tipo_fonte="relato"),
    ]
    assert pontuar_eixo2(sinais, [], matriz).sinal.tipo == "atraso_pagamento"


def test_eixo2_anuncio_do_operador_conta(matriz):
    ex = execucao({"pend_e": _pe([{"tipo": "limite_saque", "data": None, "evidencia": 0}], evidencias=[ev("operador")])})
    e = pontuar_eixo2(*sinais_da_execucao(ex, matriz, None), matriz)
    assert (e.estagio, e.sinal.tipo_fonte) == ("E4", "operador")


@pytest.mark.parametrize("status", ["nao_encontrado", "inconclusivo"])
def test_eixo2_so_resposta_confirmada(status, matriz):
    assert sinais_da_execucao(execucao({"pend_e": resp(status)}), matriz, None) == ([], [])


def test_eixo2_pe_sem_resposta(matriz):
    assert sinais_da_execucao(execucao(status={"pend_e": "aguardando"}), matriz, None) == ([], [])


def test_eixo2_sem_sinal(matriz):
    assert pontuar_eixo2([], [], matriz) == Eixo2(estagio=None, sinal=None, janela=None, modificadores=[])


def test_prova_aportes_novos_dispara_a_r3(matriz):
    ex = execucao({"pend_e": _pe([{"tipo": "prova_aportes_novos", "data": "2020-01-05", "evidencia": 1}])})
    sinais, modificadores = sinais_da_execucao(ex, matriz, None)
    assert [(s.tipo, s.estagio) for s in sinais] == [("prova_aportes_novos", None)]
    assert pontuar_eixo2(sinais, modificadores, matriz).estagio is None  # não é estágio
    e1 = pontuar_eixo1(itens_da_execucao(ex, matriz), matriz, sinais=sinais)
    assert e1.classe == "confirmado" and "R3" in e1.regras_disparadas


def test_eixo2_e0_e_e6(matriz):
    trinta_dias = (HOJE - timedelta(days=30)).isoformat()
    sem_cnpj = {"cnpj": {"cnpj": None, "motivo": "não encontrado"}}
    pcnpj = [julgamento("P-CNPJ", "nao_encontrado")]
    ex = execucao({"rdap": {**base()["rdap"], "registro": trinta_dias}, **sem_cnpj}, julgamentos=pcnpj)
    sinais, mods = sinais_da_execucao(ex, matriz, None)
    assert [(s.tipo, s.estagio, s.data, s.tipo_fonte) for s in sinais] == [
        ("registro_recente", "E0", date.fromisoformat(trinta_dias), "coletor")
    ]
    e = pontuar_eixo2(sinais, mods, matriz)
    assert (e.estagio, e.janela) == ("E0", matriz.janelas["E0"])
    # NXDOMAIN: E6 e, com outro sinal, nada de E0
    dns = {**base()["dns"], "A": [], "nxdomain": True}
    ex = execucao({"rdap": {**base()["rdap"], "registro": trinta_dias}, "dns": dns, **sem_cnpj}, julgamentos=pcnpj)
    sinais, mods = sinais_da_execucao(ex, matriz, None)
    assert [(s.tipo, s.estagio) for s in sinais] == [("site_fora_do_ar", "E6")]
    assert pontuar_eixo2(sinais, mods, matriz).estagio == "E6"


@pytest.mark.parametrize(
    "registro,abertura,tem_e0",
    [
        (89, None, True),
        (90, None, False),  # 90 dias: não é "menos de 90"
        (30, 20, True),  # CNPJ também novo
        (30, 400, False),  # CNPJ antigo
        (2000, 10, False),  # domínio antigo
    ],
)
def test_e0_datas(registro, abertura, tem_e0, matriz):
    rdap = {**base()["rdap"], "registro": (HOJE - timedelta(days=registro)).isoformat()}
    if abertura is None:
        saidas, julgamentos = {"rdap": rdap, "cnpj": {"cnpj": None, "motivo": "não encontrado"}}, [julgamento("P-CNPJ", "nao_encontrado")]
    else:
        cnpj = {**base()["cnpj"], "abertura": (HOJE - timedelta(days=abertura)).isoformat()}
        saidas, julgamentos = {"rdap": rdap, "cnpj": cnpj}, []
    sinais, _ = sinais_da_execucao(execucao(saidas, julgamentos=julgamentos), matriz, None)
    assert [s.estagio for s in sinais] == (["E0"] if tem_e0 else [])


def test_e0_nao_com_outro_sinal(matriz):
    rdap = {**base()["rdap"], "registro": (HOJE - timedelta(days=10)).isoformat()}
    pe = _pe([{"tipo": "influenciadores", "data": None, "evidencia": 0}])
    sinais, _ = sinais_da_execucao(
        execucao({"rdap": rdap, "cnpj": {"cnpj": None, "motivo": "x"}, "pend_e": pe}), matriz, None
    )
    assert [s.estagio for s in sinais] == ["E2"]


def test_e0_prova_aportes_novos_nao_suprime(matriz):
    # o prova_aportes_novos não é estágio: não conta como "outro sinal" para o E0
    rdap = {**base()["rdap"], "registro": (HOJE - timedelta(days=10)).isoformat()}
    pe = _pe([{"tipo": "prova_aportes_novos", "data": None, "evidencia": 1}])
    sinais, _ = sinais_da_execucao(
        execucao({"rdap": rdap, "cnpj": {"cnpj": None, "motivo": "x"}, "pend_e": pe}), matriz, None
    )
    assert [(s.tipo, s.estagio) for s in sinais] == [("prova_aportes_novos", None), ("registro_recente", "E0")]


@pytest.mark.parametrize(
    "saidas,status",
    [
        ({}, {"cnpj": "erro"}),  # empresa desconhecida: o CNPJ pode ser antigo
        ({}, {"cnpj": "bloqueado"}),
        ({}, {"cnpj": "aguardando"}),  # P-CNPJ aberta
        ({"cnpj": {**base()["cnpj"], "abertura": None}}, {}),  # empresa sem data de abertura
        ({"cnpj": {**base()["cnpj"], "abertura": "2026-12-01"}}, {}),  # abertura depois do as_of
    ],
)
def test_e0_exige_datas_conhecidas(saidas, status, matriz):
    rdap = {**base()["rdap"], "registro": (HOJE - timedelta(days=10)).isoformat()}
    sinais, _ = sinais_da_execucao(execucao({"rdap": rdap, **saidas}, status), matriz, None)
    assert sinais == []


def test_e0_sem_data_do_dominio(matriz):
    sem_cnpj = {"cnpj": {"cnpj": None, "motivo": "x"}}
    assert sinais_da_execucao(execucao(sem_cnpj, {"rdap": "erro"}), matriz, None)[0] == []
    rdap = {**base()["rdap"], "registro": None}
    assert sinais_da_execucao(execucao({"rdap": rdap, **sem_cnpj}), matriz, None)[0] == []


def test_retroativo_descarta_sinal_depois_do_as_of(matriz):
    pe = _pe(
        [
            {"tipo": "fuga_operador", "data": "2021-03-10", "evidencia": 1},  # depois do as_of (2019-07-01)
            {"tipo": "atraso_pagamento", "data": "2019-06-20", "evidencia": 0},
            {"tipo": "limite_saque", "data": None, "evidencia": 0},  # sem data: não dá para dizer que é depois
        ]
    )
    sinais, _ = sinais_da_execucao(retroativa({"pend_e": pe}), matriz, None)
    assert [s.tipo for s in sinais] == ["atraso_pagamento", "limite_saque"]
    assert pontuar_eixo2(sinais, [], matriz).estagio == "E4"


FALHA = ("erro", "captura falhou: net::ERR_CONNECTION_REFUSED")
# R-T14-e6: só conta como site fora do ar a falha de navegação sem resposta HTTP e a página inicial com 5xx
# (inclusive os 52x da Cloudflare), 404 ou 410. Recusa ao visitante (401, 403, 407, 429, 451...) não é queda
_FALHAS_QUE_CONTAM = [
    "captura falhou: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://exemplo.com.br/",
    "captura falhou: Page.goto: net::ERR_CONNECTION_REFUSED at https://exemplo.com.br/",
    "captura falhou: Page.goto: Timeout 30000ms exceeded.",
    "captura falhou: HTTP 500", "captura falhou: HTTP 502", "captura falhou: HTTP 503",
    "captura falhou: HTTP 520", "captura falhou: HTTP 522", "captura falhou: HTTP 526",
    "captura falhou: HTTP 404", "captura falhou: HTTP 410",
]  # fmt: skip
# I2: a forma nova, que a captura grava desde a revisão final, para cada falha de alcance do site
_FALHAS_DE_ALCANCE = [
    "captura falhou: navegação: net::ERR_NAME_NOT_RESOLVED", "captura falhou: navegação: net::ERR_CONNECTION_REFUSED",
    "captura falhou: navegação: net::ERR_CONNECTION_RESET", "captura falhou: navegação: net::ERR_CONNECTION_CLOSED",
    "captura falhou: navegação: net::ERR_CONNECTION_TIMED_OUT", "captura falhou: navegação: net::ERR_ADDRESS_UNREACHABLE",
    "captura falhou: navegação: net::ERR_TIMED_OUT", "captura falhou: navegação: timeout",
]  # fmt: skip
# falha do lado do analista (navegador ausente, proxy ou túnel fora, sem internet, TLS): nunca é "site fora do ar",
# nem na forma nova nem na antiga ("captura falhou: <mensagem do Playwright>"), que execuções em disco ainda têm
_FALHAS_DO_ANALISTA = [
    "captura indisponível: BrowserType.launch: Executable doesn't exist at /ms-playwright/chromium",
    "captura indisponível: Page.goto: net::ERR_PROXY_CONNECTION_FAILED at https://exemplo.com.br/",
    "captura indisponível: ValueError: HAR ilegível",
    "captura falhou: BrowserType.launch: Executable doesn't exist at /ms-playwright/chromium",
    "captura falhou: Page.goto: net::ERR_PROXY_CONNECTION_FAILED at https://exemplo.com.br/",
    "captura falhou: Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://exemplo.com.br/",
    "captura falhou: Page.goto: net::ERR_INTERNET_DISCONNECTED at https://exemplo.com.br/",
    "captura falhou: Page.goto: net::ERR_CERT_AUTHORITY_INVALID at https://exemplo.com.br/",
    "captura falhou: Page.goto: net::ERR_SSL_PROTOCOL_ERROR at https://exemplo.com.br/",
]  # fmt: skip
_RECUSAS = [
    "captura falhou: HTTP 401", "captura falhou: HTTP 403", "captura falhou: HTTP 407",
    "captura falhou: HTTP 429", "captura falhou: HTTP 451", "captura falhou: HTTP 400",
    "captura falhou: HTTP 418",
]  # fmt: skip


@pytest.mark.parametrize("motivo", _FALHAS_QUE_CONTAM + _FALHAS_DE_ALCANCE)
def test_e6_falhas_que_contam(motivo, matriz):
    falha = {"captura": ("erro", motivo)}
    sinais, _ = sinais_da_execucao(execucao(status=falha), matriz, execucao(status=falha))
    assert [s.tipo for s in sinais] == ["site_fora_do_ar"]
    # misturada com uma falha de outra classe que também conta
    sinais, _ = sinais_da_execucao(execucao(status=falha), matriz, execucao(status={"captura": FALHA}))
    assert [s.tipo for s in sinais] == ["site_fora_do_ar"]


@pytest.mark.parametrize("motivo", _RECUSAS)
def test_e6_recusa_ao_visitante_nao_e_queda(motivo, matriz):
    recusa = {"captura": ("erro", motivo)}
    assert sinais_da_execucao(execucao(status=recusa), matriz, execucao(status=recusa))[0] == []
    # numa execução só, com uma queda de verdade na outra, também não
    assert sinais_da_execucao(execucao(status=recusa), matriz, execucao(status={"captura": FALHA}))[0] == []
    assert sinais_da_execucao(execucao(status={"captura": FALHA}), matriz, execucao(status=recusa))[0] == []


@pytest.mark.parametrize("motivo", _FALHAS_DO_ANALISTA)
def test_e6_falha_do_lado_do_analista_nao_e_queda(motivo, matriz):
    falha = {"captura": ("erro", motivo)}
    assert sinais_da_execucao(execucao(status=falha), matriz, execucao(status=falha))[0] == []
    assert sinais_da_execucao(execucao(status=falha), matriz, execucao(status={"captura": FALHA}))[0] == []


def test_e6_duas_falhas_de_captura(matriz):
    ex, anterior = execucao(status={"captura": FALHA}), execucao(status={"captura": FALHA})
    sinais, _ = sinais_da_execucao(ex, matriz, anterior)
    assert [(s.tipo, s.estagio, s.data) for s in sinais] == [("site_fora_do_ar", "E6", HOJE)]


def test_e6_uma_falha_nao_basta(matriz):
    assert sinais_da_execucao(execucao(status={"captura": FALHA}), matriz, None)[0] == []
    assert sinais_da_execucao(execucao(status={"captura": FALHA}), matriz, execucao())[0] == []
    assert sinais_da_execucao(execucao(), matriz, execucao(status={"captura": FALHA}))[0] == []


def test_e6_captura_bloqueada_nao_e_falha(matriz):
    bloqueada = {"captura": {**base()["captura"], "bloqueada": True}}
    assert sinais_da_execucao(execucao(bloqueada), matriz, execucao(status={"captura": FALHA}))[0] == []


def test_e6_erro_do_codigo_nao_e_site_fora(matriz):
    bug = ("erro", "erro inesperado: KeyError: 'x'")
    assert sinais_da_execucao(execucao(status={"captura": bug}), matriz, execucao(status={"captura": bug}))[0] == []


def test_e6_retroativo_nao_le_dns(matriz):
    # no retroativo o dns e a captura são pulados: nada de E6
    assert sinais_da_execucao(retroativa(), matriz, None)[0] == []


# ---------------------------------------------------------------------------- modificadores


def test_modificadores_deterministicos(matriz):
    ex = execucao(
        {
            "pend_a1": resp(valor={"pct_mes": 34.78, "taxa_diaria": True, "garantido": False}),
            "pend_d1": resp(valor={"historico_fraude": True, "pessoas": []}),
            "rdap": {**base()["rdap"], "registro": "2026-03-01"},
            "pend_b": resp(valor={**B_NEGATIVO, "carencia_com_multa": True}),
        }
    )
    _, mods = sinais_da_execucao(ex, matriz, None)
    assert [(m.id, m.direcao, m.origem) for m in mods] == [
        ("retorno_alto", "encurta", "A1"), ("historico_fraude", "encurta", "D1"),
        ("identidade_nova", "encurta", "D3"), ("carencia_longa", "alonga", "B3"),
    ]  # fmt: skip
    assert mods[0].evidencia is not None and mods[0].evidencia.trecho == "trecho literal citado da fonte"
    assert mods[2].evidencia is None  # D3 vem do coletor, sem trecho


def test_retorno_alto_so_com_a1_4(matriz):
    _, mods = sinais_da_execucao(execucao(), matriz, None)  # A1=3
    assert mods == []


def test_modificadores_da_pe(matriz):
    evidencias = [ev("relato"), ev("imprensa", trecho="reportagem sobre a investigação em curso")]
    pe = _pe(
        [{"tipo": "eventos", "data": None, "evidencia": 0}],
        [{"id": "investigacao_em_curso", "evidencia": 1}, {"id": "idosos_alvo", "evidencia": 0},
         {"id": "investigacao_em_curso", "evidencia": 0}],
        evidencias,
    )  # fmt: skip
    _, mods = sinais_da_execucao(execucao({"pend_e": pe}), matriz, None)
    assert mods == [
        ModificadorAplicado(
            id="investigacao_em_curso", direcao="corte_sem_aviso", origem="P-E",
            evidencia=Evidencia.model_validate(evidencias[1]),
        ),
        ModificadorAplicado(
            id="idosos_alvo", direcao="alonga", origem="P-E", evidencia=Evidencia.model_validate(evidencias[0])
        ),
    ]  # fmt: skip
    e = pontuar_eixo2(*sinais_da_execucao(execucao({"pend_e": pe}), matriz, None), matriz)
    assert e.estagio == "E2" and [m.id for m in e.modificadores] == ["investigacao_em_curso", "idosos_alvo"]
