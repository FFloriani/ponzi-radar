"""Extração por regex dos candidatos de uma página: promessas, CNPJs, contratos, regras, carteiras e contatos.

`extrair` roda sobre o texto visível de uma página (o texto da captura ou do Wayback) e devolve
`Candidato`s. `extrair_atributos` faz o mesmo com os valores de `href`, `src` e `action` do HTML da página,
onde ficam os links de contato que o texto não mostra (o texto de `<a href="https://wa.me/...">` é só
"Fale conosco"); só as regex de contato e de carteira rodam sobre eles. `texto_interno` lê as strings de
linguagem natural dos `<script>` embutidos no HTML (o dicionário de textos do aplicativo, o payload do Next.js), que o
nó guarda como artefato derivado e sobre o qual as mesmas regex do texto rodam. Os candidatos só apontam onde
olhar: o nó `claude` (T12) confirma ou corrige cada um, e a matriz (T14) só pontua o que foi confirmado.

O texto e o HTML são do site investigado: as regex rodam sobre conteúdo hostil. A regra que garante o
custo linear:
- todo quantificador tem limite superior (`{1,3}`, `{1,64}`...); não há `*`, `+` nem `{n,}`;
- onde uma repetição fica dentro de outra (rótulos de domínio `{1,4}` de `{1,63}` letras, grupos de milhar
  `{1,4}` de 3 dígitos), cada volta externa termina num literal (`.`) que a classe repetida por dentro não
  aceita: só há uma forma de dividir o texto, e o trabalho a partir de cada posição é limitado por uma
  constante, não pelo tamanho do texto;
- as alternativas começam por literais diferentes ou diferem logo, então duas não casam o mesmo trecho.
O custo é linear também para `"1" * 100_000`, `"%" * 100_000`, `"a." * 100_000` e `"1%" * 1_000_000`
(ver tests/test_extracao.py). O HTML passa pelo `HTMLParser` da stdlib, que é linear, e só até
`_HTML_MAXIMO` caracteres ou `_TAGS_MAXIMAS` tags. Os scripts são achados por `str.find` nos mesmos `_HTML_MAXIMO`
caracteres e lidos literal a literal, com teto de literais, de linhas e de caracteres por página. Cada script é
lido uma vez por conteúdo (`_CACHE_DE_SCRIPTS`), e o nó faz o cálculo das páginas numa thread: o loop do servidor
não para.

Convenções:
- as regex ignoram a caixa: as de letras rodam numa cópia do texto em minúsculas, com os mesmos índices
  (e por isso sem `re.IGNORECASE`, que desliga a busca rápida pelo primeiro caractere). Sem a regex
  `(?<!\\w)` na frente, que também a desliga, a borda de palavra da esquerda é conferida em Python;
- o `valor` das categorias sem normalização é o termo achado, em minúsculas e com os espaços colapsados
  (`"bônus de indicação"`). Endereços de carteira, convites e caminhos de rede social não mudam de
  caixa: `Ab12` e `ab12` não são o mesmo código;
- `posicao` é o índice do início do achado no texto e `trecho` o recorte de ±120 caracteres em volta. Nos
  candidatos dos atributos, `posicao` é o offset do valor do atributo no HTML;
- na mesma página, candidatos com a mesma (categoria, valor) viram um só, o da primeira ocorrência (o do
  texto vale mais que o do atributo);
- no máximo `TETO_POR_CATEGORIA` candidatos por (página, categoria): ficam os primeiros por posição.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import threading
from bisect import bisect_right
from collections import Counter, OrderedDict
from collections.abc import Iterable, Iterator
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any, NamedTuple

from radar.cnpj_util import cnpj_valido
from radar.modelos import ORIGEM_TEXTO_INTERNO, Candidato, Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos

TETO_POR_CATEGORIA = 100  # candidatos por (página, categoria); um site hostil não pode inflar o dossiê
_MARGEM = 120  # caracteres de contexto de cada lado do achado
# O `HTMLParser` é linear, mas custa ~1,3 µs por caractere nos piores textos (`"<" * N`) e até ~8 µs por tag com
# atributos. Páginas normais têm de 5 a 50 mil tags e podem passar de 4 MB só de base64 (que é barato): o HTML
# é lido até um dos dois limites.
_HTML_MAXIMO = 4_000_000  # caracteres
_TAGS_MAXIMAS = 300_000  # ocorrências de "<"
_VALOR_MAXIMO = 2000  # de cada atributo; um `href` maior que isso não é link de contato

# ---------------------------------------------------------------------------- conversão de período

_PERIODO_COM_NUMERO = re.compile(r"([0-9]{1,6})([md])")


def converter_para_mes(pct: float, periodo: str) -> float:
    """Retorno mensal equivalente (em %), por composição, arredondado a 4 casas.

    `periodo` é `dia` (30 dias), `semana` (30/7), `ano` (1/12), `Nm` (1/N: `24m` é 24 meses), `Nd` (30/N:
    `30d` é 30 dias, igual a um mês) ou `mes` (identidade). Levanta `ValueError` para período desconhecido
    ou `pct` que não é um retorno possível.
    """
    if periodo == "dia":
        expoente = 30.0
    elif periodo == "semana":
        expoente = 30 / 7
    elif periodo == "mes":
        expoente = 1.0
    elif periodo == "ano":
        expoente = 1 / 12
    elif (n := _PERIODO_COM_NUMERO.fullmatch(periodo)) and int(n.group(1)) > 0:
        expoente = 1 / int(n.group(1)) if n.group(2) == "m" else 30 / int(n.group(1))
    else:
        raise ValueError(f"período desconhecido: {periodo!r}")
    if not math.isfinite(pct) or pct < -100:
        raise ValueError(f"percentual impossível: {pct!r}")
    try:
        return round(((1 + pct / 100) ** expoente - 1) * 100, 4)
    except OverflowError:
        raise ValueError(f"percentual grande demais: {pct!r}") from None


# ---------------------------------------------------------------------------- achados


class _Achado(NamedTuple):
    inicio: int
    fim: int
    categoria: str
    valor: str
    extra: dict[str, Any]


_I_PONTUADO = chr(0x130)  # U+0130, "I" maiúsculo com ponto


def _minusculas(texto: str) -> str:
    """O texto em minúsculas com o mesmo tamanho, para que os índices valham nos dois.

    O único caractere que `str.lower()` alonga é o U+0130 (vira "i" + acento combinante); o
    teste `test_minusculas_nao_muda_o_tamanho` confere isso para todos os code points.
    """
    return texto.replace(_I_PONTUADO, "i").lower()


def _colado(texto: str, i: int, tambem: str = "") -> bool:
    """O caractere logo antes de `i` é letra, dígito, `_` (ou um de `tambem`)? Então o achado que
    começa em `i` é pedaço de uma palavra maior. Faz o papel de `(?<!\\w)`."""
    if i == 0:
        return False
    antes = texto[i - 1]
    return antes.isalnum() or antes == "_" or antes in tambem


# espaço dentro de uma frase: 1 a 3 e nunca uma quebra de linha (blocos vizinhos não formam frase)
_ESP = r"[^\S\n]{1,3}"


def _frases(*alternativas: str) -> re.Pattern[str]:
    """Regex de termos soltos, para o texto em minúsculas: cada espaço das alternativas vira `_ESP` e
    o termo não pode ser seguido de letra. Toda alternativa começa por um literal (é o que mantém a
    busca rápida) e, quando começam igual, vale a primeira. A borda da esquerda é de `_termos`."""
    corpo = "|".join(a.replace(" ", _ESP) for a in alternativas)
    return re.compile(rf"(?:{corpo})(?!\w)")


def _termos(categoria: str, rx: re.Pattern[str], baixo: str) -> Iterator[_Achado]:
    vistos: set[str] = set()
    for m in rx.finditer(baixo):
        if _colado(baixo, m.start()):
            continue
        valor = " ".join(m.group().split())
        if valor not in vistos:
            vistos.add(valor)
            yield _Achado(m.start(), m.end(), categoria, valor, {})


_GARANTIDO = _frases(
    r"garantid[oa]s?",
    r"garantia de (?:retorno|lucro|rendimento|rentabilidade|ganho)s?",
    r"sem riscos?",
    r"risco zero",
    r"zero risco",
)
_INVESTIMENTO = _frases(
    r"investimentos?",
    r"investidor(?:es|as?)?",
    r"investir",
    r"investindo",
    r"invista",
    r"aportes?",
    r"aportar",
)
_HISTORICO = _frases(
    r"hist[óo]rico de (?:rentabilidade|rendimento|ganho|lucro|retorno|pagamento|resultado|performance"
    r"|desempenho)s?",
    r"hist[óo]rico de opera(?:[çc][ãa]o|[çc][õo]es)",
    r"tabela de (?:rentabilidade|rendimento|retorno)s?",
    r"rentabilidade hist[óo]rica",
    r"rentabilidade m[eê]s a m[eê]s",
    r"rentabilidade acumulada",
    r"rentabilidade(?: mensal)? dos [úu]ltimos [0-9]{1,3} m[eê]s(?:es)?",
    r"m[eê]s a m[eê]s",
)
_INDICACAO = _frases(
    r"b[ôo]nus (?:de|por) indica(?:[çc][ãa]o|[çc][õo]es)",
    r"comiss(?:[ãa]o|[õo]es) (?:de|por) indica(?:[çc][ãa]o|[çc][õo]es)",
    r"programa de (?:afiliad[oa]s?|indica(?:[çc][ãa]o|[çc][õo]es)|parceiros)",
    r"link de (?:indica(?:[çc][ãa]o|[çc][õo]es)|afiliad[oa]|convite)",
    r"c[óo]digo de (?:indica(?:[çc][ãa]o|[çc][õo]es)|afiliad[oa]|convite)",
    r"indique e (?:ganhe|receba)",
    r"indique (?:amigos|um amigo)",
    r"indicar amigos",
    r"convide (?:amigos|e ganhe)",
    r"indiquem",
    r"indique",
    r"convidem",
    r"convide",
    r"rede de indicados",
    r"b[ôo]nus bin[áa]ri[oa]",
    r"bin[áa]ri[oa]",
    r"matriz for[çc]ada",
    r"matriz [0-9]{1,2}[^\S\n]{0,2}x[^\S\n]{0,2}[0-9]{1,2}",
    r"indica(?:[çc][ãa]o|[çc][õo]es)",
    r"afiliad[oa]s?",
    r"multin[ií]vel",
    r"n[ií]v(?:el|eis) de (?:indica(?:[çc][ãa]o|[çc][õo]es)|comiss[ãa]o|b[ôo]nus|rede)",
    r"n[ií]v(?:el|eis) [0-9]{1,2}",
    r"downline",
    r"upline",
)
_SAQUE = _frases(
    r"taxas? de (?:saque|retirada|resgate|libera[çc][ãa]o|desbloqueio)s?",
    r"libera[çc][ãa]o d[oe] saques?",
    r"valor m[ií]nimo (?:de|para) (?:saque|retirada)s?",
    r"m[ií]nimo (?:de|para) (?:saque|retirada)s?",
    r"prazo (?:de|para) (?:saque|retirada|resgate)s?",
    r"limite (?:de|para) saques?",
    r"saques? m[ií]nimos?",
    r"saques?",
    r"retiradas? (?:de|do|dos) (?:saldo|lucro|rendimento)s?",
)
_CARENCIA = _frases(
    r"car[êe]ncia(?: de [0-9]{1,3} (?:dias?|semanas?|m[eê]s|meses|anos?))?",
    r"multa (?:de [0-9]{1,3}(?:[.,][0-9]{1,2})?[^\S\n]{0,2}%"
    r"|por (?:saque|resgate|cancelamento|rescis[ãa]o|antecipa[çc][ãa]o)"
    r"|rescis[óo]ria)",
    r"saques? antecipad[oa]s?",
    r"resgates? antecipad[oa]s?",
    r"retiradas? antecipad[oa]s?",
    r"per[ií]odo de (?:bloqueio|car[êe]ncia)",
    r"prazo de (?:bloqueio|car[êe]ncia)",
    r"bloqueio d[oe] (?:capital|saldo|valor|aporte)s?",
    r"lock(?:-?up)?",
)
_TOKEN = _frases(
    r"tokens?",
    r"criptomoeda pr[óo]pria",
    r"moeda pr[óo]pria",
    r"airdrop",
    r"staking",
    r"whitepaper",
    r"smart contracts?",
    r"contratos? inteligentes?",
)
# "ido" em minúsculas é só o particípio de "ir": a sigla vale em maiúsculas e roda no texto original
_SIGLAS_DE_TOKEN = re.compile(r"(?<![A-Za-z0-9_])(?:ICO|IDO|NFTs?)(?![A-Za-z0-9_])")
_PIX = _frases(r"chave pix", r"pix copia e cola", r"pix")

# (código do contrato, regex): o `valor` é o código, não o termo achado
_CONTRATOS = (
    ("scp", _frases(r"sociedade em conta de participa[çc][ãa]o", r"scp")),
    (
        "mutuo",
        # "mútuo acordo" é outra coisa: só o contrato, o mutuário e o mutuante
        _frases(
            r"contratos? de m[úu]tuo",
            r"m[úu]tuo (?:financeiro|feneratício|conversível)",
            r"mutu[aá]ri[oa]s?",
            r"mutuante",
        ),
    ),
    (
        "locacao_cripto",
        _frases(
            *(
                rf"{aluguel} de (?:cripto(?:moedas?|ativos?)?|bitcoins?|moedas? digitais?|ativos? digitais?"
                r"|tokens?|m[áa]quinas? de minera[çc][ãa]o|poder computacional)"
                for aluguel in (r"aluguel", r"alugu[eé]is", r"loca[çc][ãa]o", r"loca[çc][õo]es")
            )
        ),
    ),
    (
        "cessao",
        _frases(
            r"cess[ãa]o de (?:direitos?|cr[ée]ditos?|receb[ií]veis|cotas?|quotas?)",
            r"contratos? de cess[ãa]o",
            r"cess[ãa]o onerosa",
        ),
    ),
    (
        "parceria",
        _frases(
            r"contratos? de parceria",
            r"parceria (?:comercial|agr[ií]cola|pecu[aá]ria|rural|financeira)",
        ),
    ),
)


def _contratos(baixo: str) -> Iterator[_Achado]:
    for codigo, rx in _CONTRATOS:
        for m in rx.finditer(baixo):
            if not _colado(baixo, m.start()):
                yield _Achado(m.start(), m.end(), "contrato", codigo, {})
                break  # o valor é o código: só a primeira ocorrência interessa


def _siglas_de_token(texto: str) -> Iterator[_Achado]:
    vistos: set[str] = set()
    for m in _SIGLAS_DE_TOKEN.finditer(texto):
        valor = m.group().lower()
        if valor not in vistos:
            vistos.add(valor)
            yield _Achado(m.start(), m.end(), "token", valor, {})


# --- percentual

_MILHAR = r"[1-9][0-9]{0,2}(?:\.[0-9]{3}){1,4}(?:,[0-9]{1,4})?"  # 1.000 / 10.000,00 / 1.000.000
_DECIMAL = r"[0-9]{1,4}(?:[.,][0-9]{1,4})?"  # 1,5 / 1.5 / 0.500
_NUMERO = rf"(?:{_MILHAR}|{_DECIMAL})"
_E_MILHAR = re.compile(_MILHAR)
# o número não pode ser o fim de outro maior ("12345%", "1.000.000%" lido a partir do meio)
_PCT = re.compile(rf"(?<![0-9])(?<![0-9][.,])({_NUMERO})[^\S\n]{{0,3}}%")

# "de 1% a 3% ao dia": a unidade do 1% é a do 3%
_FAIXA_RX = rf"[^\S\n]{{0,3}}(?:até|ate|a|à|e|ou|-|–|—)[^\S\n]{{0,3}}{_NUMERO}[^\S\n]{{0,3}}%"
# A unidade vem logo depois do número ("1,5% a.d.", "30%\nao dia", "1% de lucro diário"). Os grupos
# `dia`, `semana`, `mes` e `ano` dão o período; `n` ("em 24 meses" -> 24m), `nd` ("em 30 dias" -> 30d, o
# prazo fica como está escrito) e `nc` ("a cada 15 dias" -> 15d; 1, 7 e 30 viram dia, semana e mes).
_SUBSTANTIVO = r"(?:(?:lucro|rendimento|rentabilidade|retorno|ganho)s?|comiss(?:[ãa]o|[õo]es))"
_DIA = (
    r"a\s?[./]\s?d\b\.?|ad\b|ao\s{1,3}dia\b|por\s{1,3}dia\b|/\s{0,2}dia\b|di[aá]ri[oa]s?\b|diariamente\b"
    r"|a\s{1,3}cada\s{1,3}(?:dia|24\s{0,2}(?:horas?|h))\b|dia\b"
)
_SEMANA = (
    r"por\s{1,3}semana\b|[àa]\s{1,3}semana\b|/\s{0,2}semana\b|semana(?:l|is)\b|semanalmente\b"
    r"|a\s{1,3}cada\s{1,3}semana\b"
)
_MES = (
    r"a\s?[./]\s?m\b\.?|am\b|ao\s{1,3}m[eê]s\b|por\s{1,3}m[eê]s\b|/\s{0,2}m[eê]s\b|mensa(?:l|is)\b"
    r"|mensalmente\b|a\s{1,3}cada\s{1,3}m[eê]s\b|m[eê]s\b"
)
_ANO = (
    r"a\s?[./]\s?a\b\.?|aa\b|ao\s{1,3}ano\b|por\s{1,3}ano\b|/\s{0,2}ano\b|anua(?:l|is)\b|anualmente\b"
    r"|a\s{1,3}cada\s{1,3}ano\b"
)
_PRAZO = (
    r"(?:em|ap[óo]s|ao\s{1,3}(?:fim|final)\s{1,3}de)(?:\s{1,3}at[eé])?\s{1,3}"
    r"(?:(?P<n>[0-9]{1,3})\s{1,3}m[eê]s(?:es)?|(?P<nd>[0-9]{1,3})\s{1,3}dias?)\b"
)
_A_CADA = r"a\s{1,3}cada\s{1,3}(?P<nc>[0-9]{1,3})\s{1,3}dias?\b"
_DEPOIS_RX = (
    r"\s{0,3}(?:de\s{1,3}" + _SUBSTANTIVO + r"\s{1,3})?(?:"
    rf"(?P<dia>{_DIA})|(?P<semana>{_SEMANA})|(?P<mes>{_MES})|(?P<ano>{_ANO})|{_PRAZO}|{_A_CADA})"
)
# O número que tem a unidade (ou a faixa e a unidade) logo depois. A unidade fica num lookahead: não é
# consumida, e o número seguinte de uma faixa ("1% a 3% ao dia") é achado também.
_PCT_COM_UNIDADE = re.compile(
    rf"(?<![0-9])(?<![0-9][.,])({_NUMERO})[^\S\n]{{0,3}}%(?=(?P<faixa>{_FAIXA_RX})?(?P<unidade>{_DEPOIS_RX}))"
)

# A unidade antes do número ("rendimento diário de 1%"). Alternativas simples, todas começando por
# literal: é o que deixa a varredura do texto inteiro rápida. `_periodo_do_marcador` diz qual é.
_ANTES = re.compile(
    r"(?:di[aá]ri[oa]s?|diariamente|ao[^\S\n]{1,3}dia|por[^\S\n]{1,3}dia"
    r"|semana(?:l|is)|semanalmente|por[^\S\n]{1,3}semana"
    r"|mensa(?:l|is)|mensalmente|ao[^\S\n]{1,3}m[eê]s|por[^\S\n]{1,3}m[eê]s"
    r"|anua(?:l|is)|anualmente|ao[^\S\n]{1,3}ano|por[^\S\n]{1,3}ano)(?!\w)"
)
_ATE = re.compile(r"(?<!\w)(?:at[eé]|m[aá]xim[oa](?:[^\S\n]{1,3}de)?)[^\S\n]{0,3}$")
_CORTE = re.compile(r"[.,!?;\n%]")  # fim de oração: a unidade de lá não vale para este número
_JANELA_ANTES = 48
_PERIODO_DE_N_DIAS = {1: "dia", 7: "semana", 30: "mes"}  # "a cada N dias"


def _periodo_de(m: re.Match[str]) -> str | None:
    """`dia`, `semana`, `mes`, `ano`, `Nm` ou `Nd` do que `_PCT_COM_UNIDADE` achou."""
    for nome in ("dia", "semana", "mes", "ano"):
        if m.group(nome):
            return nome
    if n := int(m.group("n") or 0):
        return f"{n}m"
    if nd := int(m.group("nd") or 0):
        return f"{nd}d"
    if nc := int(m.group("nc") or 0):
        return _PERIODO_DE_N_DIAS.get(nc, f"{nc}d")
    return None


def _periodo_do_marcador(termo: str) -> str:
    if "semana" in termo:
        return "semana"
    if "mens" in termo or "mes" in termo or "mês" in termo:
        return "mes"
    if "anua" in termo or "ano" in termo:
        return "ano"
    return "dia"  # diário, diariamente, ao dia, por dia


def _para_decimal(numero: str) -> Decimal:
    """`1,5` e `1.5` são 1,5; `1.000` e `10.000,50` (um a três dígitos, grupos de três, sem zero à esquerda)
    são milhares."""
    if _E_MILHAR.fullmatch(numero):
        return Decimal(numero.replace(".", "").replace(",", "."))
    return Decimal(numero.replace(",", "."))


def _percentual(baixo: str, bruto: str, periodo: str, inicio: int, fim: int) -> _Achado | None:
    numero = _para_decimal(bruto)
    try:
        pct_mes = converter_para_mes(float(numero), periodo)
    except ValueError:
        return None  # "10.000.000.000.000% ao dia" estoura o float: sem conversão, o achado é descartado
    ate = bool(_ATE.search(baixo[max(0, inicio - 24) : inicio]))
    extra = {"pct_mes": pct_mes, "ate": ate}
    return _Achado(inicio, fim, "percentual", f"{format(numero.normalize(), 'f')}|{periodo}", extra)


def _percentuais(texto: str, baixo: str) -> Iterator[_Achado]:
    """Os números com `%` e a unidade, que vem depois (a do próprio número) ou antes (a do marcador mais
    próximo, na mesma oração). Cada passada percorre só o que tem unidade, não todos os `%` do texto."""
    if "%" not in texto:
        return
    vistos: set[tuple[str, str]] = set()
    # a unidade depois do número
    for m in _PCT_COM_UNIDADE.finditer(baixo):
        periodo = _periodo_de(m)
        if periodo is None or (m.group(1), periodo) in vistos:
            continue
        vistos.add((m.group(1), periodo))
        fim = m.end() if m.group("faixa") else m.end("unidade")  # o achado vai até o fim da unidade
        if achado := _percentual(baixo, m.group(1), periodo, m.start(1), fim):
            yield achado
    # a unidade antes: o número que vem logo depois de cada marcador, se ele for o mais próximo
    inicios, fins, periodos = [], [], []
    for marcador in _ANTES.finditer(baixo):
        if not _colado(baixo, marcador.start()):
            inicios.append(marcador.start())
            fins.append(marcador.end())
            periodos.append(_periodo_do_marcador(marcador.group()))
    for k, periodo in enumerate(periodos):
        numero = _PCT.search(baixo, fins[k], fins[k] + _JANELA_ANTES + 32)
        if numero is None:
            continue
        inicio = numero.start(1)
        proximo = inicios[k + 1] if k + 1 < len(inicios) else len(baixo)
        if inicio >= proximo or inicio - inicios[k] > _JANELA_ANTES or _CORTE.search(baixo, fins[k], inicio):
            continue
        propria = _PCT_COM_UNIDADE.match(baixo, inicio)
        if (propria and _periodo_de(propria)) or (numero.group(1), periodo) in vistos:
            continue  # a unidade de depois do número vale mais, e já foi vista
        vistos.add((numero.group(1), periodo))
        if achado := _percentual(baixo, numero.group(1), periodo, inicio, numero.end()):
            yield achado


# --- CNPJ

# Numérico (14 dígitos, com ou sem pontuação) que não é parte de um número maior; letras coladas antes
# ("CNPJ33.000.167/0001-01") não impedem.
_CNPJ_NUMERICO = re.compile(r"(?<![0-9.])[0-9]{2}\.?[0-9]{3}\.?[0-9]{3}/?[0-9]{4}-?[0-9]{2}(?![0-9])")
# Alfanumérico (12 letras ou dígitos e 2 dígitos): tem de ser uma palavra inteira, senão "CNPJ12ABC..." seria
# lido a partir do "C". Entrada em qualquer caixa; o valor sai em maiúsculas.
_CNPJ_ALFANUMERICO = re.compile(
    r"(?<![0-9A-Za-z.])[0-9A-Z]{2}\.?[0-9A-Z]{3}\.?[0-9A-Z]{3}/?[0-9A-Z]{4}-?[0-9]{2}(?![0-9A-Za-z])",
    re.IGNORECASE | re.ASCII,
)
_SEPARADORES_DE_CNPJ = re.compile(r"[./-]")
_TEM_LETRA = re.compile(r"[A-Za-z]")


def _cnpjs(texto: str) -> Iterator[_Achado]:
    vistos: set[str] = set()
    for rx in (_CNPJ_NUMERICO, _CNPJ_ALFANUMERICO):
        for m in rx.finditer(texto):
            bruto = m.group()
            if rx is _CNPJ_ALFANUMERICO and not _TEM_LETRA.search(bruto):
                continue  # só dígitos é do outro (e o outro aceita letra colada antes)
            cnpj = _SEPARADORES_DE_CNPJ.sub("", bruto).upper()
            if cnpj not in vistos and cnpj_valido(cnpj):
                vistos.add(cnpj)
                yield _Achado(m.start(), m.end(), "cnpj", cnpj, {})


# --- carteiras

_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58 = "1-9A-HJ-NP-Za-km-z"
# no texto original: o alfabeto base58 e o hex dos endereços dependem da caixa
_BECH32 = re.compile(r"(?<![A-Za-z0-9])(?:bc1[a-z0-9]{25,87}|BC1[A-Z0-9]{25,87})(?![A-Za-z0-9])")
_BTC_LEGADO = re.compile(rf"(?<![A-Za-z0-9])[13][{_B58}]{{25,34}}(?![A-Za-z0-9])")
_ETH = re.compile(r"(?<![A-Za-z0-9])0[xX][0-9a-fA-F]{40}(?![A-Za-z0-9])")
_TRON = re.compile(rf"(?<![A-Za-z0-9])T[{_B58}]{{33}}(?![A-Za-z0-9])")


def _base58check_valido(endereco: str) -> bool:
    """Endereço Bitcoin legado (`1...` ou `3...`): 25 bytes, os 4 últimos são o checksum."""
    n = 0
    for c in endereco:
        n = n * 58 + _BASE58.index(c)
    try:
        bruto = n.to_bytes(25, "big")
    except OverflowError:
        return False
    return (
        bruto[0] in (0x00, 0x05)
        and hashlib.sha256(hashlib.sha256(bruto[:21]).digest()).digest()[:4] == bruto[21:]
    )


def _carteiras(texto: str) -> Iterator[_Achado]:
    # `bc1...` (bech32), `0x` + 40 hex e `T` + 33 base58 valem pela forma. O endereço legado do Bitcoin
    # se confunde com qualquer palavra de 26 a 35 letras que comece por 1 ou 3: só vale com o checksum
    vistos: set[str] = set()
    for rx, rede in ((_BECH32, "btc"), (_ETH, "eth"), (_TRON, "tron")):
        for m in rx.finditer(texto):
            if m.group() not in vistos:
                vistos.add(m.group())
                yield _Achado(m.start(), m.end(), "carteira", m.group(), {"rede": rede})
    for m in _BTC_LEGADO.finditer(texto):
        if m.group() not in vistos and _base58check_valido(m.group()):
            vistos.add(m.group())
            yield _Achado(m.start(), m.end(), "carteira", m.group(), {"rede": "btc"})


# --- contatos

# no texto em minúsculas, como os termos: o que diferencia a caixa (convite, caminho) sai do original
_WHATSAPP = re.compile(
    r"(?:wa\.me/\+?(?P<wa>(?:message/)?[\w-]{1,40})"
    r"|(?:(?:api|web)\.whatsapp\.com|whatsapp:/)/send/?\?(?:[\w%.+=-]{1,100}&)?phone=\+?(?P<tel>[0-9]{8,15})"
    r"|chat\.whatsapp\.com/(?P<convite>[\w-]{1,40}))(?![\w-])"
)
_TELEGRAM = re.compile(
    r"(?:t|telegram)\.(?:me|dog)/(?P<caminho>(?:joinchat/|\+)?[\w-]{3,64}|s/[\w-]{3,64})(?![\w-])"
)
_REDE_SOCIAL = re.compile(
    r"(?P<host>instagram\.com|facebook\.com|fb\.com|fb\.me|youtube\.com|youtu\.be|tiktok\.com|twitter\.com"
    r"|x\.com|linkedin\.com|kwai\.com|discord\.gg|discord\.com)"
    r"/(?P<caminho>[\w@.+%/-]{1,100})"
)
_EMAIL = re.compile(
    r"(?<![a-z0-9_.%+-])[a-z0-9_.%+-]{1,64}@(?:[a-z0-9-]{1,63}\.){1,4}[a-z]{2,24}(?![a-z0-9_-])"
)
# "logo@2x.png" tem cara de e-mail e é nome de arquivo
_EXTENSOES_DE_ARQUIVO = frozenset({"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "ico", "css", "js"})
# Primeiro trecho do caminho que não é perfil: pixel de rastreio, botão de compartilhar, vídeo e incorporação.
# São os links de rede social que mais aparecem em `src` e `href` de qualquer site.
_NAO_E_PERFIL = frozenset(
    {"tr", "sharer", "sharer.php", "share", "share.php", "intent", "plugins", "dialog", "embed", "watch"}
)


def _contatos(texto: str, baixo: str) -> Iterator[_Achado]:
    vistos: set[str] = set()
    # O host não pode estar colado numa palavra ("max.com", "meu-x.com"); o subdomínio vale ("www.", "m.")
    for m in _WHATSAPP.finditer(baixo):
        if _colado(baixo, m.start(), "-"):
            continue
        if m.group("wa"):
            valor = f"wa.me/{texto[m.start('wa') : m.end('wa')]}"
        elif m.group("tel"):
            valor = f"wa.me/{m.group('tel')}"  # as duas formas do link do mesmo número são um contato só
        else:
            valor = f"chat.whatsapp.com/{texto[m.start('convite') : m.end('convite')]}"
        if valor not in vistos:
            vistos.add(valor)
            yield _Achado(m.start(), m.end(), "whatsapp", valor, {})
    for m in _TELEGRAM.finditer(baixo):
        if _colado(baixo, m.start(), "-."):
            continue
        # o `@usuario` não diferencia a caixa; convite (`+código`, `joinchat/código`) diferencia
        caminho = m.group("caminho")
        if caminho.startswith(("+", "joinchat/")):
            caminho = texto[m.start("caminho") : m.end("caminho")]
        valor = f"t.me/{caminho}"
        if valor not in vistos:
            vistos.add(valor)
            yield _Achado(m.start(), m.end(), "telegram", valor, {})
    for m in _REDE_SOCIAL.finditer(baixo):
        caminho = texto[m.start("caminho") : m.end("caminho")].rstrip(".,;:-/")
        if caminho.split("/", 1)[0].lower() in _NAO_E_PERFIL:
            continue
        if caminho and not _colado(baixo, m.start(), "-"):
            valor = f"{m.group('host')}/{caminho}"
            if valor not in vistos:
                vistos.add(valor)
                yield _Achado(m.start(), m.end(), "rede_social", valor, {})
    for m in _EMAIL.finditer(baixo):
        bruto = m.group()
        if bruto in vistos:
            continue
        vistos.add(bruto)
        email = bruto.lstrip("._%+-")
        if email.startswith("@") or email.rpartition(".")[2] in _EXTENSOES_DE_ARQUIVO:
            continue
        yield _Achado(m.start(), m.end(), "email", email, {})


# ---------------------------------------------------------------------------- extrair

# a ordem das categorias da tabela da spec: desempata candidatos na mesma posição
_CATEGORIAS = (
    "percentual", "garantido", "investimento", "historico_rentabilidade", "indicacao", "saque",
    "carencia", "contrato", "token", "cnpj", "carteira", "pix", "whatsapp", "telegram", "rede_social",
    "email",
)  # fmt: skip
_ORDEM = {categoria: i for i, categoria in enumerate(_CATEGORIAS)}


def _achados(texto: str) -> Iterable[_Achado]:
    baixo = _minusculas(texto)
    yield from _percentuais(texto, baixo)
    yield from _termos("garantido", _GARANTIDO, baixo)
    yield from _termos("investimento", _INVESTIMENTO, baixo)
    yield from _termos("historico_rentabilidade", _HISTORICO, baixo)
    yield from _termos("indicacao", _INDICACAO, baixo)
    yield from _termos("saque", _SAQUE, baixo)
    yield from _termos("carencia", _CARENCIA, baixo)
    yield from _contratos(baixo)
    yield from _termos("token", _TOKEN, baixo)
    yield from _siglas_de_token(texto)
    yield from _cnpjs(texto)
    yield from _carteiras(texto)
    yield from _termos("pix", _PIX, baixo)
    yield from _contatos(texto, baixo)


def _montar(
    achados: Iterable[_Achado], base: str, artefato: str, origem: str | None = None
) -> tuple[list[Candidato], set[str]]:
    """Os `Candidato`s de `achados` (índices em `base`, o texto ou o HTML guardado em `artefato`).

    Fica a primeira ocorrência de cada (categoria, valor), em ordem de posição, e no máximo
    `TETO_POR_CATEGORIA` por categoria. Devolve também as categorias que passaram do teto. Com `origem`, o
    `extra` de cada candidato a leva em `extra["origem"]`.
    """
    primeiros: dict[tuple[str, str], _Achado] = {}
    for achado in achados:
        chave = (achado.categoria, achado.valor)
        if chave not in primeiros or achado.inicio < primeiros[chave].inicio:
            primeiros[chave] = achado
    ordenados = sorted(primeiros.values(), key=lambda a: (a.inicio, _ORDEM[a.categoria], a.valor))
    candidatos: list[Candidato] = []
    por_categoria: Counter[str] = Counter()
    truncadas: set[str] = set()
    for a in ordenados:
        if por_categoria[a.categoria] >= TETO_POR_CATEGORIA:
            truncadas.add(a.categoria)
            continue
        por_categoria[a.categoria] += 1
        candidatos.append(
            Candidato(
                categoria=a.categoria,
                valor=a.valor,
                trecho=base[max(0, a.inicio - _MARGEM) : a.fim + _MARGEM],
                artefato=artefato,
                posicao=a.inicio,
                extra=a.extra if origem is None else {**a.extra, "origem": origem},
            )
        )
    return candidatos, truncadas


def _extrair_texto(texto: str, artefato: str) -> tuple[list[Candidato], set[str]]:
    return _montar(_achados(texto), texto, artefato)


def extrair(texto: str, artefato: str) -> list[Candidato]:
    """Candidatos do `texto` da página guardada em `artefato`, na ordem em que aparecem.

    Na mesma (categoria, valor) fica só a primeira ocorrência e, por categoria, os primeiros
    `TETO_POR_CATEGORIA`.
    """
    return _extrair_texto(texto, artefato)[0]


# ---------------------------------------------------------------------------- atributos do HTML

_ATRIBUTOS_DE_LINK = frozenset({"href", "src", "action"})
_ATRIBUTOS_POR_TAG = 20  # valores novos lidos de uma mesma tag


class _Atributos(HTMLParser):
    """Os valores de `href`, `src` e `action` de todas as tags, com o offset de cada um no HTML.

    O `HTMLParser` não executa nem baixa nada e não entra em `<script>` e `<style>`. Valores repetidos
    ficam com o primeiro offset; `data:` (imagem em base64) e valores vazios ficam de fora. De cada tag
    vêm no máximo `_ATRIBUTOS_POR_TAG` valores novos, e o offset de cada um é achado na tag a partir do fim
    do anterior (a busca de cada valor desde o começo da tag era quadrática numa tag com milhares de `href`).
    """

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self._html = html
        self._inicios_de_linha: list[int] | None = None
        self.valores: dict[str, int] = {}  # valor -> offset, na ordem do documento

    def _offset_da_tag(self) -> int:
        """O `getpos()` é (linha, coluna); a tabela das linhas só se monta se algum valor aparecer."""
        if self._inicios_de_linha is None:
            self._inicios_de_linha = [0]
            i = self._html.find("\n")
            while i != -1:
                self._inicios_de_linha.append(i + 1)
                i = self._html.find("\n", i + 1)
        linha, coluna = self.getpos()
        return self._inicios_de_linha[linha - 1] + coluna

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        novos = 0
        bruto: str | None = None  # o texto da tag, só se algum valor for novo
        base = 0  # offset da tag no HTML
        cursor = 0  # onde, na tag, acabou o valor anterior: a busca do próximo parte daí
        for nome, valor in attrs:
            if nome not in _ATRIBUTOS_DE_LINK or not valor:
                continue
            valor = valor.strip()[:_VALOR_MAXIMO]
            if not valor or valor in self.valores or valor[:5].lower() == "data:":
                continue
            if novos == _ATRIBUTOS_POR_TAG:
                break  # uma tag com dezenas de links distintos não é de contato (e cada busca custa a tag)
            if bruto is None:
                bruto, base = self.get_starttag_text() or "", self._offset_da_tag()
            novos += 1
            # o valor lido já tem as entidades resolvidas (`&amp;`): se não aparece igual na tag, o
            # offset é o da tag
            achou = bruto.find(valor, cursor)
            if achou >= 0:
                cursor = achou + len(valor)
            self.valores[valor] = base + max(achou, 0)


def _recortar_html(html: str) -> str:
    """O começo do HTML até `_HTML_MAXIMO` caracteres ou até o `_TAGS_MAXIMAS`-ésimo "<"."""
    html = html[:_HTML_MAXIMO]
    i = -1
    for _ in range(_TAGS_MAXIMAS):
        i = html.find("<", i + 1)
        if i == -1:
            return html
    return html[:i]


def _achados_dos_atributos(html: str) -> Iterator[_Achado]:
    html = _recortar_html(html)
    parser = _Atributos(html)
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # HTML do site investigado: o que o parser achou antes de engasgar ainda vale
        pass
    valores = list(parser.valores.items())
    if not valores:
        return
    # os valores viram um texto só (um por linha) para rodar cada regex uma vez; o início de cada valor
    # nele leva de volta ao offset no HTML
    junto = "\n".join(valor for valor, _ in valores)
    inicios, desde = [], 0
    for valor, _ in valores:
        inicios.append(desde)
        desde += len(valor) + 1
    for a in (*_contatos(junto, _minusculas(junto)), *_carteiras(junto)):
        valor, offset = valores[bisect_right(inicios, a.inicio) - 1]
        yield _Achado(offset, offset + min(len(valor), 2 * _MARGEM), a.categoria, a.valor, a.extra)


def _extrair_atributos(html: str, artefato: str) -> tuple[list[Candidato], set[str]]:
    return _montar(_achados_dos_atributos(html), html, artefato)


def extrair_atributos(html: str, artefato: str) -> list[Candidato]:
    """Candidatos de contato e de carteira nos `href`, `src` e `action` do `html` guardado em `artefato`.

    `posicao` é o offset do valor do atributo no HTML (o da tag, se o valor lido não aparece igual a como
    está escrito) e `trecho` o HTML em volta dele. Só o começo do HTML é lido (ver `_recortar_html`).
    """
    return _extrair_atributos(html, artefato)[0]


# ---------------------------------------------------------------------------- textos internos (scripts embutidos)

MAX_LINHAS_DO_TEXTO_INTERNO = 5_000  # por página
MAX_CARACTERES_DO_TEXTO_INTERNO = 300_000  # por página, com as quebras de linha
# `ORIGEM_TEXTO_INTERNO` (de `radar.modelos`) é o `tipo` do artefato, o `extra.origem` dos candidatos e a marca do
# `truncado`
_TEXTO_MINIMO = 12  # caracteres de um texto de linguagem natural, depois de colapsar os espaços
_TEXTO_MAXIMO = 300
_CHAVE_MAXIMA = 200  # chave maior que isto não entra na linha: fica só o texto
# Literal maior que isto não vira um texto de até 300 caracteres (nem com um escape `\uXXXX` por letra): não é
# decodificado para virar linha, só para ser lido por dentro, se tiver aspas.
_BRUTO_MAXIMO = 4_000
# o código do script e até três strings, uma dentro da outra: o JSON do RSC do Next.js vem dentro de uma string JS
_CAMADAS = 4
# Literais lidos por página, em todas as camadas. O HTML do aceite (168 mil caracteres, 117 mil de payload do Next.js)
# tem ~2.900; milhões de strings vazias (`""""...`) custariam segundos só no laço.
_LITERAIS_MAXIMOS = 500_000
_BLOCO = 16_384  # caracteres de um literal consumidos por chamada da regex do corpo

