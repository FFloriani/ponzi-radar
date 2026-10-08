"""Modelos compartilhados do radar: contexto da execução, pendências, respostas, itens e resultados de nó."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
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
    """`itens`: os ids de item da pendência que a evidência sustenta (`["B3"]`). Numa pendência de vários itens (P-B,
    P-C) cada item do dossiê cita só as evidências marcadas com ele; `None` (julgamento antigo) vale para todos."""

    fonte: str
    trecho: str
    data_fonte: date | None = None
    tipo_fonte: Literal["operador", "oficial", "imprensa", "relato"]
    itens: list[str] | None = None


class Resposta(BaseModel):
    status: Literal["confirmado", "corrigido", "nao_encontrado", "inconclusivo"]
    valor: dict = Field(default_factory=dict)
    evidencias: list[Evidencia] = Field(default_factory=list)
    onde_procurou: list[str] = Field(default_factory=list)
    substitui: str | None = None

    @model_validator(mode="after")
    def _regras_por_status(self) -> Resposta:
        # o trecho tem de ter texto: um trecho vazio passaria trivialmente na checagem
        # "trecho conferido" (`"" in texto` é sempre True)
        tem_trecho = any(e.trecho.strip() for e in self.evidencias)
        if self.status in ("confirmado", "corrigido") and not tem_trecho:
            raise ValueError(f"status '{self.status}' exige ao menos 1 evidência com trecho")
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
    # `None`: o sinal não marca estágio (o `prova_aportes_novos` alimenta a regra de corte R3, não o eixo 2)
    estagio: str | None
    data: date | None
    tipo_fonte: str
    evidencia: Evidencia | None = None


# Resultados de nó: dataclasses simples (e não pydantic) porque os nós os criam com
# argumento posicional, como `Feito({...})` e `Pulado("motivo")`.


@dataclass(frozen=True)
class Feito:
    """`pendencias`: as pendências do nó que já têm resposta, refeitas com os insumos de agora. O motor compara cada
    uma com a guardada: se os candidatos ou o `conteudo_do_alvo` mudaram (uma correção a montante), a resposta perde
    o valor e a pendência reabre. Não entram na igualdade: dois `Feito` com as mesmas saídas são o mesmo resultado."""

    saidas: dict
    pendencias: Sequence[Pendencia] = field(default=(), compare=False)


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
