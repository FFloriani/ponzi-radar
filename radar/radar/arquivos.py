"""Gravação atômica de JSON, leitura tolerante e trava de arquivo entre processos."""

from __future__ import annotations

import errno
import json
import logging
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

_log = logging.getLogger(__name__)
# teto de ~1 s (19 esperas de 50 ms) para o destino ficar livre no os.replace
_TENTATIVAS_REPLACE = 20
_ESPERA_REPLACE_S = 0.05


def _serializar(obj: Any) -> str:
    # `datetime` é subclasse de `date`: os dois saem em ISO
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"{type(obj).__name__} não é serializável em JSON")


def _substituir(origem: Path, destino: Path) -> None:
    """`os.replace` com repetição curta para o `PermissionError` transitório do Windows.

    No Windows, trocar um destino que outro handle mantém aberto (leitor, antivírus,
    indexador) dá "acesso negado" até o handle fechar. Fora do Windows, ou esgotadas as
    tentativas, o erro sobe.
    """
    for tentativa in range(1, _TENTATIVAS_REPLACE + 1):
        try:
            os.replace(origem, destino)
            return
        except PermissionError:
            if sys.platform != "win32" or tentativa == _TENTATIVAS_REPLACE:
                raise
            time.sleep(_ESPERA_REPLACE_S)


def gravar_json_atomico(caminho: Path, dados: Any) -> None:
    """Grava `dados` em `caminho` sem nunca deixar o arquivo pela metade.

    Escreve num `.tmp` do mesmo diretório e troca com `os.replace`: quem lê vê o conteúdo
    antigo ou o novo, nunca um parcial. Se a serialização ou a troca falhar, o original
    fica intacto e o `.tmp` é removido.
    """
    caminho = Path(caminho)
    tmp = caminho.with_name(f"{caminho.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2, default=_serializar)
            f.flush()
            os.fsync(f.fileno())
        _substituir(tmp, caminho)
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


def _travar_sem_esperar(descritor: int) -> bool:
    """Tenta a trava exclusiva do sistema no lockfile aberto em `descritor`. `False`: outro handle a segura."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(descritor, 0, os.SEEK_SET)  # `locking` trava a partir da posição atual
        try:
            msvcrt.locking(descritor, msvcrt.LK_NBLCK, 1)
        except OSError as erro:
            if erro.errno in (errno.EACCES, errno.EDEADLK):  # o byte 0 está travado por outro handle
                return False
            raise
        return True
    import fcntl

    try:
        fcntl.flock(descritor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _destravar(descritor: int) -> None:
    if sys.platform == "win32":
        import msvcrt

        os.lseek(descritor, 0, os.SEEK_SET)
        msvcrt.locking(descritor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(descritor, fcntl.LOCK_UN)


@contextmanager
def trava(caminho: Path, timeout: float = 10.0) -> Iterator[None]:
    """Exclusão mútua entre processos (e entre threads: cada chamada abre o próprio handle) pela trava do sistema
    operacional num lockfile permanente: `msvcrt.locking` no byte 0 no Windows, `flock` no POSIX.

    O lockfile é criado na primeira vez e nunca apagado: quem decide é a trava do kernel, não a existência do arquivo.
    O kernel solta a trava quando o handle fecha, inclusive quando o processo morre com ela na mão (I8: um servidor MCP
    morto não impede a retomada), então não existe trava órfã. Tenta a cada 50 ms; passados `timeout` segundos,
    levanta `TimeoutError`, que nomeia o arquivo e diz que outro processo do radar está gravando nele. O lockfile do
    protocolo anterior (pid e instante dentro) é só um arquivo: não segura nada.
    """
    caminho = Path(caminho)
    # modo binário (O_BINARY no Windows) e sem O_EXCL: o lockfile que já existe é o mesmo de sempre
    descritor = os.open(caminho, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o666)
    try:
        limite = time.monotonic() + timeout
        while not _travar_sem_esperar(descritor):
            if time.monotonic() >= limite:
                raise TimeoutError(
                    f"trava ocupada há mais de {timeout:g} s: {caminho}; outro processo do radar está gravando nesta "
                    "pasta (espere ele terminar)"
                )
            time.sleep(_ESPERA_TRAVA_S)
        try:
            yield
        finally:
            try:
                _destravar(descritor)
            except OSError:  # o fechamento do handle, logo abaixo, também solta a trava
                _log.warning("trava %s: o desbloqueio falhou; ela sai quando o arquivo fecha", caminho, exc_info=True)
    finally:
        os.close(descritor)
