"""Motor do DAG: ordem, paralelismo, pendências, correção, concorrência e retomada (Tarefa 5)."""

from __future__ import annotations

import asyncio
import graphlib
import inspect
import json
import shutil
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pytest

from radar.arquivos import ler_json
from radar.config import Config
from radar.custodia import Custodia, verificar
from radar.modelos import Aguardando, Contexto, ErroNo, Feito, Pendencia, Pulado, Resposta
from radar.motor import Motor, NoBase, Servicos
from radar.rede import Rede


def ctx(pasta: Path, as_of: date = date(2026, 10, 7)) -> Contexto:
    return Contexto(
        alvo="exemplo.com.br",
        slug="exemplo-com-br",
        url_inicial="https://exemplo.com.br/",
        as_of=as_of,
        data_execucao=datetime(2026, 10, 7, 12, 0, 0),
        modo_contato="captura",
        modo_cego=False,
        run_id="exemplo-com-br/2026-10-07_120000",
        pasta=pasta,
    )


@pytest.fixture
async def serv(tmp_path):
    config = Config()
    rede = Rede(config.rede)
    yield Servicos(config=config, rede=rede, custodia=Custodia(tmp_path))
    await rede.fechar()


class Diario:
    """O que os nós falsos fizeram: ordem das chamadas, contagem, entradas e respostas recebidas."""

    def __init__(self) -> None:
        self.ordem: list[str] = []
        self.contador: Counter[str] = Counter()
        self.entradas: dict[str, dict] = {}
        self.respostas: dict[str, dict] = {}


@pytest.fixture
def diario() -> Diario:
    return Diario()


class Falso(NoBase):
    """Nó de teste: registra a chamada no diário e devolve o resultado de `acao` (sync ou async)."""

    def __init__(self, nome: str, diario: Diario, acao=None, **atributos) -> None:
        super().__init__(nome=nome, **atributos)
        self.diario = diario
        self.acao = acao

    async def executar(self, ctx, entradas, respostas, s):
        self.diario.ordem.append(self.nome)
        self.diario.contador[self.nome] += 1
        self.diario.entradas[self.nome] = entradas
        self.diario.respostas[self.nome] = respostas
        if self.acao is None:
            return Feito({"de": self.nome})
        resultado = self.acao(entradas, respostas)
        return await resultado if inspect.isawaitable(resultado) else resultado


def pend(id_: str, no: str) -> Pendencia:
    return Pendencia(
        id=id_,
        itens=["X"],
        pergunta=f"pergunta de {id_}",
        criterios="",
        candidatos=[],
        formato_resposta={},
        restricoes={},
        conteudo_do_alvo="",
        no_origem=no,
    )


def pede(no: str, *ids: str):
    """Ação de nó de pendência: `Aguardando` as que não têm resposta; com todas, `Feito` com os valores."""

    def acao(entradas, respostas):
        faltam = [pend(i, no) for i in ids if i not in respostas]
        return Aguardando(faltam) if faltam else Feito({i: respostas[i].valor for i in ids})

    return acao


def resp(substitui: str | None = None, **valor) -> Resposta:
    return Resposta(status="inconclusivo", valor=valor, substitui=substitui)


def falha(mensagem: str):
    def acao(entradas, respostas):
        raise ErroNo(mensagem, permanente=True)

    return acao


def motivos(pasta: Path) -> dict[str, str | None]:
    return {nome: no["motivo"] for nome, no in ler_json(pasta / "estado.json")["nos"].items()}


def linhas_custodia(pasta: Path) -> list[dict]:
    log = pasta / "custodia.log"
    if not log.exists():
        return []
    return [json.loads(linha) for linha in log.read_text(encoding="utf-8").splitlines()]


# --- ordem, paralelismo e propagação ---------------------------------------------------------


