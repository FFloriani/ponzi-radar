"""Dossiê de risco (spec 8.4): o `dossie.md` que o usuário lê, a `pontuacao.json` e, havendo execução anterior, o
`diff.md`.

`gerar_dossie` lê a execução gravada em disco, pontua com a matriz dada, monta os dados de cada seção aqui e deixa
o texto para o template `dossie.md.j2`. O template é Markdown, sem escape automático: tudo o que vem do site, das
fontes ou do Claude passa pelo filtro `md` (uma linha só, `|` e formatação escapados, sem CPF) e URLs e hashes de
tabela pelo filtro `cod`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import ValidationError

from radar.arquivos import gravar_json_atomico
from radar.custodia import hash_final, registros
from radar.diff import (
    NOME_DA_PONTUACAO,
    ROTULO_DO_ESTADO,
    Alerta,
    Diff,
    Pontuacao,
    alertas_da_execucao,
    comparar,
    data_iso,
    julgamento_ativo,
    ler_anterior,
    pontuar,
    renderizar_diff,
    saida,
    status_do_no,
    texto_classe,
    texto_intervalo,
    total_de_pontos,
    valor_confirmado,
)
from radar.execucao import ExecucaoSalva, carregar_execucao
from radar.modelos import Evidencia, Item, Sinal
from radar.pendencias.esquemas import ValorD1
from radar.pontuacao import PREFIXO_CAPTURA_INDISPONIVEL, Matriz, dominio_reaproveitado
from radar.texto import codigo_md, escapar_md

__all__ = ["PendenciasAbertas", "gerar_dossie"]

_ORIGEM = {"coletor": "coletor", "regex_confirmada": "regex confirmada", "claude": "Claude", "nenhuma": "—"}
_DIRECAO = {
    "encurta": "encurta a janela",
    "alonga": "alonga a janela",
    "corte_sem_aviso": "corte possível sem aviso",
}
SUFIXO_REGISTRO_ANTERIOR = " (registro anterior do domínio)"
_ORIGENS_COM_JULGAMENTO = frozenset({"regex_confirmada", "claude"})  # as marcas são do julgamento do Claude
# os itens que o coletor pontua, e os nós de onde vem a conta de cada um (coluna Fonte da tabela)
_NOS_DO_COLETOR = {"C1": "registros", "C3": "cnpj", "C4": "cvm_alertas", "D3": "rdap, cnpj"}
# o nó pulado que deixa dado sem cobertura (só o presente, sem visita ao alvo, dependência pulada); os outros
# pulados (`captura ok`, pendência que não se aplica) não são lacuna
_PULADO_COM_LACUNA = ("só atual", "modo_contato=nenhum", "dependência pulada")
_PENDENCIA = re.compile(r"P-[A-Z0-9]+")
_DEPENDENCIA = re.compile(r"^dependência (?:com erro|bloqueada): (.+)$")
_SEM_DIFF_RETROATIVA = "Execução retroativa: sem comparação com execuções atuais."
_SEM_DIFF_PRIMEIRA = "Não há execução anterior deste alvo em modo atual para comparar."
_PREFIXO_HASH = "sha256:"
_HASH_CURTO = len(_PREFIXO_HASH) + 12
_MAX_SANS = 20
_MAX_TERCEIROS = 20
_MAX_PAGINAS = 10
_NA = "—"
# o `redirect_ignorado.motivo` da captura é um identificador (`nos.captura._destino_do_redirect`); o dossiê o escreve
# em português. Um motivo que não está aqui (uma saída de versão futura) sai como veio.
_MOTIVO_DO_REDIRECT_IGNORADO = {
    "plataforma": "plataforma",
    "estacionamento": "estacionamento de domínio",
    "servico_de_terceiro": "serviço de terceiro",
}
_AMBIENTE = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    undefined=StrictUndefined,
    autoescape=False,  # a saída é Markdown: o escape é o dos filtros
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
_AMBIENTE.filters["md"] = escapar_md
_AMBIENTE.filters["cod"] = codigo_md


class PendenciasAbertas(Exception):
    """O dossiê pede as pendências respondidas. `ids` são as que ainda estão abertas."""

    def __init__(self, ids: list[str]) -> None:
        super().__init__("pendências abertas: " + ", ".join(ids))
        self.ids = ids


# ---------------------------------------------------------------------------- custódia


class _Custodia:
    """O que o `custodia.log` diz de cada hash, para citar a fonte e o hash de cada evidência e montar o anexo."""

    def __init__(self, pasta: Path) -> None:
        self.registros = registros(pasta)
        self.por_hash: dict[str, dict] = {}
        self.fonte_por_url: dict[str, str] = {}
        for registro in self.registros:
            hex_ = registro.get("sha256")
            if not isinstance(hex_, str):
                continue
            self.por_hash.setdefault(hex_, registro)
            if registro.get("tipo") == "fonte" and isinstance(registro.get("origem"), str):
                self.fonte_por_url[registro["origem"]] = hex_  # a mais recente vale

    def fonte_e_hash(self, evidencia: Evidencia) -> tuple[str, str]:
        """A fonte como citar e o hash do artefato dela. `sha256:<hex>` cita um artefato da custódia (a fonte é o que
        o log diz dele: tipo e origem); uma URL tem o hash do que foi arquivado dela (`tipo=fonte`, `origem=url`), se
        foi arquivada (senão, hash vazio)."""
        fonte = evidencia.fonte.strip()
        if fonte.startswith(_PREFIXO_HASH):
            registro = self.por_hash.get(fonte.removeprefix(_PREFIXO_HASH))
            if registro is None:
                return "artefato da custódia", fonte
            return f"{registro.get('tipo')}: {registro.get('origem')}", fonte
        hex_ = self.fonte_por_url.get(fonte)
        return fonte, (_PREFIXO_HASH + hex_) if hex_ else ""

    def artefatos(self) -> list[dict]:
        """Um item por hash, na ordem do log: o primeiro `seq`, os tipos com que foi registrado, a primeira origem e
        quantas outras origens o mesmo conteúdo teve."""
        agrupados: dict[str, dict] = {}
        for registro in self.registros:
            hex_ = registro.get("sha256")
            if not isinstance(hex_, str):
                continue
            item = agrupados.setdefault(hex_, {"seq": registro.get("seq"), "tipos": [], "origens": []})
            for chave, campo in (("tipos", "tipo"), ("origens", "origem")):
                if registro.get(campo) not in item[chave]:
                    item[chave].append(registro.get(campo))
        return [
            {
                "hash": _PREFIXO_HASH + hex_,
                "seq": item["seq"],
                "tipos": ", ".join(map(str, item["tipos"])),
                "origem": item["origens"][0],
                "outras": len(item["origens"]) - 1,
            }
            for hex_, item in agrupados.items()
        ]


# ---------------------------------------------------------------------------- cabeçalho e veredito


def _hash_da_custodia(pasta: Path) -> tuple[str | None, bool]:
    """`(hash final, custódia ilegível)`: a última linha ilegível do log não impede o dossiê, só o hash."""
    try:
        return hash_final(pasta), False
    except ValueError:
        return None, True


def _cabecalho(ex: ExecucaoSalva, matriz: Matriz, pasta: Path) -> dict:
    ctx = ex.ctx
    hash_custodia, custodia_ilegivel = _hash_da_custodia(pasta)
    return {
        "alvo": ctx.alvo,
        "url_inicial": ctx.url_inicial,
        "data_execucao": ctx.data_execucao.isoformat(sep=" ", timespec="seconds"),
        "as_of": ctx.as_of.isoformat(),
        "retroativo": ctx.retroativo,
        "modo_contato": ctx.modo_contato,
        "modo_cego": "sim" if ctx.modo_cego else "não",
        "run_id": ctx.run_id,
        "matriz_versao": matriz.versao,
        "matriz_hash": matriz.hash,
        "hash_custodia": hash_custodia,
        "custodia_ilegivel": custodia_ilegivel,
        "parametros_removidos": _parametros_removidos(ex),
        "redirecionamento": _redirecionamento(ex),
        "redirect_ignorado": _redirect_ignorado(ex),
    }


def _redirecionamento(ex: ExecucaoSalva) -> dict | None:
    """O redirect que os coletores seguiram (saída do nó `destino`): `{"de", "url", "dominio"}`, ou `None` sem ele."""
    destino = saida(ex, "destino") or {}
    de, url, dominio = destino.get("redirecionado_de"), destino.get("url_destino"), destino.get("dominio")
    if not all(isinstance(valor, str) and valor for valor in (de, url, dominio)):
        return None
    return {"de": de, "url": url, "dominio": dominio}


def _redirect_ignorado(ex: ExecucaoSalva) -> dict | None:
    """O redirect da página inicial para plataforma, estacionamento ou serviço de terceiro, que a captura não seguiu
    (`redirect_ignorado`): `{"url", "motivo"}` (o motivo em português), ou `None` sem ele."""
    ignorado = (saida(ex, "captura") or {}).get("redirect_ignorado")
    if not isinstance(ignorado, dict) or not isinstance(ignorado.get("url"), str) or not ignorado["url"]:
        return None
    motivo = str(ignorado.get("motivo") or _NA)
    return {"url": ignorado["url"], "motivo": _MOTIVO_DO_REDIRECT_IGNORADO.get(motivo, motivo)}


def _parametros_removidos(ex: ExecucaoSalva) -> list[str]:
    """Os parâmetros de indicação tirados da URL dada: da saída do nó `alvo` ou, sem ela, do contexto."""
    removidos = (saida(ex, "alvo") or {}).get("parametros_removidos", ex.ctx.parametros_removidos)
    return [str(nome) for nome in removidos] if isinstance(removidos, list) else []


def _regra(matriz: Matriz, id_: str) -> str:
    regra = next((r for r in matriz.regras_corte if r.id == id_), None)
    if regra is None:
        return id_
    if regra.tipo == "classe_fixa":
        return f"{id_}: classe {regra.classe}, com o sinal {regra.sinal}"
    return f"{id_}: classe mínima {regra.classe}"


def _fonte_da(evidencia: Evidencia | None, custodia: _Custodia) -> str:
    """A fonte de uma evidência para citar numa linha (vazia se não há evidência: o sinal é do coletor)."""
    return custodia.fonte_e_hash(evidencia)[0] if evidencia is not None else ""


def _veredito(matriz: Matriz, pont: Pontuacao, forcadas: list[str], custodia: _Custodia) -> dict:
    eixo1, eixo2 = pont.eixo1, pont.eixo2
    sinal = None
    if eixo2.sinal is not None:
        sinal = {
            "tipo": eixo2.sinal.tipo,
            "data": eixo2.sinal.data.isoformat() if eixo2.sinal.data else "sem data",
            "tipo_fonte": eixo2.sinal.tipo_fonte,
            "fonte": _fonte_da(eixo2.sinal.evidencia, custodia),
        }
    return {
        "forcadas": forcadas,
        "intervalo": texto_intervalo(eixo1.minimo, eixo1.maximo, total_de_pontos(matriz)),
        "classe": texto_classe(eixo1),
        "regras_disparadas": [_regra(matriz, id_) for id_ in eixo1.regras_disparadas],
        "regras_pendentes": eixo1.regras_pendentes,
        "estagio": eixo2.estagio,
        "sinal": sinal,
        "janela": eixo2.janela,
        "modificadores": [
            {
                "id": m.id,
                "direcao": _DIRECAO.get(m.direcao, m.direcao),
                "origem": m.origem,
                "fonte": _fonte_da(m.evidencia, custodia),
            }
            for m in eixo2.modificadores
        ],
    }


# ---------------------------------------------------------------------------- itens


def _pontos(item: Item) -> str:
    if item.estado == "confirmado":
        return f"{item.pontos}/{item.maximo}"
    if item.estado in ("nao_verificado", "inconclusivo"):
        return f"0–{item.maximo}"
    return f"0/{item.maximo}"


def _marcas_das_evidencias(julgamento: dict, marcas: list[str], item: Item) -> list[str]:
    """As marcas por evidência (`marca:evidencias[i]`) das evidências que o item cita, sem repetir."""
    evidencias = (julgamento.get("resposta") or {}).get("evidencias")
    indices = set()
    for i, bruta in enumerate(evidencias if isinstance(evidencias, list) else []):
        try:
            if Evidencia.model_validate(bruta) in item.evidencias:
                indices.add(f"evidencias[{i}]")
        except ValidationError:
            continue
    return list(dict.fromkeys(m.partition(":")[0] for m in marcas if m.partition(":")[2] in indices))


def _marcas(ex: ExecucaoSalva, id_: str, item: Item) -> list[str]:
    """As marcas de validação (`trecho_nao_conferido`, `data_desconhecida`) do julgamento ativo da pendência do item.
    O item do coletor não tem julgamento por trás: as marcas da pendência não são dele. Com as marcas por evidência
    (I3), o item leva só as das evidências que ele cita; um julgamento só com as agregadas as dá a todos os itens."""
    if item.origem not in _ORIGENS_COM_JULGAMENTO:
        return []
    for pid, pendencia in ex.pendencias.items():
        if id_ in (pendencia.get("itens") or []):
            julgamento = julgamento_ativo(ex, pid) or {}
            marcas = julgamento.get("marcas", [])
            marcas = [m for m in marcas if isinstance(m, str)] if isinstance(marcas, list) else []
            if any(":" in m for m in marcas):
                return _marcas_das_evidencias(julgamento, marcas, item)
            return marcas
    return []


def _linhas_dos_itens(ex: ExecucaoSalva, matriz: Matriz, itens: dict[str, Item], custodia: _Custodia) -> list[dict]:
    """Uma linha por evidência do item confirmado (as do item que pontuou); os outros ficam com uma linha só. Só a
    primeira linha do item leva estado, pontos, origem, marcas e nota."""
    linhas = []
    for id_, item in itens.items():
        evidencias = item.evidencias if item.estado == "confirmado" else []
        primeira = {
            "item": f"{id_} — {matriz.itens[id_].nome}",
            "estado": ROTULO_DO_ESTADO[item.estado],
            "pontos": _pontos(item),
            "origem": _ORIGEM[item.origem],
            "marcas": _marcas(ex, id_, item),
            "sem_marcas": _NA,
            "nota": item.nota or "",
        }
        coletor = f"coletor: {_NOS_DO_COLETOR[id_]}" if item.origem == "coletor" and id_ in _NOS_DO_COLETOR else ""
        if not evidencias:
            linhas.append({**primeira, "trecho": _NA, "meta": coletor, "fonte": "", "hash": ""})
        for n, evidencia in enumerate(evidencias):
            fonte, hash_ = custodia.fonte_e_hash(evidencia)
            data = evidencia.data_fonte.isoformat() if evidencia.data_fonte else "sem data"
            meta = f"{evidencia.tipo_fonte}, {data}"
            continuacao = dict.fromkeys(primeira, "") | {"item": id_}
            linhas.append(
                {
                    **(primeira if n == 0 else continuacao),
                    "trecho": evidencia.trecho,
                    "meta": f"{coletor}; {meta}" if coletor else meta,
                    "fonte": fonte,
                    "hash": hash_[:_HASH_CURTO],
                }
            )
    return linhas


# ---------------------------------------------------------------------------- linha do tempo


def _evento(data: str | None, evento: str, fonte: str, url: str = "") -> dict:
    return {"data": data or "sem data", "ordem": data, "evento": evento, "fonte": fonte, "url": url}


def _linha_do_tempo(ex: ExecucaoSalva, sinais: list[Sinal], alertas: list[Alerta], custodia: _Custodia) -> list[dict]:
    """Registro do domínio, abertura do CNPJ, primeiro certificado, primeiro e último snapshot, alertas e sinais,
    por data (o que não tem data vai para o fim).

    Com o domínio reaproveitado, os eventos de histórico do domínio (certificado e snapshots) anteriores ao registro
    levam o sufixo `SUFIXO_REGISTRO_ANTERIOR` e o evento "Domínio registrado de novo" toma o lugar do "Domínio
    registrado"."""
    reaproveitado = dominio_reaproveitado(ex)
    registro = reaproveitado["registro"] if reaproveitado is not None else None

    def historico(data: str, rotulo: str, fonte: str) -> dict:
        anterior = registro is not None and data < registro  # as duas são AAAA-MM-DD: a ordem do texto é a da data
        return _evento(data, rotulo + SUFIXO_REGISTRO_ANTERIOR if anterior else rotulo, fonte)

    eventos = []
    if reaproveitado is not None:  # toma o lugar do "Domínio registrado": a data é a mesma
        eventos.append(
            _evento(
                reaproveitado["registro"],
                "Domínio registrado de novo; o histórico anterior pode ser de outro dono",
                f"RDAP e {reaproveitado['fonte_historico']}",
            )
        )
    elif (rdap := saida(ex, "rdap")) and data_iso(rdap.get("registro")):
        eventos.append(_evento(rdap["registro"][:10], "Domínio registrado", "RDAP"))
    if (cnpj := saida(ex, "cnpj")) and cnpj.get("cnpj") and data_iso(cnpj.get("abertura")):
        eventos.append(_evento(cnpj["abertura"][:10], "CNPJ aberto", f"Receita Federal ({cnpj.get('fonte') or '?'})"))
    if (ct := saida(ex, "ct")) and data_iso(ct.get("primeiro_certificado")):
        eventos.append(historico(ct["primeiro_certificado"][:10], "Primeiro certificado TLS", "crt.sh"))
    if (wayback := saida(ex, "wayback_indice")) is not None:
        for chave, rotulo in (("primeiro", "Primeiro snapshot no Wayback"), ("ultimo", "Último snapshot no Wayback")):
            if data_iso(wayback.get(chave)):
                eventos.append(historico(wayback[chave][:10], rotulo, "Wayback CDX"))
    for alerta in alertas:
        eventos.append(_evento(alerta.data, alerta.rotulo, "alerta oficial", alerta.fonte or ""))
    for sinal in sinais:
        rotulo = f"Sinal {sinal.tipo}" + (f" ({sinal.estagio})" if sinal.estagio else "")
        data = sinal.data.isoformat() if sinal.data else None
        eventos.append(_evento(data, rotulo, sinal.tipo_fonte, _fonte_da(sinal.evidencia, custodia)))
    return sorted(eventos, key=lambda e: (e["ordem"] is None, e["ordem"] or ""))


