"""Nó `alvo`: domínio registrável, slug e URL inicial a partir do que o usuário digitou."""

from __future__ import annotations

import re
from typing import NamedTuple
from urllib.parse import unquote_plus, urlsplit, urlunsplit

import tldextract

from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos

# lista de sufixos embutida no pacote: nenhuma consulta de rede para descobrir o domínio registrável. Com os sufixos
# privados da PSL (github.io, vercel.app, blogspot.com, br.com...): o site do esquema é `piramide.github.io`, não a
# plataforma inteira, que juntaria golpes diferentes no mesmo alvo (C1 da revisão final)
_PSL = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)
# Plataformas de conteúdo fora da PSL: quem está nelas é um perfil, e o domínio é da plataforma, não do esquema. Não
# servem de alvo nem de chave de correspondência (uma deliberação que cita instagram.com fala de outro perfil).
PLATAFORMAS = frozenset(
    {
        "instagram.com", "facebook.com", "fb.com", "youtube.com", "youtu.be", "tiktok.com", "x.com", "twitter.com",
        "t.me", "telegram.org", "wa.me", "whatsapp.com", "linktr.ee", "google.com", "linkedin.com", "kwai.com",
    }
)  # fmt: skip
_ESQUEMA = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://")
# o slug vira nome de pasta: só letras, dígitos, "_" e "-" (nada de "\" ou ".." vindo da entrada),
# com hífen apenas no meio de cada rótulo
_ROTULO = r"[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?"
_DOMINIO = re.compile(rf"(?:{_ROTULO}\.)+{_ROTULO}")


def dominio_registravel(host: str) -> str:
    """Domínio registrável de `host` (`cdn.exemplo.com.br` → `exemplo.com.br`, `cdn.piramide.github.io` →
    `piramide.github.io`), em minúsculas.

    Usa a lista de sufixos embutida, com os privados, sem rede. IP, `localhost`, sufixo desconhecido e o sufixo
    sozinho (`github.io`) não têm domínio registrável: devolve `""`.
    """
    return _PSL(host).top_domain_under_public_suffix.lower()


# parâmetros de indicação e de rastreamento: a captura não abre o link de afiliado de quem mandou o site (o operador
# saberia quem indicou o analista)
_PARAMETROS_DE_INDICACAO = frozenset(
    {"ref", "indicacao", "indicador", "invite", "convite", "afiliado", "aff", "sponsor", "patrocinador"}
)


class AlvoNormalizado(NamedTuple):
    dominio: str
    slug: str
    url_inicial: str
    parametros_removidos: list[str]


def _sem_parametros_de_indicacao(query: str) -> tuple[str, list[str]]:
    """A query sem os parâmetros de indicação e `utm_*` (sem diferenciar maiúsculas), no resto como veio, e os nomes
    tirados, na ordem."""
    mantidos: list[str] = []
    removidos: list[str] = []
    for parte in query.split("&") if query else []:
        nome = unquote_plus(parte.partition("=")[0])
        if nome.lower() in _PARAMETROS_DE_INDICACAO or nome.lower().startswith("utm_"):
            removidos.append(nome)
        else:
            mantidos.append(parte)
    return "&".join(mantidos), removidos


def e_plataforma(dominio: str) -> bool:
    """`dominio` (registrável) é de uma plataforma de conteúdo de `PLATAFORMAS`."""
    return dominio.strip().lower().rstrip(".") in PLATAFORMAS


def _invalido(entrada: str, motivo: str) -> ErroNo:
    return ErroNo(f"alvo inválido ({motivo}): {entrada!r}", permanente=True)


def normalizar_alvo(entrada: str) -> AlvoNormalizado:
    """Devolve `(dominio, slug, url_inicial, parametros_removidos)`.

    `dominio` é o registrável (`app.Exemplo.com.br.` → `exemplo.com.br`; IDN em punycode), `slug`
    troca os pontos por hífen e `url_inicial` é a URL dada, com `https://` se faltar o esquema,
    sem fragmento e sem os parâmetros de indicação e rastreamento (`ref`, `indicacao`, `convite`, `utm_*`...), cujos
    nomes vão em `parametros_removidos`. Entrada que não é URL http(s) de um domínio registrável → `ErroNo` permanente; perfil numa
    plataforma de conteúdo (`PLATAFORMAS`) também, com a mensagem que manda analisar o site próprio do esquema.
    """
    bruta = entrada.strip()
    if not bruta or any(c.isspace() for c in bruta):
        raise _invalido(entrada, "vazia ou com espaços")
    url = bruta if _ESQUEMA.match(bruta) else f"https://{bruta}"
    try:
        partes = urlsplit(url)
        host = partes.hostname
        _ = partes.port  # só para validar a porta
    except ValueError as e:
        raise _invalido(entrada, str(e)) from e
    if partes.scheme.lower() not in ("http", "https"):
        raise _invalido(entrada, f"esquema {partes.scheme!r} não é http nem https")
    if "@" in partes.netloc:
        raise _invalido(entrada, "URL com usuário e senha")
    host = (host or "").rstrip(".")
    if not host:
        raise _invalido(entrada, "sem host")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise _invalido(entrada, f"host inválido: {e}") from e
    dominio = dominio_registravel(host)
    if not _DOMINIO.fullmatch(dominio):
        raise _invalido(entrada, "sem domínio registrável")
    if e_plataforma(dominio):
        raise ErroNo(f"alvo é uma plataforma ({dominio}); analise o site próprio do esquema", permanente=True)
    query, removidos = _sem_parametros_de_indicacao(partes.query)
    url_inicial = urlunsplit(partes._replace(query=query, fragment=""))
    return AlvoNormalizado(dominio, dominio.replace(".", "-"), url_inicial, removidos)


class AlvoNo(NoBase):
    """Repassa ao DAG o alvo já normalizado por `criar_contexto`."""

    nome = "alvo"
    saidas = ("dominio", "slug", "url_inicial", "parametros_removidos")

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        return Feito(
            {
                "dominio": ctx.alvo,
                "slug": ctx.slug,
                "url_inicial": ctx.url_inicial,
                "parametros_removidos": list(ctx.parametros_removidos),
            }
        )