async def test_ordem_topologica(tmp_path, serv, diario):  # a→b→c, passados fora de ordem
    nos = [Falso("c", diario, entradas=("b",)), Falso("b", diario, entradas=("a",)), Falso("a", diario)]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    assert diario.ordem == ["a", "b", "c"] and set(m.status().values()) == {"feito"}
    assert diario.entradas == {"a": {}, "b": {"a": {"de": "a"}}, "c": {"b": {"de": "b"}}}
    assert m.saidas("c") == {"de": "c"} and m.saidas("inexistente") is None


async def test_paralelo(tmp_path, serv, diario):  # b só termina depois que c começa: exige b e c juntos
    c_comecou = asyncio.Event()

    async def espera_c(entradas, respostas):
        await c_comecou.wait()
        return Feito({})

    def avisa(entradas, respostas):
        c_comecou.set()
        return Feito({})

    nos = [
        Falso("a", diario),
        Falso("b", diario, espera_c, entradas=("a",)),
        Falso("c", diario, avisa, entradas=("a",)),
    ]
    m = Motor(ctx(tmp_path), nos, serv)
    await asyncio.wait_for(m.executar(), timeout=5)
    assert m.status()["b"] == m.status()["c"] == "feito"


async def test_erro_bloqueia_so_dependentes(tmp_path, serv, diario):
    nos = [
        Falso("a", diario, falha("fonte fora do ar")),
        Falso("b", diario, entradas=("a",)),
        Falso("c", diario, entradas=("b",)),
        Falso("x", diario),
    ]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    assert m.status() == {"a": "erro", "b": "bloqueado", "c": "bloqueado", "x": "feito"}
    assert motivos(tmp_path) == {
        "a": "fonte fora do ar",
        "b": "dependência com erro: a",
        "c": "dependência bloqueada: b",
        "x": None,
    }
    assert "b" not in diario.contador and "c" not in diario.contador


async def test_excecao_inesperada_vira_erro_sem_derrubar_o_motor(tmp_path, serv, diario):
    def explode(entradas, respostas):
        raise RuntimeError("boom")

    nos = [Falso("a", diario, explode), Falso("b", diario, entradas=("a",)), Falso("x", diario)]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    assert m.status() == {"a": "erro", "b": "bloqueado", "x": "feito"}
    assert motivos(tmp_path)["a"] == "erro inesperado: RuntimeError: boom"


async def test_resultado_invalido_e_saidas_normalizadas(tmp_path, serv, diario):
    nos = [
        Falso("nada", diario, lambda e, r: None),
        Falso("objeto", diario, lambda e, r: Feito({"x": object()})),
        Falso("data", diario, lambda e, r: Feito({"d": date(2020, 1, 2), "t": (1, 2)})),
        Falso("usa", diario, entradas=("data",)),
    ]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    assert m.status() == {"nada": "erro", "objeto": "erro", "data": "feito", "usa": "feito"}
    assert motivos(tmp_path)["nada"] == "resultado inválido: NoneType"
    assert motivos(tmp_path)["objeto"].startswith("saídas não serializáveis em JSON: ")
    # o dependente recebe o mesmo que receberia depois de uma retomada (o JSON do disco)
    assert diario.entradas["usa"] == {"data": {"d": "2020-01-02", "t": [1, 2]}}


class FeitoQuebrado(Feito):
    """Passa no isinstance, mas ler `saidas` levanta: exercita a proteção genérica do resultado."""

    @property
    def saidas(self):
        raise RuntimeError("quebrou")


