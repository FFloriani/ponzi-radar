"""Custódia: artefatos endereçados por SHA-256 e log encadeado que só aceita acréscimo."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radar.arquivos import _substituir, trava

_ZEROS = "0" * 64
_HEX = re.compile(r"[0-9a-f]{64}")
_EXT = re.compile(r"[A-Za-z0-9]+(\.[A-Za-z0-9]+)*")
_CAMPOS = frozenset({"seq", "ts", "tipo", "origem", "sha256", "prev", "entrada"})


def _canonico(registro: dict[str, Any]) -> str:
    return json.dumps(registro, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_entrada(prev: str, registro_sem_entrada: dict[str, Any]) -> str:
    return hashlib.sha256((prev + _canonico(registro_sem_entrada)).encode("utf-8")).hexdigest()


def _hex_de(ref: str) -> str:
    """Extrai o hash de `"sha256:<hex>"`; recusa qualquer outra forma (inclusive `..` e `/`)."""
    prefixo, _, hex_ = ref.partition(":")
    if prefixo != "sha256" or not _HEX.fullmatch(hex_):
        raise ValueError(f"ref de artefato inválida: {ref!r}")
    return hex_


def _ler_linhas(log: Path) -> list[str]:
    """Registros do log, sem o `\\n` final.

    Só o LF separa registros: com `ensure_ascii=False`, U+2028 e U+0085 aparecem crus dentro
    do JSON e `str.splitlines()` partiria a linha neles.
    """
    with log.open(encoding="utf-8", errors="replace", newline="\n") as f:
        return [linha.removesuffix("\n") for linha in f]


def _arquivos_do_hash(artefatos: Path, hex_: str) -> list[Path]:
    # o nome é `<hex>.<ext>`; temporários da gravação começam com "." e não casam
    return sorted(artefatos.glob(f"{hex_}.*"))


def _gravar_artefato(destino: Path, dados: bytes) -> None:
    """Grava num temporário do mesmo diretório e troca: o nome do hash nunca fica pela metade."""
    tmp = destino.with_name(f".tmp-{uuid.uuid4().hex}")
    try:
        with tmp.open("xb") as f:
            f.write(dados)
            f.flush()
            os.fsync(f.fileno())
        _substituir(tmp, destino)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class Custodia:
    """Guarda artefatos em `<pasta>/artefatos/<sha256>.<ext>` e registra cada gravação em
    `<pasta>/custodia.log`, um JSON por linha, cada uma encadeada à anterior pelo hash."""

    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)
        self._artefatos = self.pasta / "artefatos"
        self._log = self.pasta / "custodia.log"

    def guardar(self, dados: bytes, ext: str, tipo: str, origem: str) -> str:
        """Guarda `dados` e devolve `"sha256:<hex>"`.

        O arquivo só é gravado se esse conteúdo ainda não existir (qualquer extensão); a linha do
        log é sempre acrescentada.
        """
        if not _EXT.fullmatch(ext):
            raise ValueError(f"extensão inválida: {ext!r}")
        hex_ = hashlib.sha256(dados).hexdigest()
        self._artefatos.mkdir(parents=True, exist_ok=True)
        with trava(self.pasta / "custodia.lock"):
            seq, prev = self._proxima_posicao()
            registro: dict[str, Any] = {
                "seq": seq,
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "tipo": tipo,
                "origem": origem,
                "sha256": hex_,
                "prev": prev,
            }
            registro["entrada"] = _hash_entrada(prev, registro)
            linha = _canonico(registro) + "\n"
            if not _arquivos_do_hash(self._artefatos, hex_):
                _gravar_artefato(self._artefatos / f"{hex_}.{ext}", dados)
            with self._log.open("a", encoding="utf-8", newline="\n") as f:
                f.write(linha)
                f.flush()
                os.fsync(f.fileno())
        return f"sha256:{hex_}"

    def caminho(self, ref: str) -> Path:
        """Caminho do arquivo de `ref`. `FileNotFoundError` se o artefato não existe."""
        achados = _arquivos_do_hash(self._artefatos, _hex_de(ref))
        if not achados:
            raise FileNotFoundError(f"artefato ausente: {ref}")
        return achados[0]

    def ler(self, ref: str) -> bytes:
        return self.caminho(ref).read_bytes()

    def _proxima_posicao(self) -> tuple[int, str]:
        """`seq` e `prev` da próxima linha, a partir da última do log."""
        if not self._log.exists():
            return 0, _ZEROS
        linhas = _ler_linhas(self._log)
        if not linhas:
            return 0, _ZEROS
        try:
            ultima = json.loads(linhas[-1])
            prev = ultima["entrada"]
            if not isinstance(prev, str):
                raise TypeError("entrada não é texto")
        except (ValueError, KeyError, TypeError) as e:
            raise ValueError(
                f"custodia.log ilegível na linha {len(linhas) - 1}: não dá para continuar a cadeia"
            ) from e
        return len(linhas), prev


def _registro_integro(registro: Any, posicao: int, prev_esperado: str | None) -> bool:
    """A linha é um registro completo, na sua posição, encadeado e com `entrada` correta.

    `prev_esperado` é a `entrada` da linha anterior; `None` quando ela é ilegível e não há o
    que conferir.
    """
    if not isinstance(registro, dict) or not _CAMPOS <= registro.keys():
        return False
    prev, entrada = registro["prev"], registro["entrada"]
    if registro["seq"] != posicao or not isinstance(prev, str) or not isinstance(entrada, str):
        return False
    if prev_esperado is not None and prev != prev_esperado:
        return False
    sem_entrada = {k: v for k, v in registro.items() if k != "entrada"}
    try:
        return entrada == _hash_entrada(prev, sem_entrada)
    except ValueError:  # texto com substituto isolado (\ud800) não codifica em UTF-8
        return False


def _problema_do_artefato(artefatos: Path, hex_: str) -> str | None:
    arquivos = _arquivos_do_hash(artefatos, hex_)
    if not arquivos:
        return f"artefato ausente: sha256:{hex_}"
    for arquivo in arquivos:
        with arquivo.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != hex_:
                return f"artefato alterado: sha256:{hex_}"
    return None


def verificar(pasta: Path) -> list[str]:
    """Refaz a cadeia do log e o hash de cada artefato citado. Lista vazia = íntegro.

    Os problemas saem na ordem do log. Uma linha adulterada é acusada sozinha: a seguinte é
    conferida contra a `entrada` gravada, não contra a recalculada. Não pega o corte das
    últimas linhas, porque a cadeia não tem âncora externa.
    """
    pasta = Path(pasta)
    log = pasta / "custodia.log"
    if not log.exists():
        return []
    problemas: list[str] = []
    prev_esperado: str | None = _ZEROS
    vistos: set[str] = set()
    for posicao, linha in enumerate(_ler_linhas(log)):
        try:
            registro = json.loads(linha)
        except ValueError:
            registro = None
        if not _registro_integro(registro, posicao, prev_esperado):
            problemas.append(f"cadeia quebrada na linha {posicao}")
        entrada = registro.get("entrada") if isinstance(registro, dict) else None
        prev_esperado = entrada if isinstance(entrada, str) else None
        hex_ = registro.get("sha256") if isinstance(registro, dict) else None
        if isinstance(hex_, str) and _HEX.fullmatch(hex_) and hex_ not in vistos:
            vistos.add(hex_)
            problema = _problema_do_artefato(pasta / "artefatos", hex_)
            if problema:
                problemas.append(problema)
    return problemas
