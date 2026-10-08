"""Validação das respostas do Claude às pendências (spec 7.4) e arquivamento de fontes.

`validar` é a defesa contra citação inventada. A primeira falha decide, nesta ordem:

1. esquema do `valor` (e, na P-E, tipos de sinal, modificadores e índices de evidência contra a matriz);
2. fonte de cada evidência: `sha256:<hex>` da custódia ou URL http(s), que `arquivar_fonte` baixa;
3. trecho: tem de existir no texto da fonte, comparado sem caixa, acento, aspas curvas nem espaços repetidos;
4. data: no modo retroativo, `data_fonte` (ou a data detectada na página) não passa do `as_of`.

A evidência cuja fonte não dá para conferir (rede indisponível, imagem sem OCR) entra com a marca
`trecho_nao_conferido`; a sem data, com `data_desconhecida`.

`arquivar_fonte` é o único lugar por onde uma URL dada pelo Claude chega à rede. Ele recusa o que não é
fonte pública (esquema que não é http(s), `localhost`, IP interno, e o alvo no `modo_contato="nenhum"`) e
confere cada salto de redirect com as mesmas regras: sem isso, um endereço público que redireciona para
`http://127.0.0.1/` passaria. Não resolve DNS: um nome público que aponta para IP interno não é detectado.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from typing import Any

import httpx
from pydantic import ValidationError

from radar.modelos import Contexto, ErroNo, Pendencia, Resposta
from radar.motor import Servicos
from radar.nos.alvo import dominio_registravel

# o mesmo decodificador dos snapshots do Wayback: charset do cabeçalho, senão o do <meta>, senão UTF-8
from radar.nos.wayback import _decodificar
from radar.pendencias.definicoes import DEFINICOES, _validos_da_matriz
from radar.pendencias.esquemas import ValorE
from radar.rede import ErroRede, RespostaRede
from radar.texto import normalizar, texto_de_html

MARCA_TRECHO_NAO_CONFERIDO = "trecho_nao_conferido"
MARCA_DATA_DESCONHECIDA = "data_desconhecida"

_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_MAX_REDIRECTS = 10  # como a Rede
_MAX_ERROS_NO_MOTIVO = 3

_EXT_POR_TIPO = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/plain": "txt",
    "application/json": "json",
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
# o Núcleo não faz OCR: o trecho de uma imagem não se confere
_IMAGENS = frozenset({"png", "jpg", "jpeg", "gif", "webp", "img"})
_CLASSES_DE_IP = (
    ("loopback", "is_loopback"),
    ("privado", "is_private"),
    ("link-local", "is_link_local"),
    ("reservado", "is_reserved"),
    ("multicast", "is_multicast"),
    ("não especificado", "is_unspecified"),
)


@dataclass(frozen=True)
class FonteArquivada:
    """`texto` é o texto visível (HTML passa por `texto_de_html`; imagem fica vazia); `data_publicacao` é a
    data detectada na página (`article:published_time`, `meta name=date`, `datePublished` do JSON-LD ou
    `<time datetime>`, nessa ordem de prioridade) ou `None`."""

    ref: str
    texto: str
    data_publicacao: date | None


@dataclass(frozen=True)
class Validacao:
    """`motivo` e `campo` dizem ao Claude o que corrigir (`campo`: `valor`, `evidencias[i].fonte`,
    `evidencias[i].trecho` ou `evidencias[i].data_fonte`). `marcas` só existem quando `aceita`."""

    aceita: bool
    motivo: str | None = None
    campo: str | None = None
    marcas: list[str] = field(default_factory=list)


# --- decodificação ----------------------------------------------------------------------------------------


def decodificar(conteudo: bytes, ext: str, headers: dict[str, str] | None = None) -> str:
    """O texto de um artefato. HTML: charset do cabeçalho, senão o do `<meta>` (sites antigos em ISO-8859-1),
    senão UTF-8. O resto: UTF-8 com `replace`."""
    resposta = RespostaRede(status=200, url="", conteudo=conteudo, headers=headers or {})
    return _decodificar(resposta) if ext == "html" else resposta.texto


def _ext_do_tipo(content_type: str) -> str:
    """A extensão do artefato mais próxima do `Content-Type`; sem ele (ou desconhecido), `html`."""
    tipo = content_type.partition(";")[0].strip().lower()
    if tipo in _EXT_POR_TIPO:
        return _EXT_POR_TIPO[tipo]
    if tipo.endswith("+json"):
        return "json"
    if tipo.endswith("+xml"):
        return "xml"
    if tipo.startswith("image/"):
        return "img"
    if tipo.startswith("text/"):
        return "txt"
    return "html"


# --- data de publicação -----------------------------------------------------------------------------------


def _data(valor: Any) -> date | None:
    """Os 10 primeiros caracteres de `valor` como data ISO que existe no calendário, senão `None`."""
    if not isinstance(valor, str):
        return None
    inicio = valor.strip()[:10]
    if not _DATA_ISO.fullmatch(inicio):
        return None
    try:
        return date.fromisoformat(inicio)
    except ValueError:
        return None


def _data_do_json_ld(texto: str) -> date | None:
    """O primeiro `datePublished` válido do JSON-LD (qualquer profundidade, na ordem do documento)."""
    try:
        dados = json.loads(texto)
    except (ValueError, RecursionError):  # o JSON é do site: lixo e aninhamento absurdo são "sem data"
        return None
    pilha = [dados]
    while pilha:  # sem recursão: a profundidade vem de fora
        atual = pilha.pop()
        if isinstance(atual, dict):
            if (achada := _data(atual.get("datePublished"))) is not None:
                return achada
            pilha.extend(reversed(list(atual.values())))
        elif isinstance(atual, list):
            pilha.extend(reversed(atual))
    return None


class _Datas(HTMLParser):
    """Guarda, de cada fonte de data, a primeira que for uma data válida."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.article: date | None = None
        self.meta_date: date | None = None
        self.json_ld: date | None = None
        self.time: date | None = None
        self._json: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        atributos = {nome.lower(): valor or "" for nome, valor in attrs}
        if tag == "meta":
            if self.article is None and atributos.get("property", "").strip().lower() == "article:published_time":
                self.article = _data(atributos.get("content"))
            elif self.meta_date is None and atributos.get("name", "").strip().lower() == "date":
                self.meta_date = _data(atributos.get("content"))
        elif tag == "time":
            if self.time is None:
                self.time = _data(atributos.get("datetime"))
        elif tag == "script" and self.json_ld is None:
            if atributos.get("type", "").strip().lower() == "application/ld+json":
                self._json = []

    def handle_data(self, data: str) -> None:
        if self._json is not None:
            self._json.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json is not None:
            self.json_ld = _data_do_json_ld("".join(self._json))
            self._json = None


