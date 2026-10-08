"""Máscara do modo cego (spec 7.5): o que identifica o alvo vira marcador antes de chegar ao Claude.

`montar_mascara` junta, das saídas dos nós, os termos que revelam o site (`[ALVO]`), a empresa (`[EMPRESA]`), o
CNPJ (`[CNPJ]`) e os sócios (`[PESSOA_n]`); `mascarar` aplica o dicionário a um texto.

A comparação é sobre o texto dobrado (sem acento, sem caixa, sem caracteres invisíveis), com o mapa de volta às
posições do original: o que fica de fora do termo achado continua como estava. Entre as palavras de um termo vale
qualquer sequência de espaços, pontos, hífens e barras ("S.A.", "S A" e "S/A" são o mesmo), e o CNPJ aceita esses
separadores entre qualquer par de caracteres. O termo só vale como palavra inteira: "Home" não troca "Homenagem".
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from html.parser import HTMLParser
from typing import Any

from radar.nos.alvo import dominio_registravel
from radar.texto import decodificar, normalizar

# trocar um termo curto mudaria palavras comuns do texto
_MINIMO_DE_CARACTERES = 4
# os nós que entregam a página inicial em `paginas[0].html`
_NOS_DE_PAGINAS = ("captura", "wayback_snapshot")
_PONTUACAO_DO_CNPJ = re.compile(r"[.\-/\s]")
_SEPARADOR = r"[\s.\-/]"
_PARTES_DO_TERMO = re.compile(r"[\s.\-/]+")
# o hífen só separa partes do título quando está solto ("Marca - Slogan"): em "pré-venda" ele é da palavra
_SEPARADORES_DO_TITULO = re.compile(r"\s*[|–—·:]\s*|\s+-\s+")
_CNPJ = re.compile(r"[0-9a-z]{12}[0-9]{2}")
# os marcadores que `montar_mascara` produz
MARCADOR = re.compile(r"\[(?:alvo|empresa|cnpj|pessoa_\d+)\]", re.IGNORECASE)


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
            # a spec do Open Graph usa `property`; muitos sites escrevem `name`
            nomes = {atributos.get("property", "").strip().lower(), atributos.get("name", "").strip().lower()}
            if "og:site_name" in nomes:
                self.site_name = atributos.get("content", "")

    def handle_data(self, data: str) -> None:
        if self._buffer is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._buffer is not None:
            self.titulo = "".join(self._buffer)
            self._buffer = None


def _identidade_da_pagina(html: str) -> tuple[list[str], str | None]:
    """As partes do título (partido nos separadores) e o `og:site_name`."""
    identidade = _Identidade()
    identidade.feed(html)
    identidade.close()
    partes = _SEPARADORES_DO_TITULO.split(identidade.titulo) if identidade.titulo else []
    return partes, identidade.site_name


def _palavras(texto: Any) -> set[str]:
    """As palavras do texto dobrado (sem acento nem caixa) com 4 caracteres ou mais."""
    if not isinstance(texto, str):
        return set()
    return {p for p in re.findall(r"[^\W_]+", normalizar(texto)) if len(p) >= _MINIMO_DE_CARACTERES}


def _parte_do_titulo_vale(parte: str, referencias: set[str]) -> bool:
    """Uma parte do título só vira `[EMPRESA]` se ligar ao site: sem número nem "%" (uma promessa no título não
    é o nome de ninguém) e com ao menos uma palavra das `referencias`."""
    if "%" in parte or any(c.isdigit() for c in parte):
        return False
    return not _palavras(parte).isdisjoint(referencias)


def _formas_idn(dominio: str) -> list[str]:
    """O domínio como veio e na outra grafia IDN (Unicode <-> punycode), quando ela existe."""
    try:
        outra = dominio.encode("ascii").decode("idna") if dominio.isascii() else dominio.encode("idna").decode("ascii")
    except UnicodeError:  # rótulo inválido: fica só o que veio
        return [dominio]
    return [dominio, outra]


def _palavras_do_rotulo(dominio: str) -> set[str]:
    """As palavras do rótulo do domínio registrável (`exemplo` em `app.exemplo.com.br`; o sufixo público não
    conta), nas grafias punycode e Unicode."""
    ascii_ = next((forma for forma in _formas_idn(dominio) if forma.isascii()), "")
    registravel = dominio_registravel(ascii_) if ascii_ else ""
    if not registravel:
        return set()
    palavras: set[str] = set()
    for forma in _formas_idn(registravel.split(".")[0]):
        palavras |= _palavras(forma)
    return palavras


def _no(saidas: dict[str, dict], nome: str) -> dict:
    saida = saidas.get(nome)
    return saida if isinstance(saida, dict) else {}


def _cnpj_formatado(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def montar_mascara(saidas: dict[str, dict], ler_artefato: Callable[[str], bytes]) -> dict[str, str]:
    """Termo -> marcador, a partir das `saidas` dos nós (nome do nó -> saída). `ler_artefato` (normalmente
    `Custodia.ler`) só é chamado para o HTML da página inicial, de onde saem o `<title>` e o `og:site_name`.

    - `alvo.dominio` e `ct.sans` (o domínio e os subdomínios), nas duas grafias se forem IDN -> `[ALVO]`;
    - `cnpj.razao_social`, `cnpj.nome_fantasia` e o `og:site_name` da página inicial -> `[EMPRESA]`;
    - cada parte do título da página inicial (partido em `| – — · :` e em " - ") que tenha uma palavra (4
      caracteres ou mais, dobrada) em comum com o rótulo do domínio, o `og:site_name`, a razão social ou o nome
      fantasia, e nenhum dígito nem "%" -> `[EMPRESA]`. Um título como "Marca | Rendimento de 1,5% ao dia" ou
      "Investimentos - Marca" não faz da promessa ou da palavra genérica o nome da empresa;
    - `cnpj.cnpj`, formatado e só com os caracteres (numérico ou alfanumérico) -> `[CNPJ]`;
    - `cnpj.socios[].nome` -> `[PESSOA_n]`, com n a posição do sócio no quadro.

    Termos com menos de 4 caracteres não entram. Um termo que já entrou (sem diferenciar maiúsculas) não entra
    de novo; o primeiro marcador vale.
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

    referencias: set[str] = set()  # as palavras que ligam uma parte do título ao site
    dominios = [_no(saidas, "alvo").get("dominio")]
    sans = _no(saidas, "ct").get("sans")
    for dominio in [*dominios, *(sans if isinstance(sans, list) else [])]:
        if isinstance(dominio, str):
            referencias |= _palavras_do_rotulo(dominio.strip())
            for forma in _formas_idn(dominio.strip()):
                adicionar(forma, "[ALVO]")

    cnpj = _no(saidas, "cnpj")
    for nome_da_empresa in (cnpj.get("razao_social"), cnpj.get("nome_fantasia")):
        referencias |= _palavras(nome_da_empresa)
        adicionar(nome_da_empresa, "[EMPRESA]")
    partes_do_titulo: list[str] = []
    for nome in _NOS_DE_PAGINAS:
        paginas = _no(saidas, nome).get("paginas")
        inicial = paginas[0] if isinstance(paginas, list) and paginas else None
        ref = inicial.get("html") if isinstance(inicial, dict) else None
        if isinstance(ref, str) and ref:  # a captura barrada por anti-bot não tem HTML
            partes, site_name = _identidade_da_pagina(decodificar(ler_artefato(ref), "text/html"))
            referencias |= _palavras(site_name)
            adicionar(site_name, "[EMPRESA]")
            partes_do_titulo.extend(partes)
    for parte in partes_do_titulo:
        if _parte_do_titulo_vale(parte, referencias):
            adicionar(parte, "[EMPRESA]")

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


