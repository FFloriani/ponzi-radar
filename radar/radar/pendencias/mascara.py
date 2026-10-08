"""Máscara do modo cego (spec 7.5): o que identifica o alvo vira marcador antes de chegar ao Claude.

`montar_mascara` junta, das saídas dos nós, os termos que revelam o site (`[ALVO]`), a empresa (`[EMPRESA]`), o
CNPJ (`[CNPJ]`) e os sócios (`[PESSOA_n]`); `mascarar` aplica o dicionário a um texto. Termos com menos de 4
caracteres ficam de fora: trocá-los mudaria palavras comuns do texto.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any

from radar.pendencias.validacao import decodificar

_MINIMO_DE_CARACTERES = 4
# os nós que entregam a página inicial em `paginas[0].html`
_NOS_DE_PAGINAS = ("captura", "wayback_snapshot")
_PONTUACAO_DO_CNPJ = re.compile(r"[.\-/\s]")


class _Identidade(HTMLParser):
    """O `<title>` e o `og:site_name` (o primeiro de cada) do HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titulo: str | None = None
        self.site_name: str | None = None
        self._buffer: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "title" and self.titulo is None:
            self._buffer = []
        elif tag == "meta" and self.site_name is None:
            atributos = {nome.lower(): valor or "" for nome, valor in attrs}
            if atributos.get("property", "").strip().lower() == "og:site_name":
                self.site_name = atributos.get("content", "")

    def handle_data(self, data: str) -> None:
        if self._buffer is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._buffer is not None:
            self.titulo = "".join(self._buffer)
            self._buffer = None


def _identidade_da_pagina(html: str) -> list[str]:
    identidade = _Identidade()
    identidade.feed(html)
    identidade.close()
    return [termo for termo in (identidade.titulo, identidade.site_name) if termo]


def _no(saidas: dict[str, dict], nome: str) -> dict:
    saida = saidas.get(nome)
    return saida if isinstance(saida, dict) else {}


def _cnpj_formatado(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def montar_mascara(saidas: dict[str, dict], ler_artefato: Callable[[str], bytes]) -> dict[str, str]:
    """Termo -> marcador, a partir das `saidas` dos nós (nome do nó -> saída). `ler_artefato` (normalmente
    `Custodia.ler`) só é chamado para o HTML da página inicial, de onde saem o `<title>` e o `og:site_name`.

    - `alvo.dominio` e `ct.sans` (o domínio e os subdomínios) -> `[ALVO]`;
    - título e `og:site_name` da página inicial, `cnpj.razao_social` e `cnpj.nome_fantasia` -> `[EMPRESA]`;
    - `cnpj.cnpj`, formatado e só com os caracteres (numérico ou alfanumérico) -> `[CNPJ]`;
    - `cnpj.socios[].nome` -> `[PESSOA_n]`, com n a posição do sócio no quadro.

    Um termo que já entrou (sem diferenciar maiúsculas) não entra de novo; o primeiro marcador vale.
    """
    mascara: dict[str, str] = {}
    vistos: set[str] = set()

    def adicionar(termo: Any, marcador: str) -> None:
        if not isinstance(termo, str):
            return
        termo = " ".join(termo.split())
        if len(termo) < _MINIMO_DE_CARACTERES or termo.casefold() in vistos:
            return
        vistos.add(termo.casefold())
        mascara[termo] = marcador

    adicionar(_no(saidas, "alvo").get("dominio"), "[ALVO]")
    sans = _no(saidas, "ct").get("sans")
    for dominio in sans if isinstance(sans, list) else []:
        adicionar(dominio, "[ALVO]")

    cnpj = _no(saidas, "cnpj")
    adicionar(cnpj.get("razao_social"), "[EMPRESA]")
    adicionar(cnpj.get("nome_fantasia"), "[EMPRESA]")
    for nome in _NOS_DE_PAGINAS:
        paginas = _no(saidas, nome).get("paginas")
        inicial = paginas[0] if isinstance(paginas, list) and paginas else None
        ref = inicial.get("html") if isinstance(inicial, dict) else None
        if isinstance(ref, str) and ref:  # a captura barrada por anti-bot não tem HTML
            for termo in _identidade_da_pagina(decodificar(ler_artefato(ref), "html")):
                adicionar(termo, "[EMPRESA]")

    numero = cnpj.get("cnpj")
    if isinstance(numero, str):
        limpo = _PONTUACAO_DO_CNPJ.sub("", numero).upper()
        if len(limpo) == 14:
            adicionar(_cnpj_formatado(limpo), "[CNPJ]")
            adicionar(limpo, "[CNPJ]")

    socios = cnpj.get("socios")
    for n, socio in enumerate(socios if isinstance(socios, list) else [], start=1):
        if isinstance(socio, dict):
            adicionar(socio.get("nome"), f"[PESSOA_{n}]")
    return mascara


def mascarar(texto: str, mascara: dict[str, str]) -> str:
    """Troca cada termo da `mascara` pelo marcador, sem diferenciar maiúsculas. Os termos mais longos vêm
    primeiro (`app.exemplo.com.br` antes de `exemplo.com.br`) e o texto é varrido uma vez só, então um
    marcador que acabou de entrar não é trocado de novo."""
    termos = sorted((termo for termo in mascara if termo), key=len, reverse=True)
    if not termos or not texto:
        return texto
    padrao = re.compile("|".join(f"({re.escape(termo)})" for termo in termos), re.IGNORECASE)
    marcadores = [mascara[termo] for termo in termos]
    return padrao.sub(lambda achado: marcadores[achado.lastindex - 1], texto)
