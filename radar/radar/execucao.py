"""Execuções em disco: criar a pasta e o contexto, montar os serviços, listar e carregar o que o motor gravou."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from radar.arquivos import ler_json
from radar.config import Config
from radar.custodia import Custodia
from radar.modelos import Contexto
from radar.motor import Servicos
from radar.nos.alvo import normalizar_alvo
from radar.rede import Rede

_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}_\d{6}")
_PASTA_INDICES = "_indices"


def criar_contexto(
    entrada: str,
    as_of: date | None,
    modo_contato: Literal["captura", "nenhum"],
    modo_cego: bool,
    casos_dir: Path,
    agora: datetime,
) -> Contexto:
    """Normaliza o alvo e cria a pasta `casos_dir/<slug>/<AAAA-MM-DD_HHMMSS>`.

    `as_of=None` vale hoje (`agora.date()`). Entrada inválida ou modo desconhecido levantam antes
    de criar qualquer pasta; dois chamados no mesmo segundo para o mesmo alvo levantam
    `FileExistsError` na segunda.
    """
    dominio, slug, url_inicial = normalizar_alvo(entrada)
    carimbo = agora.strftime("%Y-%m-%d_%H%M%S")
    ctx = Contexto(
        alvo=dominio,
        slug=slug,
        url_inicial=url_inicial,
        as_of=as_of if as_of is not None else agora.date(),
        data_execucao=agora,
        modo_contato=modo_contato,
        modo_cego=modo_cego,
        run_id=f"{slug}/{carimbo}",
        pasta=Path(casos_dir) / slug / carimbo,
    )
    ctx.pasta.mkdir(parents=True, exist_ok=False)
    return ctx


def criar_servicos(
    config: Config, pasta: Path, rede: Rede, indices: Any = None, matriz: Any = None
) -> Servicos:
    """Os serviços de uma execução: a custódia é a da `pasta`; rede, índices e matriz são compartilhados."""
    return Servicos(config=config, rede=rede, custodia=Custodia(pasta), indices=indices, matriz=matriz)


@dataclass
class ExecucaoSalva:
    """O que o motor gravou em disco, sem interpretação (mesmos formatos de `Motor._salvar`).

    - `status`: `estado.json["nos"]`, `{nó: {"status": ..., "motivo": ...}}`;
    - `saidas`: `evidencias.json`, `{nó: saídas}` só dos nós `feito`;
    - `pendencias`: `estado.json["pendencias"]`, `{id: campos da Pendencia + "aberta": bool}`;
    - `julgamentos`: `julgamentos.json`, na ordem em que foram gravados, cada um com `ativa`.
    """

    ctx: Contexto
    status: dict
    saidas: dict
    pendencias: dict
    julgamentos: list


def carregar_execucao(pasta: Path) -> ExecucaoSalva:
    """Lê a execução gravada em `pasta`. `ctx.pasta` aponta para onde ela está agora.

    `FileNotFoundError` se não houver `estado.json`; os outros arquivos ausentes valem vazios.
    """
    pasta = Path(pasta)
    estado = ler_json(pasta / "estado.json")
    if estado is None:
        raise FileNotFoundError(f"execução sem estado.json: {pasta}")
    return ExecucaoSalva(
        ctx=Contexto.model_validate({**estado["contexto"], "pasta": str(pasta)}),
        status=estado["nos"],
        saidas=ler_json(pasta / "evidencias.json", {}),
        pendencias=estado["pendencias"],
        julgamentos=ler_json(pasta / "julgamentos.json", []),
    )


def _execucoes(pasta_do_alvo: Path) -> list[Path]:
    return sorted(
        (p for p in pasta_do_alvo.iterdir() if p.is_dir() and _TIMESTAMP.fullmatch(p.name)),
        key=lambda p: p.name,
    )


def listar_casos(casos_dir: Path) -> dict[str, list[str]]:
    """`{slug: [AAAA-MM-DD_HHMMSS, ...]}`, as execuções da mais antiga para a mais nova.

    `_indices` (cache global) e o que não for pasta de execução ficam de fora.
    """
    casos_dir = Path(casos_dir)
    if not casos_dir.is_dir():
        return {}
    casos: dict[str, list[str]] = {}
    for alvo in sorted(casos_dir.iterdir()):
        if alvo.is_dir() and alvo.name != _PASTA_INDICES:
            if execucoes := _execucoes(alvo):
                casos[alvo.name] = [p.name for p in execucoes]
    return casos


def _em_modo_atual(pasta: Path) -> bool:
    """O `as_of` do `estado.json` é o dia da execução. Estado ausente ou ilegível → não."""
    try:
        contexto = ler_json(pasta / "estado.json")["contexto"]
        return (
            date.fromisoformat(contexto["as_of"])
            == datetime.fromisoformat(contexto["data_execucao"]).date()
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def execucao_anterior(pasta: Path) -> Path | None:
    """A execução mais recente do mesmo alvo que veio antes de `pasta` e foi feita em modo atual.

    Execuções retroativas e pastas sem `estado.json` legível não servem de base de comparação.
    """
    pasta = Path(pasta)
    if not pasta.parent.is_dir():
        return None
    for irma in reversed(_execucoes(pasta.parent)):
        if irma.name < pasta.name and _em_modo_atual(irma):
            return irma
    return None