async def test_resultado_malformado_vira_erro_e_a_retomada_segue(tmp_path, serv, diario):
    def explode_erro(entradas, respostas):
        raise ErroNo(object(), permanente=True)  # mensagem que não é texto

    def nos():
        return [
            Falso("lista_de_dict", diario, lambda e, r: Aguardando([{"id": "P-1"}])),
            Falso("pendencias_none", diario, lambda e, r: Aguardando(None)),
            Falso("nada", diario, lambda e, r: None),
            Falso("dict", diario, lambda e, r: {"x": 1}),
            Falso("pulado_ruim", diario, lambda e, r: Pulado(object())),
            Falso("erro_ruim", diario, explode_erro),
            Falso("quebrado", diario, lambda e, r: object.__new__(FeitoQuebrado)),
            Falso("x", diario),
            Falso("dep", diario, entradas=("x",)),
        ]

    ruins = ["lista_de_dict", "pendencias_none", "nada", "dict", "pulado_ruim", "erro_ruim", "quebrado"]
    esperado = {**dict.fromkeys(ruins, "erro"), "x": "feito", "dep": "feito"}
    m = Motor(ctx(tmp_path), nos(), serv)
    await m.executar()
    assert m.status() == esperado
    assert {n: v["status"] for n, v in ler_json(tmp_path / "estado.json")["nos"].items()} == esperado
    aguardando_ruim = "resultado inválido: Aguardando.pendencias precisa ser lista de Pendencia"
    assert motivos(tmp_path) | {"erro_ruim": None} == {
        "lista_de_dict": f"{aguardando_ruim} (veio item dict)",
        "pendencias_none": f"{aguardando_ruim} (veio NoneType)",
        "nada": "resultado inválido: NoneType",
        "dict": "resultado inválido: dict",
        "pulado_ruim": "resultado inválido: Pulado.motivo precisa ser texto (veio object)",
        "erro_ruim": None,
        "quebrado": "resultado inválido: RuntimeError: quebrou",
        "x": None,
        "dep": None,
    }
    assert motivos(tmp_path)["erro_ruim"].startswith("<object object at ")
    assert m.pendencias_abertas() == []

    # a retomada não levanta e não reexecuta nada: os nós ruins ficam em `erro`
    m2 = Motor.carregar(tmp_path, nos(), serv)
    await m2.executar()
    assert m2.status() == esperado and diario.contador == Counter(dict.fromkeys(esperado, 1))


def test_no_declara_saidas(diario):
    class Rdap(NoBase):
        nome = "rdap"
        saidas = ("registro", "expiracao")

        async def executar(self, ctx, entradas, respostas, s):
            return Feito({})

    assert NoBase.saidas == () and Falso("x", diario).saidas == ()
    assert Rdap().saidas == ("registro", "expiracao")
    assert Rdap(saidas=["cnpj_titular"]).saidas == ("cnpj_titular",)
    assert Rdap.saidas == ("registro", "expiracao")  # a troca é só na instância


async def test_pulado_e_opcionais(tmp_path, serv, diario):
    nos = [
        Falso("pula", diario, lambda e, r: Pulado("modo nenhum")),
        Falso("falha", diario, falha("4xx")),
        Falso("ok", diario),
        Falso("obrig", diario, entradas=("pula",)),
        Falso("opc", diario, entradas=("ok",), opcionais=("pula", "falha")),
    ]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    assert m.status() == {
        "pula": "pulado",
        "falha": "erro",
        "ok": "feito",
        "obrig": "pulado",
        "opc": "feito",
    }
    assert motivos(tmp_path)["obrig"] == "dependência pulada: pula"
    assert motivos(tmp_path)["pula"] == "modo nenhum"
    assert "obrig" not in diario.contador
    # opcionais só entram se `feito`, mas o nó espera elas terminarem
    assert diario.entradas["opc"] == {"ok": {"de": "ok"}}
    assert diario.ordem.index("opc") > max(diario.ordem.index("pula"), diario.ordem.index("falha"))


async def test_exige_um_de(tmp_path, serv, diario):  # x pulado, y feito → e feito; ambos pulados → e bloqueado
    def pula(entradas, respostas):
        return Pulado("n/a")

    um =[Falso("x", diario, pula), Falso("y", diario), Falso("e", diario, exige_um_de=("x", "y"))]
    m = Motor(ctx(tmp_path / "um"), um, serv)
    await m.executar()
    assert m.status()["e"] == "feito" and diario.entradas["e"] == {"y": {"de": "y"}}

    dois = [Falso("x", diario, pula), Falso("y", diario, pula), Falso("e", diario, exige_um_de=("x", "y"))]
    m2 = Motor(ctx(tmp_path / "dois"), dois, serv)
    await m2.executar()
    assert m2.status()["e"] == "bloqueado"
    assert motivos(tmp_path / "dois")["e"] == "nenhuma dependência feita entre: x, y"


