"""Extração por regex dos candidatos de uma página: promessas, CNPJs, contratos, regras, carteiras e contatos.

`extrair` roda sobre o texto visível de uma página (o texto da captura ou do Wayback) e devolve
`Candidato`s. `extrair_atributos` faz o mesmo com os valores de `href`, `src` e `action` do HTML da página,
onde ficam os links de contato que o texto não mostra (o texto de `<a href="https://wa.me/...">` é só
"Fale conosco"); só as regex de contato e de carteira rodam sobre eles. Os candidatos só apontam onde
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
`_HTML_MAXIMO` caracteres ou `_TAGS_MAXIMAS` tags.

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

import hashlib
import math
import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Iterable, Iterator
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any, NamedTuple

from radar.cnpj_util import cnpj_valido
from radar.modelos import Candidato, Contexto, ErroNo, Feito
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
    r"convide (?:amigos|e ganhe)",
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


def _percentual(baixo: str, bruto: str, periodo: str, inicio: int, fim: int) -> _Achado:
    numero = _para_decimal(bruto)
    ate = bool(_ATE.search(baixo[max(0, inicio - 24) : inicio]))
    extra = {"pct_mes": converter_para_mes(float(numero), periodo), "ate": ate}
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
        yield _percentual(baixo, m.group(1), periodo, m.start(1), fim)
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
        yield _percentual(baixo, numero.group(1), periodo, inicio, numero.end())


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


def _montar(achados: Iterable[_Achado], base: str, artefato: str) -> tuple[list[Candidato], set[str]]:
    """Os `Candidato`s de `achados` (índices em `base`, o texto ou o HTML guardado em `artefato`).

    Fica a primeira ocorrência de cada (categoria, valor), em ordem de posição, e no máximo
    `TETO_POR_CATEGORIA` por categoria. Devolve também as categorias que passaram do teto.
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
                extra=a.extra,
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


class _Atributos(HTMLParser):
    """Os valores de `href`, `src` e `action` de todas as tags, com o offset de cada um no HTML.

    O `HTMLParser` não executa nem baixa nada e não entra em `<script>` e `<style>`. Valores repetidos
    ficam com o primeiro offset; `data:` (imagem em base64) e valores vazios ficam de fora.
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
        for nome, valor in attrs:
            if nome not in _ATRIBUTOS_DE_LINK or not valor:
                continue
            valor = valor.strip()[:_VALOR_MAXIMO]
            if not valor or valor in self.valores or valor[:5].lower() == "data:":
                continue
            # o valor lido já tem as entidades resolvidas (`&amp;`): se não aparece igual na tag, o
            # offset é o da tag
            achou = (self.get_starttag_text() or "").find(valor)
            self.valores[valor] = self._offset_da_tag() + max(achou, 0)


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


def _juntar(
    do_texto: list[Candidato], dos_atributos: list[Candidato], truncadas: set[str]
) -> tuple[list[Candidato], set[str]]:
    """Os do texto e depois os dos atributos que o texto ainda não tem, com o teto da página inteira."""
    vistos = {(c.categoria, c.valor) for c in do_texto}
    por_categoria: Counter[str] = Counter()
    juntos: list[Candidato] = []
    for c in (*do_texto, *(c for c in dos_atributos if (c.categoria, c.valor) not in vistos)):
        if por_categoria[c.categoria] >= TETO_POR_CATEGORIA:
            truncadas.add(c.categoria)
            continue
        por_categoria[c.categoria] += 1
        juntos.append(c)
    return juntos, truncadas


def _ler(s: Servicos, ref: str) -> str:
    return s.custodia.ler(ref).decode("utf-8", errors="replace")


class ExtracaoNo(NoBase):
    """Roda `extrair` e `extrair_atributos` em cada página da fonte e junta os candidatos.

    A fonte é o `wayback_snapshot`, quando ele está nas entradas, ou a `captura` (se não foi bloqueada).
    Saídas:
    - `candidatos`: os campos do `Candidato`, como dicionários (o motor grava e repassa as saídas em JSON).
      Os do texto vêm primeiro, com `artefato` = ref do texto da página e `posicao` = índice nele; depois
      os dos atributos do HTML (`href`, `src`, `action`) que o texto não tem, com `artefato` = ref do HTML
      e `posicao` = offset do atributo. O mesmo achado em páginas diferentes sai uma vez por página;
    - `fonte`: `"wayback_snapshot"` ou `"captura"`;
    - `truncado`: `{url da página: [categorias]}` das que passaram de `TETO_POR_CATEGORIA` candidatos na
      página (ficam os primeiros); `{}` se nenhuma.
    """

    nome = "extracao"
    exige_um_de = ("captura", "wayback_snapshot")
    opcionais = ("captura", "wayback_snapshot")
    saidas = ("candidatos", "fonte", "truncado")

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        fonte, paginas = _escolher_fonte(entradas)
        candidatos: list[dict] = []
        truncado: dict[str, set[str]] = {}
        for pagina in paginas:
            ref = pagina["texto"]
            do_texto, truncadas = _extrair_texto(_ler(s, ref), ref)
            if ref_html := pagina.get("html"):
                dos_atributos, truncadas_html = _extrair_atributos(_ler(s, ref_html), ref_html)
                do_texto, truncadas = _juntar(do_texto, dos_atributos, truncadas | truncadas_html)
            candidatos.extend(c.model_dump() for c in do_texto)
            if truncadas:
                truncado.setdefault(pagina.get("url") or ref, set()).update(truncadas)
        return Feito(
            {
                "candidatos": candidatos,
                "fonte": fonte,
                "truncado": {url: [c for c in _CATEGORIAS if c in cs] for url, cs in truncado.items()},
            }
        )
