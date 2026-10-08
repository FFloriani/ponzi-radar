"""Gravação atômica de JSON, leitura tolerante e trava de arquivo entre processos."""

from __future__ import annotations

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
# uma trava com mais que isto foi esquecida: as nossas duram o tempo de gravar um arquivo
_TRAVA_ORFA_S = 10 * 60
_ACESSO_NEGADO = 5  # ERROR_ACCESS_DENIED: o processo existe, mas é de outro usuário
_AINDA_RODANDO = 259  # STILL_ACTIVE

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


def _processo_vivo(pid: int) -> bool:
    """O processo `pid` existe. Na dúvida (sem permissão para consultar), existe."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == _ACESSO_NEGADO
        try:
            codigo = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return True
            return codigo.value == _AINDA_RODANDO  # o handle de um processo que já saiu ainda abre
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:  # PermissionError: existe, é de outro usuário
        return True
    return True


def _dono(caminho: Path) -> tuple[bytes | None, int | None, float | None]:
    """O conteúdo do lockfile e o `pid` e o instante (epoch) gravados nele; os dois `None` se ilegível (o processo
    pode ter morrido entre criar e escrever). O instante, sem conteúdo legível, é o da última escrita do arquivo.
    Lockfile que não existe mais: `(None, None, None)`."""
    try:
        conteudo = caminho.read_bytes()
        alterado = caminho.stat().st_mtime
    except OSError:
        return None, None, None
    try:
        pid, instante = conteudo.decode("ascii").split()
        return conteudo, int(pid), float(instante)
    except (UnicodeDecodeError, ValueError):
        return conteudo, None, alterado


def _quebrar_se_orfa(caminho: Path, dono: tuple[bytes | None, int | None, float | None] | None = None) -> bool:
    """Quebra o lockfile de um processo que não existe mais ou de mais de 10 minutos, com aviso no log. `True`: vale
    tentar de novo (a órfã foi quebrada, o lockfile sumiu ou a trava mudou de dono no meio); `False`: o dono está vivo.
    `dono` é o que o chamador acabou de ler do lockfile (`_dono`); sem ele, o lockfile é lido aqui.

    A quebra troca o nome do lockfile por um único antes de apagar: entre dois processos que veem a mesma órfã, só
    um consegue. O renomeado é conferido; se não é a órfã (outro processo pegou a trava entre a leitura e a troca),
    volta ao nome de antes.
    """
    conteudo, pid, instante = dono if dono is not None else _dono(caminho)
    if conteudo is None:
        return True  # sumiu entre o estouro do tempo e a leitura: a trava está livre
    idade = time.time() - instante if instante is not None else None
    morto = pid is not None and not _processo_vivo(pid)
    if not (morto or (idade is not None and idade > _TRAVA_ORFA_S)):
        return False
    unico = caminho.with_name(f"{caminho.name}.orfa-{uuid.uuid4().hex}")
    try:
        os.rename(caminho, unico)
    except FileNotFoundError:
        return True  # outro processo quebrou antes
    except PermissionError:
        # no Windows, outro processo lendo ou trocando o mesmo arquivo nesse instante: tenta de novo
        return sys.platform == "win32"
    except OSError:
        return False
    try:
        if unico.read_bytes() != conteudo:
            try:
                os.rename(unico, caminho)  # é a trava nova de outro processo: devolve
            except OSError:
                _log.warning("trava %s: não deu para devolver a trava de outro processo (%s)", caminho, unico)
            return True
        unico.unlink()
    except OSError:
        _log.warning("trava %s: a órfã renomeada ficou em %s", caminho, unico)
        return True  # o nome da trava já está livre
    motivo = f"o processo {pid} não existe mais" if morto else f"tem {idade / 60:.0f} minutos"
    _log.warning("trava órfã quebrada: %s (%s)", caminho, motivo)
    return True


def _ocupada(caminho: Path, timeout: float) -> TimeoutError:
    _, pid, instante = _dono(caminho)
    dono = f"pid {pid}" if pid is not None else "dono desconhecido"
    if instante is not None:
        dono += ", desde " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(instante))
    return TimeoutError(
        f"trava ocupada há mais de {timeout:g} s: {caminho} ({dono}); se nenhum processo do radar estiver usando "
        "esta execução, apague o arquivo para liberar"
    )


@contextmanager
def trava(caminho: Path, timeout: float = 10.0) -> Iterator[None]:
    """Exclusão mútua entre processos por lockfile criado com `O_CREAT|O_EXCL`, com o pid e o instante de quem a pegou.

    Tenta a cada 50 ms. Passado `timeout` segundos, uma trava órfã (o processo que a pegou não existe mais, ou ela
    tem mais de 10 minutos) é quebrada com aviso no log e a espera recomeça (I8: um servidor MCP morto com a trava na
    mão não pode impedir a retomada); senão levanta `TimeoutError`, que nomeia o arquivo e diz como liberar, sem mexer
    no lockfile de quem a segura. O prazo conta o tempo com o mesmo dono: se a trava trocou de dono durante a espera
    (a fila andou), a espera recomeça em vez de estourar. A liberação só apaga o lockfile se ele ainda é o desta
    trava, e uma falha ao escrevê-lo não deixa o lockfile vazio para trás.
    """
    caminho = Path(caminho)
    limite = time.monotonic() + timeout
    dono_no_inicio: bytes | None = None
    while True:
        try:
            # O_BINARY: no Windows o modo texto gravaria \r\n, e a liberação compara o conteúdo byte a byte
            descritor = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0))
        except FileExistsError:
            if dono_no_inicio is None:
                dono_no_inicio = _dono(caminho)[0]
        except PermissionError:
            # no Windows, um lockfile que acabou de ser apagado ainda dá "acesso negado"
            # até o sistema concluir a remoção: é só ocupado, tenta de novo
            if sys.platform != "win32":
                raise
        else:
            # o instante com microssegundos também distingue esta trava de outra do mesmo processo na liberação
            meu = f"{os.getpid()} {time.time():.6f}\n".encode("ascii")
            try:
                os.write(descritor, meu)
            except BaseException:
                os.close(descritor)
                caminho.unlink(missing_ok=True)
                raise
            os.close(descritor)
            break
        if time.monotonic() >= limite:
            atual = _dono(caminho)
            if atual[0] is not None and atual[0] != dono_no_inicio:
                dono_no_inicio = atual[0]  # outro processo pegou e soltou no meio: não é o mesmo dono há `timeout`
            elif not _quebrar_se_orfa(caminho, atual):
                raise _ocupada(caminho, timeout)
            limite = time.monotonic() + timeout
            continue
        time.sleep(_ESPERA_TRAVA_S)
    try:
        yield
    finally:
        try:
            if caminho.read_bytes() == meu:
                caminho.unlink()
            else:
                _log.warning("trava %s já é de outro processo: não apago", caminho)
        except OSError:
            pass
