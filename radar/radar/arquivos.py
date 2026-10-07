"""Gravação atômica de JSON, leitura tolerante e trava de arquivo entre processos."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

_ESPERA_TRAVA_S = 0.05


def _serializar(obj: Any) -> str:
    # `datetime` é subclasse de `date`: os dois saem em ISO
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"{type(obj).__name__} não é serializável em JSON")


def gravar_json_atomico(caminho: Path, dados: Any) -> None:
    """Grava `dados` em `caminho` sem nunca deixar o arquivo pela metade.

    Escreve num `.tmp` do mesmo diretório e troca com `os.replace`: quem lê vê o conteúdo
    antigo ou o novo, nunca um parcial. Se a serialização falhar, o original fica intacto.
    """
    caminho = Path(caminho)
    tmp = caminho.with_name(f"{caminho.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2, default=_serializar)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, caminho)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def ler_json(caminho: Path, padrao: Any = None) -> Any:
    """Lê o JSON de `caminho`; se o arquivo não existir, devolve `padrao`."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except FileNotFoundError:
        return padrao
    return json.loads(texto)


@contextmanager
def trava(caminho: Path, timeout: float = 10.0) -> Iterator[None]:
    """Exclusão mútua entre processos por lockfile criado com `O_CREAT|O_EXCL`.

    Tenta a cada 50 ms; passado `timeout` segundos, levanta `TimeoutError` sem mexer no
    lockfile de quem a segura. Um lockfile órfão (processo morto) precisa ser apagado à mão.
    """
    caminho = Path(caminho)
    limite = time.monotonic() + timeout
    while True:
        try:
            os.close(os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            pass
        except PermissionError:
            # no Windows, um lockfile que acabou de ser apagado ainda dá "acesso negado"
            # até o sistema concluir a remoção: é só ocupado, tenta de novo
            if sys.platform != "win32":
                raise
        if time.monotonic() >= limite:
            raise TimeoutError(f"trava ocupada: {caminho}")
        time.sleep(_ESPERA_TRAVA_S)
    try:
        yield
    finally:
        caminho.unlink(missing_ok=True)