# ---------------------------------------------------------------------------- empresa e pessoas


def _nao_disponivel(ex: ExecucaoSalva, no: str) -> str:
    """Por que o nó não tem resultado: "nó dns pulado: só atual"."""
    status, motivo = status_do_no(ex, no), (ex.status.get(no) or {}).get("motivo")
    if status is None:
        return f"nó {no} não executado"
    return f"nó {no} {status}" + (f": {motivo}" if motivo else "")


def _cnpj_formatado(cnpj: str) -> str:
    if len(cnpj) != 14:
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def _empresa(ex: ExecucaoSalva) -> dict:
    """Os campos da Receita para o dossiê. `hoje` marca o que o nó `cnpj` guardou em `vazamento_temporal`: no modo
    retroativo é o dado de hoje, não o do `as_of`. Sócios: só nome, qualificação e entrada."""
    dados = saida(ex, "cnpj")
    if dados is None:
        return {"situacao": "indisponivel", "motivo": _nao_disponivel(ex, "cnpj"), "campos": [], "socios": []}
    if dados.get("cnpj") is None:
        return {"situacao": "sem_cnpj", "motivo": str(dados.get("motivo") or ""), "campos": [], "socios": []}
    vazados = set(dados.get("vazamento_temporal") or ())
    cnae = dados.get("cnae")
    codigo = f"{cnae:07d}" if isinstance(cnae, int) and not isinstance(cnae, bool) else None
    campos = [
        ("CNPJ", _cnpj_formatado(str(dados["cnpj"])), "cnpj"),
        ("Razão social", dados.get("razao_social"), "razao_social"),
        ("Nome fantasia", dados.get("nome_fantasia"), "nome_fantasia"),
        ("Abertura", dados.get("abertura"), "abertura"),
        ("CNAE", " — ".join(p for p in (codigo, dados.get("cnae_descricao")) if p), "cnae"),
        ("Situação", dados.get("situacao"), "situacao"),
        ("Fonte dos dados", dados.get("fonte"), "fonte"),
    ]
    socios = [
        {"nome": s["nome"], "qualificacao": s.get("qualificacao") or _NA, "entrada": s.get("entrada") or _NA}
        for s in dados.get("socios") or []
        if isinstance(s, dict) and isinstance(s.get("nome"), str)
    ]
    return {
        "situacao": "ok",
        "motivo": "",
        "campos": [{"rotulo": r, "valor": v or _NA, "hoje": campo in vazados} for r, v, campo in campos],
        "socios": socios,
        "socios_hoje": "socios" in vazados,
    }


