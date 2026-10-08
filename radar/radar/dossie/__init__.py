"""Dossiê de risco (spec 8.4): o `dossie.md` que o usuário lê, a `pontuacao.json` e, havendo execução anterior, o
`diff.md`.

`gerar_dossie` lê a execução gravada em disco, pontua com a matriz dada, monta os dados de cada seção aqui e deixa
o texto para o template `dossie.md.j2`. O template é Markdown, sem escape automático: tudo o que vem do site, das
fontes ou do Claude passa pelo filtro `md` (uma linha só, `|` e formatação escapados, sem CPF) e URLs e hashes de
tabela pelo filtro `cod`.
"""

from __future__ import annotations

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
    carregar_anterior,
    comparar,
    data_iso,
    julgamento_ativo,
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
from radar.pontuacao import Matriz
from radar.texto import codigo_md, escapar_md

__all__ = ["PendenciasAbertas", "gerar_dossie"]

_ORIGEM = {"coletor": "coletor", "regex_confirmada": "regex confirmada", "claude": "Claude", "nenhuma": "—"}
_DIRECAO = {
    "encurta": "encurta a janela",
    "alonga": "alonga a janela",
    "corte_sem_aviso": "corte possível sem aviso",
}
_ORIGENS_COM_JULGAMENTO = frozenset({"regex_confirmada", "claude"})  # as marcas são do julgamento do Claude
_PREFIXO_HASH = "sha256:"
_HASH_CURTO = len(_PREFIXO_HASH) + 12
_MAX_SANS = 20
_MAX_TERCEIROS = 20
_MAX_PAGINAS = 10
_NA = "—"
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


def _cabecalho(ex: ExecucaoSalva, matriz: Matriz, pasta: Path) -> dict:
    ctx = ex.ctx
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
        "hash_custodia": hash_final(pasta),
    }


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