async def test_so_atual_pulado_no_retroativo(tmp_path, serv, diario):
    def nos():
        return [
            Falso("alvo", diario),
            Falso("dns", diario, entradas=("alvo",), as_of="so_atual"),
            Falso("ct", diario, entradas=("alvo",), as_of="filtravel"),
        ]

    m = Motor(ctx(tmp_path, as_of=date(2019, 5, 1)), nos(), serv)
    await m.executar()
    estado = ler_json(tmp_path / "estado.json")
    assert m.status()["dns"] == "pulado" and estado["nos"]["dns"]["motivo"] == "só atual"
    assert m.status()["ct"] == "feito" and "dns" not in diario.contador

    atual = Motor(ctx(tmp_path / "atual"), nos(), serv)
    await atual.executar()
    assert atual.status()["dns"] == "feito"


# --- pendências --------------------------------------------------------------------------------


async def test_aguardando_e_responder(tmp_path, serv, diario):
    m = Motor(ctx(tmp_path), [Falso("p", diario, pede("p", "P-X")), Falso("d", diario, entradas=("p",))], serv)
    await m.executar()
    assert [p.id for p in m.pendencias_abertas()] == ["P-X"] and m.status()["d"] == "pendente"
    assert m.status()["p"] == "aguardando" and diario.contador["p"] == 1
    assert await m.responder("P-X", Resposta(status="nao_encontrado", onde_procurou=["x"])) == []
    assert m.status() == {"p": "feito", "d": "feito"}
    assert diario.respostas["p"]["P-X"].status == "nao_encontrado"
    assert diario.entradas["d"] == {"p": {"P-X": {}}}


async def test_aguardando_retem_ate_todas_respondidas(tmp_path, serv, diario):
    m = Motor(ctx(tmp_path), [Falso("q", diario, pede("q", "P-1", "P-2"))], serv)
    await m.executar()
    assert [p.id for p in m.pendencias_abertas()] == ["P-1", "P-2"]

    abertas = await m.responder("P-1", resp(v=1))
    assert [p.id for p in abertas] == ["P-2"]
    assert m.status()["q"] == "aguardando" and diario.contador["q"] == 1

    assert await m.responder("P-2", resp(v=2)) == []
    assert m.status()["q"] == "feito" and diario.contador["q"] == 2
    assert set(diario.respostas["q"]) == {"P-1", "P-2"}
    assert m.saidas("q") == {"P-1": {"v": 1}, "P-2": {"v": 2}}


async def test_opcional_aguardando_segura_o_dependente(tmp_path, serv, diario):
    nos = [Falso("p", diario, pede("p", "P-X")), Falso("o", diario, opcionais=("p",))]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    assert m.status() == {"p": "aguardando", "o": "pendente"}
    await m.responder("P-X", resp(v=1))
    assert m.status() == {"p": "feito", "o": "feito"} and diario.entradas["o"] == {"p": {"P-X": {"v": 1}}}


async def test_guardas_do_aguardando(tmp_path, serv, diario):
    nos = [
        Falso("vazio", diario, lambda e, r: Aguardando([])),
        Falso("p", diario, pede("p", "P-X")),
        Falso("x", diario),
        # roda num lote depois de `p` e tenta pegar a pendência dele
        Falso("intruso", diario, lambda e, r: Aguardando([pend("P-X", "intruso")]), entradas=("x",)),
    ]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    assert m.status() == {"vazio": "erro", "p": "aguardando", "x": "feito", "intruso": "erro"}
    assert motivos(tmp_path)["vazio"] == "Aguardando sem pendências"
    assert motivos(tmp_path)["intruso"] == "a pendência P-X já pertence ao nó p"
    assert [p.no_origem for p in m.pendencias_abertas()] == ["p"]