def _data_de_publicacao(html: str) -> date | None:
    datas = _Datas()
    datas.feed(html)
    datas.close()
    return datas.article or datas.meta_date or datas.json_ld or datas.time


# --- destino permitido (SSRF e modo_contato) --------------------------------------------------------------


def _recusa(motivo: str) -> ErroNo:
    return ErroNo(f"fonte recusada: {motivo}", permanente=True)


def _ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """O IP que `host` escreve, ou `None` se for um nome. Inclui as notações antigas de IPv4 que o resolvedor do
    sistema aceita (`127.1`, `2130706433`, `0x7f000001`): o `httpx` as repassa como estão."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except (OSError, ValueError):
        return None


def _classe_nao_publica(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    ip = getattr(ip, "ipv4_mapped", None) or ip  # ::ffff:127.0.0.1 vale pelo IPv4 dentro dele
    return next((nome for nome, atributo in _CLASSES_DE_IP if getattr(ip, atributo)), None)


def _checar_destino(url: str, ctx: Contexto) -> None:
    """`ErroNo` permanente "fonte recusada: ..." se `url` não é uma fonte pública que se possa visitar."""
    try:
        destino = httpx.URL(url)
    except httpx.InvalidURL as erro:
        raise _recusa(f"URL inválida ({erro})") from erro
    if destino.scheme not in ("http", "https"):
        raise _recusa(f"esquema não permitido ({destino.scheme or 'nenhum'}); use http ou https")
    host = destino.host.rstrip(".").lower()
    if not host:
        raise _recusa("URL sem host")
    if host == "localhost" or host.endswith(".localhost"):
        raise _recusa(f"host local não permitido: {host}")
    ip = _ip_literal(host)
    if ip is not None and (classe := _classe_nao_publica(ip)):
        raise _recusa(f"IP não público ({classe}): {host}")
    if ctx.modo_contato == "nenhum" and dominio_registravel(host) == ctx.alvo:
        raise _recusa("modo_contato=nenhum não permite acessar o alvo; cite o snapshot do Wayback")


# --- arquivar_fonte ---------------------------------------------------------------------------------------


def _proximo_salto(base: str, location: str, url: str) -> str:
    try:
        return str(httpx.URL(base).join(location))
    except httpx.InvalidURL as erro:
        raise ErroRede(
            f"GET {url}: Location inválido no redirect de {base}: {location!r}", permanente=True, url=url
        ) from erro


async def _arquivar(url: str, ctx: Contexto, s: Servicos) -> tuple[FonteArquivada, str]:
    """A fonte arquivada e a extensão com que ficou na custódia."""
    atual = url
    for _ in range(_MAX_REDIRECTS + 1):
        _checar_destino(atual, ctx)
        resposta = await s.rede.get(atual, tipo="navegador", seguir_redirect=False)
        location = resposta.headers.get("location")
        if not (300 <= resposta.status < 400 and location):
            break
        atual = _proximo_salto(resposta.url, location, url)
    else:
        raise ErroRede(f"GET {url}: mais de {_MAX_REDIRECTS} redirects seguidos", permanente=True, url=url)

    ext = _ext_do_tipo(resposta.headers.get("content-type", ""))
    ref = s.custodia.guardar(resposta.conteudo, ext, tipo="fonte", origem=url)
    if ext in _IMAGENS:
        return FonteArquivada(ref, "", None), ext
    texto = decodificar(resposta.conteudo, ext, resposta.headers)
    if ext == "html":
        return FonteArquivada(ref, texto_de_html(texto), _data_de_publicacao(texto)), ext
    return FonteArquivada(ref, texto, None), ext


async def arquivar_fonte(url: str, ctx: Contexto, s: Servicos) -> FonteArquivada:
    """Baixa `url` pela `Rede` e guarda na custódia (`tipo="fonte"`, `origem=url`).

    `ErroNo` permanente "fonte recusada: ..." se o destino (da URL ou de qualquer redirect) não é permitido;
    `ErroRede` se a página não pôde ser baixada. Uma URL repetida na mesma execução sai do cache da `Rede`.
    """
    return (await _arquivar(url, ctx, s))[0]


# --- validar ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Fonte:
    """`texto` é o normalizado, ou `None` quando não dá para conferir o trecho."""

    texto: str | None
    data_detectada: date | None = None


def _rejeitar(motivo: str, campo: str) -> Validacao:
    return Validacao(False, motivo, campo)


def _resumo(erro: ValidationError) -> str:
    erros = erro.errors(include_url=False, include_context=False, include_input=False)
    partes = []
    for item in erros[:_MAX_ERROS_NO_MOTIVO]:
        local = ".".join(str(parte) for parte in item["loc"])
        partes.append(f"{local}: {item['msg']}" if local else item["msg"])
    resto = len(erros) - _MAX_ERROS_NO_MOTIVO
    return "; ".join(partes) + (f" (e mais {resto})" if resto > 0 else "")


def _validar_pe(valor: ValorE, total_evidencias: int, matriz: Any) -> Validacao | None:
    """Os tipos e modificadores têm de ser os que a `nova_pendencia` listou ao Claude (`tipos_validos` e
    `modificadores_validos`), e cada índice tem de apontar para uma evidência da resposta."""
    validos = _validos_da_matriz(matriz)
    tipos = set(filter(None, validos["tipos_validos"].split("|")))
    modificadores = set(filter(None, validos["modificadores_validos"].split("|")))
    for sinal in valor.sinais:
        if sinal.tipo not in tipos:
            return _rejeitar(f"tipo de sinal desconhecido: {sinal.tipo}", "valor")
        if sinal.evidencia >= total_evidencias:
            return _rejeitar(f"índice de evidência inválido: {sinal.evidencia}", "valor")
    for modificador in valor.modificadores:
        if modificador.id not in modificadores:
            return _rejeitar(f"modificador desconhecido: {modificador.id}", "valor")
        if modificador.evidencia >= total_evidencias:
            return _rejeitar(f"índice de evidência inválido: {modificador.evidencia}", "valor")
    return None


def _validar_valor(resposta: Resposta, pendencia: Pendencia, s: Servicos) -> Validacao | None:
    """Passo 1. Só `confirmado` e `corrigido` trazem `valor`; `nao_encontrado` e `inconclusivo` vêm com ele
    vazio, e nenhum nó o lê."""
    definicao = DEFINICOES.get(pendencia.id)
    if definicao is None:
        raise ValueError(f"pendência desconhecida: {pendencia.id}")
    if resposta.status not in ("confirmado", "corrigido"):
        return None
    try:
        valor = definicao.modelo_valor.model_validate(resposta.valor)
    except ValidationError as erro:
        return _rejeitar(f"valor fora do esquema: {_resumo(erro)}", "valor")
    if isinstance(valor, ValorE):
        return _validar_pe(valor, len(resposta.evidencias), s.matriz)
    return None


def _fonte_da_custodia(ref: str, s: Servicos) -> _Fonte:
    try:
        caminho = s.custodia.caminho(ref)
        conteudo = caminho.read_bytes()
    except FileNotFoundError:
        raise ErroNo("fonte não encontrada na custódia", permanente=True) from None
    ext = caminho.suffix.lstrip(".").lower()
    if ext in _IMAGENS:
        return _Fonte(None)
    texto = decodificar(conteudo, ext)
    return _Fonte(normalizar(texto_de_html(texto) if ext == "html" else texto))


async def _fonte_da_url(url: str, ctx: Contexto, s: Servicos) -> _Fonte:
    try:
        arquivada, ext = await _arquivar(url, ctx, s)
    except ErroRede:
        return _Fonte(None)  # não deu para baixar: o trecho fica sem conferir, e a resposta não é culpada
    return _Fonte(None if ext in _IMAGENS else normalizar(arquivada.texto), arquivada.data_publicacao)


async def _carregar_fonte(fonte: str, ctx: Contexto, s: Servicos) -> _Fonte:
    """`ErroNo` com o motivo exato da rejeição quando a fonte é inválida, não está na custódia ou foi recusada."""
    if _HASH.fullmatch(fonte):
        return _fonte_da_custodia(fonte, s)
    if fonte.lower().startswith(("http://", "https://")):
        return await _fonte_da_url(fonte, ctx, s)
    raise ErroNo("fonte inválida: use sha256:<hex> ou URL http(s)", permanente=True)


def _marcar(marcas: list[str], marca: str) -> None:
    if marca not in marcas:
        marcas.append(marca)


async def validar(resposta: Resposta, pendencia: Pendencia, ctx: Contexto, s: Servicos) -> Validacao:
    """Confere a resposta do Claude à `pendencia` (spec 7.4). Ver o docstring do módulo para a ordem.

    `nao_encontrado` e `inconclusivo` sem evidências pulam os passos 2 a 4; com evidências, elas são
    validadas como as de qualquer outra resposta.
    """
    if (rejeicao := _validar_valor(resposta, pendencia, s)) is not None:
        return rejeicao
    if not resposta.evidencias:
        return Validacao(True)

    fontes: list[_Fonte] = []
    carregadas: dict[str, _Fonte] = {}
    for i, evidencia in enumerate(resposta.evidencias):
        fonte = evidencia.fonte.strip()
        try:
            if fonte not in carregadas:
                carregadas[fonte] = await _carregar_fonte(fonte, ctx, s)
        except ErroNo as erro:
            return _rejeitar(erro.mensagem, f"evidencias[{i}].fonte")
        fontes.append(carregadas[fonte])

    marcas: list[str] = []
    for i, (evidencia, fonte) in enumerate(zip(resposta.evidencias, fontes, strict=True)):
        procurado = normalizar(evidencia.trecho)
        if not procurado:  # "" está em qualquer texto: um trecho em branco não cita nada
            return _rejeitar("trecho vazio: cite o trecho literal da fonte", f"evidencias[{i}].trecho")
        if fonte.texto is None:
            _marcar(marcas, MARCA_TRECHO_NAO_CONFERIDO)
        elif procurado not in fonte.texto:
            return _rejeitar("trecho não encontrado na fonte", f"evidencias[{i}].trecho")

    for i, (evidencia, fonte) in enumerate(zip(resposta.evidencias, fontes, strict=True)):
        data = evidencia.data_fonte or fonte.data_detectada
        if data is None:
            _marcar(marcas, MARCA_DATA_DESCONHECIDA)
        elif ctx.retroativo and data > ctx.as_of:
            return _rejeitar("data_fonte posterior ao as_of", f"evidencias[{i}].data_fonte")
    return Validacao(True, marcas=marcas)
