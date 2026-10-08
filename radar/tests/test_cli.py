"""CLI (Tarefa 17): `radar coletar | verificar | dossie | diff | mcp`, em processo e sem rede.

`coletar` roda o motor com nós falsos (o `alvo` é o de verdade, só normaliza) e as outras subcomandos leem execuções
gravadas em disco por `tests/execucao_em_disco.py`. `carregar_config` aponta para `casos/` dentro de `tmp_path`.
"""

from __future__ import annotations

import io
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from radar import cli, mcp_server
from radar.arquivos import ler_json
from radar.config import Config
from radar.diff import comparar, renderizar_diff
from radar.execucao import carregar_execucao
from radar.indices import Indices
from radar.modelos import Aguardando
from radar.motor import NoBase
from radar.nos.alvo import AlvoNo
from radar.pendencias.definicoes import DEFINICOES, nova_pendencia
from radar.rede import Rede
from tests.execucao_em_disco import AGORA, MATRIZ, REF_NOTICIA, REF_PAGINA, gravar, resposta

HOJE = datetime(2026, 10, 8, 12, 0, 0)
RUN_ID = re.compile(r"[a-z0-9-]+/\d{4}-\d{2}-\d{2}_\d{6}")
PERGUNTA_A1 = DEFINICOES["P-A1"].pergunta
PERGUNTA_B = DEFINICOES["P-B"].pergunta


# ---------------------------------------------------------------------------- apoio


class PendFalsa(NoBase):
    """Abre a P-A1 e guarda os serviços que o motor lhe deu."""

    nome = "pend_a1"
    entradas = ("alvo",)

    def __init__(self, servicos: list) -> None:
        super().__init__()
        self.servicos = servicos

    async def executar(self, ctx, entradas, respostas, s):
        self.servicos.append(s)
        return Aguardando([nova_pendencia("P-A1", ctx, [], self.nome, s.matriz)])


@pytest.fixture
def casos(tmp_path, monkeypatch) -> Path:
    """A `casos/` desta execução de teste: é a que a CLI lê."""
    config = Config(casos_dir=tmp_path / "casos")
    monkeypatch.setattr(cli, "carregar_config", lambda: config)
    return config.casos_dir


@pytest.fixture(autouse=True)
def relogio(monkeypatch):
    """Um segundo a mais a cada execução criada: duas coletas do mesmo alvo nunca caem no mesmo carimbo."""
    segundos = iter(range(10_000))
    monkeypatch.setattr(cli, "_agora", lambda: HOJE + timedelta(seconds=next(segundos)))


@pytest.fixture
def nos_falsos(monkeypatch) -> list:
    """Troca os nós do Núcleo pelos falsos; a lista devolvida recebe os `Servicos` de cada nó que rodou."""
    servicos: list = []
    monkeypatch.setattr(cli, "nos_do_nucleo", lambda: [AlvoNo(), PendFalsa(servicos)])
    return servicos


@pytest.fixture
def redes_fechadas(monkeypatch) -> list[Rede]:
    """Troca `Rede` por uma que registra o `fechar()`."""
    fechadas: list[Rede] = []

    class RedeEspia(Rede):
        async def fechar(self) -> None:
            fechadas.append(self)
            await super().fechar()

    monkeypatch.setattr(cli, "Rede", RedeEspia)
    return fechadas


def run_id_de(pasta: Path) -> str:
    return f"{pasta.parent.name}/{pasta.name}"


def coletar(capsys, *argumentos: str) -> str:
    """O `run_id` que `radar coletar` imprimiu (a primeira linha); a execução tem de ter terminado com 0."""
    assert cli.main(["coletar", *argumentos]) == 0
    return capsys.readouterr().out.splitlines()[0]


# ---------------------------------------------------------------------------- verificar


def test_verificar_integra_e_adulterada(casos, capsys):
    pasta = gravar(casos)
    run_id = run_id_de(pasta)
    assert cli.main(["verificar", run_id]) == 0
    saida = capsys.readouterr()
    assert (saida.out, saida.err) == ("custódia íntegra\n", "")

    pagina = pasta / "artefatos" / f"{REF_PAGINA.removeprefix('sha256:')}.html"
    pagina.write_bytes(pagina.read_bytes() + b" ")
    assert cli.main(["verificar", run_id]) == 1
    saida = capsys.readouterr()
    assert saida.out == f"artefato alterado: {REF_PAGINA}\n"
    assert saida.err == ""