def _cadastro_cvm(r: dict) -> str:
    return f"{r.get('denominacao')} ({r.get('cadastro')}, {r.get('situacao')})"


def _instituicao_bcb(r: dict) -> str:
    return f"{r.get('nome')} ({r.get('conjunto')})"


def _dominio_bcb(r: dict) -> str:
    return f"{r.get('dominio')} ({r.get('instituicao')})"


def _registros_oficiais(ex: ExecucaoSalva) -> dict:
    dados = saida(ex, "registros")
    if dados is None:
        return {"motivo": _nao_disponivel(ex, "registros"), "linhas": [], "nota": ""}
    vazados = set(dados.get("vazamento_temporal") or ())

    def linha(rotulo: str, campo: str, texto) -> dict:
        lista = dados.get(campo)
        valores = [t for r in lista if isinstance(r, dict) and (t := texto(r))] if isinstance(lista, list) else []
        return {"rotulo": rotulo, "valor": "; ".join(valores) or "nenhum", "hoje": campo in vazados}

    return {
        "motivo": "",
        "linhas": [
            linha("Registro na CVM", "cvm", _cadastro_cvm),
            linha("Instituição autorizada pelo BCB", "bcb", _instituicao_bcb),
            linha("Domínio verificado pelo BCB", "bcb_dominio", _dominio_bcb),
        ],
        "nota": "Sem CNPJ: só o domínio foi consultado." if dados.get("motivo") == "sem CNPJ" else "",
    }