async def test_aguardando_so_com_respondidas_vira_erro(tmp_path, serv, diario):  # sem laço infinito
    teimoso = Falso("teimoso", diario, lambda e, r: Aguardando([pend("P-T", "teimoso")]))
    m = Motor(ctx(tmp_path), [teimoso], serv)
    await m.executar()
    assert await asyncio.wait_for(m.responder("P-T", resp(v=1)), timeout=5) == []
    assert m.status() == {"teimoso": "erro"} and diario.contador["teimoso"] == 2
    assert motivos(tmp_path)["teimoso"] == "Aguardando só com pendências já respondidas: P-T"


# --- julgamentos e correções -------------------------------------------------------------------


async def test_correcao_mantem_historico(tmp_path, serv, diario):
    m = Motor(ctx(tmp_path), [Falso("p", diario, pede("p", "P-X"))], serv)
    await m.executar()
    await m.responder("P-X", resp(v=1))
    await m.responder("P-X", resp(v=2, substitui="P-X#1"))

    julgamentos = ler_json(tmp_path / "julgamentos.json")
    assert [(j["id"], j["pendencia"], j["substitui"], j["ativa"]) for j in julgamentos] == [
        ("P-X#1", "P-X", None, False),
        ("P-X#2", "P-X", "P-X#1", True),
    ]
    assert julgamentos[1]["resposta"]["valor"] == {"v": 2}
    assert julgamentos[1]["resposta"]["substitui"] == "P-X#1"
    assert datetime.fromisoformat(julgamentos[0]["em"]) <= datetime.fromisoformat(julgamentos[1]["em"])

    # cada resposta aceita também vai para a custódia
    linhas = linhas_custodia(tmp_path)
    assert [(linha["tipo"], linha["origem"]) for linha in linhas] == [
        ("julgamento", "P-X#1"),
        ("julgamento", "P-X#2"),
    ]
    guardado = json.loads(Custodia(tmp_path).ler("sha256:" + linhas[0]["sha256"]))
    assert guardado == {k: v for k, v in julgamentos[0].items() if k != "ativa"}
    assert verificar(tmp_path) == []


async def test_correcao_reexecuta_dono_e_descendentes(tmp_path, serv, diario):
    nos = [
        Falso("p", diario, pede("p", "P-X")),
        Falso("d", diario, lambda e, r: Feito({"dobro": e["p"]["P-X"]["v"] * 2}), entradas=("p",)),
        Falso("f", diario, entradas=("d",)),
        Falso("x", diario),
    ]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    await m.responder("P-X", resp(v=1))
    assert m.saidas("d") == {"dobro": 2}
    assert diario.contador == Counter({"p": 2, "d": 1, "f": 1, "x": 1})

    assert await m.responder("P-X", resp(v=5, substitui="P-X#1")) == []
    assert diario.contador == Counter({"p": 3, "d": 2, "f": 2, "x": 1})
    assert diario.entradas["d"] == {"p": {"P-X": {"v": 5}}}
    assert m.saidas("d") == {"dobro": 10} and set(m.status().values()) == {"feito"}
    assert ler_json(tmp_path / "evidencias.json")["d"] == {"dobro": 10}