_FIM_DO_NOME_DA_TAG = frozenset(" \t\n\r\f/>")
_SRC = re.compile(r"(?<![^\s\"'/])src\s{0,20}=")  # no texto da tag em minúsculas; `data-src` não conta
_ABRE_NO_CODIGO = re.compile("[\"'`]")
_ABRE_NA_STRING = re.compile('"')  # dentro de uma string só há JSON: o apóstrofo é texto
# o corpo de um literal até a aspa que o fecha, um caractere (ou um escape) por vez; a de aspas não passa da quebra de
# linha (no JavaScript e no JSON, a string que chega nela não fechou)
_CORPO_DE_ASPAS = re.compile(rf'(?:[^"\\\n]|\\(?:\r\n|[\s\S])){{0,{_BLOCO}}}')
_CORPO_DE_APOSTROFO = re.compile(rf"(?:[^'\\\n]|\\(?:\r\n|[\s\S])){{0,{_BLOCO}}}")
_CORPO_DE_CRASE = re.compile(rf"(?:[^`\\]|\\(?:\r\n|[\s\S])){{0,{_BLOCO}}}")
_CORPO = {'"': _CORPO_DE_ASPAS, "'": _CORPO_DE_APOSTROFO, "`": _CORPO_DE_CRASE}
_ESPACOS_JS = re.compile(r"[ \t\r\n]{0,64}")
_ESCAPE = re.compile(r"\\(?:u\{[0-9A-Fa-f]{1,6}\}|u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2}|\r\n|[\s\S])")
_ESCAPES_SIMPLES = {
    "n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0",
    "\n": "", "\r": "", "\r\n": "", "\u2028": "", "\u2029": "",  # continuação de linha
}  # fmt: skip
_SUBSTITUTO = re.compile("[\ud800-\udfff]")