_VINCULO_DO_PROCESSO = {"razao_social": "razão social", "socio": "sócio"}


def _processos_sancionadores(ex: ExecucaoSalva) -> list[dict]:
    """Os processos sancionadores da CVM que o coletor ligou à empresa ou a um sócio (I7); o nome curto de sócio leva
    o aviso de homônimo provável."""
    processos = (saida(ex, "cvm_sancionador") or {}).get("processos")
    linhas = []
    for p in processos if isinstance(processos, list) else []:
        if not isinstance(p, dict):
            continue
        vinculo = _VINCULO_DO_PROCESSO.get(p.get("vinculo"), str(p.get("vinculo") or _NA))
        if p.get("nome_curto") is True:
            vinculo += ", nome curto: possível homônimo"
        linhas.append(
            {
                "nup": str(p.get("nup") or _NA),
                "objeto": str(p.get("objeto") or _NA),
                "acusado": str(p.get("acusado") or _NA),
                "vinculo": vinculo,
                "abertura": str(p.get("data_abertura") or _NA),
                "situacao": str(p.get("situacao") or _NA),
            }
        )
    return linhas


def _pessoas_com_vinculo(ex: ExecucaoSalva, itens: dict[str, Item]) -> list[dict]:
    """As pessoas que a P-D1 ligou a esquemas, com o vínculo (nome e vínculo; nunca documento)."""
    if itens["D1"].estado != "confirmado" or (valor := valor_confirmado(ex, "P-D1")) is None:
        return []
    try:
        d1 = ValorD1.model_validate(valor)
    except ValidationError:
        return []
    return [{"nome": p.pessoa, "vinculo": p.vinculo} for p in d1.pessoas] if d1.historico_fraude else []