# --- mascarar ---------------------------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _dobrar_caractere(c: str) -> str:
    """O caractere sem acento, em caixa baixa, com aspas retas; marca combinante e caractere invisível somem
    (`""`) e qualquer espaço vira `" "`."""
    return " " if c.isspace() else normalizar(c)


def _dobrar(texto: str) -> tuple[str, Sequence[int]]:
    """O texto dobrado e, para cada caractere dele, a posição do caractere de `texto` de onde veio."""
    if texto.isascii():  # um para um: só a caixa muda
        return texto.casefold(), range(len(texto))
    saida: list[str] = []
    posicoes: list[int] = []
    for i, c in enumerate(texto):
        dobrado = _dobrar_caractere(c)
        saida.append(dobrado)
        posicoes.extend([i] * len(dobrado))
    return "".join(saida), posicoes


def _padrao_do_termo(termo: str) -> tuple[int, str] | None:
    """O tamanho do termo (sem separadores) e a regex que o acha no texto dobrado."""
    dobrado, _ = _dobrar(termo)
    partes = [parte for parte in _PARTES_DO_TERMO.split(dobrado) if parte]
    if not partes:
        return None
    junto = "".join(partes)
    ponto = ""
    if _CNPJ.fullmatch(junto):  # o CNPJ aceita separador entre quaisquer caracteres, não só nos pontos de sempre
        corpo = f"{_SEPARADOR}*".join(re.escape(c) for c in junto)
    else:
        corpo = f"{_SEPARADOR}*".join(re.escape(parte) for parte in partes)
        if dobrado.rstrip().endswith("."):  # "S.A." leva o ponto final junto, se ele estiver no texto
            ponto = r"\.?"
    return len(junto), rf"(?<!\w){corpo}{ponto}(?!\w)"


