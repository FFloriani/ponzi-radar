"""Modelos compartilhados do radar: contexto da execução, pendências, respostas, itens e resultados de nó."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

StatusNo = Literal["pendente", "executando", "feito", "aguardando", "erro", "bloqueado", "pulado"]
CapacidadeAsOf = Literal["exato", "filtravel", "so_atual"]
EstadoItem = Literal["confirmado", "nao_se_aplica", "nao_encontrado", "nao_verificado", "inconclusivo"]


class Contexto(BaseModel):
    alvo: str
    slug: str
    url_inicial: str
    as_of: date
    data_execucao: datetime
    modo_contato: Literal["captura", "nenhum"]
    modo_cego: bool
    run_id: str
    pasta: Path

    @property
    def retroativo(self) -> bool:
        """A execução olha para o passado quando o `as_of` é anterior ao dia da execução."""
        return self.as_of < self.data_execucao.date()


class Candidato(BaseModel):
    categoria: str
    valor: str
    trecho: str
    artefato: str
    posicao: int
    extra: dict = Field(default_factory=dict)


class Pendencia(BaseModel):
    id: str
    itens: list[str]
    pergunta: str
    criterios: str
    candidatos: list[Candidato]
    formato_resposta: dict[str, str]
    restricoes: dict
    conteudo_do_alvo: str
    no_origem: str


class Evidencia(BaseModel):
    fonte: str
    trecho: str
    data_fonte: date | None = None
    tipo_fonte: Literal["operador", "oficial", "imprensa", "relato"]


class Resposta(BaseModel):
    status: Literal["confirmado", "corrigido", "nao_encontrado", "inconclusivo"]
    valor: dict = Field(default_factory=dict)
    evidencias: list[Evidencia] = Field(default_factory=list)
    onde_procurou: list[str] = Field(default_factory=list)
    substitui: str | None = None

    @model_validator(mode="after")
    def _regras_por_status(self) -> Resposta:
        if self.status in ("confirmado", "corrigido") and not self.evidencias:
            raise ValueError(f"status '{self.status}' exige ao menos 1 evidência")
        if self.status == "nao_encontrado" and not self.onde_procurou:
            raise ValueError("status 'nao_encontrado' exige 'onde_procurou' não vazio")
        return self


class Item(BaseModel):
    id: str
    estado: EstadoItem
    pontos: int
    maximo: int
    origem: Literal["coletor", "regex_confirmada", "claude", "nenhuma"]
    evidencias: list[Evidencia] = Field(default_factory=list)
    nota: str | None = None


class Sinal(BaseModel):
    tipo: str
    estagio: str
    data: date | None
    tipo_fonte: str
    evidencia: Evidencia | None = None


# Resultados de nó: dataclasses simples (e não pydantic) porque os nós os criam com
# argumento posicional, como `Feito({...})` e `Pulado("motivo")`.


@dataclass(frozen=True)
class Feito:
    saidas: dict


@dataclass(frozen=True)
class Aguardando:
    pendencias: list[Pendencia]


@dataclass(frozen=True)
class Pulado:
    motivo: str


class ErroNo(Exception):
    """Falha de um nó. `permanente=True` não adianta repetir; `False` pode ser tentada de novo."""

    def __init__(self, mensagem: str, permanente: bool) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.permanente = permanente
