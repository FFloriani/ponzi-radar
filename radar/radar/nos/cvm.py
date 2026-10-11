"""Nós `registros`, `cvm_sancionador` e `cvm_alertas`: a empresa está registrada, tem processo ou foi alertada?

Os três consultam os índices em cache (`Servicos.indices`, ver `radar/indices.py`), que são compartilhados entre
as execuções: o que fica na custódia de cada execução é um JSON com a consulta e as correspondências achadas
(`tipo="indice"`, `origem=<nome do índice>`), como prova do que foi olhado e do que apareceu. O `cvm_sancionador` e o
`cvm_alertas` devolvem a ref desse JSON em `artefato`: é a fonte citável dos candidatos da P-D1 e da P-C4 (no modo
cego, o Claude cita o JSON, que ele vê mascarado, em vez do NUP ou da URL da deliberação, que ele não vê).
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date

from radar.cnpj_util import cnpj_valido, normalizar_cnpj
from radar.indices import Deliberacao, Indices, RegistroCVM, vencido_desde
from radar.modelos import Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos
from radar.nos.alvo import e_plataforma
from radar.texto import normalizar

# situações do cadastro de crowdfunding sem registro concedido: não têm DT_REG, e a data ausente não pode
# valer como "registrado antes do as_of"
_SEM_REGISTRO = frozenset({"", "em analise", "registro nao concedido"})
_TAMANHO_MINIMO_DO_NOME = 8
# nome de sócio com menos palavras que isto ("João Silva") casa com muita gente: o processo entra como homônimo provável
_PALAVRAS_DO_NOME_DE_SOCIO = 3
_MARGEM_DO_TRECHO = 120


def _indices(s: Servicos) -> Indices:
    if s.indices is None:
        raise ErroNo("serviço de índices não configurado", permanente=True)
    return s.indices


def _com_vencidos(saidas: dict, **listas: object) -> dict:
    """`saidas` com `indices_vencidos` (`{nome do índice: vencido_desde em ISO}`) quando algum dos índices consultados
    é o anterior a uma renovação que falhou (I6); sem nenhum, as saídas ficam como estão."""
    vencidos = {nome: desde.isoformat() for nome, lista in listas.items() if (desde := vencido_desde(lista))}
    return {**saidas, "indices_vencidos": vencidos} if vencidos else saidas


def _guardar(s: Servicos, indice: str, consulta: dict, correspondencias: list[dict]) -> str:
    """Guarda na custódia o JSON da consulta e das correspondências; devolve a ref (`sha256:<hex>`)."""
    corpo = {"indice": indice, "consulta": consulta, "correspondencias": correspondencias}
    dados = json.dumps(corpo, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    return s.custodia.guardar(dados, "json", tipo="indice", origem=indice)


def _dominio_analisado(ctx: Contexto, entradas: dict[str, dict]) -> str:
    """O domínio que o nó `destino` escolheu (o do site para onde o alvo redireciona); sem ele, o do alvo."""
    dominio = (entradas.get("destino") or {}).get("dominio")
    return dominio if isinstance(dominio, str) and dominio.strip() else ctx.alvo


def _cnpj_da_entrada(entradas: dict[str, dict]) -> str | None:
    """O CNPJ que o nó `cnpj` achou; `None` se a empresa não foi identificada (ou se o nó não está nas entradas)."""
    cnpj = (entradas.get("cnpj") or {}).get("cnpj")
    return cnpj if isinstance(cnpj, str) and cnpj_valido(cnpj) else None


def _normalizado_com_posicoes(texto: str) -> tuple[str, list[int]]:
    """Como `normalizar` (sem acento, minúsculo), mas o que não é letra nem dígito vira um espaço só, para
    "S.A." e "S A" serem o mesmo nome. Cada caractere devolvido leva a posição de onde veio no `texto`, que
    permite citar o trecho do original."""
    saida: list[str] = []
    posicoes: list[int] = []

    def acrescentar(caractere: str, posicao: int) -> None:
        if caractere.isalnum():
            saida.append(caractere)
            posicoes.append(posicao)
        elif saida and saida[-1] != " ":
            saida.append(" ")
            posicoes.append(posicao)

    for i, c in enumerate(texto):
        if c.isascii():
            acrescentar(c.lower(), i)
            continue
        for decomposto in unicodedata.normalize("NFKD", c):
            if not unicodedata.combining(decomposto):
                for e in decomposto.casefold():
                    acrescentar(e, i)
    if saida and saida[-1] == " ":
        saida.pop()
        posicoes.pop()
    return "".join(saida), posicoes


def _chave_do_nome(nome: str) -> str:
    return _normalizado_com_posicoes(nome)[0]


# --- registros -------------------------------------------------------------------------------------


def _vigente(registro: RegistroCVM, as_of: date) -> bool:
    """O registro valia no `as_of`: `dt_reg <= as_of` e sem cancelamento até lá (no dia do cancelamento já não vale).

    Registro sem `dt_reg` conta como anterior ao `as_of`, exceto nas situações que são a ausência de registro.
    """
    if registro.dt_reg is None:
        if normalizar(registro.situacao) in _SEM_REGISTRO:
            return False
    elif registro.dt_reg > as_of:
        return False
    return registro.dt_cancel is None or registro.dt_cancel > as_of


class RegistrosNo(NoBase):
    """A empresa está registrada na CVM ou no BCB, ou o domínio é verificado pelo BCB?

    - CVM: o CNPJ de 14 caracteres tem registro vigente no `as_of` (`dt_reg <= as_of`, cancelamento nulo ou depois).
    - BCB: a raiz de 8 caracteres do CNPJ está nas sedes de bancos, sociedades, cooperativas ou consórcios.
    - Domínio: o domínio analisado (o do `destino`, opcional; sem ele, `ctx.alvo`) é um domínio verificado de alguma
      instituição do BCB.

    Sem CNPJ (o nó `cnpj` não achou a empresa) só o domínio vale e `motivo` é "sem CNPJ". O Olinda só lista o que
    funciona hoje, sem datas: no modo retroativo `bcb` e `bcb_dominio` vêm em `vazamento_temporal`, e quem pontua
    decide o que fazer com `registrado` quando só eles o sustentam.
    """

    nome = "registros"
    entradas = ("alvo", "cnpj")
    opcionais = ("destino",)
    # `indices_vencidos` só aparece quando algum índice é o anterior a uma renovação que falhou
    saidas = ("cvm", "bcb", "bcb_dominio", "registrado", "motivo", "vazamento_temporal", "indices_vencidos")
    as_of = "filtravel"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        indices = _indices(s)
        cnpj = _cnpj_da_entrada(entradas)
        dominio = _dominio_analisado(ctx, entradas).lower()
        consulta = {"cnpj": cnpj, "dominio": dominio, "as_of": ctx.as_of.isoformat()}
        cvm: list[dict] = []
        bcb: list[dict] = []
        consultados: dict[str, list] = {}
        if cnpj is not None:
            consultados["cadastros_cvm"] = await indices.cadastros_cvm()
            cvm = [
                r.model_dump(mode="json")
                for r in consultados["cadastros_cvm"]
                if r.cnpj == cnpj and _vigente(r, ctx.as_of)
            ]
            _guardar(s, "cadastros_cvm", consulta, cvm)
            consultados["instituicoes_bcb"] = await indices.instituicoes_bcb()
            bcb = [i.model_dump(mode="json") for i in consultados["instituicoes_bcb"] if i.raiz_cnpj == cnpj[:8]]
            _guardar(s, "instituicoes_bcb", consulta, bcb)
        consultados["dominios_bcb"] = await indices.dominios_bcb()
        bcb_dominio = [d.model_dump(mode="json") for d in consultados["dominios_bcb"] if d.dominio == dominio]
        _guardar(s, "dominios_bcb", consulta, bcb_dominio)
        saidas = {
            "cvm": cvm,
            "bcb": bcb,
            "bcb_dominio": bcb_dominio,
            "registrado": bool(cvm or bcb or bcb_dominio),
            "motivo": None if cnpj is not None else "sem CNPJ",
            "vazamento_temporal": ["bcb", "bcb_dominio"] if ctx.retroativo else [],
        }
        return Feito(_com_vencidos(saidas, **consultados))


# --- cvm_sancionador --------------------------------------------------------------------------------


class CvmSancionadorNo(NoBase):
    """Processos sancionadores da CVM cujo acusado é a empresa ou um sócio dela.

    O acusado casa com a razão social ou com o nome de algum sócio (sem acento, caixa nem pontuação) e o processo
    só conta se foi aberto até o `as_of`. Cada processo sai com `vinculo` ("razao_social" ou "socio"): o quadro
    de sócios é o de hoje e a fonte não tem CPF, então um homônimo de sócio pesa menos que a razão social. O nome de
    sócio com menos de 3 palavras casa com muita gente: o processo entra com `nome_curto=True` (homônimo provável).
    Os processos vão para a P-D1 como candidatos `processo_cvm`, com `artefato` (a ref do JSON guardado na custódia)
    como fonte citável, e para a seção 5 do dossiê (I7). Sem CNPJ não há nome para procurar: `processos` vazio,
    `motivo` "sem CNPJ" e nada na custódia.
    """

    nome = "cvm_sancionador"
    entradas = ("cnpj",)
    saidas = ("processos", "motivo", "artefato", "indices_vencidos")
    as_of = "filtravel"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        indices = _indices(s)
        cnpj = _cnpj_da_entrada(entradas)
        if cnpj is None:
            return Feito({"processos": [], "motivo": "sem CNPJ"})
        empresa = entradas["cnpj"]
        vinculos: dict[str, str] = {}
        if isinstance(empresa.get("razao_social"), str):
            vinculos[_chave_do_nome(empresa["razao_social"])] = "razao_social"
        for socio in empresa.get("socios") or []:
            if isinstance(socio, dict) and isinstance(socio.get("nome"), str):
                vinculos.setdefault(_chave_do_nome(socio["nome"]), "socio")
        vinculos.pop("", None)
        curtos = {
            chave for chave, vinculo in vinculos.items()
            if vinculo == "socio" and len(chave.split()) < _PALAVRAS_DO_NOME_DE_SOCIO
        }  # fmt: skip

        todos = await indices.sancionador()
        achados = []
        for p in todos:
            chave = _chave_do_nome(p.acusado)
            vinculo = vinculos.get(chave)
            if vinculo is not None and p.data_abertura is not None and p.data_abertura <= ctx.as_of:
                achados.append(
                    {
                        "nup": p.nup,
                        "objeto": p.objeto,
                        "data_abertura": p.data_abertura.isoformat(),
                        "fase": p.fase,
                        "acusado": p.acusado,
                        "situacao": p.situacao,
                        "vinculo": vinculo,
                        "nome_curto": chave in curtos,
                    }
                )
        achados.sort(key=lambda a: (a["data_abertura"], a["nup"], a["acusado"]), reverse=True)
        consulta = {
            "cnpj": cnpj,
            "as_of": ctx.as_of.isoformat(),
            "nomes_consultados": len(vinculos),
            "processos_consultados": len(todos),
        }
        artefato = _guardar(s, "sancionador", consulta, achados)
        return Feito(_com_vencidos({"processos": achados, "motivo": None, "artefato": artefato}, sancionador=todos))


# --- cvm_alertas -----------------------------------------------------------------------------------


def _padrao_cnpj(cnpj: str) -> re.Pattern[str]:
    """O CNPJ com ou sem `.`, `/` e `-`, em qualquer caixa, sem estar colado a outro número ou palavra.

    Um espaço ou uma quebra de linha depois de cada separador também vale: a extração de texto de PDF deixa
    "06.151.776/0001- 99" e quebra a linha no meio do número.
    """
    raiz, ordem, dv = cnpj[:8], cnpj[8:12], cnpj[12:]
    corpo = rf"{raiz[:2]}\.?\s?{raiz[2:5]}\.?\s?{raiz[5:]}/?\s?{ordem}-?\s?{dv}"
    return re.compile(rf"(?<![0-9A-Za-z]){corpo}(?![0-9A-Za-z])", re.IGNORECASE)


def _padrao_dominio(dominio: str) -> re.Pattern[str]:
    """O domínio como domínio inteiro: `www.` e outros subdomínios valem, `santotrader.com.br` ou
    `meu-santotrader.com` não são `santotrader.com`. O ponto final da frase não faz parte dele."""
    return re.compile(
        r"(?<![A-Za-z0-9\-])" + re.escape(dominio) + r"(?![A-Za-z0-9\-]|\.[A-Za-z0-9])", re.IGNORECASE
    )


def _correspondencia(tipo: str, valor: str, d: Deliberacao, inicio: int, fim: int) -> dict:
    """A correspondência de `valor` em `d.texto[inicio:fim]`, com 120 caracteres de contexto de cada lado."""
    trecho = d.texto[max(0, inicio - _MARGEM_DO_TRECHO) : fim + _MARGEM_DO_TRECHO]
    return {
        "tipo": tipo,
        "valor": valor,
        "numero": d.numero,
        "data": d.data.isoformat() if d.data is not None else None,
        "url": d.url,
        "trecho": " ".join(trecho.split()),
    }


def casar_deliberacoes(
    delibs: list[Deliberacao],
    cnpj: str | None,
    dominio: str | None,
    nomes: list[str | None],
    as_of: date,
) -> list[dict]:
    """As deliberações de atuação irregular que citam o CNPJ, o domínio ou um dos nomes.

    Devolve, da mais nova para a mais antiga e dentro de cada deliberação na ordem cnpj, domínio, nomes, uma
    correspondência por (deliberação, tipo, valor): `{"tipo", "valor", "numero", "data", "url", "trecho"}`.

    - `cnpj`: formatado ou só os caracteres (com espaço ou quebra de linha depois dos separadores, como o PDF deixa),
      sem colar em outro número;
    - `dominio`: sem diferenciar maiúsculas, como domínio inteiro (subdomínio vale). O de uma plataforma de conteúdo
      (`alvo.PLATAFORMAS`) não casa: a deliberação que cita instagram.com fala de um perfil, não do alvo;
    - `nome`: o nome sem acento, caixa nem pontuação, de 8 ou mais caracteres, como palavras inteiras;
    - só entram deliberações com `data <= as_of` (sem data não dá para saber se já existia).
    """
    cnpj = normalizar_cnpj(cnpj) if cnpj else None
    padrao_cnpj = _padrao_cnpj(cnpj) if cnpj else None
    dominio = dominio.strip().lower() if dominio else None
    if dominio and e_plataforma(dominio):
        dominio = None
    padrao_dominio = _padrao_dominio(dominio) if dominio else None
    padroes_nomes: dict[str, re.Pattern[str]] = {}
    for nome in nomes:
        chave = _chave_do_nome(nome) if nome else ""
        if len(chave) >= _TAMANHO_MINIMO_DO_NOME and chave not in padroes_nomes:
            padroes_nomes[chave] = re.compile(r"(?<!\w)" + re.escape(chave) + r"(?!\w)")

    correspondencias = []
    for d in sorted(delibs, key=lambda d: d.numero, reverse=True):
        if d.data is None or d.data > as_of:
            continue

        if padrao_cnpj and (m := padrao_cnpj.search(d.texto)):
            correspondencias.append(_correspondencia("cnpj", cnpj, d, m.start(), m.end()))
        if padrao_dominio and (m := padrao_dominio.search(d.texto)):
            correspondencias.append(_correspondencia("dominio", dominio, d, m.start(), m.end()))
        if padroes_nomes:
            texto_normalizado, posicoes = _normalizado_com_posicoes(d.texto)
            for chave, padrao in padroes_nomes.items():
                if m := padrao.search(texto_normalizado):
                    inicio, fim = posicoes[m.start()], posicoes[m.end() - 1] + 1
                    correspondencias.append(_correspondencia("nome", chave, d, inicio, fim))
    return correspondencias


class CvmAlertasNo(NoBase):
    """Deliberações de "Atuação Irregular" da CVM (stop orders) que citam a empresa ou o site.

    Casa por CNPJ e razão social/nome fantasia quando o nó `cnpj` identificou a empresa; sem ele (nó em erro ou
    empresa não achada), só pelo domínio: o do `destino` (opcional; sem ele, `ctx.alvo`). A pontuação confirma o item C4 sozinha com `cnpj` ou `dominio`; o `nome`
    vai para a pendência P-C4. O ato conta a partir da data dele (`as_of` exato).

    `cobertura` diz em quantas das deliberações consultadas (as de data até o `as_of`) o texto integral foi lido
    e em quantas só o resumo, que quase nunca traz CNPJ nem domínio: sem correspondência, o resultado só vale
    como evidência negativa para as `com_texto_integral`. `artefato` é a ref do JSON guardado na custódia, a fonte
    citável das deliberações que vão para a P-C4.
    """

    nome = "cvm_alertas"
    entradas = ("alvo",)
    opcionais = ("cnpj", "destino")
    saidas = ("correspondencias", "cobertura", "artefato", "indices_vencidos")
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito:
        indices = _indices(s)
        cnpj = _cnpj_da_entrada(entradas)
        empresa = entradas.get("cnpj") or {}
        nomes = [empresa.get("razao_social"), empresa.get("nome_fantasia")] if cnpj else []
        delibs = await indices.deliberacoes()
        dominio = _dominio_analisado(ctx, entradas)
        correspondencias = casar_deliberacoes(delibs, cnpj, dominio, nomes, ctx.as_of)
        consultadas = [d for d in delibs if d.data is not None and d.data <= ctx.as_of]
        integrais = sum(d.integral for d in consultadas)
        cobertura = {"com_texto_integral": integrais, "so_resumo": len(consultadas) - integrais}
        consulta = {"dominio": dominio, "cnpj": cnpj, "as_of": ctx.as_of.isoformat(), "cobertura": cobertura}
        artefato = _guardar(s, "deliberacoes", consulta, correspondencias)
        saidas = {"correspondencias": correspondencias, "cobertura": cobertura, "artefato": artefato}
        return Feito(_com_vencidos(saidas, deliberacoes=delibs))
