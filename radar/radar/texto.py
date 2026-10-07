"""Texto visível de HTML e normalização para comparar trechos e nomes."""

from __future__ import annotations

import unicodedata
from html.parser import HTMLParser

# conteúdo que um visitante não lê: some junto com tudo que estiver dentro
_DESCARTADAS = frozenset({"script", "style", "noscript", "template"})

# tags que começam/terminam uma linha de texto; as demais (b, span, a...) continuam a linha
_BLOCOS = frozenset({
    "address", "article", "aside", "blockquote", "body", "br", "button", "caption", "dd",
    "details", "dialog", "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer",
    "form", "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr", "html",
    "legend", "li", "main", "nav", "ol", "option", "p", "pre", "section", "summary", "table",
    "tbody", "td", "tfoot", "th", "thead", "title", "tr", "ul",
})

_ASPAS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "„": '"'})


class _Extrator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocos: list[str] = []
        self._atual: list[str] = []
        self._descartando = 0

    def _fechar_bloco(self) -> None:
        texto = " ".join("".join(self._atual).split())
        self._atual.clear()
        if texto:
            self.blocos.append(texto)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _DESCARTADAS:
            self._descartando += 1
        elif tag in _BLOCOS and not self._descartando:
            self._fechar_bloco()

    def handle_endtag(self, tag: str) -> None:
        if tag in _DESCARTADAS:
            self._descartando = max(0, self._descartando - 1)
        elif tag in _BLOCOS and not self._descartando:
            self._fechar_bloco()

    def handle_data(self, data: str) -> None:
        if not self._descartando:
            self._atual.append(data)


def texto_de_html(html: str) -> str:
    """Texto visível do HTML: um bloco por linha (`\\n`), espaços internos colapsados.

    Descarta `script`, `style`, `noscript` e `template` com tudo que há dentro.
    """
    extrator = _Extrator()
    extrator.feed(html)
    extrator.close()
    extrator._fechar_bloco()
    return "\n".join(extrator.blocos)


def normalizar(s: str) -> str:
    """Forma comparável: sem acentos, caixa baixa, aspas retas e espaços colapsados."""
    decomposto = unicodedata.normalize("NFKD", s)
    sem_marcas = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_marcas.casefold().translate(_ASPAS).split())