def _marcas(ex: ExecucaoSalva, id_: str, item: Item) -> list[str]:
    """As marcas de validação (`trecho_nao_conferido`, `data_desconhecida`) do julgamento ativo da pendência do item.
    O item do coletor não tem julgamento por trás: as marcas da pendência não são dele."""
    if item.origem not in _ORIGENS_COM_JULGAMENTO:
        return []
    for pid, pendencia in ex.pendencias.items():
        if id_ in (pendencia.get("itens") or []):
            marcas = (julgamento_ativo(ex, pid) or {}).get("marcas", [])
            return [m for m in marcas if isinstance(m, str)] if isinstance(marcas, list) else []
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
        if not evidencias:
            linhas.append({**primeira, "trecho": _NA, "meta": "", "fonte": "", "hash": ""})
        for n, evidencia in enumerate(evidencias):
            fonte, hash_ = custodia.fonte_e_hash(evidencia)
            data = evidencia.data_fonte.isoformat() if evidencia.data_fonte else "sem data"
            continuacao = dict.fromkeys(primeira, "") | {"item": id_}
            linhas.append(
                {
                    **(primeira if n == 0 else continuacao),
                    "trecho": evidencia.trecho,
                    "meta": f"{evidencia.tipo_fonte}, {data}",
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
    por data (o que não tem data vai para o fim)."""
    eventos = []
    if (rdap := saida(ex, "rdap")) and data_iso(rdap.get("registro")):
        eventos.append(_evento(rdap["registro"][:10], "Domínio registrado", "RDAP"))
    if (cnpj := saida(ex, "cnpj")) and cnpj.get("cnpj") and data_iso(cnpj.get("abertura")):
        eventos.append(_evento(cnpj["abertura"][:10], "CNPJ aberto", f"Receita Federal ({cnpj.get('fonte') or '?'})"))
    if (ct := saida(ex, "ct")) and data_iso(ct.get("primeiro_certificado")):
        eventos.append(_evento(ct["primeiro_certificado"][:10], "Primeiro certificado TLS", "crt.sh"))
    if (wayback := saida(ex, "wayback_indice")) is not None:
        for chave, rotulo in (("primeiro", "Primeiro snapshot no Wayback"), ("ultimo", "Último snapshot no Wayback")):
            if data_iso(wayback.get(chave)):
                eventos.append(_evento(wayback[chave][:10], rotulo, "Wayback CDX"))
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


def _lacunas(ex: ExecucaoSalva, itens: dict[str, Item]) -> dict:
    """Nós sem resultado (com o motivo), itens `nao_verificado` ou `inconclusivo` (com a pendência que os resolve,
    se está aberta) e o que limita a cobertura das fontes."""
    nos = [
        {"no": no, "status": estado.get("status"), "motivo": estado.get("motivo") or ""}
        for no, estado in ex.status.items()
        if estado.get("status") != "feito"
    ]
    abertas = {pid: p.get("itens") or [] for pid, p in ex.pendencias.items() if p.get("aberta")}
    em_aberto = []
    for id_, item in itens.items():
        if item.estado in ("nao_verificado", "inconclusivo"):
            responder = [f"responder a {pid}" for pid, cobertos in abertas.items() if id_ in cobertos]
            em_aberto.append(
                {
                    "id": id_,
                    "estado": ROTULO_DO_ESTADO[item.estado],
                    "nota": item.nota or "",
                    "resolve": "; ".join(responder),
                }
            )
    fontes = []
    so_resumo = ((saida(ex, "cvm_alertas") or {}).get("cobertura") or {}).get("so_resumo")
    if isinstance(so_resumo, int) and so_resumo > 0:
        fontes.append(
            f"{so_resumo} {_plural(so_resumo, 'deliberação', 'deliberações')} da CVM "
            f"{_plural(so_resumo, 'só tem resumo', 'só têm resumo')}: sem prova negativa por CNPJ ou domínio nelas."
        )
    if (saida(ex, "wayback_indice") or {}).get("truncado") is True:
        fontes.append(
            "A listagem do Wayback veio truncada (limite do CDX): o total e o primeiro e o último snapshot podem "
            "não cobrir todo o domínio."
        )
    return {"nos": nos, "itens": em_aberto, "fontes": fontes}


# ---------------------------------------------------------------------------- mudanças


def _mudancas(anterior: ExecucaoSalva | None, diff: Diff | None) -> dict:
    if anterior is None or diff is None:
        return {
            "anterior": "",
            "as_of": "",
            "texto": "",
            "motivo": "Não há execução anterior deste alvo em modo atual para comparar.",
        }
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
        "infra": _infraestrutura(ex),
        "lacunas": _lacunas(ex, pont.itens),
        "mud": _mudancas(anterior, diff),
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
    `nao_verificado` e o dossiê avisa. O diff compara com `execucao_anterior` (repontuando as duas com `matriz`);
    sem anterior, o `diff.md` que existisse é apagado. Nada é escrito se a montagem falha.
    """
    pasta = Path(pasta)
    ex = carregar_execucao(pasta)
    abertas = [pid for pid, p in ex.pendencias.items() if p.get("aberta")]
    if abertas and not forcar:
        raise PendenciasAbertas(abertas)
    anterior = carregar_anterior(ex)
    pont = pontuar(ex, matriz, anterior)
    diff = comparar(anterior, ex, matriz) if anterior is not None else None
    contexto = _contexto(ex, matriz, pasta, pont, anterior, diff, abertas)
    texto = _AMBIENTE.get_template("dossie.md.j2").render(**contexto)

    _gravar_pontuacao(pasta, matriz, pont)
    if anterior is not None and diff is not None:
        (pasta / "diff.md").write_bytes(_texto_do_diff(anterior, ex, diff).encode("utf-8"))
    else:
        (pasta / "diff.md").unlink(missing_ok=True)
    # bytes: o modo texto do Windows trocaria \n por \r\n
    (pasta / "dossie.md").write_bytes(texto.encode("utf-8"))
    return pasta / "dossie.md"