# ---------------------------------------------------------------------------- infraestrutura


def _textos(dados: dict | None, chave: str) -> list[str]:
    valores = (dados or {}).get(chave)
    return [v for v in valores if isinstance(v, str)] if isinstance(valores, list) else []


def _resumo_dos_meses(meses: list[str]) -> dict:
    """Quantos meses têm captura no Wayback e o primeiro e o último (`AAAA-MM`, em ordem)."""
    return {"quantidade": len(meses), "primeiro": meses[0] if meses else "", "ultimo": meses[-1] if meses else ""}


def _infraestrutura(ex: ExecucaoSalva) -> dict:
    rdap, dns, ct = saida(ex, "rdap"), saida(ex, "dns"), saida(ex, "ct")
    wayback, captura = saida(ex, "wayback_indice"), saida(ex, "captura")
    sans, terceiros = _textos(ct, "sans"), _textos(captura, "terceiros")
    meses = sorted((wayback or {}).get("por_mes") or {})
    paginas = [p for p in (captura or {}).get("paginas") or [] if isinstance(p, dict)]
    return {
        "rdap": rdap,
        "rdap_falta": _nao_disponivel(ex, "rdap") if rdap is None else "",
        "dns": dns,
        "dns_falta": _nao_disponivel(ex, "dns") if dns is None else "",
        "hospedagem": _textos(dns, "A") + _textos(dns, "AAAA"),
        "mx": _textos(dns, "MX"),
        "ns": _textos(dns, "NS"),
        "ct": ct,
        "ct_falta": _nao_disponivel(ex, "ct") if ct is None else "",
        "sans": sans[:_MAX_SANS],
        "sans_a_mais": max(0, len(sans) - _MAX_SANS),
        "wayback": wayback,
        "wayback_falta": _nao_disponivel(ex, "wayback_indice") if wayback is None else "",
        "reaproveitado": dominio_reaproveitado(ex),
        "meses": _resumo_dos_meses(meses),
        "captura": captura,
        "captura_falta": _nao_disponivel(ex, "captura") if captura is None else "",
        "paginas": [{"url": p.get("url"), "status": p.get("status")} for p in paginas[:_MAX_PAGINAS]],
        "paginas_a_mais": max(0, len(paginas) - _MAX_PAGINAS),
        "terceiros": terceiros[:_MAX_TERCEIROS],
        "terceiros_a_mais": max(0, len(terceiros) - _MAX_TERCEIROS),
    }


