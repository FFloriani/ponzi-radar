"""Diff entre duas execuções do mesmo alvo (spec 8.5) e as leituras que ele divide com o dossiê.

`comparar(a, b, matriz)` pontua as duas execuções de novo com a matriz atual, a partir do que está guardado em disco
(saídas dos nós e julgamentos), e compara intervalo e classe, estágio, itens, sinais e alertas, infraestrutura,
sócios e capturas do Wayback. Se a `a` foi pontuada antes com outra matriz (o hash em `pontuacao.json` difere do
da matriz atual), o diff guarda também a conta original dela: o que mudou de uma execução para a outra pode ser só
a matriz.

`renderizar_diff` escreve o resultado em Markdown, a seção 8 do dossiê e o `diff.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import ValidationError

from radar.arquivos import ler_json
from radar.execucao import ExecucaoSalva, carregar_execucao, execucao_anterior
from radar.modelos import Item, Sinal
from radar.pendencias.esquemas import ValorC4
from radar.pontuacao import (
    Eixo1,
    Eixo2,
    Matriz,
    itens_da_execucao,
    pontuar_eixo1,
    pontuar_eixo2,
    sinais_da_execucao,
    site_nao_respondeu,
)
from radar.texto import escapar_md

NOME_DA_PONTUACAO = "pontuacao.json"
DIAS_PARA_EXPIRAR = 60

ROTULO_DO_ESTADO = {
    "confirmado": "confirmado",
    "nao_se_aplica": "não se aplica",
    "nao_encontrado": "não encontrado",
    "nao_verificado": "não verificado",
    "inconclusivo": "inconclusivo",
}
_COM_PONTOS = frozenset({"confirmado", "nao_se_aplica", "nao_encontrado"})  # os outros são um intervalo, não zero
_SEM_ESTAGIO = "sem estágio"
_CITA = {"cnpj": "o CNPJ", "dominio": "o domínio", "nome": "o nome"}
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------------------- leitura da execução salva


def saida(ex: ExecucaoSalva, no: str) -> dict | None:
    """As saídas do nó, se ele terminou `feito`."""
    if (ex.status.get(no) or {}).get("status") != "feito":
        return None
    dados = ex.saidas.get(no)
    return dados if isinstance(dados, dict) else None


def status_do_no(ex: ExecucaoSalva, no: str) -> str | None:
    return (ex.status.get(no) or {}).get("status")


def julgamento_ativo(ex: ExecucaoSalva, pendencia: str) -> dict | None:
    return next((j for j in ex.julgamentos if j.get("pendencia") == pendencia and j.get("ativa")), None)


def valor_confirmado(ex: ExecucaoSalva, pendencia: str) -> dict | None:
    """O `valor` da resposta ativa à pendência, se ela é `confirmado` ou `corrigido`."""
    resposta = (julgamento_ativo(ex, pendencia) or {}).get("resposta")
    if not isinstance(resposta, dict) or resposta.get("status") not in ("confirmado", "corrigido"):
        return None
    return resposta["valor"] if isinstance(resposta.get("valor"), dict) else None


def data_iso(valor: Any) -> date | None:
    """A data `AAAA-MM-DD` do texto (ignora a hora que vier depois); qualquer outra coisa é `None`."""
    if not isinstance(valor, str) or not _DATA_ISO.fullmatch(inicio := valor.strip()[:10]):
        return None
    try:
        return date.fromisoformat(inicio)
    except ValueError:
        return None


# ---------------------------------------------------------------------------- pontuação


@dataclass(frozen=True)
class Pontuacao:
    """A conta de uma execução com uma matriz: os 15 itens, os sinais do eixo 2 e os dois eixos."""

    itens: dict[str, Item]
    sinais: list[Sinal]
    eixo1: Eixo1
    eixo2: Eixo2


def ler_anterior(ex: ExecucaoSalva) -> tuple[ExecucaoSalva | None, str | None]:
    """A execução anterior de `ex` (`execucao_anterior`), carregada, e o aviso que a nomeia se ela existe mas não
    pôde ser lida (JSON corrompido, arquivo faltando): uma execução antiga ruim não pode impedir a análise nova.
    `(None, None)`: não há anterior."""
    pasta = execucao_anterior(ex.ctx.pasta)
    if pasta is None:
        return None, None
    try:
        return carregar_execucao(pasta), None
    except (OSError, ValueError, KeyError, TypeError) as erro:
        nome = f"{pasta.parent.name}/{pasta.name}"
        return None, f"A execução anterior {nome} não pôde ser lida ({type(erro).__name__})."


def carregar_anterior(ex: ExecucaoSalva) -> ExecucaoSalva | None:
    """A execução anterior de `ex`, carregada, ou `None` se não há ou não pôde ser lida (ver `ler_anterior`)."""
    return ler_anterior(ex)[0]


def pontuar(ex: ExecucaoSalva, matriz: Matriz, anterior: ExecucaoSalva | None) -> Pontuacao:
    """Itens, sinais e eixos de `ex` com `matriz`. `anterior` serve ao E6 por duas falhas de captura."""
    itens = itens_da_execucao(ex, matriz)
    sinais, modificadores = sinais_da_execucao(ex, matriz, anterior)
    return Pontuacao(
        itens=itens,
        sinais=sinais,
        eixo1=pontuar_eixo1(itens, matriz, sinais=sinais),
        eixo2=pontuar_eixo2(sinais, modificadores, matriz),
    )


def total_de_pontos(matriz: Matriz) -> int:
    """A soma dos máximos dos itens: o "34" de "8–10 de 34"."""
    return sum(i.max for i in matriz.itens.values())


def texto_intervalo(minimo: int, maximo: int, total: int) -> str:
    """`"{min}–{max} de {total}"`, ou `"{min} de {total}"` quando os dois são iguais."""
    return f"{minimo} de {total}" if minimo == maximo else f"{minimo}–{maximo} de {total}"


def texto_classe(eixo1: Eixo1) -> str:
    """A classe, com `"(pode chegar a <classe>)"` quando a faixa do máximo é mais alta."""
    return f"{eixo1.classe} (pode chegar a {eixo1.pode_chegar_a})" if eixo1.pode_chegar_a else eixo1.classe


# ---------------------------------------------------------------------------- alertas


@dataclass(frozen=True)
class Alerta:
    """Um alerta oficial citado pela execução. `chave` o identifica entre execuções; `fonte` é a URL, se houver."""

    chave: str
    rotulo: str
    data: str | None
    fonte: str | None


def alertas_da_execucao(ex: ExecucaoSalva) -> list[Alerta]:
    """As deliberações da CVM que citam o alvo (`cvm_alertas`) e os alertas que a P-C4 confirmou."""
    alertas: list[Alerta] = []
    cvm = saida(ex, "cvm_alertas")
    if cvm is not None and "correspondencias" not in (cvm.get("vazamento_temporal") or ()):
        for c in cvm.get("correspondencias") or []:
            if not isinstance(c, dict):
                continue
            numero, tipo = c.get("numero"), c.get("tipo")
            data = d.isoformat() if (d := data_iso(c.get("data"))) else None
            rotulo = f"alerta CVM: Deliberação {numero}" + (f" ({data})" if data else "")
            rotulo += f" cita {_CITA.get(tipo, 'o alvo')}"
            fonte = c.get("url") if isinstance(c.get("url"), str) else None
            alertas.append(Alerta(f"cvm:{numero}:{tipo}", rotulo, data, fonte))
    if (valor := valor_confirmado(ex, "P-C4")) is not None:
        try:
            c4 = ValorC4.model_validate(valor)
        except ValidationError:
            c4 = None
        if c4 is not None and c4.alerta_vigente:
            for a in c4.alertas:
                data = a.data.isoformat()
                alertas.append(Alerta(f"{a.regulador}:{data}:{a.url}", f"alerta {a.regulador} ({data})", data, a.url))
    return alertas


# ---------------------------------------------------------------------------- o diff


@dataclass(frozen=True)
class Diff:
    """O que mudou da execução `a` (a mais antiga) para a `b`, as duas pontuadas com a matriz atual.

    - `itens_mudados`: `(id, estado_a, pontos_a, estado_b, pontos_b)` dos itens cujo estado ou pontos mudaram, na
      ordem da matriz;
    - `sinais_novos`: sinais do eixo 2 (tipo, estágio, data) e alertas que `b` tem e `a` não tem;
    - `infra`: `domínio analisado mudou: <a> → <b>` (o domínio que os coletores de domínio analisaram, ver
      `_dominio_analisado`, mudou: um redirect que apareceu, sumiu ou mudou, com "(sem captura em b)" quando a captura
      não terminou numa delas), `hospedagem mudou` (A/AAAA), `NS mudou` e `MX mudou` (só quando o domínio analisado é
      o mesmo: o DNS de domínios diferentes não se compara), `domínio expira em menos de 60 dias` (em `b`, a partir do
      `as_of` dela) e `site fora do ar` (NXDOMAIN em `b`, ou o site não respondeu à captura em `b` e respondeu em
      `a`, pelo critério da pontuação: `pontuacao.site_nao_respondeu`);
    - `socios_entraram` e `socios_sairam`: nomes do quadro de sócios (nunca CPF);
    - `wayback_novas`: capturas do Wayback que `b` tem a mais (0 quando o domínio analisado mudou);
    - `matriz_diferente`: a `a` foi pontuada antes com outra matriz. `eixo1_a_matriz_original` é a conta de então
      (`None` se o `pontuacao.json` dela não a traz) e `matriz_versoes`, `(versão original, versão atual)` (com os
      8 primeiros hex do hash de cada uma quando as versões coincidem);
    - `total_pontos`: a soma dos máximos dos itens (o "de 34" do intervalo).
    """

    eixo1_a: Eixo1
    eixo1_b: Eixo1
    estagio_a: str | None
    estagio_b: str | None
    itens_mudados: list[tuple]
    sinais_novos: list[str]
    infra: list[str]
    socios_entraram: list[str]
    socios_sairam: list[str]
    wayback_novas: int
    matriz_diferente: bool
    eixo1_a_matriz_original: Eixo1 | None
    total_pontos: int = 34
    matriz_versoes: tuple[str, str] | None = None


def _conta_original(a: ExecucaoSalva, matriz: Matriz) -> tuple[str, str, Eixo1 | None] | None:
    """`(versão, hash, eixo 1)` com que a `a` foi pontuada, se foi com outra matriz; `None` se a matriz é a mesma, se
    não há `pontuacao.json` ou se ele não diz com que matriz foi feito (nesses casos vale como igual)."""
    try:
        dados = ler_json(a.ctx.pasta / NOME_DA_PONTUACAO)
    except (OSError, ValueError):
        return None
    registro = dados.get("matriz") if isinstance(dados, dict) else None
    if not isinstance(registro, dict) or not isinstance(registro.get("hash"), str) or registro["hash"] == matriz.hash:
        return None
    versao = registro["versao"] if isinstance(registro.get("versao"), str) else "desconhecida"
    try:
        return versao, registro["hash"], Eixo1.model_validate(dados.get("eixo1"))
    except ValidationError:
        return versao, registro["hash"], None


def _nome_do_socio(nome: str) -> str:
    return " ".join(nome.split())


def _socios(ex: ExecucaoSalva) -> dict[str, str] | None:
    """`{nome sem caixa: nome}` do quadro; `None` se o `cnpj` não terminou ou não achou a empresa."""
    dados = saida(ex, "cnpj")
    if dados is None or dados.get("cnpj") is None:
        return None
    socios: dict[str, str] = {}
    for socio in dados.get("socios") or []:
        if isinstance(socio, dict) and isinstance(socio.get("nome"), str) and (nome := _nome_do_socio(socio["nome"])):
            socios.setdefault(nome.casefold(), nome)
    return socios


def _registros_dns(dns: dict, *tipos: str) -> frozenset[str]:
    return frozenset(
        valor.strip().lower().rstrip(".")
        for tipo in tipos
        for valor in dns.get(tipo) or []
        if isinstance(valor, str)
    )


def _dominio_analisado(ex: ExecucaoSalva) -> str:
    """O domínio que os coletores de domínio (`rdap`, `dns`, `ct`, `wayback_*`) analisaram: o `dominio` do nó
    `destino` quando ele terminou, com captura ou sem; sem ele (a execução de antes da T1, que não tem o nó), o do alvo,
    que era o que os coletores recebiam."""
    dominio = (saida(ex, "destino") or {}).get("dominio")
    return dominio.strip().lower() if isinstance(dominio, str) and dominio.strip() else ex.ctx.alvo.lower()


def _mudanca_de_dominio(a: ExecucaoSalva, b: ExecucaoSalva) -> str | None:
    """"domínio analisado mudou: <a> → <b>", ou `None` se é o mesmo. Sem captura numa delas, o `destino` dela voltou ao
    alvo por falta de dado (o redirect não foi visto), e a linha diz qual."""
    dominio_a, dominio_b = _dominio_analisado(a), _dominio_analisado(b)
    if dominio_a == dominio_b:
        return None
    sem_captura = [nome for nome, ex in (("a", a), ("b", b)) if saida(ex, "captura") is None]
    motivo = f" (sem captura em {' e '.join(sem_captura)})" if sem_captura else ""
    return f"domínio analisado mudou: {dominio_a} → {dominio_b}{motivo}"


def _infra(a: ExecucaoSalva, b: ExecucaoSalva, mudanca_de_dominio: str | None) -> list[str]:
    infra: list[str] = [mudanca_de_dominio] if mudanca_de_dominio else []
    dns_a, dns_b = saida(a, "dns"), saida(b, "dns")
    # hospedagem, NS e MX de domínios diferentes não são mudança de infraestrutura (I3 da revisão da T1)
    if dns_a is not None and dns_b is not None and mudanca_de_dominio is None:
        for tipos, mensagem in ((("A", "AAAA"), "hospedagem mudou"), (("NS",), "NS mudou"), (("MX",), "MX mudou")):
            if _registros_dns(dns_a, *tipos) != _registros_dns(dns_b, *tipos):
                infra.append(mensagem)
    rdap = saida(b, "rdap")
    expiracao = data_iso(rdap.get("expiracao")) if rdap is not None else None
    if expiracao is not None and (expiracao - b.ctx.as_of).days < DIAS_PARA_EXPIRAR:
        infra.append(f"domínio expira em menos de {DIAS_PARA_EXPIRAR} dias")
    nxdomain = dns_b is not None and dns_b.get("nxdomain") is True
    # o critério é o do E6: HTTP 403/429 (WAF) ou "erro inesperado" não são o site fora do ar
    captura_caiu = site_nao_respondeu(b) and not site_nao_respondeu(a)
    if nxdomain or captura_caiu:
        infra.append("site fora do ar")
    return infra


def _rotulo_do_sinal(sinal: Sinal) -> str:
    texto = sinal.tipo + (f" ({sinal.estagio})" if sinal.estagio else "")
    return texto + (f", {sinal.data.isoformat()}" if sinal.data else "")


def _capturas_novas(a: ExecucaoSalva, b: ExecucaoSalva) -> int:
    indice_a, indice_b = saida(a, "wayback_indice"), saida(b, "wayback_indice")
    if indice_a is None or indice_b is None:
        return 0
    total_a, total_b = indice_a.get("total"), indice_b.get("total")
    if not isinstance(total_a, int) or not isinstance(total_b, int):
        return 0
    return max(0, total_b - total_a)


def comparar(a: ExecucaoSalva, b: ExecucaoSalva, matriz: Matriz) -> Diff:
    """Compara `a` (mais antiga) com `b`, as duas pontuadas de novo com `matriz`.

    O E6 de `b` usa `a` como execução anterior; o de `a`, a execução anterior a ela no disco (`execucao_anterior`).
    """
    pa = pontuar(a, matriz, carregar_anterior(a))
    pb = pontuar(b, matriz, a)

    mudados = [
        (id_, ia.estado, ia.pontos, pb.itens[id_].estado, pb.itens[id_].pontos)
        for id_, ia in pa.itens.items()
        if (ia.estado, ia.pontos) != (pb.itens[id_].estado, pb.itens[id_].pontos)
    ]
    tipos_antigos = {s.tipo for s in pa.sinais}
    chaves_antigas = {al.chave for al in alertas_da_execucao(a)}
    sinais_novos = [_rotulo_do_sinal(s) for s in pb.sinais if s.tipo not in tipos_antigos]
    sinais_novos += [al.rotulo for al in alertas_da_execucao(b) if al.chave not in chaves_antigas]

    socios_a, socios_b = _socios(a), _socios(b)
    entraram: list[str] = []
    sairam: list[str] = []
    if socios_a is not None and socios_b is not None:
        entraram = [nome for chave, nome in socios_b.items() if chave not in socios_a]
        sairam = [nome for chave, nome in socios_a.items() if chave not in socios_b]

    mudanca_de_dominio = _mudanca_de_dominio(a, b)
    original = _conta_original(a, matriz)
    versoes = None
    if original is not None:
        versoes = (original[0], matriz.versao)
        if original[0] == matriz.versao:  # a versão não distingue as duas: o hash distingue
            versoes = (f"{original[0]} (hash {original[1][:8]})", f"{matriz.versao} (hash {matriz.hash[:8]})")
    return Diff(
        eixo1_a=pa.eixo1,
        eixo1_b=pb.eixo1,
        estagio_a=pa.eixo2.estagio,
        estagio_b=pb.eixo2.estagio,
        itens_mudados=mudados,
        sinais_novos=sinais_novos,
        infra=_infra(a, b, mudanca_de_dominio),
        socios_entraram=entraram,
        socios_sairam=sairam,
        # as capturas de outro domínio não são novas: o Wayback do domínio de antes não se compara com o de agora
        wayback_novas=0 if mudanca_de_dominio else _capturas_novas(a, b),
        matriz_diferente=original is not None,
        eixo1_a_matriz_original=original[2] if original is not None else None,
        total_pontos=total_de_pontos(matriz),
        matriz_versoes=versoes,
    )


# ---------------------------------------------------------------------------- Markdown


def _numero_do_estagio(estagio: str | None) -> int:
    """`E4` → 4; sem estágio → -1 (abaixo do E0)."""
    digitos = re.sub(r"\D", "", estagio or "")
    return int(digitos) if digitos else -1


def _mudanca(rotulo: str, antes: str, depois: str) -> str:
    return f"- {rotulo}: {antes} (sem mudança)" if antes == depois else f"- {rotulo}: {antes} → {depois}"


def _linha_do_estagio(antes: str | None, depois: str | None) -> str:
    a, b = antes or _SEM_ESTAGIO, depois or _SEM_ESTAGIO
    if _numero_do_estagio(depois) > _numero_do_estagio(antes):
        return f"- ⚠ estágio subiu: {a} → {b}"
    if _numero_do_estagio(depois) < _numero_do_estagio(antes):
        return f"- Estágio: {a} → {b} (desceu)"
    return f"- Estágio: {a} (sem mudança)"


def _estado_com_pontos(estado: str, pontos: int) -> str:
    rotulo = ROTULO_DO_ESTADO.get(estado, estado)
    return f"{rotulo} ({pontos})" if estado in _COM_PONTOS else rotulo


def _lista(titulo: str, itens: list[str]) -> list[str]:
    if not itens:
        return [f"- {titulo}: nenhum"]
    return [f"- {titulo}:", *(f"  - {escapar_md(item)}" for item in itens)]


def _linhas_da_matriz(d: Diff) -> list[str]:
    if not d.matriz_diferente:
        return []
    antes, atual = d.matriz_versoes or ("desconhecida", "atual")
    linhas = [
        f"- Matriz diferente: a execução anterior foi pontuada com a versão {escapar_md(antes)}; "
        f"as duas execuções foram repontuadas aqui com a versão {escapar_md(atual)}."
    ]
    if d.eixo1_a_matriz_original is not None:
        original = d.eixo1_a_matriz_original
        conta = texto_intervalo(original.minimo, original.maximo, d.total_pontos)
        linhas.append(f"  - Anterior, com a matriz original: {conta}, {escapar_md(texto_classe(original))}")
    a = d.eixo1_a
    linhas.append(
        f"  - Anterior, com a matriz atual: {texto_intervalo(a.minimo, a.maximo, d.total_pontos)}, "
        f"{escapar_md(texto_classe(a))}"
    )
    return linhas


def renderizar_diff(d: Diff) -> str:
    """O diff em Markdown, uma linha por tópico, sem título (quem o usa põe o título). Termina em `\\n`."""
    a, b = d.eixo1_a, d.eixo1_b
    linhas = [
        _mudanca(
            "Intervalo",
            texto_intervalo(a.minimo, a.maximo, d.total_pontos),
            texto_intervalo(b.minimo, b.maximo, d.total_pontos),
        ),
        _mudanca("Classe", escapar_md(texto_classe(a)), escapar_md(texto_classe(b))),
        *_linhas_da_matriz(d),
        _linha_do_estagio(d.estagio_a, d.estagio_b),
    ]
    if d.itens_mudados:
        linhas.append("- Itens que mudaram:")
        for id_, estado_a, pontos_a, estado_b, pontos_b in d.itens_mudados:
            antes, depois = _estado_com_pontos(estado_a, pontos_a), _estado_com_pontos(estado_b, pontos_b)
            linhas.append(f"  - {escapar_md(id_)}: {antes} → {depois}")
    else:
        linhas.append("- Itens que mudaram: nenhum")
    linhas += _lista("Sinais e alertas novos", d.sinais_novos)
    if d.infra:
        linhas += ["- Infraestrutura:", *(f"  - {escapar_md(item)}" for item in d.infra)]
    else:
        linhas.append("- Infraestrutura: nada a destacar")
    linhas += _lista("Sócios que entraram", d.socios_entraram)
    linhas += _lista("Sócios que saíram", d.socios_sairam)
    linhas.append(f"- Capturas novas no Wayback: {d.wayback_novas}")
    return "\n".join(linhas) + "\n"
