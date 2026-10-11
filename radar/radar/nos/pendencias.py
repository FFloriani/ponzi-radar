"""Nós `pend_*`: abrem as pendências que o Claude responde via MCP e entregam a resposta ao resto do DAG.

Cada nó é um `PendNo` parametrizado pelo nome. Ele escolhe os candidatos da sua pendência (cada nó só leva as
categorias que a definição lista) e:

- se a condição de geração falha, fica `Pulado`; a condição vem antes da resposta, de modo que uma resposta
  que perdeu o sentido (a P-A3 depois de a P-A1 ser corrigida para "sem retorno") não passa adiante;
- se há resposta ativa, entrega `Feito({"resposta": ...})`, com a pendência refeita em `Feito.pendencias`: se os
  candidatos mudaram desde a resposta (a P-CNPJ corrigida para outra empresa muda os sócios da P-D1), o motor
  invalida a resposta e reabre a pendência;
- senão, devolve `Aguardando` com a pendência.

| Nó | Entradas (opcionais entre parênteses) | Gera |
|---|---|---|
| `pend_a1`, `pend_b`, `pend_d4` | (`extracao`) | sempre |
| `pend_a2` | `extracao` | só com candidato `historico_rentabilidade` visível |
| `pend_a3` | `pend_a1` (`extracao`) | P-A1 `confirmado`/`corrigido` com `pct_mes` > 0 ou `taxa_diaria`, ou candidato `investimento` visível |
| `pend_c` | (`extracao`, `cnpj`) | sempre; a empresa do `cnpj`, se há, é o candidato `empresa` |
| `pend_c4` | (`cvm_alertas`, `cnpj`) | sempre; candidato `empresa` e as correspondências só por nome |
| `pend_d1` | (`extracao`, `cnpj`, `cvm_sancionador`) | sempre; os sócios do `cnpj` e os processos da CVM são os candidatos |
| `pend_e` | todos os coletores, opcionais | sempre |

Visível é o candidato do texto da página ou dos atributos. O dos textos internos do aplicativo
(`extra.origem = "texto_interno"`) não abre a P-A2 nem a P-A3 (ruling R-A-T3-a2), mas vai junto quando outro motivo
as abre.

O `cnpj` é opcional da P-C, da P-C4 e da P-D1 porque a pendência abre depois dele (a P-CNPJ pode estar aguardando)
e usa o que ele achou. A `extracao` e o `cvm_alertas` são opcionais onde a pendência sai sempre (spec 7.1, I6 da
revisão final): o site com anti-bot e sem snapshot no Wayback, ou o índice da CVM fora do ar, não podem tirar do Claude
as perguntas que não dependem deles. Sem eles a pendência abre sem os candidatos que viriam deles e os critérios
ganham o aviso (`AVISO_SEM_PAGINA`, `AVISO_SEM_INDICE_CVM`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from radar.modelos import Aguardando, Candidato, Contexto, ErroNo, Feito, Pulado
from radar.motor import NoBase, Servicos
from radar.pendencias.definicoes import DEFINICOES, nova_pendencia

# o que o nó decide antes de abrir a pendência: os candidatos dela ou o motivo de não gerá-la
_Preparo = Callable[[Contexto, dict[str, dict], Servicos], list[Candidato] | Pulado]

AVISO_SEM_PAGINA = (
    "Atenção: o site não pôde ser lido nesta execução (nem a captura nem o Wayback deram o texto da página), então não "
    "há candidatos tirados dele: pesquise você mesmo nas cópias arquivadas, nas redes do operador, na imprensa e em "
    "sites de reclamação."
)
AVISO_SEM_INDICE_CVM = (
    "Atenção: o índice local de deliberações da CVM falhou nesta execução, então nenhuma deliberação foi conferida "
    "automaticamente: confira à mão as fontes oficiais (deliberações de atuação irregular e Atos Declaratórios da "
    "CVM, I-SCAN da IOSCO, reguladores estrangeiros)."
)

# todos os nós que coletam dados (o `alvo` só normaliza a entrada): a P-E espera por eles, qualquer que seja o resultado
_COLETORES = (
    "rdap", "dns", "ct", "wayback_indice", "captura", "wayback_snapshot", "extracao", "cnpj", "registros",
    "cvm_sancionador", "cvm_alertas",
)  # fmt: skip


def _da_extracao(entradas: dict[str, dict], pendencia: str) -> list[Candidato]:
    """Os candidatos da extração nas categorias da pendência, na ordem em que a extração os entregou. Sem a
    `extracao` nas entradas (a página não pôde ser lida), nenhum."""
    categorias = DEFINICOES[pendencia].categorias
    candidatos = (Candidato.model_validate(c) for c in (entradas.get("extracao") or {}).get("candidatos") or [])
    return [c for c in candidatos if c.categoria in categorias]


def _candidatos_da_extracao(pendencia: str) -> _Preparo:
    def preparar(ctx: Contexto, entradas: dict[str, dict], s: Servicos) -> list[Candidato]:
        return _da_extracao(entradas, pendencia)

    return preparar


def _da_empresa(entradas: dict[str, dict]) -> list[Candidato]:
    """A empresa que o nó `cnpj` identificou, como candidato `empresa`; nenhum se o nó não está nas entradas ou
    não achou o CNPJ. É o que os critérios da P-C e da P-C4 mandam comparar e pesquisar. No modo retroativo a razão
    social e o nome fantasia são os de hoje (o `cnpj` os marca em `vazamento_temporal`); aqui só identificam a empresa."""
    empresa = entradas.get("cnpj") or {}
    if not (cnpj := empresa.get("cnpj")):
        return []
    partes = [empresa.get("razao_social"), f"CNPJ {cnpj}", empresa.get("nome_fantasia")]
    trecho = " — ".join(parte for parte in partes if parte)
    return [Candidato(categoria="empresa", valor=cnpj, trecho=trecho, artefato="cnpj", posicao=0)]


def _algum_visivel(candidatos: list[Candidato]) -> bool:
    """Algum candidato veio do texto da página ou dos atributos, não dos textos internos do aplicativo. O rótulo de
    uma tela que o visitante não vê (`Veja o histórico de rendimentos`) não abre pendência (ruling R-A-T3-a2): ele vai
    junto quando um visível a abre."""
    return any(not c.do_texto_interno for c in candidatos)


def _preparar_a2(ctx: Contexto, entradas: dict[str, dict], s: Servicos) -> list[Candidato] | Pulado:
    candidatos = _da_extracao(entradas, "P-A2")
    return candidatos if _algum_visivel(candidatos) else Pulado("sem histórico de rentabilidade")


def _a1_promete_retorno(saida: dict | None) -> bool:
    """A P-A1 foi `confirmado`/`corrigido` com retorno em % ao mês (maior que zero) ou taxa diária.

    Lê o `valor` como veio, sem validar: um campo que falta é "não prometeu".
    """
    resposta = (saida or {}).get("resposta") or {}
    if resposta.get("status") not in ("confirmado", "corrigido"):
        return False
    valor = resposta.get("valor") or {}
    pct_mes = valor.get("pct_mes")
    com_pct = isinstance(pct_mes, int | float) and not isinstance(pct_mes, bool) and pct_mes > 0
    return com_pct or valor.get("taxa_diaria") is True


def _preparar_a3(ctx: Contexto, entradas: dict[str, dict], s: Servicos) -> list[Candidato] | Pulado:
    candidatos = _da_extracao(entradas, "P-A3")
    if _algum_visivel(candidatos) or _a1_promete_retorno(entradas.get("pend_a1")):
        return candidatos
    return Pulado("sem oferta de investimento")


def _preparar_c(ctx: Contexto, entradas: dict[str, dict], s: Servicos) -> list[Candidato]:
    return [*_da_empresa(entradas), *_da_extracao(entradas, "P-C")]


def _preparar_c4(ctx: Contexto, entradas: dict[str, dict], s: Servicos) -> list[Candidato]:
    """A empresa e as deliberações da CVM que o `cvm_alertas` achou só pelo nome. Sem CNPJ nem domínio batendo, a
    identidade da empresa é palpite e quem confirma é o Claude. `artefato` das deliberações é a ref de custódia do
    JSON do `cvm_alertas` (a fonte citável); sem ela (execução de antes da ref), o nome do nó."""
    saida = entradas.get("cvm_alertas") or {"correspondencias": []}  # sem o índice: o aviso vai nos critérios
    artefato = saida.get("artefato") or "cvm_alertas"
    deliberacoes = [
        Candidato(
            categoria="alerta_cvm_nome",
            valor=f"Deliberação {c['numero']}",
            trecho=c["trecho"],
            artefato=artefato,
            posicao=0,
            # o que o Claude precisa para citar o alerta em `ValorC4.alertas`
            extra={"nome": c.get("valor"), "data": c.get("data"), "url": c.get("url")},
        )
        for c in saida["correspondencias"]
        if c.get("tipo") == "nome"
    ]
    return [*_da_empresa(entradas), *deliberacoes]


def _candidato_do_socio(socio: dict) -> Candidato:
    trecho = socio["nome"]
    if socio.get("qualificacao"):
        trecho += f" — {socio['qualificacao']}"
    if socio.get("entrada"):
        trecho += f" (entrada {socio['entrada']})"
    return Candidato(categoria="socio", valor=socio["nome"], trecho=trecho, artefato="cnpj", posicao=0)


def _entrou_depois(socio: dict, as_of: date) -> bool:
    """A `entrada` do sócio é posterior ao `as_of`. Sem data (ou com uma que não é ISO) não dá para saber: não vale."""
    try:
        return date.fromisoformat(socio["entrada"]) > as_of
    except (KeyError, TypeError, ValueError):
        return False


def _candidato_do_processo(processo: dict, artefato: str) -> Candidato:
    """Um processo sancionador da CVM que o `cvm_sancionador` ligou à empresa ou a um sócio (I7). `artefato` é a ref
    de custódia do JSON do `cvm_sancionador` (a fonte citável); sem ela (execução de antes da ref), o nome do nó."""
    partes = [
        f"Processo sancionador CVM {processo.get('nup')}",
        processo.get("objeto"),
        f"acusado: {processo.get('acusado')}" + (f" ({processo['situacao']})" if processo.get("situacao") else ""),
        f"aberto em {processo.get('data_abertura')}",
    ]
    extra = {
        chave: processo.get(chave)
        for chave in ("acusado", "vinculo", "nome_curto", "fase", "situacao", "data_abertura")
    }
    return Candidato(
        categoria="processo_cvm", valor=str(processo.get("nup")), trecho=" — ".join(p for p in partes if p),
        artefato=artefato, posicao=0, extra=extra,
    )  # fmt: skip


def _preparar_d1(ctx: Contexto, entradas: dict[str, dict], s: Servicos) -> list[Candidato]:
    """A P-D1 é sempre gerada. Os sócios do quadro da Receita são os candidatos; sem eles (o `cnpj` não achou a
    empresa, falhou ou veio sem quadro) a pendência pede ao Claude que identifique os responsáveis.

    O quadro é o de hoje (o `cnpj` marca `socios` em `vazamento_temporal` no modo retroativo, e a marca não chega
    até aqui): na execução retroativa ficam de fora os que entraram depois do `as_of`. Quem já saiu da sociedade
    não aparece no quadro, e isso os critérios dizem.
    """
    socios = (entradas.get("cnpj") or {}).get("socios") or []
    if ctx.retroativo:
        socios = [socio for socio in socios if not _entrou_depois(socio, ctx.as_of)]
    # os processos já vêm filtrados pelo `as_of` (abertos até ele)
    sancionador = entradas.get("cvm_sancionador") or {}
    processos = sancionador.get("processos") or []
    artefato = sancionador.get("artefato") or "cvm_sancionador"
    return [
        *(_candidato_do_socio(socio) for socio in socios),
        *(_candidato_do_processo(p, artefato) for p in processos if isinstance(p, dict)),
    ]


def _preparar_e(ctx: Contexto, entradas: dict[str, dict], s: Servicos) -> list[Candidato]:
    if s.matriz is None:
        raise ErroNo("matriz não configurada", permanente=True)
    return []


@dataclass(frozen=True)
class _Especificacao:
    pendencia: str
    entradas: tuple[str, ...]
    opcionais: tuple[str, ...]
    preparar: _Preparo


_ESPECIFICACOES = {
    "pend_a1": _Especificacao("P-A1", (), ("extracao",), _candidatos_da_extracao("P-A1")),
    "pend_a2": _Especificacao("P-A2", ("extracao",), (), _preparar_a2),
    "pend_a3": _Especificacao("P-A3", ("pend_a1",), ("extracao",), _preparar_a3),
    "pend_b": _Especificacao("P-B", (), ("extracao",), _candidatos_da_extracao("P-B")),
    "pend_c": _Especificacao("P-C", (), ("extracao", "cnpj"), _preparar_c),
    "pend_c4": _Especificacao("P-C4", (), ("cvm_alertas", "cnpj"), _preparar_c4),
    "pend_d1": _Especificacao("P-D1", (), ("extracao", "cnpj", "cvm_sancionador"), _preparar_d1),
    "pend_d4": _Especificacao("P-D4", (), ("extracao",), _candidatos_da_extracao("P-D4")),
    "pend_e": _Especificacao("P-E", (), _COLETORES, _preparar_e),
}
# a fonte opcional que, ausente, vira aviso nos critérios (a P-E espera todos os coletores e não avisa)
_AVISOS = {"extracao": AVISO_SEM_PAGINA, "cvm_alertas": AVISO_SEM_INDICE_CVM}


class PendNo(NoBase):
    """O nó da pendência `nome` (`pend_a1`, `pend_b`...). Saída: `{"resposta": <Resposta em JSON>}`."""

    saidas = ("resposta",)

    def __init__(self, nome: str) -> None:
        if (especificacao := _ESPECIFICACOES.get(nome)) is None:
            raise ValueError(f"nó de pendência desconhecido: {nome}")
        super().__init__(nome=nome, entradas=especificacao.entradas, opcionais=especificacao.opcionais)
        self._especificacao = especificacao

    @property
    def pendencia(self) -> str:
        return self._especificacao.pendencia

    def _avisos(self, entradas: dict[str, dict]) -> list[str]:
        """O aviso de cada fonte opcional da pendência que não chegou (nó em erro, bloqueado ou pulado)."""
        if self.nome == "pend_e":
            return []
        return [aviso for fonte, aviso in _AVISOS.items() if fonte in self.opcionais and fonte not in entradas]

    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict, s: Servicos
    ) -> Feito | Aguardando | Pulado:
        candidatos = self._especificacao.preparar(ctx, entradas, s)
        if isinstance(candidatos, Pulado):
            return candidatos
        pendencia = nova_pendencia(self.pendencia, ctx, candidatos, self.nome, s.matriz, self._avisos(entradas))
        if (resposta := respostas.get(self.pendencia)) is not None:
            return Feito({"resposta": resposta.model_dump(mode="json")}, pendencias=[pendencia])
        return Aguardando([pendencia])


def nos_de_pendencia() -> list[PendNo]:
    """Os nove nós `pend_*`, na ordem das pendências da spec (7.1)."""
    return [PendNo(nome) for nome in _ESPECIFICACOES]