# --- o que é texto de linguagem natural
_CONTROLE = re.compile("[\x00-\x1f\x7f-\x9f]")
_TAG_HTML = re.compile(r"<[A-Za-z/!?]")
_CODIGO = ("=>", "&&", "||", "${", "!=", "==", "();", "){", "};", "function(", "function (", "\\", '":', '{"', '["')
_BORDA_DA_PALAVRA = ".,;:!?…()[]{}\"'«»“”‘’*+–—-/"
_PALAVRA = re.compile(r"[^\W\d_]{1,64}(?:['’-][^\W\d_]{1,64}){0,4}")
# classe utilitária de CSS (`items-center`, `md:flex`, `dark:bg-gray-900`): listas delas não são texto
_CLASSE_CSS = re.compile(
    r"[a-z][a-z0-9]{0,30}(?:-[a-z0-9.%#/\[\]]{1,40}){1,6}|[a-z0-9-]{1,30}:[a-z0-9\[\]-]{1,40}"
)
_HASH_OU_BASE64 = re.compile(r"[A-Za-z0-9+/=_-]{24,300}")


class TextoInterno(NamedTuple):
    """`texto`: uma string por linha, `<chave> = <texto>` quando a string é o valor de uma chave de objeto e só
    `<texto>` nos outros casos (vazio se não há nenhuma); `truncado`: o texto foi cortado num dos tetos."""

    texto: str
    truncado: bool