async def test_responder_rejeita_sem_gravar(tmp_path, serv, diario):
    m = Motor(ctx(tmp_path), [Falso("p", diario, pede("p", "P-X"))], serv)
    await m.executar()
    with pytest.raises(ValueError, match="pendência desconhecida: P-Y"):
        await m.responder("P-Y", resp(v=1))
    with pytest.raises(ValueError, match="não tem resposta ativa"):
        await m.responder("P-X", resp(v=1, substitui="P-X#1"))
    await m.responder("P-X", resp(v=1))
    with pytest.raises(ValueError, match=r"já tem resposta ativa \(P-X#1\)"):
        await m.responder("P-X", resp(v=2))
    with pytest.raises(ValueError, match="P-X#9 não é o julgamento ativo"):
        await m.responder("P-X", resp(v=2, substitui="P-X#9"))
    assert [j["id"] for j in ler_json(tmp_path / "julgamentos.json")] == ["P-X#1"]
    assert len(linhas_custodia(tmp_path)) == 1 and diario.contador["p"] == 2


async def test_respostas_concorrentes(tmp_path, serv, diario):
    def devagar(no, pid):
        async def acao(entradas, respostas):
            if pid not in respostas:
                return Aguardando([pend(pid, no)])
            await asyncio.sleep(0.02)  # sem a trava, a outra resposta reexecutaria este nó junto
            return Feito({"v": respostas[pid].valor["v"]})

        return acao

    nos = [Falso("p1", diario, devagar("p1", "P-1")), Falso("p2", diario, devagar("p2", "P-2"))]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    await asyncio.gather(m.responder("P-1", resp(v=1)), m.responder("P-2", resp(v=2)))

    assert m.status() == {"p1": "feito", "p2": "feito"} and m.pendencias_abertas() == []
    assert diario.contador == Counter({"p1": 2, "p2": 2})
    julgamentos = ler_json(tmp_path / "julgamentos.json")
    assert sorted((j["id"], j["ativa"]) for j in julgamentos) == [("P-1#1", True), ("P-2#1", True)]
    estado = ler_json(tmp_path / "estado.json")
    assert {n: v["status"] for n, v in estado["nos"].items()} == {"p1": "feito", "p2": "feito"}
    assert {pid: p["aberta"] for pid, p in estado["pendencias"].items()} == {"P-1": False, "P-2": False}
    assert ler_json(tmp_path / "evidencias.json") == {"p1": {"v": 1}, "p2": {"v": 2}}
    assert verificar(tmp_path) == [] and not (tmp_path / "motor.lock").exists()


# --- estado em disco e retomada ----------------------------------------------------------------


async def test_estado_em_disco(tmp_path, serv, diario):
    nos = [
        Falso("a", diario),
        Falso("p", diario, pede("p", "P-X"), entradas=("a",)),
        Falso("s", diario, lambda e, r: Pulado("não se aplica")),
    ]
    c = ctx(tmp_path)
    m = Motor(c, nos, serv)
    await m.executar()
    estado = ler_json(tmp_path / "estado.json")
    assert estado["contexto"] == c.model_dump(mode="json")
    assert estado["nos"] == {
        "a": {"status": "feito", "motivo": None},
        "p": {"status": "aguardando", "motivo": None},
        "s": {"status": "pulado", "motivo": "não se aplica"},
    }
    assert estado["pendencias"] == {"P-X": {**pend("P-X", "p").model_dump(mode="json"), "aberta": True}}
    assert ler_json(tmp_path / "evidencias.json") == {"a": {"de": "a"}}
    assert ler_json(tmp_path / "julgamentos.json") == []
    # nada de trava nem temporário esquecido
    assert sorted(f.name for f in tmp_path.iterdir()) == ["estado.json", "evidencias.json", "julgamentos.json"]


async def test_estado_gravado_a_cada_mudanca(tmp_path, serv, diario):
    def espia(entradas, respostas):
        estado = ler_json(tmp_path / "estado.json")
        return Feito({"visto": {nome: no["status"] for nome, no in estado["nos"].items()}})

    m = Motor(ctx(tmp_path), [Falso("a", diario), Falso("b", diario, espia, entradas=("a",))], serv)
    await m.executar()
    assert m.saidas("b") == {"visto": {"a": "feito", "b": "executando"}}