# ---------------------------------------------------------------------------- lacunas


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


def _resolver_no(ex: ExecucaoSalva, no: str, status: str, motivo: str) -> str:
    """O que resolveria o nó sem resultado. Vazio para `pulado`: o dado não existe nessa execução (só o presente,
    sem visita ao alvo) e rodar de novo não muda isso."""
    if status == "bloqueado":
        dependencia = _DEPENDENCIA.match(motivo)
        if dependencia is not None:
            return f"resolver a dependência {dependencia.group(1)}"
        return f"resolver a dependência ({motivo.rpartition(': ')[2]})" if motivo else "resolver a dependência"
    if status == "aguardando":
        abertas = [pid for pid, p in ex.pendencias.items() if p.get("aberta") and p.get("no_origem") == no]
        return "; ".join(f"responder a {pid}" for pid in abertas)
    if status == "erro" and motivo.startswith(PREFIXO_CAPTURA_INDISPONIVEL):
        return "conferir o ambiente do analista (Chromium instalado, proxy no ar) e rodar de novo a análise"
    if status in ("erro", "pendente", "executando"):
        return "rodar de novo a análise"
    return ""


def _nos_sem_resultado(ex: ExecucaoSalva) -> list[dict]:
    nos = []
    for no, estado in ex.status.items():
        status, motivo = estado.get("status"), estado.get("motivo") or ""
        if status == "feito" or (status == "pulado" and not motivo.startswith(_PULADO_COM_LACUNA)):
            continue
        nos.append({"no": no, "status": status, "motivo": motivo, "resolve": _resolver_no(ex, no, status, motivo)})
    return nos