def test_verificar_um_problema_por_linha(casos, capsys):
    pasta = gravar(casos)
    for ref in (REF_PAGINA, REF_NOTICIA):
        artefato = next((pasta / "artefatos").glob(f"{ref.removeprefix('sha256:')}.*"))
        artefato.write_bytes(b"adulterado")
    assert cli.main(["verificar", run_id_de(pasta)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        f"artefato alterado: {REF_PAGINA}",
        f"artefato alterado: {REF_NOTICIA}",
    ]


# ---------------------------------------------------------------------------- dossie


def test_dossie_codigo_2_com_pendencias(casos, capsys):
    pasta = gravar(casos, abertas=("P-A1", "P-B"))
    run_id = run_id_de(pasta)
    assert cli.main(["dossie", run_id]) == 2
    saida = capsys.readouterr()
    assert saida.out == ""
    cabecalho, *linhas = saida.err.splitlines()
    assert "pendências abertas" in cabecalho and "--forcar" in cabecalho
    assert linhas == [f"P-A1: {PERGUNTA_A1}", f"P-B: {PERGUNTA_B}"]
    assert not (pasta / "dossie.md").exists()

    assert cli.main(["dossie", run_id, "--forcar"]) == 0
    saida = capsys.readouterr()
    assert Path(saida.out.strip()).resolve() == (pasta / "dossie.md").resolve()
    assert saida.err == ""
    assert "## 1. Identificação" in (pasta / "dossie.md").read_text(encoding="utf-8")


def test_dossie_sem_pendencias_imprime_o_caminho(casos, capsys):
    pasta = gravar(casos)
    assert cli.main(["dossie", run_id_de(pasta)]) == 0
    saida = capsys.readouterr()
    assert Path(saida.out.strip()).resolve() == (pasta / "dossie.md").resolve()
    assert saida.err == ""
    assert (pasta / "dossie.md").is_file()


def test_dossie_de_pasta_sem_estado(casos, capsys):
    (casos / "exemplo-com-br" / "2026-10-07_120000").mkdir(parents=True)
    assert cli.main(["dossie", "exemplo-com-br/2026-10-07_120000"]) == 2
    saida = capsys.readouterr()
    assert saida.out == "" and "sem estado.json" in saida.err


# ---------------------------------------------------------------------------- run_id


@pytest.mark.parametrize("comando", ["verificar", "dossie"])
@pytest.mark.parametrize(
    "run_id",
    [
        "../exemplo-com-br/2026-10-07_120000",
        "exemplo-com-br/../../x",
        "exemplo-com-br/2026-10-07_120000/..",
        "/exemplo-com-br/2026-10-07_120000",
        "C:\\x\\2026-10-07_120000",
        "exemplo-com-br\\2026-10-07_120000",
        "exemplo-com-br",
        "exemplo-com-br/2026-10-07_120000/artefatos",
        "Exemplo-Com-Br/2026-10-07_120000",
    ],
)
def test_run_id_invalido_sai_com_2(casos, capsys, comando, run_id):
    gravar(casos)
    assert cli.main([comando, run_id]) == 2
    saida = capsys.readouterr()
    assert saida.out == ""
    assert saida.err.startswith("erro: run_id inválido") and "Traceback" not in saida.err


@pytest.mark.parametrize("comando", ["verificar", "dossie"])
def test_run_id_inexistente_sai_com_2(casos, capsys, comando):
    gravar(casos)
    assert cli.main([comando, "outro-com-br/2026-10-07_120000"]) == 2
    saida = capsys.readouterr()
    assert (saida.out, saida.err) == ("", "erro: execução não encontrada\n")


# ---------------------------------------------------------------------------- coletar


def test_coletar_com_nos_falsos(casos, nos_falsos, redes_fechadas, capsys):
    assert cli.main(["coletar", "https://exemplo.com.br/"]) == 0
    saida = capsys.readouterr()
    run_id, *pendencias = saida.out.splitlines()
    assert RUN_ID.fullmatch(run_id) and run_id.startswith("exemplo-com-br/2026-10-08_120000")
    assert pendencias == [f"P-A1: {PERGUNTA_A1}"]
    assert saida.err == ""
    estado = ler_json(casos / run_id / "estado.json")
    assert estado["nos"]["alvo"]["status"] == "feito" and estado["nos"]["pend_a1"]["status"] == "aguardando"
    assert estado["contexto"]["modo_contato"] == "captura" and estado["contexto"]["modo_cego"] is False
    # os nós recebem a rede, os índices (cache em casos/_indices) e a matriz
    (servicos,) = nos_falsos
    assert servicos.rede is redes_fechadas[0]
    assert isinstance(servicos.indices, Indices) and servicos.matriz.versao == MATRIZ.versao
    assert servicos.custodia.pasta == casos / run_id
    assert len(redes_fechadas) == 1  # a rede é fechada no fim


def test_coletar_fecha_a_rede_quando_o_motor_falha(casos, redes_fechadas, monkeypatch, capsys):
    def nos():
        raise RuntimeError("falha no motor")

    monkeypatch.setattr(cli, "nos_do_nucleo", nos)
    assert cli.main(["coletar", "exemplo.com.br"]) == 1
    assert len(redes_fechadas) == 1
    assert "falha interna: RuntimeError" in capsys.readouterr().err


def test_coletar_sem_pendencias_imprime_so_o_run_id(casos, monkeypatch, capsys):
    monkeypatch.setattr(cli, "nos_do_nucleo", lambda: [AlvoNo()])
    assert cli.main(["coletar", "exemplo.com.br"]) == 0
    saida = capsys.readouterr().out.splitlines()
    assert len(saida) == 1 and RUN_ID.fullmatch(saida[0])


def test_coletar_as_of_e_sem_contato(casos, nos_falsos, capsys):
    run_id = coletar(capsys, "exemplo.com.br", "--as-of", "2026-01-01", "--sem-contato")
    contexto = ler_json(casos / run_id / "estado.json")["contexto"]
    assert contexto["as_of"] == "2026-01-01" and contexto["modo_contato"] == "nenhum"
    assert contexto["modo_cego"] is False
    # o padrão: as_of é hoje, com contato de captura
    contexto = ler_json(casos / coletar(capsys, "exemplo.com.br") / "estado.json")["contexto"]
    assert contexto["as_of"] == HOJE.date().isoformat() and contexto["modo_contato"] == "captura"
    # hoje vale como as_of (o que passa de hoje, não)
    contexto = ler_json(casos / coletar(capsys, "exemplo.com.br", "--as-of", "2026-10-08") / "estado.json")["contexto"]
    assert contexto["as_of"] == "2026-10-08"


def test_coletar_cego_usa_o_slug_opaco(casos, nos_falsos, capsys):
    assert cli.main(["coletar", "https://exemplo.com.br/", "--cego"]) == 0
    saida = capsys.readouterr()
    assert re.fullmatch(r"cego-[0-9a-f]{16}/\d{4}-\d{2}-\d{2}_\d{6}", saida.out.splitlines()[0])
    assert "exemplo" not in saida.out and "exemplo" not in saida.err
    assert ler_json(casos / saida.out.splitlines()[0] / "estado.json")["contexto"]["modo_cego"] is True


@pytest.mark.parametrize(
    ("as_of", "mensagem"),
    [
        ("2026-13-45", "as_of inválido: use AAAA-MM-DD"),
        ("ontem", "as_of inválido: use AAAA-MM-DD"),
        ("20260101", "as_of inválido: use AAAA-MM-DD"),
        ("2026-10-09", "as_of posterior a hoje"),
    ],
)
def test_coletar_as_of_invalido_sai_com_2(casos, nos_falsos, capsys, as_of, mensagem):
    assert cli.main(["coletar", "exemplo.com.br", "--as-of", as_of]) == 2
    saida = capsys.readouterr()
    assert (saida.out, saida.err) == ("", f"erro: {mensagem}\n")
    assert not casos.exists() and nos_falsos == []  # nada criado, nenhum nó rodou


def test_coletar_alvo_invalido_sai_com_2(casos, nos_falsos, capsys):
    assert cli.main(["coletar", "isto não é uma url"]) == 2
    saida = capsys.readouterr()
    assert saida.out == "" and saida.err.startswith("erro: alvo inválido") and "isto não é uma url" in saida.err
    # o modo cego não repete o alvo
    assert cli.main(["coletar", "isto não é uma url", "--cego"]) == 2
    assert capsys.readouterr().err == "erro: alvo inválido\n"
    assert not casos.exists()


def test_coletar_no_mesmo_segundo_sai_com_2(casos, nos_falsos, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_agora", lambda: HOJE)
    assert cli.main(["coletar", "exemplo.com.br"]) == 0
    capsys.readouterr()
    assert cli.main(["coletar", "exemplo.com.br"]) == 2
    saida = capsys.readouterr()
    assert saida.out == "" and "já existe uma execução deste alvo" in saida.err


# ---------------------------------------------------------------------------- diff


def test_diff_com_uma_execucao_so(casos, capsys):
    gravar(casos)
    assert cli.main(["diff", "exemplo-com-br"]) == 2
    saida = capsys.readouterr()
    assert saida.out == ""
    assert saida.err == "erro: são necessárias duas execuções em modo atual deste alvo para comparar\n"


def test_diff_de_alvo_sem_execucoes(casos, capsys):
    gravar(casos)
    assert cli.main(["diff", "outro.com.br"]) == 2
    assert capsys.readouterr().err == "erro: nenhuma execução deste alvo\n"


def test_diff_de_execucao_cega_e_indisponivel(casos, nos_falsos, capsys):
    primeira, segunda = coletar(capsys, "exemplo.com.br", "--cego"), coletar(capsys, "exemplo.com.br", "--cego")
    slug = primeira.split("/")[0]
    assert slug == segunda.split("/")[0]
    for argumentos in (["diff", slug], ["diff", slug, "--a", primeira, "--b", segunda]):
        assert cli.main(argumentos) == 2
        saida = capsys.readouterr()
        assert (saida.out, saida.err) == ("", "erro: indisponível no modo cego\n")


def test_diff_padrao_compara_as_duas_ultimas_em_modo_atual(casos, capsys):
    a = gravar(casos, agora=AGORA)
    gravar(casos, agora=AGORA + timedelta(days=1), as_of=date(2026, 1, 1))  # retroativa: fica de fora
    b = gravar(casos, agora=AGORA + timedelta(days=2), saidas={"pend_a1": resposta("nao_encontrado")})
    esperado = renderizar_diff(comparar(carregar_execucao(a), carregar_execucao(b), MATRIZ))

    assert cli.main(["diff", "exemplo-com-br"]) == 0
    saida = capsys.readouterr()
    assert saida.out == esperado
    assert "- Itens que mudaram:\n  - A1: confirmado (3) → não encontrado (0)" in saida.out
    assert saida.err == f"comparando {run_id_de(a)} com {run_id_de(b)}\n"


def test_diff_com_a_e_b(casos, capsys):
    a = gravar(casos, agora=AGORA)
    b = gravar(casos, agora=AGORA + timedelta(days=1), saidas={"pend_a1": resposta("nao_encontrado")})
    c = gravar(casos, agora=AGORA + timedelta(days=2))
    esperado = renderizar_diff(comparar(carregar_execucao(a), carregar_execucao(b), MATRIZ))

    # o alvo pode ser o domínio; a e b valem como run_id ou como carimbo, em qualquer ordem
    assert cli.main(["diff", "https://exemplo.com.br/", "--a", b.name, "--b", run_id_de(a)]) == 0
    saida = capsys.readouterr()
    assert saida.out == esperado and saida.err == f"comparando {run_id_de(a)} com {run_id_de(b)}\n"
    # só b: a anterior a ele em modo atual
    assert cli.main(["diff", "exemplo-com-br", "--b", c.name]) == 0
    assert capsys.readouterr().err == f"comparando {run_id_de(b)} com {run_id_de(c)}\n"

    assert cli.main(["diff", "exemplo-com-br", "--a", "2020-01-01_000000"]) == 2
    assert capsys.readouterr().err == "erro: execução não encontrada: 2020-01-01_000000\n"


# ---------------------------------------------------------------------------- mcp


def test_mcp_chama_o_servidor(monkeypatch, capsys):
    chamadas: list[int] = []
    monkeypatch.setattr(mcp_server, "main", lambda: chamadas.append(1))
    assert cli.main(["mcp"]) == 0
    assert chamadas == [1]
    saida = capsys.readouterr()
    assert (saida.out, saida.err) == ("", "")


# ---------------------------------------------------------------------------- erros e saída


def test_falha_inesperada_sem_traceback_e_com_debug(casos, monkeypatch, capsys):
    pasta = gravar(casos)

    def quebra(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "gerar_dossie", quebra)
    run_id = run_id_de(pasta)
    assert cli.main(["dossie", run_id]) == 1
    saida = capsys.readouterr()
    assert saida.out == ""
    assert saida.err == "erro: falha interna: RuntimeError (use --debug para o detalhe)\n"
    for argumentos in (["dossie", run_id, "--debug"], ["--debug", "dossie", run_id]):
        assert cli.main(argumentos) == 1
        saida = capsys.readouterr()
        assert "Traceback" in saida.err and "RuntimeError: boom" in saida.err


def test_ctrl_c_sai_sem_traceback(casos, monkeypatch, capsys):
    pasta = gravar(casos)

    def interrompe(_pasta):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "verificar", interrompe)
    assert cli.main(["verificar", run_id_de(pasta)]) == 130
    assert capsys.readouterr().err == "interrompido\n"


@pytest.mark.parametrize(
    "argv", [[], ["verificar"], ["diff"], ["coletar"], ["nao-existe"], ["coletar", "x.com", "--zzz"]]
)
def test_uso_errado_sai_com_2(capsys, argv):
    assert cli.main(argv) == 2
    saida = capsys.readouterr()
    assert saida.out == "" and "usage:" in saida.err


def test_ajuda_sai_com_0(capsys):
    assert cli.main(["--help"]) == 0
    assert "coletar" in capsys.readouterr().out


def test_saida_em_utf8(casos, monkeypatch):
    """O console do Windows costuma ser cp1252: a saída da CLI é UTF-8 de qualquer jeito."""
    pasta = gravar(casos)
    bruto = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(bruto, encoding="cp1252", newline="\n"))
    assert cli.main(["verificar", run_id_de(pasta)]) == 0
    sys.stdout.flush()
    assert bruto.getvalue().decode("utf-8") == "custódia íntegra\n"
