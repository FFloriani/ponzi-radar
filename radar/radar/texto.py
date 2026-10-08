"""Texto visível de HTML, normalização para comparar trechos e nomes, decodificação de bytes, texto de PDF e escape
para Markdown."""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from html.parser import HTMLParser

from pypdf import PdfReader

from radar.rede import RespostaRede

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

_BYTES_PARA_META = 4096
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_.:\-]+)""", re.IGNORECASE)
_BOM = chr(0xFEFF)

# as deliberações têm 1 ou 2 páginas e 40 a 300 KB; o que passar disso não é uma delas
_MAX_BYTES_PDF = 10_000_000
_MAX_PAGINAS_PDF = 60
# o menor texto de PDF real tinha mais de 2 mil caracteres; abaixo disto é PDF de imagem ou lixo
_MIN_CARACTERES_PDF = 100

logging.getLogger("pypdf").setLevel(logging.ERROR)


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
    """Forma comparável: sem acentos, caixa baixa, aspas retas e espaços colapsados.

    Os caracteres invisíveis de formatação (categoria Cf: hífen opcional, espaço de largura zero, junção, BOM,
    marcas de direção) somem: um site pode salpicá-los numa palavra sem que o visitante veja.
    """
    decomposto = unicodedata.normalize("NFKD", s)
    visiveis = "".join(c for c in decomposto if not unicodedata.combining(c) and unicodedata.category(c) != "Cf")
    return " ".join(visiveis.casefold().translate(_ASPAS).split())


def decodificar(dados: bytes, content_type: str | None) -> str:
    """O texto de `dados`: o charset do `Content-Type`; sem ele, o do `<meta>` (sites antigos em ISO-8859-1), se
    o conteúdo é HTML ou XML ou o tipo é desconhecido (`None`); senão UTF-8 com `replace`.

    O charset vem do site investigado e pode ser qualquer coisa: o nome que o Python não conhece (`LookupError`)
    e o codec que não decodifica texto (`idna`, `undefined`: `UnicodeError`) caem no UTF-8, nunca levantam.
    """
    tipo = (content_type or "").lower()
    if "charset" not in tipo and (not tipo or "html" in tipo or "xml" in tipo):
        achado = _META_CHARSET.search(dados[:_BYTES_PARA_META])
        if achado:
            try:
                return dados.decode(achado.group(1).decode("ascii"), errors="replace").removeprefix(_BOM)
            except (LookupError, UnicodeError):
                pass
    cabecalhos = {"content-type": content_type} if content_type else {}
    return RespostaRede(status=200, url="", conteudo=dados, headers=cabecalhos).texto


def texto_de_pdf(dados: bytes) -> str:
    """O texto do PDF (páginas separadas por linha em branco), ou `""` se não é PDF, é grande demais ou não tem
    texto para extrair (PDF de imagem). O PDF vem de fora, mas qualquer falha do `pypdf` com ele é só "sem texto".

    A extração parte palavras ("COSTA F ERREIRA"): quem compara com ela deve ignorar os espaços. O texto sai
    saneado: o `pypdf` decodifica CMap malformado em substituto UTF-16 solto, que não se grava em JSON UTF-8.
    """
    if len(dados) > _MAX_BYTES_PDF:
        return ""
    try:
        paginas = PdfReader(io.BytesIO(dados)).pages
        partes = [(paginas[i].extract_text() or "").strip() for i in range(min(len(paginas), _MAX_PAGINAS_PDF))]
    except Exception:  # PdfReadError, EmptyFileError, ValueError, RecursionError...
        return ""
    texto = "\n\n".join(parte for parte in partes if parte).encode("utf-8", "replace").decode("utf-8")
    return texto if len(" ".join(texto.split())) >= _MIN_CARACTERES_PDF else ""


# ---------------------------------------------------------------------------- Markdown

# caracteres que o Markdown lê como formatação, link, HTML ou título: com `\` antes, valem como texto
_ESPECIAIS_MD = re.compile(r"([\\|`*\[\]<>&#~])")
# o sublinhado entre letras ou dígitos (`atraso_pagamento`, `a_b.html`) não vira ênfase: fica como está
_SUBLINHADO_SOLTO = re.compile(r"(?<![^\W_])_|_(?![^\W_])")
# controles (a quebra de linha e o tab viram espaço), marcas de direção e largura zero: um trecho do site não
# reordena nem esconde texto no dossiê
_INVISIVEIS_MD = dict.fromkeys(
    (*range(0x00, 0x09), *range(0x0E, 0x1C), 0x7F, *range(0x200B, 0x2010), *range(0x202A, 0x202F),
     *range(0x2066, 0x206A), 0xFEFF)
)  # fmt: skip
# CPF formatado, ou 11 dígitos logo depois do rótulo "CPF": nenhuma saída do radar grava CPF
_CPF = re.compile(
    r"(?<!\d)\d{3}\.\d{3}\.\d{3}\s?-\s?\d{2}(?!\d)|\bCPF\b[^\d\n]{0,4}\d{11}(?!\d)", re.IGNORECASE
)
_SEQUENCIA_DE_CRASES = re.compile(r"`+")
_CPF_OMITIDO = "(CPF omitido)"


def _em_uma_linha(valor: object) -> str:
    """O texto sem invisíveis, com qualquer quebra ou espaço repetido virando um espaço e o CPF mascarado."""
    texto = "" if valor is None else str(valor)
    return _CPF.sub(_CPF_OMITIDO, " ".join(texto.translate(_INVISIVEIS_MD).split()))


def escapar_md(valor: object, limite: int | None = None) -> str:
    """`valor` como texto literal numa linha ou célula de Markdown.

    Sem quebra de linha, com `\\` antes de cada caractere de formatação (o `|` não abre célula, `<script>` e
    `[a](url)` não viram HTML nem link) e sem CPF. `limite`: o máximo de caracteres do texto, cortado com `…`
    (depois de mascarar o CPF, antes do escape). `None` vira `""`.
    """
    texto = _em_uma_linha(valor)
    if limite is not None and len(texto) > limite:
        texto = texto[: limite - 1].rstrip() + "…"
    return _SUBLINHADO_SOLTO.sub(r"\\_", _ESPECIAIS_MD.sub(r"\\\1", texto))


def codigo_md(valor: object) -> str:
    """`valor` como trecho de código numa célula de tabela: URLs e hashes ficam sem escape e sem link.

    O `|` leva `\\` (a tabela o remove) e a cerca é mais longa que qualquer sequência de crases do texto.
    Texto vazio dá `""`.
    """
    texto = _em_uma_linha(valor).replace("|", "\\|")
    if not texto:
        return ""
    cerca = "`" * (max((len(m) for m in _SEQUENCIA_DE_CRASES.findall(texto)), default=0) + 1)
    margem = " " if texto.startswith("`") or texto.endswith("`") else ""
    return f"{cerca}{margem}{texto}{margem}{cerca}"