def _scripts_embutidos(html: str) -> Iterator[str]:
    """O conteúdo dos `<script>` sem `src`, na ordem do documento, nos primeiros `_HTML_MAXIMO` caracteres do HTML.

    Como no navegador, o script termina no primeiro `</script` seguido de espaço, `/` ou `>`, mesmo que ele esteja
    dentro de uma string do JavaScript: o que vem depois é HTML e não entra. A busca é por `str.find`, linear, e não
    passa pelo `HTMLParser`.
    """
    html = html[:_HTML_MAXIMO]
    baixo = _minusculas(html)
    i = baixo.find("<script")
    while i != -1:
        depois = i + len("<script")
        if depois < len(baixo) and baixo[depois] not in _FIM_DO_NOME_DA_TAG:
            i = baixo.find("<script", depois)  # `<scripts>`, `<script-x>`
            continue
        fim_da_tag = baixo.find(">", depois)
        if fim_da_tag == -1:
            return
        fim = _fim_do_script(baixo, fim_da_tag + 1)
        if not _SRC.search(baixo[depois:fim_da_tag]):
            yield html[fim_da_tag + 1 : fim]
        i = baixo.find("<script", fim)


def _fim_do_script(baixo: str, inicio: int) -> int:
    j = baixo.find("</script", inicio)
    while j != -1:
        k = j + len("</script")
        if k >= len(baixo) or baixo[k] in _FIM_DO_NOME_DA_TAG:
            return j
        j = baixo.find("</script", k)
    return len(baixo)


