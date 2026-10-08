"""Pontuação (spec 8): a matriz versionada e as contas dos dois eixos, em código determinístico.

- `carregar_matriz` lê o `matriz.yaml` (o dossiê registra a versão e o hash);
- `itens_da_execucao` transforma as saídas dos coletores e as respostas às pendências nos 15 itens A1–D4;
- `pontuar_eixo1` faz o intervalo, a classe e as regras de corte, interpretadas pelo tipo (sem `eval`);
- `sinais_da_execucao` e `pontuar_eixo2` fazem o estágio E0–E7, a janela e os modificadores.

A R3 é uma regra do eixo 1 que depende de um sinal da P-E (`prova_aportes_novos`): quem monta o dossiê passa a
`pontuar_eixo1` os sinais devolvidos por `sinais_da_execucao`.

Regras que valem para todos os itens:
- só respostas `confirmado`/`corrigido` têm o `valor` lido. `nao_encontrado` vira `nao_encontrado`, `inconclusivo`
  vira `inconclusivo`, nó `pulado` vira `nao_se_aplica`; nó sem resposta, em erro, bloqueado ou com a pendência
  aberta vira `nao_verificado`;
- um campo listado em `vazamento_temporal` do nó que o produziu é o de hoje, não o do `as_of`, e não entra na conta:
  o item que dependeria só dele fica `nao_verificado`.
"""

from __future__ import annotations

import calendar
import hashlib
import operator
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from radar.modelos import EstadoItem, Evidencia, Item, Resposta, Sinal
from radar.pendencias.esquemas import ValorA1, ValorA2, ValorA3, ValorB, ValorC, ValorC4, ValorD1, ValorD4, ValorE

if TYPE_CHECKING:
    from radar.execucao import ExecucaoSalva

