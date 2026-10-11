"""Validação das respostas do Claude às pendências (spec 7.4) e arquivamento de fontes.

`validar` é a defesa contra citação inventada. A primeira falha decide, nesta ordem:

1. esquema do `valor` (e, na P-E, tipos de sinal, modificadores e índices de evidência contra a matriz) e os
   `itens` de cada evidência, que têm de ser itens da pendência;
2. fonte de cada evidência: `sha256:<hex>` da custódia ou URL http(s), que `arquivar_fonte` baixa;
3. trecho: com pelo menos 12 caracteres e 2 palavras (os marcadores da máscara não contam; no PDF os caracteres
   são contados sem espaços), e existente no texto da fonte, comparado sem caixa, acento, aspas curvas nem
   espaços repetidos (PDF: sem nenhum espaço, porque a extração parte palavras). No modo cego, o trecho também
   pode citar os marcadores da máscara (`[EMPRESA] paga 1% ao mês`);
4. data: no modo retroativo, nem a `data_fonte` nem a data que a página declara ter sido publicada passam do `as_of`.

A evidência cuja fonte não dá para conferir (rede indisponível, corpo grande demais, imagem sem OCR, binário, PDF
sem texto) entra com a marca `trecho_nao_conferido`; a sem data, com `data_desconhecida`. Cada marca vem uma vez na
forma da spec (`trecho_nao_conferido`) e, depois dela, uma vez por evidência (`trecho_nao_conferido:evidencias[1]`),
para o dossiê pôr a marca só no item que cita aquela evidência.

`arquivar_fonte` é o único lugar por onde uma URL dada pelo Claude chega à rede. Ele recusa o que não é fonte
pública: esquema que não é http(s), `localhost`, nome malformado, IP ou nome que resolve para IP não global, o
alvo, o destino para onde ele redireciona (saída do nó `destino`), os outros domínios do site que a captura visitou
(`captura.dominios_visitados`: o rastreador no meio do redirect, a página de uma execução gravada antes do nó
`destino`) e os IPs do domínio analisado (só o nó `captura` visita o site) e serviços que fazem um terceiro visitar o
alvo. Cada salto de
redirect passa pelas mesmas regras: sem isso, um endereço público que redireciona para `http://127.0.0.1/`
passaria. Com proxy configurado o nome não é resolvido aqui (quem resolve é o proxy). A resolução e a conexão são
consultas separadas: um nome que muda de IP entre elas (DNS rebinding) não é detectado.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from typing import Any

import httpx
from pydantic import ValidationError

from radar.modelos import Contexto, ErroNo, Pendencia, Resposta
from radar.motor import Servicos
from radar.nos.alvo import dominio_registravel
from radar.pendencias.definicoes import DEFINICOES, validos_da_matriz
from radar.pendencias.esquemas import ValorE
from radar.pendencias.mascara import MARCADOR, mascarar
from radar.rede import ErroRede
from radar.texto import decodificar, normalizar, texto_de_html, texto_de_pdf

MARCA_TRECHO_NAO_CONFERIDO = "trecho_nao_conferido"
MARCA_DATA_DESCONHECIDA = "data_desconhecida"

_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_SALVAR_NO_WAYBACK = re.compile(r"/+save(?:/|$)", re.IGNORECASE)
_MAX_REDIRECTS = 10  # como a Rede
_MAX_BYTES = 10_000_000  # corpo maior que isto não é guardado nem lido
_MAX_ERROS_NO_MOTIVO = 3
_MAX_HOST = 253  # tamanho máximo de um nome de host, e de cada rótulo dele, em caracteres
_MAX_ROTULO = 63
_BOM_UTF8 = b"\xef\xbb\xbf"
# o nome não existe (e não é falha passageira do resolvedor): `EAI_NONAME` e, onde existe, `EAI_NODATA`
_NOME_INEXISTENTE = frozenset(c for c in (socket.EAI_NONAME, getattr(socket, "EAI_NODATA", None)) if c is not None)
_MIN_CARACTERES_DO_TRECHO = 12
_MIN_PALAVRAS_DO_TRECHO = 2

_EXT_POR_TIPO = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/plain": "txt",
    "application/json": "json",
    "application/xml": "xml",
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
# o tipo que `decodificar` recebe para um artefato da custódia, que não guarda o `Content-Type`
_TIPO_POR_EXT = {"html": "text/html", "xml": "text/xml"}
# o Núcleo não faz OCR e não lê binário: o trecho dessas fontes não se confere
_SEM_TEXTO = frozenset({"png", "jpg", "jpeg", "gif", "webp", "img", "bin"})
_CLASSES_DE_IP = (
    ("loopback", "is_loopback"),
    ("privado", "is_private"),
    ("link-local", "is_link_local"),
    ("reservado", "is_reserved"),
    ("multicast", "is_multicast"),
    ("não especificado", "is_unspecified"),
)
_MOTIVO_ALVO_NENHUM = "modo_contato=nenhum não permite acessar o alvo; cite o snapshot do Wayback"
_MOTIVO_ALVO = "o alvo só é acessado pela captura; cite o sha256 da captura ou o snapshot do Wayback"
_MOTIVO_ALVO_CEGO = "domínio não permitido"  # no modo cego a mensagem não diz que o endereço é o do alvo


@dataclass(frozen=True)
class FonteArquivada:
    """`texto` é o texto visível (HTML passa por `texto_de_html`, PDF por `texto_de_pdf`; imagem e binário ficam
    vazios); `data_publicacao` é a data detectada na página (`article:published_time`, `meta name=date`,
    `datePublished` do JSON-LD ou `<time datetime>`, nessa ordem de prioridade) ou `None`."""

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


def _ext_pelo_conteudo(corpo: bytes) -> str:
    """Tipo ausente, desconhecido ou `octet-stream`: o conteúdo diz. `<` no começo (depois de BOM e espaços) é
    HTML; UTF-8 válido e sem NUL é texto; o resto é binário."""
    if corpo.removeprefix(_BOM_UTF8).lstrip().startswith(b"<"):
        return "html"
    if b"\x00" in corpo:
        return "bin"
    try:
        corpo.decode("utf-8")
    except UnicodeDecodeError:
        return "bin"
    return "txt"


def _tipo_para_decodificar(content_type: str, ext: str) -> str:
    """O `Content-Type` com que `decodificar` lê o corpo: o HTML farejado sem tipo de HTML é lido como tal (o
    `<meta charset>` vale) e o texto farejado sem tipo é UTF-8."""
    base, _, parametros = content_type.partition(";")
    if ext == "html" and "html" not in base.lower():
        return "text/html" + (f";{parametros}" if parametros else "")
    if ext == "txt" and not base.strip():
        return "text/plain"
    return content_type


def _ext_do_tipo(content_type: str, corpo: bytes) -> str:
    """A extensão do artefato: `pdf` se o corpo começa por `%PDF-` (seja qual for o tipo declarado), senão a mais
    próxima do `Content-Type`; tipo ausente ou desconhecido, pelo conteúdo (`html`, `txt` ou `bin`)."""
    if corpo.startswith(b"%PDF-"):
        return "pdf"
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
    return _ext_pelo_conteudo(corpo)


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


def _datas_de_publicacao(html: str) -> tuple[date | None, date | None]:
    """`(forte, qualquer)`. A forte é a que a página declara no `<head>` ou no JSON-LD; a outra acrescenta o
    `<time datetime>`, que costuma ser a data de um evento e só vale quando não há nada melhor."""
    datas = _Datas()
    datas.feed(html)
    datas.close()
    forte = datas.article or datas.meta_date or datas.json_ld
    return forte, forte or datas.time


# --- destino permitido (SSRF, alvo e serviços que o visitam) ----------------------------------------------


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
    """Por que o IP não é um destino público, ou `None` se é. Tudo que não é global conta (CGNAT, documentação,
    reservado...), além do multicast, que o `is_global` deixa passar."""
    ip = getattr(ip, "ipv4_mapped", None) or ip  # ::ffff:127.0.0.1 vale pelo IPv4 dentro dele
    classe = next((nome for nome, atributo in _CLASSES_DE_IP if getattr(ip, atributo)), None)
    return classe or (None if ip.is_global else "não global")


def _rotulos_validos(host: str) -> bool:
    """Nome de host com 1 a 63 caracteres por rótulo e até 253 no total. O resto o `idna` do `getaddrinfo` não
    codifica (`UnicodeError`) e a conexão da `Rede` também não faria."""
    return len(host) <= _MAX_HOST and all(0 < len(rotulo) <= _MAX_ROTULO for rotulo in host.split("."))


async def _enderecos_do_nome(host: str, timeout: float) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Os endereços do nome. `ErroNo` se o nome é inválido para o resolvedor ou não existe. Outra falha de
    resolução (ou resolução que demora demais) devolve `[]`: quem falha em seguida é a conexão da `Rede`, com
    `ErroRede`."""
    try:
        infos = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM), timeout
        )
    except ValueError as erro:  # inclui `UnicodeError`, do codec `idna`: "label empty", "label too long"
        raise _recusa("host inválido") from erro
    except socket.gaierror as erro:
        if erro.errno in _NOME_INEXISTENTE:
            raise ErroNo(
                "fonte não encontrada (domínio inexistente); cite uma URL existente ou o snapshot do Wayback",
                permanente=True,
            ) from erro
        return []
    except (OSError, TimeoutError):
        return []
    enderecos = []
    for info in infos:
        try:
            enderecos.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    return enderecos


