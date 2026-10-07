"""Extração por regex dos candidatos de uma página: promessas, CNPJs, contratos, regras, carteiras e contatos.

`extrair` roda sobre o texto visível de uma página (o texto da captura ou do Wayback, nunca o HTML) e
devolve `Candidato`s. Eles só apontam onde olhar: o nó `claude` (T12) confirma ou corrige cada um, e a
matriz (T14) só pontua o que foi confirmado.

O texto é do site investigado: as regex rodam sobre conteúdo hostil. Por isso cada quantificador é
limitado (`{1,3}`, `{1,64}`...), nenhum repete um grupo que já tem repetição por dentro e nenhuma
alternância deixa dois caminhos casarem o mesmo trecho. O custo é linear no tamanho do texto, também
para `"1" * 100_000`, `"%" * 100_000` e `"a." * 100_000` (ver tests/test_extracao.py).

Convenções:
- as regex ignoram a caixa: as de letras rodam numa cópia do texto em minúsculas, com os mesmos índices
  (e por isso sem `re.IGNORECASE`, que desliga a busca rápida pelo primeiro caractere). Sem a regex
  `(?<!\\w)` na frente, que também a desliga, a borda de palavra da esquerda é conferida em Python;
- o `valor` das categorias sem normalização é o termo achado, em minúsculas e com os espaços colapsados
  (`"bônus de indicação"`). Endereços de carteira, convites e caminhos de rede social não mudam de
  caixa: `Ab12` e `ab12` não são o mesmo código;
- `posicao` é o índice do início do achado no texto e `trecho` o recorte de ±120 caracteres em volta;
- na mesma página, candidatos com a mesma (categoria, valor) viram um só, o da primeira ocorrência.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Iterator
from decimal import Decimal
from typing import Any, NamedTuple

from radar.modelos import Candidato, Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos

_MARGEM = 120  # caracteres de contexto de cada lado do achado

# ---------------------------------------------------------------------------- conversão de período


def converter_para_mes(pct: float, periodo: str) -> float:
    """Retorno mensal equivalente (em %), por composição, arredondado a 4 casas.

    `periodo` é `dia` (30 dias), `ano` (1/12), `Nm` (1/N: `24m` é 24 meses) ou `mes` (identidade).
    Levanta `ValueError` para período desconhecido ou `pct` que não é um retorno possível.
    """
    if periodo == "dia":
        expoente = 30.0
    elif periodo == "mes":
        expoente = 1.0
    elif periodo == "ano":
        expoente = 1 / 12
    elif (n := re.fullmatch(r"([0-9]{1,6})m", periodo)) and int(n.group(1)) > 0:
        expoente = 1 / int(n.group(1))
    else:
        raise ValueError(f"período desconhecido: {periodo!r}")
    if not math.isfinite(pct) or pct < -100:
        raise ValueError(f"percentual impossível: {pct!r}")
    try:
        return round(((1 + pct / 100) ** expoente - 1) * 100, 4)
    except OverflowError:
        raise ValueError(f"percentual grande demais: {pct!r}") from None


# ---------------------------------------------------------------------------- CNPJ

_PESOS_DV = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _digito(digitos: str, pesos: tuple[int, ...]) -> int:
    resto = sum(int(d) * p for d, p in zip(digitos, pesos, strict=False)) % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(digitos: str) -> bool:
    """14 dígitos (só ASCII, sem pontuação) com os dois dígitos verificadores da Receita certos.

    Sequências de um dígito só (`00000000000000`, `11111111111111`...) não valem: a de zeros passa na
    conta dos dígitos verificadores, mas não é um CNPJ.
    """
    if not re.fullmatch(r"[0-9]{14}", digitos) or len(set(digitos)) == 1:
        return False
    dv1 = _digito(digitos[:12], _PESOS_DV)
    dv2 = _digito(digitos[:12] + str(dv1), (6, *_PESOS_DV))
    return digitos[12:] == f"{dv1}{dv2}"


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
    r"hist[óo]rico de (?:rentabilidade|rendimento|ganho|lucro|retorno|pagamento)s?",
    r"rentabilidade hist[óo]rica",
    r"rentabilidade m[eê]s a m[eê]s",
    r"rentabilidade acumulada",
)
_INDICACAO = _frases(
    r"b[ôo]nus (?:de|por) indica(?:[çc][ãa]o|[çc][õo]es)",
    r"comiss(?:[ãa]o|[õo]es) (?:de|por) indica(?:[çc][ãa]o|[çc][õo]es)",
    r"programa de (?:afiliad[oa]s?|indica(?:[çc][ãa]o|[çc][õo]es)|parceiros)",
    r"link de (?:indica(?:[çc][ãa]o|[çc][õo]es)|afiliad[oa]|convite)",
    r"c[óo]digo de (?:indica(?:[çc][ãa]o|[çc][õo]es)|afiliad[oa]|convite)",
    r"indique e ganhe",
    r"indique um amigo",
    r"rede de indicados",
    r"indica(?:[çc][ãa]o|[çc][õo]es)",
    r"afiliad[oa]s?",
    r"multin[ií]vel",
    r"n[ií]v(?:el|eis) de (?:indica(?:[çc][ãa]o|[çc][õo]es)|comiss[ãa]o|b[ôo]nus|rede)",
    r"n[ií]v(?:el|eis) [0-9]{1,2}",
    r"downline",
    r"upline",
)
_SAQUE = _frases(
    r"taxas? de (?:saque|retirada|resgate)s?",
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
    r"lock-?up",
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

_NUMERO = r"[0-9]{1,4}(?:[.,][0-9]{1,4})?"
# o número não pode ser o fim de outro maior ("12345%", "1.000.000%")
_PCT = re.compile(rf"(?<![0-9])(?<![0-9][.,])({_NUMERO})[^\S\n]{{0,3}}%")
_FAIXA = re.compile(rf"[^\S\n]{{0,3}}(?:até|ate|a|à|e|ou|-|–|—)[^\S\n]{{0,3}}{_NUMERO}[^\S\n]{{0,3}}%")
# a unidade vem logo depois do número ("1,5% a.d.", "30%\nao dia"); só `em N meses` dá o prazo
_DEPOIS = re.compile(
    r"\s{0,3}(?:"
    r"(?P<dia>a\s?\.\s?d\b\.?|ao\s{1,3}dia\b|por\s{1,3}dia\b|/\s{0,2}dia\b|di[aá]ri[oa]s?\b|diariamente\b)"
    r"|(?P<mes>a\s?\.\s?m\b\.?|ao\s{1,3}m[eê]s\b|por\s{1,3}m[eê]s\b|/\s{0,2}m[eê]s\b"
    r"|mensa(?:l|is)\b|mensalmente\b)"
    r"|(?P<ano>a\s?\.\s?a\b\.?|ao\s{1,3}ano\b|por\s{1,3}ano\b|/\s{0,2}ano\b|anua(?:l|is)\b|anualmente\b)"
    r"|(?:em|ap[óo]s|ao\s{1,3}(?:fim|final)\s{1,3}de)(?:\s{1,3}at[eé])?"
    r"\s{1,3}(?P<n>[0-9]{1,3})\s{1,3}m[eê]s(?:es)?\b"
    r")"
)
# a unidade antes do número ("rendimento diário de 1%"): vale a mais próxima, na mesma frase
_ANTES = re.compile(
    r"(?<!\w)(?:"
    r"(?P<dia>di[aá]ri[oa]s?|diariamente|(?:ao|por)[^\S\n]{1,3}dia)"
    r"|(?P<mes>mensa(?:l|is)|mensalmente|(?:ao|por)[^\S\n]{1,3}m[eê]s)"
    r"|(?P<ano>anua(?:l|is)|anualmente|(?:ao|por)[^\S\n]{1,3}ano)"
    r")(?!\w)"
)
_ATE = re.compile(r"(?<!\w)(?:at[eé]|m[aá]xim[oa](?:[^\S\n]{1,3}de)?)[^\S\n]{0,3}$")
_JANELA_DEPOIS = 48
_JANELA_ANTES = 48
_FIM_DE_FRASE = ".,!?;\n%"  # a unidade de outra oração não vale para este número


def _periodo_de(m: re.Match[str]) -> str | None:
    """`dia`, `mes`, `ano` ou `Nm` (o prazo de `em N meses`) do que `_DEPOIS` ou `_ANTES` achou."""
    for nome in ("dia", "mes", "ano"):
        if m.group(nome):
            return nome
    n = int(m.groupdict().get("n") or 0)
    return f"{n}m" if n > 0 else None


def _periodo_antes(baixo: str, inicio: int) -> str | None:
    janela = baixo[max(0, inicio - _JANELA_ANTES) : inicio]
    janela = janela[max(map(janela.rfind, _FIM_DE_FRASE)) + 1 :]
    ultimo = None
    for ultimo in _ANTES.finditer(janela):
        pass
    return _periodo_de(ultimo) if ultimo else None


def _percentuais(texto: str, baixo: str) -> Iterator[_Achado]:
    vistos: set[tuple[str, str]] = set()
    for m in _PCT.finditer(texto):
        inicio, fim = m.start(1), m.end()
        depois = baixo[fim : fim + _JANELA_DEPOIS]
        # "de 1% a 3% ao dia": a unidade do 1% é a do 3%
        faixa = _FAIXA.match(depois)
        if faixa:
            depois = depois[faixa.end() :]
        unidade = _DEPOIS.match(depois)
        periodo = _periodo_de(unidade) if unidade else None
        if periodo and not faixa:
            fim += unidade.end()  # o achado vai até o fim da unidade
        if periodo is None:
            periodo = _periodo_antes(baixo, inicio)
        if periodo is None or (m.group(1), periodo) in vistos:
            continue
        vistos.add((m.group(1), periodo))
        numero = Decimal(m.group(1).replace(",", "."))
        valor = f"{format(numero.normalize(), 'f')}|{periodo}"
        ate = bool(_ATE.search(baixo[max(0, inicio - 24) : inicio]))
        extra = {"pct_mes": converter_para_mes(float(numero), periodo), "ate": ate}
        yield _Achado(inicio, fim, "percentual", valor, extra)


# --- CNPJ

# 14 dígitos, com ou sem pontuação, que não são parte de um número maior
_CNPJ = re.compile(r"(?<![0-9.])[0-9]{2}\.?[0-9]{3}\.?[0-9]{3}/?[0-9]{4}-?[0-9]{2}(?![0-9])")


def _cnpjs(texto: str) -> Iterator[_Achado]:
    vistos: set[str] = set()
    for m in _CNPJ.finditer(texto):
        digitos = re.sub(r"[^0-9]", "", m.group())
        if digitos not in vistos and cnpj_valido(digitos):
            vistos.add(digitos)
            yield _Achado(m.start(), m.end(), "cnpj", digitos, {})


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
    r"|(?:api|web)\.whatsapp\.com/send/?\?(?:[\w%.+=-]{1,100}&)?phone=\+?(?P<tel>[0-9]{8,15})"
    r"|chat\.whatsapp\.com/(?P<convite>[\w-]{1,40}))"
)
_TELEGRAM = re.compile(
    r"(?:t|telegram)\.(?:me|dog)/(?P<caminho>(?:joinchat/|\+)?[\w-]{3,64}|s/[\w-]{3,64})"
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


def extrair(texto: str, artefato: str) -> list[Candidato]:
    """Candidatos do `texto` da página guardada em `artefato`, na ordem em que aparecem.

    Na mesma (categoria, valor) fica só a primeira ocorrência.
    """
    primeiros: dict[tuple[str, str], _Achado] = {}
    for achado in _achados(texto):
        chave = (achado.categoria, achado.valor)
        if chave not in primeiros or achado.inicio < primeiros[chave].inicio:
            primeiros[chave] = achado
    ordenados = sorted(primeiros.values(), key=lambda a: (a.inicio, _ORDEM[a.categoria], a.valor))
    return [
        Candidato(
            categoria=a.categoria,
            valor=a.valor,
            trecho=texto[max(0, a.inicio - _MARGEM) : a.fim + _MARGEM],
            artefato=artefato,
            posicao=a.inicio,
            extra=a.extra,
        )
        for a in ordenados
    ]


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


class ExtracaoNo(NoBase):
    """Roda `extrair` em cada página da fonte do texto e junta os candidatos.

    A fonte é o `wayback_snapshot`, quando ele está nas entradas, ou a `captura` (se não foi bloqueada).
    Saídas: `candidatos` (os campos do `Candidato`, como dicionários: o motor grava e repassa as saídas
    em JSON) e `fonte` (`"wayback_snapshot"` ou `"captura"`). O `artefato` de cada candidato é a ref do
    texto da página e a `posicao` o índice nele; o mesmo achado em páginas diferentes sai uma vez por
    página.
    """

    nome = "extracao"
    exige_um_de = ("captura", "wayback_snapshot")
    opcionais = ("captura", "wayback_snapshot")
    saidas = ("candidatos", "fonte")

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        fonte, paginas = _escolher_fonte(entradas)
        candidatos: list[dict] = []
        for pagina in paginas:
            ref = pagina["texto"]
            texto = s.custodia.ler(ref).decode("utf-8", errors="replace")
            candidatos.extend(c.model_dump() for c in extrair(texto, ref))
        return Feito({"candidatos": candidatos, "fonte": fonte})