@lru_cache(maxsize=16)
def _compilar(itens: tuple[tuple[str, str], ...]) -> tuple[re.Pattern[str] | None, tuple[str, ...]]:
    """A regex única da máscara (termos mais longos primeiro, um grupo por termo) e os marcadores, na ordem dos
    grupos."""
    padroes: dict[str, tuple[int, str]] = {}
    for termo, marcador in itens:
        padrao = _padrao_do_termo(termo)
        if padrao is not None and padrao[1] not in padroes:
            padroes[padrao[1]] = (padrao[0], marcador)
    if not padroes:
        return None, ()
    ordenados = sorted(padroes.items(), key=lambda item: item[1][0], reverse=True)
    regex = re.compile("|".join(f"({padrao})" for padrao, _ in ordenados))
    return regex, tuple(marcador for _, (_, marcador) in ordenados)


def mascarar(texto: str, mascara: dict[str, str]) -> str:
    """Troca cada termo da `mascara` pelo marcador, sem diferenciar maiúsculas, acentos nem o tipo de separador.

    Os termos mais longos vêm primeiro (`app.exemplo.com.br` antes de `exemplo.com.br`) e o texto é varrido uma
    vez só, então um marcador que acabou de entrar não é trocado de novo. Só a parte achada do `texto` é
    substituída; acentos e espaços do resto ficam como estavam.
    """
    regex, marcadores = _compilar(tuple(mascara.items()))
    if regex is None or not texto:
        return texto
    dobrado, posicoes = _dobrar(texto)
    partes: list[str] = []
    fim_anterior = 0
    for achado in regex.finditer(dobrado):
        inicio = max(posicoes[achado.start()], fim_anterior)
        fim = max(posicoes[achado.end() - 1] + 1, inicio)
        while fim < len(texto) and _dobrar_caractere(texto[fim]) == "":  # acento combinante colado ao fim do termo
            fim += 1
        partes.append(texto[fim_anterior:inicio])
        partes.append(marcadores[achado.lastindex - 1])
        fim_anterior = fim
    partes.append(texto[fim_anterior:])
    return "".join(partes)