def _forma_canonica(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    return str(getattr(ip, "ipv4_mapped", None) or ip)


def _canonicos(ips: set[str] | None) -> frozenset[str]:
    """Os IPs na forma canônica (`2606:2800:0220::1` e `2606:2800:220::1` são o mesmo); o que não é IP sai."""
    canonicos = set()
    for ip in ips or ():
        try:
            canonicos.add(_forma_canonica(ipaddress.ip_address(str(ip).strip())))
        except ValueError:
            continue
    return frozenset(canonicos)


def _dominios_do_alvo(ctx: Contexto, dominio_destino: str | Iterable[str | None] | None) -> frozenset[str]:
    """Os domínios registráveis que só a captura visita: o do alvo e os de `dominio_destino` (um domínio ou vários: o
    destino do redirect, saída `dominio` do nó `destino`, e os que a captura visitou, `captura.dominios_visitados`), em
    minúsculas e em punycode, como `dominio_registravel` os devolve. O que não é texto ou é vazio fica de fora."""
    dominios = {ctx.alvo.lower()}
    for dominio in [dominio_destino] if isinstance(dominio_destino, str) else dominio_destino or ():
        if isinstance(dominio, str) and (destino := dominio.strip().rstrip(".").lower()):
            try:
                dominios.add(destino.encode("idna").decode("ascii"))
            except UnicodeError:  # rótulo que o codec não aceita: vale como veio
                dominios.add(destino)
    return frozenset(dominios)


def _recusa_do_alvo(ctx: Contexto) -> ErroNo:
    if ctx.modo_cego:
        return _recusa(_MOTIVO_ALVO_CEGO)
    return _recusa(_MOTIVO_ALVO_NENHUM if ctx.modo_contato == "nenhum" else _MOTIVO_ALVO)


async def _checar_destino(
    url: str, ctx: Contexto, s: Servicos, ips_do_alvo: frozenset[str], dominios_do_alvo: frozenset[str]
) -> None:
    """`ErroNo` permanente se `url` não é uma fonte pública que se possa visitar: "fonte recusada: ..." ou, para
    um nome que não existe, "fonte não encontrada (domínio inexistente)...". `ips_do_alvo` são os IPs do alvo
    (na forma canônica): um IP literal deles é o próprio alvo. `dominios_do_alvo` (`_dominios_do_alvo`): o domínio
    registrável do alvo e o do destino do redirect; uma página deles é o próprio alvo."""
    try:
        destino = httpx.URL(url)
        # o host de rede (IDNA/punycode), não o `.host`, que vem em Unicode e não bateria com `ctx.alvo`
        host = destino.raw_host.decode("ascii").rstrip(".").lower()
        _ = destino.host  # levanta para um rótulo punycode inválido, que a Rede também não conseguiria usar
    except httpx.InvalidURL as erro:
        raise _recusa(f"URL inválida ({erro})") from erro
    except UnicodeError as erro:
        raise _recusa("host inválido") from erro
    if destino.scheme not in ("http", "https"):
        raise _recusa(f"esquema não permitido ({destino.scheme or 'nenhum'}); use http ou https")
    if not host:
        raise _recusa("URL sem host")
    if host == "localhost" or host.endswith(".localhost"):
        raise _recusa(f"host local não permitido: {host}")
    # serviços que fazem um terceiro visitar o alvo ao vivo: a visita seria dele, mas a pedido nosso
    if host == "translate.goog" or host.endswith(".translate.goog"):
        raise _recusa("serviço que visita o alvo")
    if host == "web.archive.org" and _SALVAR_NO_WAYBACK.match(destino.path):
        raise _recusa("serviço que visita o alvo")
    ip = _ip_literal(host)
    if ip is not None and (classe := _classe_nao_publica(ip)):
        raise _recusa(f"IP não público ({classe}): {host}")
    if ip is None and not _rotulos_validos(host):
        raise _recusa("host inválido")
    if (ip is not None and _forma_canonica(ip) in ips_do_alvo) or dominio_registravel(host) in dominios_do_alvo:
        raise _recusa_do_alvo(ctx)
    if ip is None and not s.config.rede.proxy:
        for endereco in await _enderecos_do_nome(host, s.config.rede.timeout_s):
            if classe := _classe_nao_publica(endereco):
                raise _recusa(f"o nome {host} resolve para IP não público ({classe}): {endereco}")


# --- arquivar_fonte ---------------------------------------------------------------------------------------


def _proximo_salto(base: str, location: str, url: str) -> str:
    try:
        return str(httpx.URL(base).join(location))
    except httpx.InvalidURL as erro:
        raise ErroRede(
            f"GET {url}: Location inválido no redirect de {base}: {location!r}", permanente=True, url=url
        ) from erro


@dataclass(frozen=True)
class _Arquivo:
    fonte: FonteArquivada
    ext: str
    data_forte: date | None


async def _arquivar(
    url: str, ctx: Contexto, s: Servicos, ips_do_alvo: frozenset[str], dominios_do_alvo: frozenset[str]
) -> _Arquivo:
    atual = url
    for _ in range(_MAX_REDIRECTS + 1):
        await _checar_destino(atual, ctx, s, ips_do_alvo, dominios_do_alvo)
        # sem cache: a fonte arquivada tem de ser a página de agora. O teto vale durante a leitura: um corpo enorme
        # ou infinito, induzido por conteúdo hostil, não chega à memória
        resposta = await s.rede.get(
            atual, tipo="navegador", seguir_redirect=False, usar_cache=False, max_bytes=_MAX_BYTES
        )
        location = resposta.headers.get("location")
        if not (300 <= resposta.status < 400 and location):
            break
        atual = _proximo_salto(resposta.url, location, url)
    else:
        raise ErroRede(f"GET {url}: mais de {_MAX_REDIRECTS} redirects seguidos", permanente=True, url=url)

    conteudo = resposta.conteudo
    tipo = resposta.headers.get("content-type", "")
    ext = _ext_do_tipo(tipo, conteudo)
    ref = s.custodia.guardar(conteudo, ext, tipo="fonte", origem=url)
    if ext in _SEM_TEXTO:
        return _Arquivo(FonteArquivada(ref, "", None), ext, None)
    if ext == "pdf":
        return _Arquivo(FonteArquivada(ref, await asyncio.to_thread(texto_de_pdf, conteudo), None), ext, None)
    texto = decodificar(conteudo, _tipo_para_decodificar(tipo, ext))
    if ext == "html":
        forte, qualquer = _datas_de_publicacao(texto)
        return _Arquivo(FonteArquivada(ref, texto_de_html(texto), qualquer), ext, forte)
    return _Arquivo(FonteArquivada(ref, texto, None), ext, None)


async def arquivar_fonte(
    url: str,
    ctx: Contexto,
    s: Servicos,
    ips_do_alvo: set[str] | None = None,
    dominio_destino: str | Iterable[str | None] | None = None,
) -> FonteArquivada:
    """Baixa `url` pela `Rede` e guarda na custódia (`tipo="fonte"`, `origem=url`).

    `ErroNo` permanente "fonte recusada: ..." se o destino (da URL ou de qualquer redirect) não é permitido, ou
    "fonte não encontrada (domínio inexistente)..."; `ErroRede` se a página não pôde ser baixada ou o corpo passa
    de 10 MB. `ips_do_alvo`: os endereços A/AAAA do domínio analisado (saída do nó `dns`, que resolve o destino do
    redirect quando há); um IP literal deles é recusado. `dominio_destino`: o domínio para onde o alvo redireciona
    (saída `dominio` do nó `destino`) ou uma coleção com ele e os que a captura visitou (`captura.dominios_visitados`),
    recusados como o do alvo.
    """
    dominios = _dominios_do_alvo(ctx, dominio_destino)
    return (await _arquivar(url, ctx, s, _canonicos(ips_do_alvo), dominios)).fonte


# --- validar ----------------------------------------------------------------------------------------------


@dataclass
class _Fonte:
    """`texto` é o texto visível da fonte, ou `None` quando não dá para conferir o trecho nela."""

    texto: str | None
    data_detectada: date | None = None
    data_forte: date | None = None
    pdf: bool = False
    _normal: str | None = field(default=None, repr=False)
    _mascarada: str | None = field(default=None, repr=False)

    def _chave(self, texto: str) -> str:
        normal = normalizar(texto)
        return "".join(normal.split()) if self.pdf else normal

    async def contem(self, procurado: str, mascara: dict[str, str] | None) -> bool:
        """O trecho (já normalizado) está no texto? PDF: sem espaços dos dois lados. Com `mascara`, também vale o
        que o Claude enxergaria: o texto com os termos trocados pelos marcadores."""
        assert self.texto is not None
        if self.pdf:
            procurado = "".join(procurado.split())
        if self._normal is None:
            self._normal = self._chave(self.texto)
        if procurado in self._normal:
            return True
        if not mascara:
            return False
        if self._mascarada is None:
            self._mascarada = self._chave(await asyncio.to_thread(mascarar, self.texto, mascara))
        return procurado in self._mascarada


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
    validos = validos_da_matriz(matriz)
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


async def _fonte_da_custodia(ref: str, s: Servicos) -> _Fonte:
    try:
        caminho = s.custodia.caminho(ref)
        conteudo = caminho.read_bytes()
    except FileNotFoundError:
        raise ErroNo("fonte não encontrada na custódia", permanente=True) from None
    if "julgamento" in s.custodia.tipos(ref):  # o que o Claude respondeu antes não prova o que ele responde agora
        raise ErroNo("fonte inválida: julgamento não é fonte", permanente=True)
    ext = caminho.suffix.lstrip(".").lower()
    if ext == "har":
        raise ErroNo("fonte .har não é citável: cite o html ou o texto da página", permanente=True)
    if ext in _SEM_TEXTO:
        return _Fonte(None)
    if ext == "pdf":
        return _Fonte(await asyncio.to_thread(texto_de_pdf, conteudo) or None, pdf=True)
    texto = decodificar(conteudo, _TIPO_POR_EXT.get(ext, "text/plain"))
    return _Fonte(texto_de_html(texto) if ext == "html" else texto)


async def _fonte_da_url(
    url: str, ctx: Contexto, s: Servicos, ips_do_alvo: frozenset[str], dominios_do_alvo: frozenset[str]
) -> _Fonte:
    try:
        arquivo = await _arquivar(url, ctx, s, ips_do_alvo, dominios_do_alvo)
    except ErroRede as erro:
        if erro.status in (404, 410):
            raise ErroNo(
                f"fonte não encontrada (HTTP {erro.status}); cite uma URL existente ou o snapshot do Wayback",
                permanente=True,
            ) from erro
        return _Fonte(None)  # não deu para baixar: o trecho fica sem conferir, e a resposta não é culpada
    texto = None if arquivo.ext in _SEM_TEXTO else arquivo.fonte.texto
    if arquivo.ext == "pdf":
        texto = texto or None  # PDF sem texto extraível não se confere
    return _Fonte(texto, arquivo.fonte.data_publicacao, arquivo.data_forte, pdf=arquivo.ext == "pdf")


async def _carregar_fonte(
    fonte: str, ctx: Contexto, s: Servicos, ips_do_alvo: frozenset[str], dominios_do_alvo: frozenset[str]
) -> _Fonte:
    """`ErroNo` com o motivo exato da rejeição quando a fonte é inválida, não existe ou foi recusada."""
    if _HASH.fullmatch(fonte):
        return await _fonte_da_custodia(fonte, s)
    if fonte.lower().startswith(("http://", "https://")):
        return await _fonte_da_url(fonte, ctx, s, ips_do_alvo, dominios_do_alvo)
    raise ErroNo("fonte inválida: use sha256:<hex> ou URL http(s)", permanente=True)


def _marcar(marcas: list[str], marca: str, indice: int) -> None:
    """A marca agregada da spec, sem repetir, e a da evidência `indice` (`marca:evidencias[i]`)."""
    for valor in (marca, f"{marca}:evidencias[{indice}]"):
        if valor not in marcas:
            marcas.append(valor)


def _itens_fora(resposta: Resposta, pendencia: Pendencia) -> Validacao | None:
    """Os `itens` de cada evidência têm de ser itens da pendência (`B3` na P-B; nenhum na P-CNPJ e na P-E)."""
    for i, evidencia in enumerate(resposta.evidencias):
        if fora := [item for item in evidencia.itens or () if item not in pendencia.itens]:
            cobre = f"cobre {', '.join(pendencia.itens)}" if pendencia.itens else "não cobre item da matriz"
            return _rejeitar(f"item fora da pendência: {', '.join(fora)} (a {pendencia.id} {cobre})",
                             f"evidencias[{i}].itens")  # fmt: skip
    return None


async def validar(
    resposta: Resposta,
    pendencia: Pendencia,
    ctx: Contexto,
    s: Servicos,
    mascara: dict[str, str] | None = None,
    ips_do_alvo: set[str] | None = None,
    dominio_destino: str | Iterable[str | None] | None = None,
) -> Validacao:
    """Confere a resposta do Claude à `pendencia` (spec 7.4). Ver o docstring do módulo para a ordem.

    `nao_encontrado` e `inconclusivo` sem evidências pulam os passos 2 a 4; com evidências, elas são
    validadas como as de qualquer outra resposta. `mascara` (a de `montar_mascara`) só vale com `ctx.modo_cego`.
    `ips_do_alvo`: os endereços A/AAAA do domínio analisado (saída do nó `dns`), cujo IP literal não é fonte.
    `dominio_destino`: o domínio para onde o alvo redireciona (saída `dominio` do nó `destino`), ou a coleção com ele e
    os que a captura visitou (`captura.dominios_visitados`), que não são fonte.
    """
    if (rejeicao := _validar_valor(resposta, pendencia, s) or _itens_fora(resposta, pendencia)) is not None:
        return rejeicao
    if not resposta.evidencias:
        return Validacao(True)

    ips = _canonicos(ips_do_alvo)
    dominios = _dominios_do_alvo(ctx, dominio_destino)
    fontes: list[_Fonte] = []
    carregadas: dict[str, _Fonte] = {}
    for i, evidencia in enumerate(resposta.evidencias):
        fonte = evidencia.fonte.strip()
        try:
            if fonte not in carregadas:
                carregadas[fonte] = await _carregar_fonte(fonte, ctx, s, ips, dominios)
        except ErroNo as erro:
            return _rejeitar(erro.mensagem, f"evidencias[{i}].fonte")
        fontes.append(carregadas[fonte])

    mascara_ativa = mascara if ctx.modo_cego else None
    marcas: list[str] = []
    for i, (evidencia, fonte) in enumerate(zip(resposta.evidencias, fontes, strict=True)):
        procurado = normalizar(evidencia.trecho)
        # um trecho de uma letra, de "%" ou de uma palavra comum está em qualquer página. O tamanho é o do que a
        # fonte de fato confere: sem os marcadores da máscara (que não são texto da fonte) e, no PDF, sem espaços
        util = " ".join(MARCADOR.sub(" ", procurado).split())
        caracteres = len("".join(util.split())) if fonte.pdf else len(util)
        if caracteres < _MIN_CARACTERES_DO_TRECHO or len(util.split()) < _MIN_PALAVRAS_DO_TRECHO:
            return _rejeitar(
                f"trecho curto demais: cite ao menos {_MIN_CARACTERES_DO_TRECHO} caracteres literais da fonte",
                f"evidencias[{i}].trecho",
            )
        if fonte.texto is None:
            _marcar(marcas, MARCA_TRECHO_NAO_CONFERIDO, i)
        elif not await fonte.contem(procurado, mascara_ativa):
            return _rejeitar("trecho não encontrado na fonte", f"evidencias[{i}].trecho")

    for i, (evidencia, fonte) in enumerate(zip(resposta.evidencias, fontes, strict=True)):
        # a data declarada vale, ou a detectada na página; mas uma data forte da página depois do as_of derruba
        # a evidência mesmo com uma data_fonte anterior
        datas = [d for d in (evidencia.data_fonte or fonte.data_detectada, fonte.data_forte) if d is not None]
        if ctx.retroativo and any(data > ctx.as_of for data in datas):
            return _rejeitar("data_fonte posterior ao as_of", f"evidencias[{i}].data_fonte")
        if not datas:
            _marcar(marcas, MARCA_DATA_DESCONHECIDA, i)
    return Validacao(True, marcas=marcas)
