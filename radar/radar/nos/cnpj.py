"""Nó `cnpj`: identifica a empresa por trás do site e busca os dados dela na Receita.

O CNPJ vem do titular do domínio no RDAP (`rdap.cnpj_titular`) e dos candidatos `cnpj` da extração. Antes
de decidir, os CNPJs (sem repetição) são agrupados pela raiz de 8 caracteres: matriz e filiais são a mesma
empresa, e cada raiz conta como um candidato só, representado pela matriz (ordem `0001`, caracteres 9 a 12)
ou, sem ela, pelo primeiro achado (o titular vem antes dos CNPJs da página). Depois:

- resposta ativa à P-CNPJ: vale ela (`confirmado`/`corrigido` informam o CNPJ; `nao_encontrado` e
  `inconclusivo` encerram o nó sem CNPJ);
- sem CNPJ na página: usa o titular do RDAP; sem titular também, abre a P-CNPJ sem candidatos;
- com CNPJ na página e titular: usa o titular se a raiz dele está entre as da página. Se não está, quem
  registrou o domínio pode ser uma agência ou contabilidade e o operador o CNPJ do rodapé: abre a P-CNPJ
  com um candidato por raiz, titular incluído;
- com CNPJ na página e sem titular: uma raiz só, usa a dela; várias (o gateway de pagamento e a contabilidade
  também aparecem no rodapé), abre a P-CNPJ com um candidato por raiz. O nó nunca escolhe sozinho na dúvida.

A consulta é à BrasilAPI e, se ela falhar de qualquer jeito (inclusive resposta sem `razao_social` ou de outro
CNPJ), ao minhareceita.org, que devolve o mesmo esquema (por isso um parser só serve às duas). O JSON bruto
vai para a custódia. Das saídas ficam só os campos usados; o quadro de sócios sai com nome, qualificação e
data de entrada, nunca com os campos de CPF (`cnpj_cpf_do_socio`, `cpf_representante_legal`,
`nome_representante_legal`).
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
_CNAE = re.compile(r"\d{1,7}", re.ASCII)  # o código tem 7 dígitos
_ID_PENDENCIA = "P-CNPJ"
# o que a Receita registra na abertura vale em qualquer `as_of`; o resto é o de hoje
_EXATOS = ("cnpj", "abertura")


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


def _cnae(valor: Any) -> int | None:
    """O código (até 7 dígitos) como `int`; número fora dessa faixa, booleano e texto não numérico são `None`."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if 0 <= valor <= 9_999_999 else None
    if isinstance(valor, str) and _CNAE.fullmatch(limpo := valor.strip()):
        return int(limpo)
    return None


def _decimal(valor: Any) -> float | None:
    """`float` finito; `10**400` (OverflowError), `inf`, `nan`, booleano e texto não numérico são `None`."""
    if isinstance(valor, bool) or not isinstance(valor, int | float | str):
        return None
    try:
        numero = float(valor)
    except (ValueError, OverflowError):
        return None
    return numero if math.isfinite(numero) else None


