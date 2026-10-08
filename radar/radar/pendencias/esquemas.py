"""Esquemas do `valor` de cada pendência (spec 7.4, passo 1: "o `valor` é validado com o modelo pydantic").

Todos recusam campo desconhecido e todos os campos são obrigatórios: quem responde diz o que não achou com
`None`, `False` ou lista vazia, nunca deixando de preencher. O texto de `Field(description=...)` aparece no
`formato_resposta` que o Claude lê (ver `definicoes.nova_pendencia`).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from radar.cnpj_util import cnpj_valido


class _Valor(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValorCNPJ(_Valor):
    """P-CNPJ: o CNPJ do operador, numérico ou alfanumérico."""

    cnpj: str = Field(description="14 caracteres, sem pontuação")

    @field_validator("cnpj")
    @classmethod
    def _cnpj_valido(cls, cnpj: str) -> str:
        if not cnpj_valido(cnpj):
            raise ValueError("CNPJ inválido: use 14 caracteres, sem pontuação, com os dígitos verificadores certos")
        return cnpj


class ValorA1(_Valor):
    """P-A1: retorno prometido (% ao mês), taxa diária e retorno garantido."""

    pct_mes: float | None
    taxa_diaria: bool
    garantido: bool


class ValorA2(_Valor):
    """P-A2: a série de retornos divulgada é lisa."""

    serie_lisa: bool


class ValorA3(_Valor):
    """P-A3: origem do retorno verificável e custodiante independente."""

    origem_verificavel: bool
    custodiante_independente: bool


class ValorB(_Valor):
    """P-B: B1 (indicação), B2 (token próprio), B3 (carência com multa) e B4 (taxa para sacar)."""

    indicacao: Literal["nenhuma", "indicacao_remunerada", "recrutar_para_sacar"]
    token_proprio: bool
    carencia_com_multa: bool
    taxa_para_sacar: bool


class ValorC(_Valor):
    """P-C: C2 (contrato atípico) e a parte de C3 que exige leitura."""

    contrato_atipico: bool
    tipo_contrato: str | None
    conta_pf_ou_terceiro: bool
    offshore_alegado: bool


class AlertaC4(_Valor):
    regulador: str
    data: date
    url: str


class ValorC4(_Valor):
    """P-C4: alerta oficial vigente, com regulador, data e endereço de cada um."""

    alerta_vigente: bool
    alertas: list[AlertaC4]


class PessoaD1(_Valor):
    pessoa: str
    vinculo: str


class ValorD1(_Valor):
    """P-D1: responsáveis com histórico de fraude. Só o nome e o vínculo, nunca CPF."""

    historico_fraude: bool
    pessoas: list[PessoaD1]


class ValorD4(_Valor):
    """P-D4: credibilidade emprestada e os tipos de figura usados."""

    credibilidade_emprestada: bool
    tipos: list[Literal["influenciador", "celebridade", "lider_religioso", "lider_comunitario"]]


class SinalE(_Valor):
    tipo: str
    data: date | None
    evidencia: int = Field(ge=0, description="índice na lista evidencias da resposta, a partir de 0")


class ModificadorE(_Valor):
    id: str
    evidencia: int = Field(ge=0, description="índice na lista evidencias da resposta, a partir de 0")


class ValorE(_Valor):
    """P-E: sinais do eixo 2 (cada um com data e a evidência que o sustenta) e modificadores."""

    sinais: list[SinalE]
    modificadores: list[ModificadorE]
