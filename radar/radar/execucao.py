"""Execuções em disco: o que o motor grava em `casos/<slug>/<AAAA-MM-DD_HHMMSS>` e o que a CLI e o servidor MCP
precisam para criá-las, achá-las e compará-las. Nada aqui fala com a rede.

- Criar: `iniciar_execucao` (valida `modo_contato` e `as_of`, cria a pasta e o `Contexto` e só devolve erros que podem
  ser mostrados: no modo cego não repetem o alvo), `criar_contexto` (o slug opaco do modo cego vem do segredo local),
  `criar_servicos` e `criar_indices`.
- Achar: `pasta_do_run` (valida o `run_id`), `listar_casos`, `em_modo_atual`, `execucao_anterior`, `execucao_cega`.
- Carregar: `carregar_execucao` (o que o motor gravou, sem interpretação).
- Comparar: `escolher_execucoes` (o par do diff e o bloqueio do modo cego).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from radar.arquivos import ler_json
from radar.config import Config
from radar.custodia import Custodia
from radar.indices import Indices
from radar.modelos import Contexto, ErroNo
from radar.motor import Servicos
from radar.nos.alvo import normalizar_alvo
from radar.rede import Rede

_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}_\d{6}")
# `<slug>/<AAAA-MM-DD_HHMMSS>`: o `run_id` é o caminho relativo a `casos_dir`
_RUN_ID = re.compile(r"[a-z0-9_-]+/\d{4}-\d{2}-\d{2}_\d{6}")
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_PASTA_INDICES = "_indices"
# o slug de uma execução cega; o de um domínio aberto sempre tem um "-" a mais (o do sufixo), então nunca casa
PADRAO_SLUG_CEGO = re.compile(r"cego-[0-9a-f]{16}")
NOME_DO_SEGREDO = ".segredo_cego"
_BYTES_DO_SEGREDO = 32
# outro processo pode ter acabado de criar o segredo e ainda estar escrevendo: até ~1 s de espera
_LEITURAS_DO_SEGREDO = 20
_ESPERA_DO_SEGREDO_S = 0.05
MODOS_DE_CONTATO = ("captura", "nenhum")


class ErroIniciar(ValueError):
    """A execução não pôde ser criada. A mensagem pode ser mostrada como está: no modo cego ela não repete o alvo."""


def agora() -> datetime:
    """O instante em que a execução começa (carimbo da pasta e `data_execucao`). Os testes trocam."""
    return datetime.now()


def _interpretar_as_of(texto: str, hoje: date) -> date:
    """`AAAA-MM-DD` como data, nunca posterior a `hoje`; senão `ErroIniciar`."""
    try:
        if not _DATA_ISO.fullmatch(texto):  # `fromisoformat` também aceitaria `20260101` e `2026-W41-4`
            raise ValueError(texto)
        data = date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise ErroIniciar("as_of inválido: use AAAA-MM-DD") from None
    if data > hoje:
        raise ErroIniciar("as_of posterior a hoje")
    return data


def pasta_do_run(casos_dir: Path, run_id: Any) -> Path | None:
    """A pasta de `run_id` (`<slug>/<AAAA-MM-DD_HHMMSS>`) dentro de `casos_dir`, ou `None` se ele é inválido: não é
    texto, tem `..` ou barra invertida, é um caminho absoluto, foge do formato ou resolve para fora de `casos_dir`.
    Não confere se a pasta existe."""
    if not isinstance(run_id, str) or ".." in run_id or "\\" in run_id:
        return None
    if PurePosixPath(run_id).is_absolute() or PureWindowsPath(run_id).is_absolute():
        return None
    if not _RUN_ID.fullmatch(run_id):
        return None
    base = Path(casos_dir).resolve()
    pasta = (base / run_id).resolve()
    return pasta if pasta.is_relative_to(base) else None


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


def iniciar_execucao(entrada: str, as_of: str | None, modo_contato: str, modo_cego: bool, casos_dir: Path) -> Contexto:
    """`criar_contexto` para quem recebe o pedido do usuário (a CLI e o servidor MCP), na hora de `agora()`.

    Confere `modo_contato` (`MODOS_DE_CONTATO`) e `as_of` (texto `AAAA-MM-DD`, nunca depois de hoje; `None` vale hoje)
    e traduz as falhas em `ErroIniciar`: alvo inválido (`alvo inválido` no modo cego, que não repete o alvo; no modo
    aberto, a mensagem do `normalizar_alvo`) e outra execução do mesmo alvo no mesmo segundo.
    """
    if modo_contato not in MODOS_DE_CONTATO:
        raise ErroIniciar("modo_contato inválido: use 'captura' ou 'nenhum'")
    momento = agora()
    data = None if as_of is None else _interpretar_as_of(as_of, momento.date())
    try:
        return criar_contexto(entrada, data, modo_contato, modo_cego, casos_dir, momento)
    except ErroNo as erro:
        raise ErroIniciar("alvo inválido" if modo_cego else erro.mensagem) from None
    except FileExistsError:
        raise ErroIniciar("já existe uma execução deste alvo iniciada neste segundo; chame de novo") from None


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


def criar_indices(config: Config, rede: Rede) -> Indices:
    """Os índices (CVM, BCB...) que todas as execuções compartilham: o cache fica em `casos_dir/_indices`."""
    return Indices(Path(config.casos_dir) / _PASTA_INDICES, rede, config.indices.ttl_horas)


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


def execucao_cega(pasta: Path) -> bool:
    """O `estado.json` da execução diz que ela foi feita no modo cego. Ausente ou ilegível → não."""
    try:
        return bool(ler_json(pasta / "estado.json")["contexto"]["modo_cego"])
    except (OSError, ValueError, KeyError, TypeError):
        return False


class ErroComparacao(ValueError):
    """As execuções pedidas não podem ser comparadas; a mensagem diz por quê."""


def escolher_execucoes(casos_dir: Path, alvo: str, a: str | None, b: str | None) -> tuple[str, str]:
    """Os `run_id` a comparar, a execução mais antiga primeiro.

    `alvo` é o domínio, a URL ou o slug (como `listar_casos` mostra); `a` e `b` são o carimbo ou o `run_id`. Sem `a`
    nem `b`: as duas últimas em modo atual; só `b`: a anterior a ela em modo atual; só `a`: a última em modo atual
    depois dela. Levanta `ErroComparacao` se o alvo é inválido ou não tem execução, se a execução pedida não existe,
    se não há par para comparar ou se alguma das duas foi feita no modo cego (o diff não passa pela máscara).
    """
    casos = listar_casos(casos_dir)
    try:
        slug = normalizar_alvo(alvo)[1]
    except ErroNo:
        if alvo not in casos:  # o slug, como `listar_casos` mostra, também vale
            raise ErroComparacao("alvo inválido") from None
        slug = alvo
    if PADRAO_SLUG_CEGO.fullmatch(slug):
        raise ErroComparacao("indisponível no modo cego")
    if slug not in casos:
        raise ErroComparacao("nenhuma execução deste alvo")
    carimbos = casos[slug]
    escolhidas: list[str | None] = []
    for valor in (a, b):
        if valor is None:
            escolhidas.append(None)
            continue
        carimbo = valor.removeprefix(f"{slug}/")
        if not _TIMESTAMP.fullmatch(carimbo) or carimbo not in carimbos:
            raise ErroComparacao(f"execução não encontrada: {valor}")
        escolhidas.append(carimbo)
    anterior, atual = _par(Path(casos_dir) / slug, carimbos, *escolhidas)
    if execucao_cega(Path(casos_dir) / slug / anterior) or execucao_cega(Path(casos_dir) / slug / atual):
        raise ErroComparacao("indisponível no modo cego")
    return f"{slug}/{anterior}", f"{slug}/{atual}"


def _par(pasta_do_alvo: Path, carimbos: list[str], a: str | None, b: str | None) -> tuple[str, str]:
    """Os dois carimbos a comparar, o mais antigo primeiro (ver `escolher_execucoes`)."""
    slug = pasta_do_alvo.name
    if a is None and b is None:
        atuais = [c for c in carimbos if em_modo_atual(pasta_do_alvo / c)]
        if len(atuais) < 2:
            raise ErroComparacao("são necessárias duas execuções em modo atual deste alvo para comparar")
        return atuais[-2], atuais[-1]
    if a is None:
        anterior = execucao_anterior(pasta_do_alvo / b)
        if anterior is None:
            raise ErroComparacao(f"não há execução anterior a {slug}/{b} em modo atual")
        return anterior.name, b
    if b is None:
        depois = [c for c in carimbos if c > a and em_modo_atual(pasta_do_alvo / c)]
        if not depois:
            raise ErroComparacao(f"não há execução em modo atual depois de {slug}/{a}")
        return a, depois[-1]
    if a == b:
        raise ErroComparacao("a e b são a mesma execução")
    return (a, b) if a < b else (b, a)