def _cnpj_da_resposta(valor: Any) -> str | None:
    """O CNPJ que a API diz ser o da empresa (texto, com ou sem pontuação, ou número) como 14 caracteres."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        valor = f"{valor:014d}"  # o zero à esquerda se perde no número
    return normalizar_cnpj(valor) if isinstance(valor, str) else None


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


def _empresa(dados: Any, rotulo: str, cnpj: str) -> dict:
    """Os campos da empresa no esquema que a BrasilAPI e o minhareceita.org compartilham.

    Só vale resposta que é da empresa pedida: um objeto com `razao_social` e com o `cnpj` igual a `cnpj`.
    Corpo de erro de API (`{"message": "..."}`) e resposta de outro CNPJ levantam `ErroNo`.
    """
    if not isinstance(dados, dict):
        raise ErroNo(f"{rotulo}: resposta não é um objeto JSON", permanente=True)
    razao_social = _texto(dados.get("razao_social"))
    if razao_social is None:
        raise ErroNo(f"{rotulo}: resposta sem razao_social", permanente=True)
    if _cnpj_da_resposta(dados.get("cnpj")) != cnpj:
        raise ErroNo(f"{rotulo}: resposta não é do CNPJ {cnpj}", permanente=True)
    return {
        "razao_social": razao_social,
        "nome_fantasia": _texto(dados.get("nome_fantasia")),
        "abertura": _data(dados.get("data_inicio_atividade")),
        "cnae": _cnae(dados.get("cnae_fiscal")),
        "cnae_descricao": _texto(dados.get("cnae_fiscal_descricao")),
        "capital_social": _decimal(dados.get("capital_social")),
        "situacao": _texto(dados.get("descricao_situacao_cadastral")),
        "socios": _socios(dados.get("qsa")),
    }


async def _consultar(s: Servicos, cnpj: str) -> tuple[dict, str]:
    """A empresa e a fonte que respondeu. Qualquer `ErroNo` da BrasilAPI (rede, HTTP, corpo que não é JSON,
    resposta que não é da empresa pedida) passa a vez para o minhareceita.org; se os dois falham, o erro não
    é permanente."""
    motivos = []
    for fonte, rotulo, modelo in _FONTES:
        try:
            empresa = _empresa(await buscar_json(s, modelo.format(cnpj=cnpj), rotulo), rotulo, cnpj)
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
    """Os candidatos `cnpj` da extração, sem repetir o valor (fica o primeiro). Sem a `extracao` (a página não pôde
    ser lida), nenhum: vale só o titular do RDAP."""
    vistos: dict[str, Candidato] = {}
    for bruto in (entradas.get("extracao") or {}).get("candidatos") or []:
        candidato = Candidato.model_validate(bruto)
        if candidato.categoria == "cnpj" and cnpj_valido(candidato.valor):
            vistos.setdefault(candidato.valor, candidato)
    return list(vistos.values())


def _candidato_do_titular(titular: str) -> Candidato:
    """O titular do RDAP como candidato da P-CNPJ (ele não vem de um texto da página)."""
    return Candidato(
        categoria="cnpj",
        valor=titular,
        trecho="titular do domínio no RDAP",
        artefato="rdap",
        posicao=0,
        extra={"origem": "rdap"},
    )


def _escolher(titular: str | None, candidatos: list[Candidato]) -> str | list[Candidato]:
    """O CNPJ a consultar ou, se há dúvida, os candidatos da P-CNPJ (um por raiz).

    Dúvida é: sem titular, nenhum CNPJ na página ou mais de uma raiz nela; com titular, a página citar CNPJ
    de raízes que não incluem a dele. Sem CNPJ na página, o titular basta.
    """
    da_pagina = _grupos_por_raiz([c.valor for c in candidatos])
    if titular is not None and (not da_pagina or titular[:8] in da_pagina):
        grupos = _grupos_por_raiz([titular, *(c.valor for c in candidatos)])
        return _representante(grupos[titular[:8]])
    if titular is None and len(da_pagina) == 1:
        return _representante(next(iter(da_pagina.values())))
    por_valor = {c.valor: c for c in candidatos}
    escolhidos = [por_valor[_representante(grupo)] for grupo in da_pagina.values()]
    return [_candidato_do_titular(titular), *escolhidos] if titular is not None else escolhidos


class CnpjNo(NoBase):
    """Quem é a empresa do site e o que a Receita diz dela.

    A abertura vale em qualquer `as_of`; o resto é o de hoje, e no modo retroativo todos os campos além de
    `cnpj` e `abertura` vêm marcados em `vazamento_temporal` para a pontuação não tratá-los como fatos da data.
    Saídas: `cnpj`, `razao_social`, `nome_fantasia`, `abertura` (ISO), `cnae` (`int`: o zero à esquerda
    do código de 7 dígitos se perde), `cnae_descricao`, `capital_social` (`float`), `situacao`, `socios`
    (`[{nome, qualificacao, entrada}]`), `fonte` (`brasilapi` ou `minhareceita`) e `vazamento_temporal`.
    Sem CNPJ (resposta `nao_encontrado` ou `inconclusivo` à P-CNPJ): `{"cnpj": None, "motivo": ...}`.
    """

    nome = "cnpj"
    # os dois opcionais (I6): sem a página, o titular do RDAP; sem nenhum dos dois, a P-CNPJ sem candidatos
    entradas = ()
    opcionais = ("extracao", "rdap")
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
            escolha = _escolher(_titular(entradas), _da_extracao(entradas))
            if isinstance(escolha, list):
                return Aguardando([nova_pendencia(_ID_PENDENCIA, ctx, escolha, self.nome, s.matriz)])
            cnpj = escolha
        empresa, fonte = await _consultar(s, cnpj)
        saidas = {"cnpj": cnpj, **empresa, "fonte": fonte}
        vazamento = [campo for campo in saidas if campo not in _EXATOS] if ctx.retroativo else []
        return Feito({**saidas, "vazamento_temporal": vazamento})