def _fim_do_literal(codigo: str, inicio: int, aspa: str) -> tuple[int, int]:
    """`(fim, retomada)` do literal cujo corpo começa em `inicio`: `fim` é a aspa que fecha (-1 se ele não fecha) e
    `retomada`, onde a busca pelo próximo continua. A string de aspas que não fecha na linha descarta o resto da
    linha; a de crase, o resto do código. Retomar logo depois da aspa que abriu seria quadrático (`"\\"\\"\\"...`)."""
    corpo = _CORPO[aspa]
    i = inicio
    while True:
        i = corpo.match(codigo, i).end()
        if i >= len(codigo) or (codigo[i] == "\\" and i + 1 == len(codigo)):  # a barra final não escapa nada
            return -1, len(codigo)
        if codigo[i] == aspa:
            return i, i + 1
        if codigo[i] == "\n":
            return -1, i + 1
        # o bloco de `_BLOCO` acabou no meio do literal (antes de um caractere ou de um escape): continua dali


def _um_escape(m: re.Match[str]) -> str:
    corpo = m.group()[1:]
    if len(corpo) > 1 and corpo[0] in "ux":
        try:
            return chr(int(corpo[1:].strip("{}"), 16))
        except ValueError:  # acima de U+10FFFF
            return "\ufffd"
    return _ESCAPES_SIMPLES.get(corpo, corpo)  # `\"`, `\\`, `\/`, `\'` e o escape desconhecido valem o caractere