async def test_retomada_sem_reexecutar(tmp_path, serv, diario):
    nos = [
        Falso("a", diario),
        Falso("p", diario, pede("p", "P-X"), entradas=("a",)),
        Falso("d", diario, entradas=("p",)),
    ]
    m = Motor(ctx(tmp_path), nos, serv)
    await m.executar()
    n = diario.contador["a"]

    m2 = Motor.carregar(tmp_path, nos, serv)
    await m2.executar()
    assert diario.contador["a"] == n and diario.contador["p"] == 1
    assert [p.id for p in m2.pendencias_abertas()] == ["P-X"]
    assert m2.ctx == m.ctx and m2.status() == m.status() and m2.saidas("a") == {"de": "a"}

    assert await m2.responder("P-X", resp(v=1)) == []
    assert m2.status() == {"a": "feito", "p": "feito", "d": "feito"} and diario.contador["a"] == n
    assert diario.entradas["d"] == {"p": {"P-X": {"v": 1}}}


async def test_retomada_depois_de_queda(tmp_path, serv, diario):
    b_comecou = asyncio.Event()

    async def trava_na_primeira(entradas, respostas):
        if diario.contador["b"] == 1:
            b_comecou.set()
            await asyncio.Event().wait()  # o processo "morre" aqui
        return Feito({"b": entradas["a"]})

    nos = [Falso("a", diario), Falso("b", diario, trava_na_primeira, entradas=("a",))]
    m = Motor(ctx(tmp_path), nos, serv)
    tarefa = asyncio.create_task(m.executar())
    await asyncio.wait_for(b_comecou.wait(), timeout=5)
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa
    assert {n: v["status"] for n, v in ler_json(tmp_path / "estado.json")["nos"].items()} == {
        "a": "feito",
        "b": "executando",
    }

    m2 = Motor.carregar(tmp_path, nos, serv)
    assert m2.status() == {"a": "feito", "b": "pendente"}
    await m2.executar()
    assert m2.status() == {"a": "feito", "b": "feito"} and m2.saidas("b") == {"b": {"de": "a"}}
    assert diario.contador == Counter({"a": 1, "b": 2})


async def test_carregar_usa_a_pasta_onde_esta(tmp_path, serv, diario):
    original = tmp_path / "original"
    nos = [Falso("p", diario, pede("p", "P-X"))]
    await Motor(ctx(original), nos, serv).executar()
    movida = tmp_path / "movida"
    shutil.copytree(original, movida)

    m = Motor.carregar(movida, nos, serv)
    assert m.ctx == ctx(movida)
    await m.responder("P-X", resp(v=1))
    assert ler_json(movida / "estado.json")["contexto"]["pasta"] == str(movida)
    assert ler_json(original / "julgamentos.json") == []


async def test_carregar_sem_estado_ou_com_status_desconhecido(tmp_path, serv, diario):
    with pytest.raises(FileNotFoundError, match="estado.json"):
        Motor.carregar(tmp_path, [Falso("a", diario)], serv)
    await Motor(ctx(tmp_path), [Falso("a", diario)], serv).executar()
    estado = ler_json(tmp_path / "estado.json")
    estado["nos"]["a"]["status"] = "concluido"
    (tmp_path / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    with pytest.raises(ValueError, match="status desconhecido em estado.json: a='concluido'"):
        Motor.carregar(tmp_path, [Falso("a", diario)], serv)


# --- validação do grafo ------------------------------------------------------------------------


async def test_validacao_do_grafo(tmp_path, serv, diario):
    with pytest.raises(ValueError, match="o nó a depende de nó inexistente: z"):
        Motor(ctx(tmp_path), [Falso("a", diario, opcionais=("z",))], serv)
    with pytest.raises(ValueError, match="nome de nó repetido: a"):
        Motor(ctx(tmp_path), [Falso("a", diario), Falso("a", diario)], serv)
    with pytest.raises(graphlib.CycleError):
        Motor(ctx(tmp_path), [Falso("a", diario, entradas=("b",)), Falso("b", diario, exige_um_de=("a",))], serv)
