"""Execuções em disco: criar a pasta e o contexto, montar os serviços, listar e carregar o que o motor gravou."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
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
# o slug de uma execução cega; o de um domínio aberto sempre tem um "-" a mais (o do sufixo), então nunca casa
PADRAO_SLUG_CEGO = re.compile(r"cego-[0-9a-f]{16}")
NOME_DO_SEGREDO = ".segredo_cego"
_BYTES_DO_SEGREDO = 32
# outro processo pode ter acabado de criar o segredo e ainda estar escrevendo: até ~1 s de espera
_LEITURAS_DO_SEGREDO = 20
_ESPERA_DO_SEGREDO_S = 0.05


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
    de criar qualquer pasta (e o segredo do modo cego); dois chamados no mesmo segundo para o mesmo
    alvo levantam `FileExistsError` na segunda. No modo cego o slug é opaco (`slug_cego`, com o
    segredo de `casos_dir`): a pasta e o `run_id` não dizem o alvo, que fica só no contexto.
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
    if modo_cego:
        slug = slug_cego(dominio, segredo_cego(casos_dir))
        pasta = Path(casos_dir) / slug / carimbo
        ctx = ctx.model_copy(update={"slug": slug, "run_id": f"{slug}/{carimbo}", "pasta": pasta})
    ctx.pasta.mkdir(parents=True, exist_ok=False)
    return ctx


def segredo_cego(casos_dir: Path) -> bytes:
    """O segredo local do slug cego: os 32 bytes de `casos_dir/.segredo_cego`, criado na primeira vez (com
    `secrets.token_bytes` e permissão só do dono, onde o sistema permite). `casos/` fica fora do git.

    Um arquivo com outro tamanho levanta `ValueError`: trocar o segredo em silêncio mudaria o slug das execuções
    cegas do mesmo alvo.
    """
    caminho = Path(casos_dir) / NOME_DO_SEGREDO
    if not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        try:
            descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        except FileExistsError:
            pass  # outro processo criou agora: vale o dele
        else:
            with os.fdopen(descritor, "wb") as arquivo:
                arquivo.write(secrets.token_bytes(_BYTES_DO_SEGREDO))
                arquivo.flush()
                os.fsync(arquivo.fileno())
    for tentativa in range(_LEITURAS_DO_SEGREDO):
        segredo = caminho.read_bytes()
        if len(segredo) == _BYTES_DO_SEGREDO:
            return segredo
        if tentativa < _LEITURAS_DO_SEGREDO - 1:
            time.sleep(_ESPERA_DO_SEGREDO_S)
    raise ValueError(f"segredo do modo cego com {len(segredo)} bytes (esperados {_BYTES_DO_SEGREDO}): {caminho}")


def slug_cego(dominio: str, segredo: bytes) -> str:
    """`cego-` + os 16 primeiros hex do HMAC-SHA256 do domínio registrável com o segredo local: o mesmo alvo dá
    sempre o mesmo slug, e sem o segredo uma lista de domínios não leva do slug ao alvo."""
    return "cego-" + hmac.new(segredo, dominio.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


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


def em_modo_atual(pasta: Path) -> bool:
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
        if irma.name < pasta.name and em_modo_atual(irma):
            return irma
    return None