CAMINHO_MATRIZ = Path(__file__).with_name("matriz.yaml")
# a ordem das classes do eixo 1: as regras de corte só sobem a classe (spec 8.2)
CLASSES = ("sem sinal estrutural forte", "suspeito", "provável", "característico", "confirmado")
IDS_ITENS = ("A1", "A2", "A3", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4", "D1", "D2", "D3", "D4")

# sinais determinísticos do eixo 2 (spec 8.3)
TIPO_E0 = "registro_recente"
TIPO_FORA_DO_AR = "site_fora_do_ar"
_ESTAGIO_E0 = "E0"
_DIAS_E0 = 90
_FONTE_COLETOR = "coletor"
# o motivo de erro da captura (radar/nos/captura.py) e os códigos HTTP da página inicial que dizem "site fora do ar"
_PREFIXO_FALHA_CAPTURA = "captura falhou:"
_HTTP_DA_CAPTURA = re.compile(r"HTTP (\d{3})")
_HTTP_SITE_SUMIU = frozenset({404, 410})  # além dos 5xx

_SEM_PONTOS = frozenset({"nao_se_aplica", "nao_encontrado"})
_EM_ABERTO = frozenset({"nao_verificado", "inconclusivo"})
_SECAO_K = ("64", "65", "66")  # atividades financeiras no CNAE
_FONTES_DE_REGISTRO = ("cvm", "bcb", "bcb_dominio")
_FONTES_BCB = frozenset({"bcb", "bcb_dominio"})
_NOTA_BCB_DE_HOJE = " (lista do BCB é a de hoje)"
_MAIOR_CNAE = 9_999_999  # o código tem 7 dígitos
_OPERADORES: dict[str, Callable[[int, int], bool]] = {
    ">=": operator.ge, ">": operator.gt, "==": operator.eq, "!=": operator.ne, "<=": operator.le, "<": operator.lt,
}  # fmt: skip


# ---------------------------------------------------------------------------- matriz


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Faixa(_Estrito):
    de: int
    ate: int
    classe: str


class ItemMatriz(_Estrito):
    nome: str
    max: int = Field(gt=0)
    # A1, em % ao mês, três valores [l1, l2, l3] estritamente crescentes (R-T14-fronteira-a1): 1 ponto se pct <= l1;
    # 2 se l1 < pct < l2; 3 se l2 <= pct <= l3; o máximo se pct > l3. O l2 (3,0) abre a faixa de cima porque a R1
    # do relatório diz "3% ao mês ou mais (A1 >= 3)" e a tabela, "de 3% a 10% = 3"
    limites_pct_mes: list[float] | None = None
    taxa_diaria: int | None = None  # A1: pontos do retorno por dia
    valores: dict[str, int] | None = None  # B1: pontos de cada forma de indicação
    meses_limite: int | None = None  # D3


class Condicao(_Estrito):
    item: str
    op: Literal[">=", ">", "==", "!=", "<=", "<"]
    valor: int


class RegraCorte(_Estrito):
    """`classe_minima`: com todas as `condicoes`, a classe é no mínimo `classe`. `classe_fixa`: com o `sinal`, a
    classe é `classe`."""

    id: str
    tipo: Literal["classe_minima", "classe_fixa"]
    classe: str
    condicoes: list[Condicao] = []
    sinal: str | None = None


class ModificadorMatriz(TypedDict):
    direcao: Literal["encurta", "alonga", "corte_sem_aviso"]
    origem: str  # id de item ou "P-E"


class Matriz(BaseModel):
    """O `matriz.yaml` validado. `hash` é o sha256 dos bytes do arquivo.

    `estagios` (`dict[str, str]`) e `modificadores` (`dict[str, dict]`) são dicionários comuns: a P-E os lê por duck
    typing (`definicoes.validos_da_matriz`).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    versao: str
    hash: str
    faixas: list[Faixa]
    itens: dict[str, ItemMatriz]
    regras_corte: list[RegraCorte]
    estagios: dict[str, str]
    janelas: dict[str, str]
    modificadores: dict[str, ModificadorMatriz]

    @model_validator(mode="after")
    def _coerente(self) -> Matriz:
        erros = []
        if set(self.itens) != set(IDS_ITENS):
            erros.append(f"os itens têm de ser {', '.join(IDS_ITENS)}")
        erros += self._erros_dos_parametros() + self._erros_das_faixas() + self._erros_das_regras()
        if list(self.janelas) != [f"E{n}" for n in range(len(self.janelas))]:
            erros.append("as janelas têm de ser E0, E1, ... En, nessa ordem")
        if fora := sorted(set(self.estagios.values()) - set(self.janelas)):
            erros.append(f"estágios sem janela: {', '.join(fora)}")
        if fora := sorted(m for m, d in self.modificadores.items() if d["origem"] not in {*self.itens, "P-E"}):
            erros.append(f"modificadores com origem desconhecida: {', '.join(fora)}")
        if erros:
            raise ValueError("; ".join(erros))
        return self

    def _erros_dos_parametros(self) -> list[str]:
        """Os parâmetros de A1, B1 e D3 existem e nenhum dá mais pontos que o máximo do item."""
        erros = []
        a1, b1, d3 = self.itens.get("A1"), self.itens.get("B1"), self.itens.get("D3")
        if a1 is not None:
            limites = a1.limites_pct_mes
            if limites is None or a1.taxa_diaria is None:
                erros.append("A1 precisa de limites_pct_mes e taxa_diaria")
            elif len(limites) != 3 or not limites[0] < limites[1] < limites[2]:
                erros.append("A1.limites_pct_mes precisa de três valores estritamente crescentes")
            elif a1.taxa_diaria > a1.max or a1.max <= len(limites):
                erros.append("A1: taxa_diaria e as faixas de limites_pct_mes têm de caber no máximo")
        if b1 is not None:
            if b1.valores is None:
                erros.append("B1 precisa de valores")
            elif any(pontos > b1.max for pontos in b1.valores.values()):
                erros.append("B1: valores acima do máximo")
        if d3 is not None and d3.meses_limite is None:
            erros.append("D3 precisa de meses_limite")
        return erros

    def _erros_das_faixas(self) -> list[str]:
        """As faixas cobrem de 0 ao total dos máximos, sem buraco nem sobreposição, com classes conhecidas."""
        erros = [f"classe desconhecida na faixa: {f.classe}" for f in self.faixas if f.classe not in CLASSES]
        inicio = 0
        for faixa in self.faixas:
            if faixa.de != inicio or faixa.ate < faixa.de:
                erros.append(f"faixa {faixa.de}–{faixa.ate} não começa em {inicio}")
            inicio = faixa.ate + 1
        if inicio <= sum(i.max for i in self.itens.values()):
            erros.append(f"as faixas param em {inicio - 1}, abaixo do total dos máximos")
        return erros

    def _erros_das_regras(self) -> list[str]:
        erros = []
        for regra in self.regras_corte:
            if regra.classe not in CLASSES:
                erros.append(f"{regra.id}: classe desconhecida {regra.classe!r}")
            if regra.tipo == "classe_minima" and not regra.condicoes:
                erros.append(f"{regra.id}: classe_minima sem condições")
            if regra.tipo == "classe_fixa" and not regra.sinal:
                erros.append(f"{regra.id}: classe_fixa sem sinal")
            erros += [f"{regra.id}: item desconhecido {c.item}" for c in regra.condicoes if c.item not in self.itens]
        return erros


def carregar_matriz(caminho: Path | None = None) -> Matriz:
    """A matriz de `caminho` (padrão: `radar/matriz.yaml`). Matriz incoerente levanta `pydantic.ValidationError`."""
    bruto = Path(caminho if caminho is not None else CAMINHO_MATRIZ).read_bytes()
    dados = yaml.safe_load(bruto.decode("utf-8"))
    if not isinstance(dados, dict):
        raise ValueError(f"matriz sem o mapeamento esperado: {caminho or CAMINHO_MATRIZ}")
    return Matriz.model_validate({**dados, "hash": hashlib.sha256(bruto).hexdigest()})


def pontos_a1(pct_mes: float | None, taxa_diaria: bool, matriz: Matriz) -> int:
    """Pontos do A1 pelo retorno prometido em % ao mês (R-T14-fronteira-a1, com `limites_pct_mes` = [1,2; 3,0; 10,0]):
    sem retorno (`None` ou <= 0) e sem taxa diária, 0; pct <= 1,2: 1; 1,2 < pct < 3,0: 2; 3,0 <= pct <= 10,0: 3;
    pct > 10,0: o máximo (4); taxa diária: `taxa_diaria` (4)."""
    a1 = matriz.itens["A1"]
    if taxa_diaria:
        return a1.taxa_diaria
    if pct_mes is None or pct_mes <= 0:
        return 0
    baixo, meio, alto = a1.limites_pct_mes
    if pct_mes <= baixo:
        return 1
    if pct_mes < meio:
        return 2
    if pct_mes <= alto:
        return 3
    return a1.max


# ---------------------------------------------------------------------------- leitura da execução


def _status(ex: ExecucaoSalva, no: str) -> tuple[str | None, str | None]:
    estado = ex.status.get(no) or {}
    return estado.get("status"), estado.get("motivo")


def _feito(ex: ExecucaoSalva, no: str) -> dict | None:
    """As saídas do nó, se ele terminou `feito`."""
    if _status(ex, no)[0] != "feito":
        return None
    saida = ex.saidas.get(no)
    return saida if isinstance(saida, dict) else None


def _sem_resultado(ex: ExecucaoSalva, no: str) -> str:
    """A nota de um nó que não terminou `feito`."""
    status, motivo = _status(ex, no)
    if status is None:
        return f"nó {no} não executado"
    return f"nó {no} {status}" + (f": {motivo}" if motivo else "")


def _vazados(saida: dict) -> set[str]:
    return set(saida.get("vazamento_temporal") or ())


def _data(valor: Any) -> date | None:
    if not isinstance(valor, str):
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _data_no_as_of(saida: dict, campo: str, as_of: date) -> date | None:
    """A data do campo, se ela vale no `as_of`: não vazada, legível e não posterior ao `as_of` (uma data depois dele
    é de outro registro, não diz nada do que havia na data)."""
    if campo in _vazados(saida):
        return None
    data = _data(saida.get(campo))
    return data if data is not None and data <= as_of else None


def _somar_meses(d: date, meses: int) -> date:
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def _julgamento_ativo(ex: ExecucaoSalva, pendencia: str) -> dict | None:
    return next((j for j in ex.julgamentos if j.get("pendencia") == pendencia and j.get("ativa")), None)


@dataclass(frozen=True)
class _Leitura:
    """O que a pendência deu. `valor` só existe com resposta `confirmado`/`corrigido` e válida; sem ele, `estado`
    é o estado do item (com 0 pontos)."""

    estado: EstadoItem | None = None
    valor: Any = None
    resposta: Resposta | None = None
    nota: str | None = None


def _ler_pendencia(ex: ExecucaoSalva, no: str, pendencia: str, modelo: type[BaseModel]) -> _Leitura:
    status, motivo = _status(ex, no)
    if status == "pulado":
        return _Leitura("nao_se_aplica", nota=f"{pendencia} não gerada: {motivo}")
    if (ex.pendencias.get(pendencia) or {}).get("aberta"):
        return _Leitura("nao_verificado", nota=f"{pendencia} aberta: falta a resposta")
    saida = _feito(ex, no)
    if saida is None:
        if status in (None, "erro", "bloqueado"):
            return _Leitura("nao_verificado", nota=_sem_resultado(ex, no))
        return _Leitura("nao_verificado", nota=f"{pendencia} sem resposta ({no} {status})")
    try:
        resposta = Resposta.model_validate(saida.get("resposta"))
    except ValidationError as erro:
        return _Leitura("nao_verificado", nota=f"{pendencia}: resposta inválida ({erro.error_count()} erro(s))")
    if resposta.status in ("nao_encontrado", "inconclusivo"):
        return _Leitura(resposta.status, resposta=resposta)
    try:
        valor = modelo.model_validate(resposta.valor)
    except ValidationError as erro:
        return _Leitura("nao_verificado", nota=f"{pendencia}: valor inválido ({erro.error_count()} erro(s))")
    return _Leitura(valor=valor, resposta=resposta)


# As categorias de candidato da extração que apontam para cada item: com candidato delas na pendência, o item é
# "regex_confirmada"; sem, quem achou foi o Claude. O "garantido" sozinho não traz o número do retorno do A1, e os
# candidatos da P-C4 (deliberações citadas pelo nome) vêm do índice da CVM, não de regex.
_CATEGORIAS_DO_ITEM: dict[str, tuple[str, ...]] = {
    "A1": ("percentual",), "A2": ("historico_rentabilidade",), "A3": ("investimento",),
    "B1": ("indicacao",), "B2": ("token",), "B3": ("carencia",), "B4": ("saque",),
    "C2": ("contrato",), "C3": ("pix", "carteira"), "C4": (), "D1": (), "D4": ("rede_social",),
}  # fmt: skip


def _origem(ex: ExecucaoSalva, item_id: str, pendencia: str, leitura: _Leitura, confirmado: bool) -> str:
    """`regex_confirmada` só com o item `confirmado`: se o Claude não confirmou o candidato, o estado vem do
    julgamento dele."""
    if leitura.resposta is None:
        return "nenhuma"
    if not confirmado:
        return "claude"
    candidatos = (ex.pendencias.get(pendencia) or {}).get("candidatos") or []
    categorias = _CATEGORIAS_DO_ITEM[item_id]
    if any(isinstance(c, dict) and c.get("categoria") in categorias for c in candidatos):
        return "regex_confirmada"
    return "claude"


# ---------------------------------------------------------------------------- itens


@dataclass(frozen=True)
class _PelaPendencia:
    no: str
    pendencia: str
    modelo: type[BaseModel]
    pontos: Callable[[Any, Matriz], int]  # (valor confirmado, matriz) -> pontos; 0 vira nao_se_aplica


def _se(item_id: str, campo: str) -> Callable[[Any, Matriz], int]:
    """O máximo do item se o campo booleano do valor é verdadeiro; senão 0."""
    return lambda valor, matriz: matriz.itens[item_id].max if getattr(valor, campo) else 0


def _pontos_a3(valor: ValorA3, matriz: Matriz) -> int:
    return 0 if valor.origem_verificavel or valor.custodiante_independente else matriz.itens["A3"].max


_PELA_PENDENCIA = {
    "A1": _PelaPendencia("pend_a1", "P-A1", ValorA1, lambda v, m: pontos_a1(v.pct_mes, v.taxa_diaria, m)),
    "A2": _PelaPendencia("pend_a2", "P-A2", ValorA2, _se("A2", "serie_lisa")),
    "A3": _PelaPendencia("pend_a3", "P-A3", ValorA3, _pontos_a3),
    "B1": _PelaPendencia("pend_b", "P-B", ValorB, lambda v, m: m.itens["B1"].valores.get(v.indicacao, 0)),
    "B2": _PelaPendencia("pend_b", "P-B", ValorB, _se("B2", "token_proprio")),
    "B3": _PelaPendencia("pend_b", "P-B", ValorB, _se("B3", "carencia_com_multa")),
    "B4": _PelaPendencia("pend_b", "P-B", ValorB, _se("B4", "taxa_para_sacar")),
    "C2": _PelaPendencia("pend_c", "P-C", ValorC, _se("C2", "contrato_atipico")),
    "C4": _PelaPendencia("pend_c4", "P-C4", ValorC4, _se("C4", "alerta_vigente")),
    "D1": _PelaPendencia("pend_d1", "P-D1", ValorD1, _se("D1", "historico_fraude")),
    "D4": _PelaPendencia("pend_d4", "P-D4", ValorD4, _se("D4", "credibilidade_emprestada")),
}


def _item_da_pendencia(ex: ExecucaoSalva, item_id: str, matriz: Matriz) -> Item:
    fonte = _PELA_PENDENCIA[item_id]
    leitura = _ler_pendencia(ex, fonte.no, fonte.pendencia, fonte.modelo)
    if leitura.valor is None:
        estado, pontos = leitura.estado, 0
    else:
        pontos = fonte.pontos(leitura.valor, matriz)
        estado = "confirmado" if pontos > 0 else "nao_se_aplica"
    return Item(
        id=item_id,
        estado=estado,
        pontos=pontos,
        maximo=matriz.itens[item_id].max,
        origem=_origem(ex, item_id, fonte.pendencia, leitura, confirmado=estado == "confirmado"),
        evidencias=leitura.resposta.evidencias if leitura.resposta is not None else [],
        nota=leitura.nota,
    )


def _oferta(a1: Item, a3: Item) -> bool | None:
    """A oferta é de investimento (A1 > 0 ou A3 > 0)? `None`: não se sabe, porque um dos dois está em aberto."""
    if any(i.estado == "confirmado" and i.pontos > 0 for i in (a1, a3)):
        return True
    if all(i.estado in _SEM_PONTOS for i in (a1, a3)):
        return False
    return None


def _item_c1(ex: ExecucaoSalva, matriz: Matriz, oferta: bool | None) -> Item:
    """Oferta de investimento sem registro na CVM nem no BCB. Sem oferta, o registro não importa. Registro sustentado
    só por dado de hoje (o BCB no retroativo) não decide: fica `nao_verificado`."""
    maximo = matriz.itens["C1"].max

    def item(estado: EstadoItem, nota: str, pontos: int = 0, origem: str = "coletor") -> Item:
        return Item(id="C1", estado=estado, pontos=pontos, maximo=maximo, origem=origem, nota=nota)

    if oferta is False:
        return item("nao_se_aplica", "sem oferta de investimento (A1 e A3 sem pontos)")
    saida = _feito(ex, "registros")
    if saida is None:
        return item("nao_verificado", _sem_resultado(ex, "registros"), origem="nenhuma")
    vazados = _vazados(saida)
    if "registrado" in vazados:
        return item("nao_verificado", "registros.registrado é o de hoje (vazamento temporal)", origem="nenhuma")
    if saida.get("registrado") is True:
        sustentam = [f for f in _FONTES_DE_REGISTRO if saida.get(f)]
        validas = [f for f in sustentam if f not in vazados]
        if sustentam and not validas:
            nota = f"registro só em dado de hoje ({', '.join(sustentam)}: vazamento temporal)"
            if set(sustentam) & _FONTES_BCB:
                nota += _NOTA_BCB_DE_HOJE
            return item("nao_verificado", nota, origem="nenhuma")
        return item("nao_se_aplica", f"registrado ({', '.join(validas) or 'registros'})")
    if oferta is None:
        nota = "sem registro, mas a oferta de investimento não foi verificada (A1/A3)"
        return item("nao_verificado", nota, origem="nenhuma")
    nota = "oferta de investimento sem registro na CVM nem no BCB"
    if saida.get("motivo"):
        nota += f" ({saida['motivo']}: só o domínio foi consultado)"
    if vazados & _FONTES_BCB:
        nota += _NOTA_BCB_DE_HOJE  # a ausência no BCB é a de hoje: o Olinda não tem datas
    return item("confirmado", nota, pontos=maximo)


@dataclass(frozen=True)
class _Parte:
    """Uma das três partes do C3. `dispara=None`: não se sabe, e `estado` diz se falta verificar ou se é
    inconclusivo."""

    dispara: bool | None
    nota: str | None = None
    estado: EstadoItem = "nao_verificado"


def _c3_pela_pc(leitura: _Leitura) -> _Parte:
    if leitura.valor is not None:
        motivos = [
            texto
            for texto, marcado in (
                ("conta de PF ou de terceiro", leitura.valor.conta_pf_ou_terceiro),
                ("sede ou licença no exterior", leitura.valor.offshore_alegado),
            )
            if marcado
        ]
        return _Parte(bool(motivos), "P-C: " + " e ".join(motivos) if motivos else None)
    if leitura.estado in _EM_ABERTO:
        return _Parte(None, leitura.nota or "P-C inconclusiva", leitura.estado)
    return _Parte(False)


def _c3_sem_cnpj(ex: ExecucaoSalva) -> _Parte:
    """Marca quando a P-CNPJ resultou em `nao_encontrado` e o nó `cnpj` ficou sem CNPJ."""
    saida = _feito(ex, "cnpj")
    if saida is None:
        return _Parte(None, _sem_resultado(ex, "cnpj"))
    if saida.get("cnpj") is not None:
        return _Parte(False)
    status = ((_julgamento_ativo(ex, "P-CNPJ") or {}).get("resposta") or {}).get("status")
    if status == "nao_encontrado":
        return _Parte(True, "sem CNPJ (P-CNPJ nao_encontrado)")
    if status == "inconclusivo":
        return _Parte(None, "P-CNPJ inconclusiva: não se sabe se há CNPJ", "inconclusivo")
    return _Parte(None, "sem CNPJ e sem resposta à P-CNPJ que o explique")


def _c3_pelo_cnae(ex: ExecucaoSalva, oferta: bool | None) -> _Parte:
    """Marca quando o CNAE está fora da seção K (64–66) e a oferta é de investimento."""
    if oferta is False:
        return _Parte(False)
    saida = _feito(ex, "cnpj")
    if saida is None:
        return _Parte(None, _sem_resultado(ex, "cnpj"))
    if saida.get("cnpj") is None:
        return _Parte(False)  # sem empresa não há CNAE: quem responde é a parte "sem CNPJ"
    if "cnae" in _vazados(saida):
        return _Parte(None, "CNAE de hoje, não o do as_of (vazamento temporal)")
    cnae = saida.get("cnae")
    if not isinstance(cnae, int) or isinstance(cnae, bool) or not 0 < cnae <= _MAIOR_CNAE:
        return _Parte(None, "CNAE desconhecido")
    codigo = f"{cnae:07d}"  # o int perde o zero à esquerda do código de 7 dígitos
    if codigo[:2] in _SECAO_K:
        return _Parte(False)
    if oferta is None:
        return _Parte(None, f"CNAE {codigo} fora da seção K, mas a oferta não foi verificada (A1/A3)")
    return _Parte(True, f"CNAE {codigo} fora da seção K (64–66) com oferta de investimento")


def _item_c3(ex: ExecucaoSalva, matriz: Matriz, oferta: bool | None) -> Item:
    """A parte automática (sem CNPJ, ou CNAE incoerente com a oferta) somada à P-C: basta uma marcar."""
    leitura = _ler_pendencia(ex, "pend_c", "P-C", ValorC)
    pela_pc = _c3_pela_pc(leitura)
    automaticas = (_c3_sem_cnpj(ex), _c3_pelo_cnae(ex, oferta))
    partes = (pela_pc, *automaticas)
    maximo = matriz.itens["C3"].max
    evidencias_pc = leitura.resposta.evidencias if leitura.resposta is not None else []
    if disparadas := [p for p in partes if p.dispara]:
        if any(p.dispara for p in automaticas):
            origem = "coletor"
        else:
            origem = _origem(ex, "C3", "P-C", leitura, confirmado=True)
        return Item(
            id="C3", estado="confirmado", pontos=maximo, maximo=maximo, origem=origem,
            evidencias=evidencias_pc if pela_pc.dispara else [], nota="; ".join(p.nota for p in disparadas),
        )  # fmt: skip
    origem_pc = _origem(ex, "C3", "P-C", leitura, confirmado=False)
    if abertas := [p for p in partes if p.dispara is None]:
        estado = "nao_verificado" if any(p.estado == "nao_verificado" for p in abertas) else "inconclusivo"
        return Item(
            id="C3", estado=estado, pontos=0, maximo=maximo, origem=origem_pc, evidencias=evidencias_pc,
            nota="; ".join(p.nota for p in abertas if p.nota),
        )  # fmt: skip
    return Item(
        id="C3", estado="nao_encontrado" if leitura.estado == "nao_encontrado" else "nao_se_aplica", pontos=0,
        maximo=maximo, origem=origem_pc if origem_pc != "nenhuma" else "coletor", evidencias=evidencias_pc,
    )  # fmt: skip


def _evidencia_cvm(correspondencia: dict) -> Evidencia:
    return Evidencia(
        fonte=correspondencia.get("url") or f"CVM, Deliberação {correspondencia.get('numero')}",
        trecho=correspondencia.get("trecho") or "",
        data_fonte=_data(correspondencia.get("data")),
        tipo_fonte="oficial",
    )


def _item_c4(ex: ExecucaoSalva, matriz: Matriz) -> Item:
    """A deliberação da CVM que cita o CNPJ ou o domínio confirma sozinha; correspondência só pelo nome vai para a
    P-C4, que decide o item."""
    saida = _feito(ex, "cvm_alertas")
    if saida is not None and "correspondencias" not in _vazados(saida):
        exatas = [
            c
            for c in saida.get("correspondencias") or []
            if isinstance(c, dict) and c.get("tipo") in ("cnpj", "dominio")
        ]
        if exatas:
            maximo = matriz.itens["C4"].max
            chave = {"cnpj": "o CNPJ", "dominio": "o domínio"}
            return Item(
                id="C4", estado="confirmado", pontos=maximo, maximo=maximo, origem="coletor",
                evidencias=[_evidencia_cvm(c) for c in exatas],
                nota="; ".join(f"Deliberação CVM {c.get('numero')} cita {chave[c['tipo']]}" for c in exatas),
            )  # fmt: skip
    return _item_da_pendencia(ex, "C4", matriz)


def _item_d3(ex: ExecucaoSalva, matriz: Matriz) -> Item:
    """Domínio registrado ou CNPJ aberto menos de `meses_limite` meses antes do `as_of`. Sem empresa identificada, só
    o domínio conta; uma data que não se sabe impede o `nao_se_aplica`."""
    info = matriz.itens["D3"]
    as_of = ex.ctx.as_of
    conhecidas: list[tuple[str, date]] = []
    desconhecidas: list[str] = []
    for rotulo, no, campo in (("domínio registrado", "rdap", "registro"), ("CNPJ aberto", "cnpj", "abertura")):
        saida = _feito(ex, no)
        if saida is None:
            desconhecidas.append(_sem_resultado(ex, no))
        elif no == "cnpj" and saida.get("cnpj") is None:
            continue
        elif (data := _data_no_as_of(saida, campo, as_of)) is None:
            desconhecidas.append(f"{rotulo}: data indisponível no as_of")
        else:
            conhecidas.append((rotulo, data))

    def item(estado: EstadoItem, nota: str, pontos: int = 0, origem: str = "coletor") -> Item:
        return Item(id="D3", estado=estado, pontos=pontos, maximo=info.max, origem=origem, nota=nota)

    if novas := [(r, d) for r, d in conhecidas if as_of < _somar_meses(d, info.meses_limite)]:
        return item("confirmado", "; ".join(f"{r} em {d.isoformat()}" for r, d in novas), pontos=info.max)
    if desconhecidas or not conhecidas:
        return item("nao_verificado", "; ".join(desconhecidas) or "sem datas", origem="nenhuma")
    nota = "; ".join(f"{r} em {d.isoformat()}" for r, d in conhecidas) + f": {info.meses_limite} meses ou mais"
    return item("nao_se_aplica", nota)


def itens_da_execucao(ex: ExecucaoSalva, matriz: Matriz) -> dict[str, Item]:
    """Os 15 itens da execução, na ordem da matriz (spec 8.2). D2 (clone de esquema) o Núcleo não verifica."""
    a1 = _item_da_pendencia(ex, "A1", matriz)
    a3 = _item_da_pendencia(ex, "A3", matriz)
    oferta = _oferta(a1, a3)
    calculados = {
        "A1": a1,
        "A3": a3,
        "C1": _item_c1(ex, matriz, oferta),
        "C3": _item_c3(ex, matriz, oferta),
        "C4": _item_c4(ex, matriz),
        "D2": Item(
            id="D2", estado="nao_verificado", pontos=0, maximo=matriz.itens["D2"].max, origem="nenhuma",
            nota="clone de esquema conhecido: o Núcleo não verifica",
        ),  # fmt: skip
        "D3": _item_d3(ex, matriz),
    }
    return {i: calculados[i] if i in calculados else _item_da_pendencia(ex, i, matriz) for i in matriz.itens}


# ---------------------------------------------------------------------------- eixo 1


class Eixo1(BaseModel):
    minimo: int
    maximo: int
    classe: str
    pode_chegar_a: str | None
    regras_disparadas: list[str]
    regras_pendentes: list[str]


def _intervalo(item: Item) -> tuple[int, int]:
    if item.estado == "confirmado":
        return item.pontos, item.pontos
    if item.estado in _EM_ABERTO:
        return 0, item.maximo
    return 0, 0


def _classe_da_faixa(pontos: int, matriz: Matriz) -> str:
    for faixa in matriz.faixas:
        if faixa.de <= pontos <= faixa.ate:
            return faixa.classe
    raise ValueError(f"{pontos} pontos fora das faixas da matriz")


def _mais_alta(a: str, b: str) -> str:
    return max(a, b, key=CLASSES.index)


def _situacao(condicao: Condicao, item: Item) -> bool | None:
    """A condição vale, não vale ou (`None`) depende de um item em aberto que ainda pode satisfazê-la. Regra só
    dispara com item confirmado: em aberto, nunca vale."""
    comparar = _OPERADORES[condicao.op]
    if item.estado in _EM_ABERTO:
        return None if any(comparar(v, condicao.valor) for v in range(item.maximo + 1)) else False
    return comparar(item.pontos if item.estado == "confirmado" else 0, condicao.valor)


def pontuar_eixo1(itens: dict[str, Item], matriz: Matriz, *, sinais: Iterable[Sinal]) -> Eixo1:
    """Intervalo, classe e regras de corte (spec 8.2).

    `sinais` são os de `sinais_da_execucao` e são obrigatórios (sem eles a R3 sumiria em silêncio); `[]` só quando
    não há sinal mesmo. A classe parte da faixa do mínimo, sobe para a de cada regra `classe_minima` disparada e
    vira a de uma regra `classe_fixa` cujo sinal está em `sinais`. `pode_chegar_a` é a classe da faixa do máximo,
    quando é mais alta.
    Uma regra fica pendente ("R1 dispara se C1 se confirmar") quando só falta um item, em aberto, e as outras
    condições já valem.
    """
    minimo = sum(_intervalo(i)[0] for i in itens.values())
    maximo = sum(_intervalo(i)[1] for i in itens.values())
    classe = _classe_da_faixa(minimo, matriz)
    tipos_de_sinal = {s.tipo for s in sinais}
    disparadas: list[str] = []
    pendentes: list[str] = []
    fixa: str | None = None
    for regra in matriz.regras_corte:
        if regra.tipo == "classe_fixa":
            if regra.sinal in tipos_de_sinal:
                disparadas.append(regra.id)
                fixa = regra.classe if fixa is None else _mais_alta(fixa, regra.classe)
            continue
        situacoes = [_situacao(c, itens[c.item]) for c in regra.condicoes]
        if all(s is True for s in situacoes):
            disparadas.append(regra.id)
            classe = _mais_alta(classe, regra.classe)
        elif False not in situacoes:
            faltam = list(dict.fromkeys(c.item for c, s in zip(regra.condicoes, situacoes, strict=True) if s is None))
            if len(faltam) == 1:
                pendentes.append(f"{regra.id} dispara se {faltam[0]} se confirmar")
    if fixa is not None:
        classe = fixa
    do_maximo = _classe_da_faixa(maximo, matriz)
    return Eixo1(
        minimo=minimo,
        maximo=maximo,
        classe=classe,
        pode_chegar_a=do_maximo if CLASSES.index(do_maximo) > CLASSES.index(classe) else None,
        regras_disparadas=disparadas,
        regras_pendentes=pendentes,
    )


# ---------------------------------------------------------------------------- eixo 2


class ModificadorAplicado(BaseModel):
    id: str
    direcao: str
    origem: str  # id do item ou "P-E"
    evidencia: Evidencia | None = None


class Eixo2(BaseModel):
    estagio: str | None
    sinal: Sinal | None
    janela: str | None
    modificadores: list[ModificadorAplicado]


def _da_pe(ex: ExecucaoSalva, matriz: Matriz) -> tuple[list[Sinal], list[ModificadorAplicado]]:
    """Sinais e modificadores da P-E respondida com `confirmado`/`corrigido`. O tipo de fonte do sinal é o da
    evidência que ele cita. Ficam de fora:
    - o sinal datado depois do `as_of`: é fato posterior, vazamento temporal (sem data, não dá para dizer que é);
    - o tipo ou modificador que a matriz não conhece (execução antiga pontuada com a matriz atual);
    - o que cita evidência inexistente."""
    leitura = _ler_pendencia(ex, "pend_e", "P-E", ValorE)
    if leitura.valor is None:
        return [], []
    evidencias = leitura.resposta.evidencias
    de_regra = {r.sinal for r in matriz.regras_corte if r.tipo == "classe_fixa"}
    sinais = []
    for s in leitura.valor.sinais:
        if s.evidencia >= len(evidencias) or (s.tipo not in matriz.estagios and s.tipo not in de_regra):
            continue
        if s.data is not None and s.data > ex.ctx.as_of:
            continue
        evidencia = evidencias[s.evidencia]
        sinais.append(
            Sinal(
                tipo=s.tipo,
                estagio=matriz.estagios.get(s.tipo),  # None: prova_aportes_novos alimenta a R3, não é estágio
                data=s.data,
                tipo_fonte=evidencia.tipo_fonte,
                evidencia=evidencia,
            )
        )
    modificadores = []
    for m in leitura.valor.modificadores:
        dados = matriz.modificadores.get(m.id)
        if dados is not None and dados["origem"] == "P-E" and m.evidencia < len(evidencias):
            modificadores.append(
                ModificadorAplicado(id=m.id, direcao=dados["direcao"], origem="P-E", evidencia=evidencias[m.evidencia])
            )
    return sinais, modificadores


def site_nao_respondeu(ex: ExecucaoSalva) -> bool:
    """A captura caiu em erro porque o site não está no ar (R-T14-e6). O nó levanta "captura falhou: <motivo>":
    - falha de navegação sem resposta HTTP (DNS, conexão recusada, timeout) conta;
    - "HTTP <código>" na página inicial conta só com 5xx (inclusive os 52x da Cloudflare), 404 e 410. 401, 403, 407,
      429, 451 e os outros 4xx são o site recusando o visitante (WAF, bloqueio geográfico), não o site fora do ar.
    Desafio anti-bot termina `feito` (`bloqueada=True`) e não é falha; erro do código ("erro inesperado: ...") não
    diz nada do site."""
    status, motivo = _status(ex, "captura")
    if status != "erro" or not isinstance(motivo, str) or not motivo.startswith(_PREFIXO_FALHA_CAPTURA):
        return False
    if (http := _HTTP_DA_CAPTURA.fullmatch(motivo[len(_PREFIXO_FALHA_CAPTURA) :].strip())) is None:
        return True
    codigo = int(http.group(1))
    return 500 <= codigo <= 599 or codigo in _HTTP_SITE_SUMIU


def _site_fora_do_ar(ex: ExecucaoSalva, matriz: Matriz, anterior: ExecucaoSalva | None) -> Sinal | None:
    """E6: NXDOMAIN no `dns`, ou a captura falhou nesta execução e na anterior."""
    if (estagio := matriz.estagios.get(TIPO_FORA_DO_AR)) is None:
        return None
    dns = _feito(ex, "dns")
    nxdomain = dns is not None and "nxdomain" not in _vazados(dns) and dns.get("nxdomain") is True
    duas_falhas = anterior is not None and site_nao_respondeu(ex) and site_nao_respondeu(anterior)
    if not (nxdomain or duas_falhas):
        return None
    return Sinal(tipo=TIPO_FORA_DO_AR, estagio=estagio, data=ex.ctx.as_of, tipo_fonte=_FONTE_COLETOR)


def _registro_recente(ex: ExecucaoSalva) -> Sinal | None:
    """E0: só com datas conhecidas. O domínio foi registrado menos de 90 dias antes do `as_of` e o nó `cnpj` terminou
    `feito`: sem empresa identificada, basta o domínio; com ela, a abertura também precisa ser conhecida e de menos de
    90 dias. `cnpj` em erro, bloqueado ou aguardando, ou empresa sem abertura conhecida: o CNPJ pode ser antigo."""
    as_of = ex.ctx.as_of

    def recente(saida: dict | None, campo: str) -> date | None:
        data = _data_no_as_of(saida, campo, as_of) if saida is not None else None
        return data if data is not None and (as_of - data).days < _DIAS_E0 else None

    if (registro := recente(_feito(ex, "rdap"), "registro")) is None:
        return None
    if (cnpj := _feito(ex, "cnpj")) is None:
        return None
    if cnpj.get("cnpj") is not None and recente(cnpj, "abertura") is None:
        return None
    return Sinal(tipo=TIPO_E0, estagio=_ESTAGIO_E0, data=registro, tipo_fonte=_FONTE_COLETOR)


def _modificadores_dos_itens(itens: dict[str, Item], matriz: Matriz) -> list[ModificadorAplicado]:
    """Os modificadores cuja origem é um item valem com o item confirmado no máximo dele: o A1 = 4 do `retorno_alto`
    (>10%/mês ou taxa diária); D1, D3 e B3 só têm um valor acima de zero."""
    aplicados = []
    for id_, dados in matriz.modificadores.items():
        item = itens.get(dados["origem"])
        if item is not None and item.estado == "confirmado" and item.pontos == item.maximo:
            evidencia = item.evidencias[0] if item.evidencias else None
            aplicados.append(
                ModificadorAplicado(id=id_, direcao=dados["direcao"], origem=dados["origem"], evidencia=evidencia)
            )
    return aplicados


def sinais_da_execucao(
    ex: ExecucaoSalva, matriz: Matriz, anterior: ExecucaoSalva | None
) -> tuple[list[Sinal], list[ModificadorAplicado]]:
    """Os sinais do eixo 2 (os confirmados da P-E, o E6 e, sem nenhum outro sinal de estágio, o E0) e os
    modificadores (os dos itens e os da P-E, sem repetir id).

    `anterior` é obrigatório: a execução anterior do alvo (`execucao.execucao_anterior`, carregada), para o E6 por
    duas falhas de captura, ou `None` explícito quando não há."""
    sinais, da_pe = _da_pe(ex, matriz)
    if (fora := _site_fora_do_ar(ex, matriz, anterior)) is not None:
        sinais.append(fora)
    # o prova_aportes_novos (sem estágio) não conta como outro sinal
    if not any(s.estagio for s in sinais) and (recente := _registro_recente(ex)) is not None:
        sinais.append(recente)
    modificadores: dict[str, ModificadorAplicado] = {}
    for m in (*_modificadores_dos_itens(itens_da_execucao(ex, matriz), matriz), *da_pe):
        modificadores.setdefault(m.id, m)
    return sinais, list(modificadores.values())


def pontuar_eixo2(sinais: Iterable[Sinal], modificadores: Iterable[ModificadorAplicado], matriz: Matriz) -> Eixo2:
    """O maior estágio entre os sinais (a ordem é a de `janelas`, E0 a E7), o sinal que o define e a janela.

    O sinal que define o estágio é o mais antigo dele, a data em que o esquema chegou lá (os sem data por último).
    Sinal sem estágio (`prova_aportes_novos`) não conta. Comunicação tranquilizadora não é sinal: nada rebaixa o
    estágio.
    """
    ordem = list(matriz.janelas)
    de_estagio = [s for s in sinais if s.estagio in matriz.janelas]
    if not de_estagio:
        return Eixo2(estagio=None, sinal=None, janela=None, modificadores=list(modificadores))
    estagio = max((s.estagio for s in de_estagio), key=ordem.index)
    sinal = min(
        (s for s in de_estagio if s.estagio == estagio), key=lambda s: (s.data is None, s.data or date.min)
    )
    return Eixo2(estagio=estagio, sinal=sinal, janela=matriz.janelas[estagio], modificadores=list(modificadores))
