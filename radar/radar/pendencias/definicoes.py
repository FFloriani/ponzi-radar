"""Definições das pendências. PROVISÓRIO: só a P-CNPJ, para o nó `cnpj` (Tarefa 10).

A Tarefa 12 troca este módulo pela versão completa (`DEFINICOES`, esquemas de valor, `conteudo_do_alvo`
com máscara e cabeçalho de dado não confiável), mantendo a assinatura de `nova_pendencia`.
"""

from __future__ import annotations

from radar.modelos import Candidato, Contexto, Pendencia

_P_CNPJ = {
    "pergunta": "Qual é o CNPJ da empresa que opera o site analisado?",
    "criterios": (
        "Escolha um candidato ou informe outro CNPJ que uma fonte (rodapé, termos, contrato, registro oficial) "
        "ligue ao operador do site. Gateway de pagamento, contabilidade e parceiros não valem. "
        "Sem fonte, responda nao_encontrado e diga onde procurou."
    ),
}


def nova_pendencia(
    id: str,  # noqa: A002 - nome da assinatura combinada com a Tarefa 12
    ctx: Contexto,
    candidatos: list[Candidato | dict],
    no_origem: str,
    matriz=None,
) -> Pendencia:
    """A pendência `id` aberta pelo nó `no_origem`, com os candidatos que o nó achou.

    `matriz` não é usada no provisório; a versão completa a lê para a P-E.
    """
    if id != "P-CNPJ":
        raise ValueError(f"pendência desconhecida: {id}")
    return Pendencia(
        id=id,
        itens=[],
        pergunta=_P_CNPJ["pergunta"],
        criterios=_P_CNPJ["criterios"],
        candidatos=[Candidato.model_validate(c) for c in candidatos],
        formato_resposta={"cnpj": "string de 14 caracteres"},
        restricoes={"as_of": ctx.as_of.isoformat(), "modo_cego": ctx.modo_cego},
        conteudo_do_alvo="",
        no_origem=no_origem,
    )