def _resolver_item(ex: ExecucaoSalva, id_: str, item: Item) -> str:
    """A pendência que resolve o item: a que a nota cita (`P-CNPJ inconclusiva...`) ou, sem citação, a que o cobre.
    Aberta: responder. Já respondida como `inconclusivo`: responder de novo, com evidência."""
    citadas = [pid for pid in _PENDENCIA.findall(item.nota or "") if pid in ex.pendencias]
    pids = citadas or [pid for pid, p in ex.pendencias.items() if id_ in (p.get("itens") or [])]
    acoes = []
    for pid in pids:
        if ex.pendencias[pid].get("aberta"):
            acoes.append(f"responder a {pid}")
        elif item.estado == "inconclusivo":
            acoes.append(f"responder de novo a {pid} com evidência")
    return "; ".join(acoes)


def _lacunas(ex: ExecucaoSalva, itens: dict[str, Item]) -> dict:
    """Nós sem resultado e itens `nao_verificado` ou `inconclusivo`, cada um com o que o resolveria, e o que limita a
    cobertura das fontes. O nó pulado só entra quando deixa dado sem cobertura (`_PULADO_COM_LACUNA`)."""
    em_aberto = []
    for id_, item in itens.items():
        if item.estado in ("nao_verificado", "inconclusivo"):
            em_aberto.append(
                {
                    "id": id_,
                    "estado": ROTULO_DO_ESTADO[item.estado],
                    "nota": item.nota or "",
                    "resolve": _resolver_item(ex, id_, item),
                }
            )
    fontes = []
    so_resumo = ((saida(ex, "cvm_alertas") or {}).get("cobertura") or {}).get("so_resumo")
    if isinstance(so_resumo, int) and so_resumo > 0:
        fontes.append(
            f"{so_resumo} {_plural(so_resumo, 'deliberação', 'deliberações')} da CVM "
            f"{_plural(so_resumo, 'só tem resumo', 'só têm resumo')}: sem prova negativa por CNPJ ou domínio nelas."
        )
    vistos: set[str] = set()
    for no in ("registros", "cvm_sancionador", "cvm_alertas"):
        vencidos = (saida(ex, no) or {}).get("indices_vencidos")
        for indice, desde in (vencidos.items() if isinstance(vencidos, dict) else ()):
            if indice not in vistos and (data := data_iso(desde)) is not None:
                vistos.add(indice)
                fontes.append(
                    f"Índice {indice} vencido desde {data.isoformat()} (a renovação falhou; {no} usou a cópia "
                    "anterior): o que mudou depois disso não foi visto."
                )
    if (saida(ex, "wayback_indice") or {}).get("truncado") is True:
        fontes.append(
            "A listagem do Wayback veio truncada (limite do CDX): o total e o primeiro e o último snapshot podem "
            "não cobrir todo o domínio."
        )
    return {"nos": _nos_sem_resultado(ex), "itens": em_aberto, "fontes": fontes}


# ---------------------------------------------------------------------------- mudanças


def _mudancas(anterior: ExecucaoSalva | None, diff: Diff | None, motivo: str) -> dict:
    """A seção 8: o diff, ou `motivo` (retroativa, anterior ilegível, primeira) se não houve comparação."""
    if anterior is None or diff is None:
        return {"anterior": "", "as_of": "", "texto": "", "motivo": motivo}
    return {
        "anterior": anterior.ctx.run_id,
        "as_of": anterior.ctx.as_of.isoformat(),
        "texto": renderizar_diff(diff),
        "motivo": "",
    }


