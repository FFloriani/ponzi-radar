"""Configuração do radar: padrões em código, `config.toml` e `config.local.toml` por cima."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

RAIZ_RADAR = Path(__file__).resolve().parents[1]
RAIZ_REPO = RAIZ_RADAR.parent

UA_NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
# com proxy configurado, a `Rede` troca este padrão por um neutro (`rede.UA_API_NEUTRO`): ele identifica o projeto
UA_API = "radar-piramides/0.1 (pesquisa; github.com/FFloriani/piramide-pentest)"


def _limites_padrao() -> dict[str, float]:
    return {"*": 1.0, "web.archive.org": 2.0, "archive.org": 2.0, "crt.sh": 3.0}


class _Secao(BaseModel):
    # chave desconhecida é erro: um typo no TOML não pode virar padrão silencioso
    model_config = ConfigDict(extra="forbid")


def _timeouts_padrao() -> dict[str, float]:
    # a listagem do CDX de um domínio grande leva mais de 70 s
    return {"web.archive.org": 120.0}


class RedeConfig(_Secao):
    proxy: str | None = None
    ua_navegador: str = UA_NAVEGADOR
    ua_api: str = UA_API
    timeout_s: float = 30.0
    tentativas: int = 4
    # segundos mínimos entre requisições por host; "*" vale para os hosts não listados
    limites: dict[str, float] = Field(default_factory=_limites_padrao)
    # timeout por host, em segundos; o host que não está aqui usa `timeout_s`
    timeouts: dict[str, float] = Field(default_factory=_timeouts_padrao)

    @field_validator("limites")
    @classmethod
    def _exige_curinga(cls, limites: dict[str, float]) -> dict[str, float]:
        return limites if "*" in limites else {"*": 1.0, **limites}

    @field_validator("timeouts")
    @classmethod
    def _soma_ao_padrao(cls, timeouts: dict[str, float]) -> dict[str, float]:
        # configurar outro host não pode tirar o timeout do Wayback; o valor dele ainda pode ser trocado
        return {**_timeouts_padrao(), **timeouts}


class CapturaConfig(_Secao):
    max_subpaginas: int = 10
    timeout_pagina_s: float = 30.0
    networkidle_s: float = 10.0


class IndicesConfig(_Secao):
    ttl_horas: int = 24


class Config(_Secao):
    rede: RedeConfig = Field(default_factory=RedeConfig)
    captura: CapturaConfig = Field(default_factory=CapturaConfig)
    indices: IndicesConfig = Field(default_factory=IndicesConfig)
    casos_dir: Path = Field(default_factory=lambda: RAIZ_REPO / "casos")

    @field_validator("casos_dir")
    @classmethod
    def _absoluto(cls, caminho: Path) -> Path:
        return caminho if caminho.is_absolute() else (RAIZ_RADAR / caminho).resolve()


def carregar_config(caminho: Path | None = None) -> Config:
    """Lê a configuração e completa o que faltar com os padrões.

    Sem `caminho`: `radar/config.toml` e, por cima, `radar/config.local.toml`.
    Com `caminho`: só esse arquivo (se existir). O merge é raso por seção: uma chave
    presente em `[rede]` troca só ela, mas `limites` inteiro é substituído.
    """
    arquivos = (
        [RAIZ_RADAR / "config.toml", RAIZ_RADAR / "config.local.toml"]
        if caminho is None
        else [caminho]
    )
    dados: dict[str, Any] = {}
    for arquivo in arquivos:
        if not arquivo.is_file():
            continue
        with arquivo.open("rb") as f:
            parcial = tomllib.load(f)
        for chave, valor in parcial.items():
            if isinstance(valor, dict) and isinstance(dados.get(chave), dict):
                dados[chave] = {**dados[chave], **valor}
            else:
                dados[chave] = valor
    return Config.model_validate(dados)
