"""Nó `cnpj`: identifica a empresa por trás do site e busca os dados dela na Receita.

O CNPJ vem do titular do domínio no RDAP (`rdap.cnpj_titular`) e dos candidatos `cnpj` da extração. Antes
de decidir, os CNPJs (sem repetição) são agrupados pela raiz de 8 caracteres: matriz e filiais são a mesma
empresa, e cada raiz conta como um candidato só, representado pela matriz (ordem `0001`, caracteres 9 a 12)
ou, sem ela, pelo primeiro achado (o titular vem antes dos CNPJs da extração). Depois:

- resposta ativa à P-CNPJ: vale ela (`confirmado`/`corrigido` informam o CNPJ; `nao_encontrado` e
  `inconclusivo` encerram o nó sem CNPJ);
- uma raiz só: usa a dela;
- várias raízes: usa a do titular do RDAP, se há titular; sem ele, abre a P-CNPJ com um candidato por raiz
  (o gateway de pagamento e a contabilidade também aparecem no rodapé: o nó não escolhe sozinho);
- nenhuma raiz: abre a P-CNPJ sem candidatos.

A consulta é à BrasilAPI e, se ela falhar de qualquer jeito, ao minhareceita.org, que devolve o mesmo
esquema (por isso um parser só serve às duas). O JSON bruto vai para a custódia. Das saídas ficam só os
campos usados; o quadro de sócios sai com nome, qualificação e data de entrada, nunca com os campos de CPF
(`cnpj_cpf_do_socio`, `cpf_representante_legal`, `nome_representante_legal`).
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from radar.cnpj_util import cnpj_valido, normalizar_cnpj
from radar.modelos import Aguardando, Candidato, Contexto, ErroNo, Feito
from radar.motor import NoBase, Servicos
from radar.nos._api import buscar_json
from radar.pendencias.definicoes import nova_pendencia

# (valor de `fonte`, rótulo nas mensagens de erro, URL)
_FONTES = (
    ("brasilapi", "BrasilAPI", "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"),
    ("minhareceita", "minhareceita", "https://minhareceita.org/{cnpj}"),
)
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
_INTEIRO = re.compile(r"\d{1,12}", re.ASCII)
_ID_PENDENCIA = "P-CNPJ"


def _texto(valor: Any) -> str | None:
    return (valor.strip() or None) if isinstance(valor, str) else None


def _data(valor: Any) -> str | None:
    """`AAAA-MM-DD` de uma data ISO que existe no calendário; qualquer outra coisa é `None`."""
    if not isinstance(valor, str) or not _DATA.fullmatch(inicio := valor.strip()[:10]):
        return None
    try:
        date.fromisoformat(inicio)
    except ValueError:
        return None
    return inicio


def _inteiro(valor: Any) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and _INTEIRO.fullmatch(limpo := valor.strip()):
        return int(limpo)
    return None


def _decimal(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float | str):
        return None
    try:
        numero = float(valor)
    except ValueError:
        return None
    return numero if math.isfinite(numero) else None


def _socios(qsa: Any) -> list[dict]:
    """Só nome, qualificação e entrada; o resto de cada sócio (inclusive os campos de CPF) fica de fora."""
    socios = []
    for socio in qsa if isinstance(qsa, list) else []:
        if isinstance(socio, dict) and (nome := _texto(socio.get("nome_socio"))):
            socios.append(
                {
                    "nome": nome,
                    "qualificacao": _texto(socio.get("qualificacao_socio")),
                    "entrada": _data(socio.get("data_entrada_sociedade")),
                }
            )
    return socios


def _empresa(dados: Any, rotulo: str) -> dict:
    """Os campos da empresa no esquema que a BrasilAPI e o minhareceita.org compartilham."""
    if not isinstance(dados, dict):
        raise ErroNo(f"{rotulo}: resposta não é um objeto JSON", permanente=True)
    return {
        "razao_social": _texto(dados.get("razao_social")),
        "nome_fantasia": _texto(dados.get("nome_fantasia")),
        "abertura": _data(dados.get("data_inicio_atividade")),
        "cnae": _inteiro(dados.get("cnae_fiscal")),
        "cnae_descricao": _texto(dados.get("cnae_fiscal_descricao")),
        "capital_social": _decimal(dados.get("capital_social")),
        "situacao": _texto(dados.get("descricao_situacao_cadastral")),
        "socios": _socios(dados.get("qsa")),
    }


async def _consultar(s: Servicos, cnpj: str) -> tuple[dict, str]:
    """A empresa e a fonte que respondeu. Qualquer `ErroNo` da BrasilAPI (rede, HTTP, corpo que não é JSON,
    formato inesperado) passa a vez para o minhareceita.org; se os dois falham, o erro não é permanente."""
    motivos = []
    for fonte, rotulo, modelo in _FONTES:
        try:
            empresa = _empresa(await buscar_json(s, modelo.format(cnpj=cnpj), rotulo), rotulo)
        except ErroNo as erro:
            motivos.append(erro.mensagem)
        else:
            return empresa, fonte
    raise ErroNo("APIs de CNPJ indisponíveis: " + "; ".join(motivos), permanente=False)


def _grupos_por_raiz(achados: list[str]) -> dict[str, list[str]]:
    """Os CNPJs sem repetição, agrupados pela raiz (8 primeiros caracteres), na ordem em que cada um apareceu."""
    grupos: dict[str, list[str]] = {}
    for cnpj in achados:
        grupo = grupos.setdefault(cnpj[:8], [])
        if cnpj not in grupo:
            grupo.append(cnpj)
    return grupos


def _representante(grupo: list[str]) -> str:
    """O CNPJ que fala pela raiz: a matriz (ordem `0001`) ou, sem ela, o primeiro achado."""
    return next((cnpj for cnpj in grupo if cnpj[8:12] == "0001"), grupo[0])


def _titular(entradas: dict[str, dict]) -> str | None:
    titular = entradas.get("rdap", {}).get("cnpj_titular")
    return titular if isinstance(titular, str) and cnpj_valido(titular) else None


def _da_extracao(entradas: dict[str, dict]) -> list[Candidato]:
    """Os candidatos `cnpj` da extração, sem repetir o valor (fica o primeiro)."""
    vistos: dict[str, Candidato] = {}
    for bruto in entradas["extracao"]["candidatos"]:
        candidato = Candidato.model_validate(bruto)
        if candidato.categoria == "cnpj" and cnpj_valido(candidato.valor):
            vistos.setdefault(candidato.valor, candidato)
    return list(vistos.values())


class CnpjNo(NoBase):
    """Quem é a empresa do site e o que a Receita diz dela.

    A abertura vale em qualquer `as_of`; situação e quadro de sócios são os de hoje, e no modo retroativo
    vêm marcados em `vazamento_temporal` para a pontuação não tratá-los como fatos da data.
    Saídas: `cnpj`, `razao_social`, `nome_fantasia`, `abertura` (ISO), `cnae` (`int`: o zero à esquerda
    do código de 7 dígitos se perde), `cnae_descricao`, `capital_social` (`float`), `situacao`, `socios`
    (`[{nome, qualificacao, entrada}]`), `fonte` (`brasilapi` ou `minhareceita`) e `vazamento_temporal`.
    Sem CNPJ (resposta `nao_encontrado` ou `inconclusivo` à P-CNPJ): `{"cnpj": None, "motivo": ...}`.
    """

    nome = "cnpj"
    entradas = ("extracao",)
    opcionais = ("rdap",)
    saidas = (
        "cnpj",
        "razao_social",
        "nome_fantasia",
        "abertura",
        "cnae",
        "cnae_descricao",
        "capital_social",
        "situacao",
        "socios",
        "fonte",
        "vazamento_temporal",
    )
    as_of = "exato"

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito | Aguardando:
        if (resposta := respostas.get(_ID_PENDENCIA)) is not None:
            if resposta.status not in ("confirmado", "corrigido"):
                return Feito({"cnpj": None, "motivo": "não encontrado"})
            informado = resposta.valor.get("cnpj")
            cnpj = normalizar_cnpj(informado) if isinstance(informado, str) else None
            if cnpj is None:
                raise ErroNo("P-CNPJ: CNPJ inválido na resposta", permanente=True)
        else:
            titular = _titular(entradas)
            candidatos = _da_extracao(entradas)
            grupos = _grupos_por_raiz(([titular] if titular else []) + [c.valor for c in candidatos])
            if len(grupos) == 1:
                cnpj = _representante(next(iter(grupos.values())))
            elif titular is not None:
                cnpj = _representante(grupos[titular[:8]])
            else:
                por_valor = {c.valor: c for c in candidatos}
                escolhidos = [por_valor[_representante(g)] for g in grupos.values()]
                return Aguardando([nova_pendencia(_ID_PENDENCIA, ctx, escolhidos, self.nome, s.matriz)])
        empresa, fonte = await _consultar(s, cnpj)
        return Feito(
            {
                "cnpj": cnpj,
                **empresa,
                "fonte": fonte,
                "vazamento_temporal": ["situacao", "socios"] if ctx.retroativo else [],
            }
        )