# ---------------------------------------------------------------------------- geração


def _contexto(
    ex: ExecucaoSalva,
    matriz: Matriz,
    pasta: Path,
    pont: Pontuacao,
    anterior: ExecucaoSalva | None,
    diff: Diff | None,
    motivo_sem_diff: str,
    forcadas: list[str],
) -> dict[str, Any]:
    custodia = _Custodia(pasta)
    return {
        "cab": _cabecalho(ex, matriz, pasta),
        "v": _veredito(matriz, pont, forcadas, custodia),
        "itens": _linhas_dos_itens(ex, matriz, pont.itens, custodia),
        "tempo": _linha_do_tempo(ex, pont.sinais, alertas_da_execucao(ex), custodia),
        "emp": _empresa(ex),
        "oficiais": _registros_oficiais(ex),
        "pessoas": _pessoas_com_vinculo(ex, pont.itens),
        "processos": _processos_sancionadores(ex),
        "infra": _infraestrutura(ex),
        "lacunas": _lacunas(ex, pont.itens),
        "mud": _mudancas(anterior, diff, motivo_sem_diff),
        "artefatos": custodia.artefatos(),
    }


def _gravar_pontuacao(pasta: Path, matriz: Matriz, pont: Pontuacao) -> None:
    gravar_json_atomico(
        pasta / NOME_DA_PONTUACAO,
        {
            "matriz": {"versao": matriz.versao, "hash": matriz.hash},
            "itens": {id_: item.model_dump(mode="json") for id_, item in pont.itens.items()},
            "eixo1": pont.eixo1.model_dump(mode="json"),
            "eixo2": pont.eixo2.model_dump(mode="json"),
            "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )


def _texto_do_diff(anterior: ExecucaoSalva, ex: ExecucaoSalva, diff: Diff) -> str:
    return (
        "# Mudanças desde a execução anterior\n\n"
        f"Execução anterior {codigo_md(anterior.ctx.run_id)} comparada com a atual {codigo_md(ex.ctx.run_id)}, "
        "as duas pontuadas de novo com a matriz atual.\n\n" + renderizar_diff(diff)
    )


def gerar_dossie(pasta: Path, matriz: Matriz, forcar: bool = False) -> Path:
    """Escreve `dossie.md` (as 9 seções da spec 8.4), `pontuacao.json` e, se há execução anterior, `diff.md` na
    pasta da execução, e devolve o caminho do `dossie.md`.

    Com pendências abertas e sem `forcar` levanta `PendenciasAbertas`; com `forcar` os itens delas valem como
    `nao_verificado` e o dossiê avisa. O diff compara com `execucao_anterior` (repontuando as duas com `matriz`).
    Não há diff, e o `diff.md` que existisse é apagado, quando a execução é retroativa (comparar o passado com
    uma execução atual não diz nada), quando não há anterior e quando a anterior não pôde ser lida (a seção 8
    diz qual das três). Um `custodia.log` com a última linha ilegível não impede o dossiê: o cabeçalho manda rodar
    `radar verificar`. Nada é escrito se a montagem falha.
    """
    pasta = Path(pasta)
    ex = carregar_execucao(pasta)
    abertas = [pid for pid, p in ex.pendencias.items() if p.get("aberta")]
    if abertas and not forcar:
        raise PendenciasAbertas(abertas)
    anterior, aviso = (None, None) if ex.ctx.retroativo else ler_anterior(ex)
    pont = pontuar(ex, matriz, anterior)
    diff = comparar(anterior, ex, matriz) if anterior is not None else None
    if ex.ctx.retroativo:
        motivo_sem_diff = _SEM_DIFF_RETROATIVA
    elif aviso is not None:
        motivo_sem_diff = f"{aviso} Sem comparação."
    else:
        motivo_sem_diff = _SEM_DIFF_PRIMEIRA
    contexto = _contexto(ex, matriz, pasta, pont, anterior, diff, motivo_sem_diff, abertas)
    texto = _AMBIENTE.get_template("dossie.md.j2").render(**contexto)

    _gravar_pontuacao(pasta, matriz, pont)
    if anterior is not None and diff is not None:
        (pasta / "diff.md").write_bytes(_texto_do_diff(anterior, ex, diff).encode("utf-8"))
    else:
        (pasta / "diff.md").unlink(missing_ok=True)
    # bytes: o modo texto do Windows trocaria \n por \r\n
    (pasta / "dossie.md").write_bytes(texto.encode("utf-8"))
    return pasta / "dossie.md"
