"""CLI do radar (`radar coletar | verificar | dossie | diff | mcp`): para os testes, para usar sem o Claude e para
conferir a custódia. Reaproveita as peças que o servidor MCP usa (`execucao`, `custodia`, `dossie`, `diff`).

O `RUN_ID` é o caminho relativo a `casos_dir` (`<slug>/<AAAA-MM-DD_HHMMSS>`), validado como no servidor.

Saída: o resultado vai para o stdout (UTF-8); erros e avisos, para o stderr, em uma linha e sem traceback (`--debug`
mostra o traceback das falhas inesperadas). Códigos de saída: 0 deu certo; 1 `verificar` achou problema na custódia
ou houve falha inesperada; 2 o pedido não pode ser atendido (argumentos, `run_id`, `as_of`, pendências abertas, nada
a comparar); 130 Ctrl+C. O `coletar` roda só os coletores: as pendências que ele deixa abertas são respondidas pelo
servidor MCP (`radar mcp`) ou ficam como `não verificado` com `dossie --forcar`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from datetime import datetime
from pathlib import Path

from radar.config import Config, carregar_config
from radar.custodia import verificar
from radar.diff import comparar, renderizar_diff
from radar.dossie import PendenciasAbertas, gerar_dossie
from radar.execucao import (
    ErroComparacao,
    carregar_execucao,
    criar_contexto,
    criar_indices,
    criar_servicos,
    escolher_execucoes,
    interpretar_as_of,
    pasta_do_run,
)
from radar.modelos import Contexto, ErroNo, Pendencia
from radar.motor import Motor
from radar.nos import nos_do_nucleo
from radar.pontuacao import carregar_matriz
from radar.rede import Rede

CODIGO_USO = 2
CODIGO_FALHA = 1
CODIGO_INTERROMPIDO = 130


class _Erro(Exception):
    """O pedido não pode ser atendido: a mensagem vai para o stderr e o programa sai com `codigo`."""

    def __init__(self, mensagem: str, codigo: int = CODIGO_USO) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


def _agora() -> datetime:
    return datetime.now()


def _pasta_da_execucao(config: Config, run_id: str) -> Path:
    pasta = pasta_do_run(config.casos_dir, run_id)
    if pasta is None:
        raise _Erro("run_id inválido: use <slug>/<AAAA-MM-DD_HHMMSS>")
    if not pasta.is_dir():
        raise _Erro("execução não encontrada")
    return pasta


# ---------------------------------------------------------------------------- subcomandos


async def _rodar(config: Config, ctx: Contexto) -> list[Pendencia]:
    """Roda os nós da execução até o fim e devolve as pendências que ficaram abertas. A rede é fechada no fim."""
    rede = Rede(config.rede)
    try:
        servicos = criar_servicos(config, ctx.pasta, rede, criar_indices(config, rede), carregar_matriz())
        motor = Motor(ctx, nos_do_nucleo(), servicos)
        await motor.executar()
        return motor.pendencias_abertas()
    finally:
        await rede.fechar()


def _coletar(args: argparse.Namespace) -> int:
    config = carregar_config()
    agora = _agora()
    as_of = None
    if args.as_of is not None:
        try:
            as_of = interpretar_as_of(args.as_of, agora.date())
        except ValueError as erro:
            raise _Erro(str(erro)) from None
    modo_contato = "nenhum" if args.sem_contato else "captura"
    try:
        ctx = criar_contexto(args.url, as_of, modo_contato, args.cego, config.casos_dir, agora)
    except ErroNo as erro:
        raise _Erro("alvo inválido" if args.cego else erro.mensagem) from None  # o modo cego não repete o alvo
    except FileExistsError:
        raise _Erro("já existe uma execução deste alvo iniciada neste segundo; chame de novo") from None
    # o run_id sai antes de a coleta começar: ela leva minutos, e uma falha no meio não pode escondê-lo
    print(ctx.run_id, flush=True)
    for pendencia in asyncio.run(_rodar(config, ctx)):
        print(f"{pendencia.id}: {pendencia.pergunta}")
    return 0


def _verificar(args: argparse.Namespace) -> int:
    pasta = _pasta_da_execucao(carregar_config(), args.run_id)
    problemas = verificar(pasta)
    if not problemas:
        print("custódia íntegra")
        return 0
    for problema in problemas:
        print(problema)
    return 1


def _dossie(args: argparse.Namespace) -> int:
    pasta = _pasta_da_execucao(carregar_config(), args.run_id)
    if not (pasta / "estado.json").is_file():
        raise _Erro("execução sem estado.json")
    try:
        caminho = gerar_dossie(pasta, carregar_matriz(), args.forcar)
    except PendenciasAbertas as erro:
        perguntas = {pid: p.get("pergunta", "") for pid, p in carregar_execucao(pasta).pendencias.items()}
        linhas = [f"{pid}: {perguntas.get(pid, '')}" for pid in erro.ids]
        cabecalho = "há pendências abertas (--forcar gera o dossiê assim, com os itens delas como não verificado):"
        raise _Erro("\n".join([cabecalho, *linhas])) from None
    print(caminho)
    return 0


def _diff(args: argparse.Namespace) -> int:
    config = carregar_config()
    try:
        anterior, atual = escolher_execucoes(config.casos_dir, args.slug, args.a, args.b)
    except ErroComparacao as erro:
        raise _Erro(str(erro)) from None
    print(f"comparando {anterior} com {atual}", file=sys.stderr)
    diff = comparar(
        carregar_execucao(config.casos_dir / anterior), carregar_execucao(config.casos_dir / atual), carregar_matriz()
    )
    sys.stdout.write(renderizar_diff(diff))
    return 0


def _mcp(_args: argparse.Namespace) -> int:
    from radar import mcp_server  # o SDK do MCP é pesado: só quem sobe o servidor o carrega

    mcp_server.main()
    return 0


# ---------------------------------------------------------------------------- argumentos


def _parser() -> argparse.ArgumentParser:
    debug = "mostra o traceback das falhas inesperadas"
    comum = argparse.ArgumentParser(add_help=False)
    # sem padrão aqui: o `--debug` dado antes do subcomando não pode ser apagado pelo padrão do subparser
    comum.add_argument("--debug", action="store_true", default=argparse.SUPPRESS, help=debug)

    parser = argparse.ArgumentParser(prog="radar", description="Radar de pirâmides financeiras.")
    parser.add_argument("--debug", action="store_true", help=debug)
    comandos = parser.add_subparsers(dest="comando", required=True, metavar="comando")

    coletar = comandos.add_parser(
        "coletar",
        parents=[comum],
        help="roda os coletores e imprime o run_id e as pendências abertas",
        description="Roda os coletores até o fim. Imprime o run_id e, em seguida, uma linha '<id>: <pergunta>' "
        "por pendência aberta.",
    )
    coletar.add_argument("url", metavar="URL", help="domínio ou URL do site a analisar")
    coletar.add_argument("--as-of", metavar="AAAA-MM-DD", help="analisa o site como ele era nesta data (padrão: hoje)")
    coletar.add_argument("--sem-contato", action="store_true", help="não visita o site (usa o Wayback)")
    coletar.add_argument("--cego", action="store_true", help="run_id opaco: a pasta não diz o alvo")
    coletar.set_defaults(executar=_coletar)

    verificar_ = comandos.add_parser(
        "verificar",
        parents=[comum],
        help="confere a custódia (cadeia do log e hash dos artefatos)",
        description="Imprime 'custódia íntegra' (código 0) ou um problema por linha (código 1).",
    )
    verificar_.add_argument("run_id", metavar="RUN_ID", help="<slug>/<AAAA-MM-DD_HHMMSS>, dentro de casos/")
    verificar_.set_defaults(executar=_verificar)

    dossie = comandos.add_parser(
        "dossie",
        parents=[comum],
        help="gera o dossiê e imprime o caminho",
        description="Gera o dossiê e imprime o caminho do dossie.md. Com pendências abertas e sem --forcar, imprime "
        "as pendências no stderr e sai com 2.",
    )
    dossie.add_argument("run_id", metavar="RUN_ID", help="<slug>/<AAAA-MM-DD_HHMMSS>, dentro de casos/")
    dossie.add_argument("--forcar", action="store_true", help="gera com pendências abertas (viram não verificado)")
    dossie.set_defaults(executar=_dossie)

    diff = comandos.add_parser(
        "diff",
        parents=[comum],
        help="compara duas execuções do mesmo alvo",
        description="Imprime o diff entre duas execuções do mesmo alvo. Sem --a e --b, compara as duas últimas em "
        "modo atual. Indisponível para execuções no modo cego.",
    )
    diff.add_argument("slug", metavar="SLUG", help="slug, domínio ou URL do alvo")
    diff.add_argument("--a", metavar="RUN_ID", help="a execução mais antiga (run_id ou carimbo)")
    diff.add_argument("--b", metavar="RUN_ID", help="a execução mais nova (run_id ou carimbo)")
    diff.set_defaults(executar=_diff)

    mcp = comandos.add_parser(
        "mcp", parents=[comum], help="sobe o servidor MCP em stdio", description="Sobe o servidor MCP em stdio."
    )
    mcp.set_defaults(executar=_mcp)
    return parser


def _saida_utf8() -> None:
    """O console do Windows costuma ser cp1252: a saída da CLI é UTF-8 de qualquer jeito."""
    for fluxo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is not None:
            try:
                reconfigurar(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    _saida_utf8()
    try:
        args = _parser().parse_args(argv)
    except SystemExit as saida:  # `--help` (0) e erro de uso (2): o argparse já escreveu a mensagem
        return saida.code if isinstance(saida.code, int) else 0
    try:
        return args.executar(args)
    except _Erro as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return erro.codigo
    except KeyboardInterrupt:
        print("interrompido", file=sys.stderr)
        return CODIGO_INTERROMPIDO
    except Exception as erro:  # o detalhe pode trazer o alvo: no modo cego, só com --debug
        if args.debug:
            traceback.print_exc()
        else:
            print(f"erro: falha interna: {type(erro).__name__} (use --debug para o detalhe)", file=sys.stderr)
        return CODIGO_FALHA


if __name__ == "__main__":
    sys.exit(main())