def _desescapar(bruto: str) -> str:
    """O texto que o literal escreve. Os escapes do JSON vão pelo `json` (em C); se ele recusa (escape só do JS,
    `\\x41`, `\\u{...}`, ou quebrado), vai a regex, que nunca falha: o escape inválido vale o caractere depois da
    barra. O substituto solto (`\\ud800`) vira U+FFFD: o texto tem de gravar em UTF-8."""
    texto = bruto
    if "\\" in bruto:
        try:
            texto = json.loads(f'"{bruto}"', strict=False)
        except ValueError:
            texto = _ESCAPE.sub(_um_escape, bruto)
    if _SUBSTITUTO.search(texto):
        texto = texto.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return texto


def _e_texto_natural(texto: str) -> bool:
    """`texto` (com os espaços já colapsados) é linguagem natural: de 12 a 300 caracteres, ao menos 2 palavras de
    letras e metade dos pedaços palavras, sem cara de código, HTML, lista de classes CSS, hash ou base64. URL dentro
    de uma frase vale; a URL sozinha não tem duas palavras."""
    if not _TEXTO_MINIMO <= len(texto) <= _TEXTO_MAXIMO:
        return False
    if _CONTROLE.search(texto) or _TAG_HTML.search(texto) or any(marca in texto for marca in _CODIGO):
        return False
    pedacos = texto.split(" ")
    palavras = classes = 0
    for pedaco in pedacos:
        if len(pedaco) >= 24 and _HASH_OU_BASE64.fullmatch(pedaco) and not (pedaco.isalpha() and pedaco[1:].islower()):
            return False
        nucleo = pedaco.strip(_BORDA_DA_PALAVRA)
        if _CLASSE_CSS.fullmatch(nucleo):
            classes += 1
        elif _PALAVRA.fullmatch(nucleo):
            palavras += 1
    return palavras >= 2 and 2 * palavras >= len(pedacos) and 2 * classes < len(pedacos)


def _chave_da_linha(chave: str | None) -> str | None:
    """A chave como vai na linha (espaços colapsados), ou `None` se ela é vazia, longa demais ou tem controle."""
    if chave is None:
        return None
    chave = " ".join(chave.split())
    return None if not chave or len(chave) > _CHAVE_MAXIMA or _CONTROLE.search(chave) else chave


class _Evento(NamedTuple):
    """Um texto do script, já de uma linha só e de linguagem natural, com a chave já como vai na linha: `literal` é
    quantos literais o script tinha lido quando o texto saiu."""

    literal: int
    chave: str | None
    texto: str


class _LeituraDoScript(NamedTuple):
    """O que um script dá ao texto interno, sem depender da página: os textos distintos e naturais, na ordem, e quantos
    literais ele tem (até `_LITERAIS_MAXIMOS` + 1, onde a leitura para de qualquer jeito). `cortado`: o script tem
    mais textos distintos do que cabem numa página, e a leitura parou no primeiro que sobra."""

    eventos: tuple[_Evento, ...]
    literais: int
    cortado: bool


