"""Nó `alvo`: domínio registrável, slug e URL inicial a partir do que o usuário digitou."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

import tldextract

from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos

# lista de sufixos embutida no pacote: nenhuma consulta de rede para descobrir o domínio registrável
_PSL = tldextract.TLDExtract(suffix_list_urls=())
_ESQUEMA = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://")
# o slug vira nome de pasta: só letras, dígitos, "_" e "-" (nada de "\" ou ".." vindo da entrada),
# com hífen apenas no meio de cada rótulo
_ROTULO = r"[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?"
_DOMINIO = re.compile(rf"(?:{_ROTULO}\.)+{_ROTULO}")


def _invalido(entrada: str, motivo: str) -> ErroNo:
    return ErroNo(f"alvo inválido ({motivo}): {entrada!r}", permanente=True)


def normalizar_alvo(entrada: str) -> tuple[str, str, str]:
    """Devolve `(dominio, slug, url_inicial)`.

    `dominio` é o registrável (`app.Exemplo.com.br.` → `exemplo.com.br`; IDN em punycode), `slug`
    troca os pontos por hífen e `url_inicial` é a URL dada, com `https://` se faltar o esquema e
    sem fragmento. Entrada que não é URL http(s) de um domínio registrável → `ErroNo` permanente.
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
    dominio = _PSL(host).top_domain_under_public_suffix.lower()
    if not _DOMINIO.fullmatch(dominio):
        raise _invalido(entrada, "sem domínio registrável")
    return dominio, dominio.replace(".", "-"), urlunsplit(partes._replace(fragment=""))


class AlvoNo(NoBase):
    """Repassa ao DAG o alvo já normalizado por `criar_contexto`."""

    nome = "alvo"
    saidas = ("dominio", "slug", "url_inicial")

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        return Feito({"dominio": ctx.alvo, "slug": ctx.slug, "url_inicial": ctx.url_inicial})