class _LeitorDeScript:
    """Lê os literais de um script sozinho e guarda os textos dele (`_LeituraDoScript`), que a página junta depois com
    os tetos dela (`_LeitorDeScripts.juntar`). Para no primeiro literal acima de `_LITERAIS_MAXIMOS` e no primeiro texto
    distinto além de `MAX_LINHAS_DO_TEXTO_INTERNO` (`cortado`): a página nunca passaria deles, e ler o resto seria
    trabalho jogado fora."""

    def __init__(self) -> None:
        self.truncado = False  # para a leitura
        self.cortado = False
        self.eventos: list[_Evento] = []
        self._vistos: set[str] = set()
        self._literais = 0

    def ler(self, codigo: str, abre: re.Pattern[str], camada: int) -> None:
        """Lê os literais de `codigo`. Um literal seguido de `:` é chave; o literal logo depois do `:` é o valor
        dela. A chave cujo valor não é uma string vale sozinha, se for texto."""
        pos = 0
        chave: str | None = None
        valor_em = -1  # onde o valor da `chave` tem de começar
        while not self.truncado:
            m = abre.search(codigo, pos)
            if m is None:
                break
            self._literais += 1
            if self._literais > _LITERAIS_MAXIMOS:
                self.truncado = True
                return
            fim, pos = _fim_do_literal(codigo, m.end(), m.group())
            dona = chave if m.start() == valor_em else None
            if chave is not None and dona is None:
                self._texto(None, chave)
            chave = None
            if fim < 0:
                continue
            bruto = codigo[m.end() : fim]
            if dona is None and len(bruto) <= _BRUTO_MAXIMO:
                dois_pontos = _ESPACOS_JS.match(codigo, pos).end()
                if codigo.startswith(":", dois_pontos):
                    chave = _desescapar(bruto)
                    valor_em = _ESPACOS_JS.match(codigo, dois_pontos + 1).end()
                    continue
            self._literal(bruto, dona, camada)
        if chave is not None:
            self._texto(None, chave)

    def _literal(self, bruto: str, chave: str | None, camada: int) -> None:
        texto = None
        if _TEXTO_MINIMO <= len(bruto) <= _BRUTO_MAXIMO:  # desescapar nunca alonga o texto
            texto = _desescapar(bruto)
            self._texto(chave, texto)
        # o JSON dentro da string: as aspas dele vêm escapadas (`\"`, ou `"` cru numa string de apóstrofo ou crase)
        if camada + 1 < _CAMADAS and ('"' in bruto or "\\x22" in bruto or "\\u0022" in bruto):
            self.ler(_desescapar(bruto) if texto is None else texto, _ABRE_NA_STRING, camada + 1)

    def _texto(self, chave: str | None, texto: str) -> None:
        texto = " ".join(texto.split())  # uma linha só: quebras (inclusive U+2028) e espaços repetidos viram um espaço
        if self.truncado or texto in self._vistos or not _e_texto_natural(texto):
            return
        if len(self._vistos) >= MAX_LINHAS_DO_TEXTO_INTERNO:
            self.cortado = self.truncado = True
            return
        self._vistos.add(texto)
        self.eventos.append(_Evento(self._literais, _chave_da_linha(chave), texto))


class _LeitorDeScripts:
    """Junta as linhas do texto interno de uma página, com os tetos de linhas, de caracteres e de literais.

    `sem_chaves` tem as mesmas linhas com a chave e o ` = ` trocados por espaços (mesmo tamanho): as regex de
    candidatos rodam nele, e a chave (`saque.backend.erro...`, um identificador do código) não vira achado.
    """

    def __init__(self) -> None:
        self.linhas: list[str] = []
        self.sem_chaves: list[str] = []
        self.truncado = False
        self._vistos: set[str] = set()
        self._caracteres = 0
        self._literais = 0

    def juntar(self, leitura: _LeituraDoScript) -> None:
        """Os textos de um script lido sozinho, como se a página o lesse agora, literal a literal: com a contagem de
        literais dela, o teto de literais corta onde cortaria (no primeiro literal acima de `_LITERAIS_MAXIMOS`), e o
        texto que a página já tem não entra de novo.

        A leitura `cortada` dá o mesmo que a leitura da página: se todos os textos guardados entraram sem estourar um
        teto, a página tem exatamente esses `MAX_LINHAS_DO_TEXTO_INTERNO` textos (ela não cabe mais), e o primeiro texto
        que o script ainda tinha é novo para ela, então a página cortaria nele."""
        antes = self._literais
        for evento in leitura.eventos:
            if antes + evento.literal > _LITERAIS_MAXIMOS:
                self.truncado = True
                return
            self._acrescentar(evento.chave, evento.texto)
            if self.truncado:
                return
        self._literais = antes + leitura.literais
        if leitura.cortado or self._literais > _LITERAIS_MAXIMOS:
            self.truncado = True

    def _acrescentar(self, chave: str | None, texto: str) -> None:
        """A linha do texto (já de uma linha só e natural, com a chave já normalizada), se a página ainda não o tem e
        ele cabe nos tetos de linhas e de caracteres; senão a página fica `truncado`."""
        if texto in self._vistos:
            return
        linha = f"{chave} = {texto}" if chave else texto
        tamanho = len(linha) + (1 if self.linhas else 0)  # com a quebra que a separa da anterior
        cheio = self._caracteres + tamanho > MAX_CARACTERES_DO_TEXTO_INTERNO
        if cheio or len(self.linhas) >= MAX_LINHAS_DO_TEXTO_INTERNO:
            self.truncado = True
            return
        self._vistos.add(texto)
        self._caracteres += tamanho
        self.linhas.append(linha)
        self.sem_chaves.append(" " * (len(linha) - len(texto)) + texto)


def _ler_um_script(script: str) -> _LeituraDoScript:
    """Os textos de um script sozinho (`_LeitorDeScript`)."""
    leitor = _LeitorDeScript()
    leitor.ler(script, _ABRE_NO_CODIGO, 0)
    return _LeituraDoScript(tuple(leitor.eventos), leitor._literais, leitor.cortado)


class _CacheDeScripts:
    """As leituras dos scripts pelo sha256 do conteúdo: o mesmo `<script>` de layout em várias páginas (o dicionário de
    textos do aplicativo, o runtime do Next.js) é lido uma vez. Guarda as `maximo` últimas, cada uma com até
    `MAX_LINHAS_DO_TEXTO_INTERNO` textos; a extração roda em threads (`asyncio.to_thread`), daí a trava."""

    def __init__(self, maximo: int = 32) -> None:
        self._maximo = maximo
        self._leituras: OrderedDict[bytes, _LeituraDoScript] = OrderedDict()
        self._trava = threading.Lock()

    def leitura(self, script: str) -> _LeituraDoScript:
        # os tetos entram na chave: a leitura guardada com outros tetos (um teste que os troca) não vale
        tetos = f"{_LITERAIS_MAXIMOS}:{MAX_LINHAS_DO_TEXTO_INTERNO}:".encode()
        chave = hashlib.sha256(tetos + script.encode("utf-8", "surrogatepass")).digest()
        with self._trava:
            if chave in self._leituras:
                self._leituras.move_to_end(chave)
                return self._leituras[chave]
        leitura = _ler_um_script(script)  # fora da trava: duas threads podem ler o mesmo script, e dá o mesmo
        with self._trava:
            self._leituras[chave] = leitura
            self._leituras.move_to_end(chave)
            while len(self._leituras) > self._maximo:
                self._leituras.popitem(last=False)
        return leitura


_CACHE_DE_SCRIPTS = _CacheDeScripts()


def _ler_scripts(html: str) -> _LeitorDeScripts:
    """O texto interno da página, script a script: cada um vem do cache (`_CACHE_DE_SCRIPTS`) e é juntado com os tetos
    da página (F3 da revisão final). O resultado é o da leitura literal a literal da página inteira."""
    leitor = _LeitorDeScripts()
    for script in _scripts_embutidos(html):
        leitor.juntar(_CACHE_DE_SCRIPTS.leitura(script))
        if leitor.truncado:
            break
    return leitor


def texto_interno(html: str) -> TextoInterno:
    """Os textos internos do aplicativo: as strings de linguagem natural dos `<script>` embutidos (sem `src`) do
    `html`, inclusive JSON e o payload do Next.js (`self.__next_f.push`), com os escapes de JS e de JSON desfeitos,
    também em camadas (o JSON dentro de uma string). Sem duplicatas, na ordem do documento, até
    `MAX_LINHAS_DO_TEXTO_INTERNO` linhas e `MAX_CARACTERES_DO_TEXTO_INTERNO` caracteres (acima disso, corta entre
    linhas e marca `truncado`). Ver `_e_texto_natural` para o que é texto.

    São as mensagens de telas que o visitante não vê (`Saques de rendimento estão bloqueados.`): o HTML é do site
    investigado, então o texto é dado não confiável.
    """
    leitor = _ler_scripts(html)
    return TextoInterno("\n".join(leitor.linhas), leitor.truncado)


# ---------------------------------------------------------------------------- nó


def _paginas_com_texto(saidas: dict) -> list[dict]:
    return [p for p in saidas.get("paginas", []) if p.get("texto")]


def _escolher_fonte(entradas: dict[str, dict]) -> tuple[str, list[dict]]:
    """O Wayback, se rodou (só roda quando não há captura utilizável); senão a captura não bloqueada."""
    if wayback := entradas.get("wayback_snapshot"):
        if paginas := _paginas_com_texto(wayback):
            return "wayback_snapshot", paginas
    captura = entradas.get("captura")
    if captura and not captura.get("bloqueada"):
        if paginas := _paginas_com_texto(captura):
            return "captura", paginas
    raise ErroNo("sem texto de página", permanente=True)


def _acrescentar(ja: list[Candidato], novos: Iterable[Candidato], truncadas: set[str]) -> list[Candidato]:
    """Os `novos` cuja (categoria, valor) a página ainda não tem em `ja`, enquanto a categoria cabe no teto da página
    (contando os de `ja`). A categoria que passa do teto vai para `truncadas`."""
    vistos = {(c.categoria, c.valor) for c in ja}
    por_categoria = Counter(c.categoria for c in ja)
    aceitos: list[Candidato] = []
    for c in novos:
        if (c.categoria, c.valor) in vistos:
            continue
        if por_categoria[c.categoria] >= TETO_POR_CATEGORIA:
            truncadas.add(c.categoria)
            continue
        por_categoria[c.categoria] += 1
        vistos.add((c.categoria, c.valor))
        aceitos.append(c)
    return aceitos


def _juntar(
    do_texto: list[Candidato], dos_atributos: list[Candidato], truncadas: set[str]
) -> tuple[list[Candidato], set[str]]:
    """Os do texto e depois os dos atributos que o texto ainda não tem, com o teto da página inteira."""
    return [*do_texto, *_acrescentar(do_texto, dos_atributos, truncadas)], truncadas


def _ler(s: Servicos, ref: str) -> str:
    return s.custodia.ler(ref).decode("utf-8", errors="replace")


class _Pagina(NamedTuple):
    """O cálculo de uma página, sem a custódia: os candidatos do texto e dos atributos, as categorias cortadas no teto
    e o texto interno (as linhas e as mesmas linhas sem as chaves)."""

    da_pagina: list[Candidato]
    truncadas: set[str]
    interno: _LeitorDeScripts | None


def _calcular_pagina(texto: str, ref: str, html: str | None, ref_html: str | None) -> _Pagina:
    """As regex do texto e dos atributos e a leitura dos scripts: o trabalho de CPU da página, que roda numa thread
    (F3 da revisão final: com 11 páginas de 4 MB, o loop do servidor ficaria parado por segundos)."""
    da_pagina, truncadas = _extrair_texto(texto, ref)
    if html is None or ref_html is None:
        return _Pagina(da_pagina, truncadas, None)
    dos_atributos, truncadas_html = _extrair_atributos(html, ref_html)
    da_pagina, truncadas = _juntar(da_pagina, dos_atributos, truncadas | truncadas_html)
    return _Pagina(da_pagina, truncadas, _ler_scripts(html))


def _montar_internos(sem_chaves: str, texto: str, ref: str) -> tuple[list[Candidato], set[str]]:
    return _montar(_achados(sem_chaves), texto, ref, origem=ORIGEM_TEXTO_INTERNO)


async def _candidatos_internos(
    leitor: _LeitorDeScripts, url: str, s: Servicos, refs_lidas: set[str], truncadas: set[str]
) -> list[Candidato]:
    """Guarda o texto interno da página (`leitor`) na custódia (`tipo="texto_interno"`, `origem=url`, `.txt`) e devolve
    os candidatos dele, com `extra.origem = "texto_interno"`. Sem texto interno, nada é guardado. O texto já lido em
    outra página (`refs_lidas`) é guardado de novo, com esta origem, mas os candidatos dele já saíram. A custódia fica
    no loop; as regex vão para uma thread."""
    if leitor.truncado:
        truncadas.add(ORIGEM_TEXTO_INTERNO)
    if not leitor.linhas:
        return []
    texto = "\n".join(leitor.linhas)
    ref = s.custodia.guardar(texto.encode("utf-8"), "txt", tipo=ORIGEM_TEXTO_INTERNO, origem=url)
    if ref in refs_lidas:
        return []
    refs_lidas.add(ref)
    candidatos, truncadas_internas = await asyncio.to_thread(_montar_internos, "\n".join(leitor.sem_chaves), texto, ref)
    truncadas |= truncadas_internas
    return candidatos


class ExtracaoNo(NoBase):
    """Roda `extrair`, `extrair_atributos` e as regex sobre o `texto_interno` em cada página da fonte e junta os
    candidatos.

    A fonte é o `wayback_snapshot`, quando ele está nas entradas, ou a `captura` (se não foi bloqueada). O texto
    interno de cada página com HTML vai para a custódia como artefato derivado (`tipo="texto_interno"`, `origem` = url
    da página, `.txt`), para ser lido no `ver_artefato` e citado pelo `sha256`.
    Saídas:
    - `candidatos`: os campos do `Candidato`, como dicionários (o motor grava e repassa as saídas em JSON).
      Página a página, os do texto vêm primeiro, com `artefato` = ref do texto da página e `posicao` = índice
      nele; depois os dos atributos do HTML (`href`, `src`, `action`) que o texto não tem, com `artefato` = ref
      do HTML e `posicao` = offset do atributo. O mesmo achado em páginas diferentes sai uma vez por página.
      Depois dos de todas as páginas vêm os do texto interno, página a página, com `artefato` = ref do texto
      interno, `posicao` = índice nele e `extra.origem = "texto_interno"`: só os que a página ainda não tem e
      dentro do teto dela. O dicionário do aplicativo se repete em todas as páginas, então o mesmo achado do texto
      interno sai uma vez só, na primeira página em que aparece;
    - `fonte`: `"wayback_snapshot"` ou `"captura"`;
    - `truncado`: `{url da página: [categorias]}` das que passaram de `TETO_POR_CATEGORIA` candidatos na
      página (ficam os primeiros), na ordem da tabela, e por último `"texto_interno"` se o texto interno da página
      passou de `MAX_LINHAS_DO_TEXTO_INTERNO` linhas ou `MAX_CARACTERES_DO_TEXTO_INTERNO` caracteres; `{}` se nada.
    """

    nome = "extracao"
    exige_um_de = ("captura", "wayback_snapshot")
    opcionais = ("captura", "wayback_snapshot")
    saidas = ("candidatos", "fonte", "truncado")

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        fonte, paginas = _escolher_fonte(entradas)
        lidas: list[tuple[str, list[Candidato], list[Candidato], set[str]]] = []  # url, da página, internos, truncadas
        refs_internas: set[str] = set()
        for pagina in paginas:
            ref = pagina["texto"]
            url = pagina.get("url") or ref
            ref_html = pagina.get("html") or None
            texto, html = _ler(s, ref), (_ler(s, ref_html) if ref_html else None)
            # o cálculo (regex, atributos e scripts) numa thread; a custódia, no loop
            calculo = await asyncio.to_thread(_calcular_pagina, texto, ref, html, ref_html)
            da_pagina, truncadas = calculo.da_pagina, calculo.truncadas
            internos: list[Candidato] = []
            if calculo.interno is not None:
                internos = await _candidatos_internos(calculo.interno, url, s, refs_internas, truncadas)
            lidas.append((url, da_pagina, internos, truncadas))
        candidatos = [c for _, da_pagina, _, _ in lidas for c in da_pagina]
        vistos_internos: set[tuple[str, str]] = set()
        for _, da_pagina, internos, truncadas in lidas:
            novos = [c for c in internos if (c.categoria, c.valor) not in vistos_internos]
            vistos_internos.update((c.categoria, c.valor) for c in internos)
            candidatos.extend(_acrescentar(da_pagina, novos, truncadas))
        truncado: dict[str, set[str]] = {}
        for url, _, _, truncadas in lidas:
            if truncadas:
                truncado.setdefault(url, set()).update(truncadas)
        ordem = (*_CATEGORIAS, ORIGEM_TEXTO_INTERNO)
        return Feito(
            {
                "candidatos": [c.model_dump() for c in candidatos],
                "fonte": fonte,
                "truncado": {url: [c for c in ordem if c in cs] for url, cs in truncado.items()},
            }
        )
