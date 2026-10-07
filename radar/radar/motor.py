"""Motor do DAG: ordem topológica incremental, paralelismo, pendências, estado em disco e retomada."""

from __future__ import annotations

import asyncio
import copy
import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Any, get_args

# `_serializar` é o mesmo `default` da gravação em disco: o que um dependente recebe em memória
# fica igual ao que receberia depois de uma retomada
from radar.arquivos import _serializar, gravar_json_atomico, ler_json, trava
from radar.config import Config
from radar.custodia import Custodia
from radar.modelos import (
    Aguardando,
    CapacidadeAsOf,
    Contexto,
    ErroNo,
    Feito,
    Pendencia,
    Pulado,
    Resposta,
    StatusNo,
)
from radar.rede import Rede

_STATUS = frozenset(get_args(StatusNo))
_TERMINAIS = frozenset({"feito", "pulado", "erro", "bloqueado"})
_COM_MOTIVO = frozenset({"erro", "bloqueado", "pulado"})


@dataclass
class Servicos:
    config: Config
    rede: Rede
    custodia: Custodia
    indices: Any = None  # Tarefa 11
    matriz: Any = None  # Tarefa 14


class NoBase(ABC):
    """Nó do DAG. Os atributos de classe podem ser trocados por instância no construtor."""

    nome: str
    entradas: tuple[str, ...] = ()  # obrigatórias
    opcionais: tuple[str, ...] = ()
    exige_um_de: tuple[str, ...] = ()
    saidas: tuple[str, ...] = ()  # declarativo (spec 5): o motor não confere
    toca_alvo: bool = False
    as_of: CapacidadeAsOf = "exato"

    def __init__(
        self,
        *,
        nome: str | None = None,
        entradas: Iterable[str] | None = None,
        opcionais: Iterable[str] | None = None,
        exige_um_de: Iterable[str] | None = None,
        saidas: Iterable[str] | None = None,
        toca_alvo: bool | None = None,
        as_of: CapacidadeAsOf | None = None,
    ) -> None:
        if nome is not None:
            self.nome = nome
        if entradas is not None:
            self.entradas = tuple(entradas)
        if opcionais is not None:
            self.opcionais = tuple(opcionais)
        if exige_um_de is not None:
            self.exige_um_de = tuple(exige_um_de)
        if saidas is not None:
            self.saidas = tuple(saidas)
        if toca_alvo is not None:
            self.toca_alvo = toca_alvo
        if as_of is not None:
            self.as_of = as_of

    @abstractmethod
    async def executar(
        self, ctx: Contexto, entradas: dict[str, dict], respostas: dict[str, Resposta], s: Servicos
    ) -> Feito | Aguardando | Pulado:
        """`entradas`: saídas das dependências `feito`. `respostas`: respostas ativas às pendências
        deste nó, pelo id da pendência."""


def _dependencias(no: NoBase) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*no.entradas, *no.opcionais, *no.exige_um_de)))


def _canonico(dados: Any) -> str:
    return json.dumps(dados, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _normalizar(saidas: Any) -> dict:
    """As saídas como ficam no `evidencias.json` (datas em ISO, tuplas como listas)."""
    if not isinstance(saidas, dict):
        raise TypeError(f"Feito.saidas precisa ser dict, veio {type(saidas).__name__}")
    return json.loads(json.dumps(saidas, ensure_ascii=False, default=_serializar))


class Motor:
    """Executa os nós em ordem topológica e guarda tudo em `ctx.pasta`.

    Cada passada monta um `TopologicalSorter` novo: os nós já terminados recebem `done()` na hora,
    os prontos de cada lote rodam juntos (`asyncio.gather`) e os `aguardando` ficam retidos sem
    `done()`, o que segura os dependentes. Uma resposta destrava o dono da pendência na próxima
    passada. `executar()` e `responder()` são serializados pela trava da instância; toda
    gravação passa pela trava de arquivo `motor.lock`.
    """

    def __init__(self, ctx: Contexto, nos: list[NoBase], servicos: Servicos) -> None:
        self.ctx = ctx
        self.servicos = servicos
        self._nos: dict[str, NoBase] = {}
        for no in nos:
            nome = getattr(no, "nome", None)
            if not isinstance(nome, str) or not nome:
                raise ValueError(f"nó sem nome: {type(no).__name__}")
            if nome in self._nos:
                raise ValueError(f"nome de nó repetido: {nome}")
            self._nos[nome] = no
        # tuplas na ordem declarada (não sets): a ordem do sorter não pode variar com o hash seed
        self._grafo = {nome: _dependencias(no) for nome, no in self._nos.items()}
        for nome, deps in self._grafo.items():
            if faltam := [dep for dep in deps if dep not in self._nos]:
                raise ValueError(f"o nó {nome} depende de nó inexistente: {', '.join(faltam)}")
        # levanta graphlib.CycleError se houver ciclo
        ordem = TopologicalSorter(self._grafo).static_order()
        self._posicao = {nome: i for i, nome in enumerate(ordem)}
        self._sucessores: dict[str, set[str]] = {nome: set() for nome in self._nos}
        for nome, deps in self._grafo.items():
            for dep in deps:
                self._sucessores[dep].add(nome)

        self._status: dict[str, StatusNo] = dict.fromkeys(self._nos, "pendente")
        self._motivo: dict[str, str | None] = dict.fromkeys(self._nos)
        self._saidas: dict[str, dict] = {}  # só dos nós `feito`
        self._pendencias: dict[str, Pendencia] = {}
        # aberta = o dono está `aguardando` e ela não tem resposta ativa
        self._abertas: set[str] = set()
        self._julgamentos: list[dict] = []
        self._evidencias_sujas = False
        self._julgamentos_sujos = False
        self._trava = asyncio.Lock()

    # --- consulta ---------------------------------------------------------------------------

    def status(self) -> dict[str, StatusNo]:
        return dict(self._status)

    def saidas(self, nome: str) -> dict | None:
        saidas = self._saidas.get(nome)
        return copy.deepcopy(saidas) if saidas is not None else None

    def pendencias_abertas(self) -> list[Pendencia]:
        """Na ordem topológica do dono; as de um mesmo nó, na ordem em que ele pediu."""
        abertas = [p for pid, p in self._pendencias.items() if pid in self._abertas]
        return sorted(abertas, key=lambda p: self._posicao.get(p.no_origem, len(self._posicao)))

    # --- execução ---------------------------------------------------------------------------

    async def executar(self) -> None:
        async with self._trava:
            Path(self.ctx.pasta).mkdir(parents=True, exist_ok=True)
            self._evidencias_sujas = self._julgamentos_sujos = True
            self._salvar()
            await self._percorrer()

    async def responder(self, pendencia_id: str, resposta: Resposta) -> list[Pendencia]:
        """Grava a resposta (sem validar o conteúdo), reexecuta o que ela destrava e devolve as
        pendências abertas.

        Uma correção traz `resposta.substitui` com o id do julgamento ativo; a anterior fica
        `ativa=false` e o dono da pendência roda de novo, com todos os descendentes já executados.
        """
        async with self._trava:
            anterior = self._conferir_resposta(pendencia_id, resposta)
            numero = 1 + sum(j["pendencia"] == pendencia_id for j in self._julgamentos)
            julgamento = {
                "id": f"{pendencia_id}#{numero}",
                "pendencia": pendencia_id,
                "resposta": resposta.model_dump(mode="json"),
                "em": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "substitui": resposta.substitui,
            }
            self.servicos.custodia.guardar(
                _canonico(julgamento).encode("utf-8"), "json", tipo="julgamento", origem=julgamento["id"]
            )
            if anterior is not None:
                anterior["ativa"] = False
            self._julgamentos.append({**julgamento, "ativa": True})
            self._julgamentos_sujos = True
            self._abertas.discard(pendencia_id)
            self._reavaliar_dono(self._pendencias[pendencia_id].no_origem)
            self._salvar()
            await self._percorrer()
            return self.pendencias_abertas()

    async def _percorrer(self) -> None:
        sorter = TopologicalSorter(self._grafo)
        sorter.prepare()
        while True:
            lote: list[str] = []
            prontos = sorter.get_ready()
            while prontos:
                for nome in prontos:
                    status = self._status[nome]
                    if status in _TERMINAIS:
                        sorter.done(nome)
                    elif status == "aguardando":
                        continue  # retido: o done() só vem depois das respostas
                    elif (decisao := self._decidir(nome)) is not None:
                        self._mudar(nome, *decisao)
                        self._salvar()
                        sorter.done(nome)
                    else:
                        lote.append(nome)
                prontos = sorter.get_ready()
            if not lote:
                return
            for nome in lote:
                self._mudar(nome, "executando")
            self._salvar()
            # return_exceptions: uma falha de gravação não deixa irmãos rodando soltos
            resultados = await asyncio.gather(*(self._rodar(n) for n in lote), return_exceptions=True)
            if falhas := [r for r in resultados if isinstance(r, BaseException)]:
                raise falhas[0]
            for nome in lote:
                if self._status[nome] != "aguardando":
                    sorter.done(nome)

    def _decidir(self, nome: str) -> tuple[StatusNo, str] | None:
        """Status de um nó que não deve rodar, com o motivo; `None` se ele pode rodar."""
        no = self._nos[nome]
        if no.as_of == "so_atual" and self.ctx.retroativo:
            return "pulado", "só atual"
        for dep in no.entradas:
            if self._status[dep] == "erro":
                return "bloqueado", f"dependência com erro: {dep}"
            if self._status[dep] == "bloqueado":
                return "bloqueado", f"dependência bloqueada: {dep}"
        for dep in no.entradas:
            if self._status[dep] == "pulado":
                return "pulado", f"dependência pulada: {dep}"
        if no.exige_um_de and not any(self._status[d] == "feito" for d in no.exige_um_de):
            return "bloqueado", f"nenhuma dependência feita entre: {', '.join(no.exige_um_de)}"
        return None

    async def _rodar(self, nome: str) -> None:
        no = self._nos[nome]
        entradas = {
            dep: copy.deepcopy(self._saidas[dep])
            for dep in _dependencias(no)
            if self._status[dep] == "feito"
        }
        respostas = {
            j["pendencia"]: Resposta.model_validate(j["resposta"])
            for j in self._julgamentos
            if j["ativa"] and self._dono(j["pendencia"]) == nome
        }
        try:
            resultado = await no.executar(self.ctx, entradas, respostas, self.servicos)
        except ErroNo as e:
            self._mudar(nome, "erro", str(e.mensagem))
        except Exception as e:
            self._mudar(nome, "erro", f"erro inesperado: {type(e).__name__}: {e}")
        else:
            # um resultado malformado também é falha do nó: nunca pode derrubar o motor nem
            # deixar o nó `executando` (a retomada o reexecutaria e cairia de novo)
            try:
                self._aplicar(nome, resultado)
            except Exception as e:
                self._mudar(nome, "erro", f"resultado inválido: {type(e).__name__}: {e}")
        self._salvar()

    def _aplicar(self, nome: str, resultado: Any) -> None:
        if isinstance(resultado, Feito):
            try:
                saidas = _normalizar(resultado.saidas)
            except (TypeError, ValueError) as e:
                self._mudar(nome, "erro", f"saídas não serializáveis em JSON: {e}")
                return
            self._mudar(nome, "feito")
            self._saidas[nome] = saidas
            self._evidencias_sujas = True
        elif isinstance(resultado, Pulado):
            if not isinstance(resultado.motivo, str):
                veio = type(resultado.motivo).__name__
                motivo = f"resultado inválido: Pulado.motivo precisa ser texto (veio {veio})"
                self._mudar(nome, "erro", motivo)
                return
            self._mudar(nome, "pulado", resultado.motivo)
        elif isinstance(resultado, Aguardando):
            self._registrar_pendencias(nome, resultado.pendencias)
        else:
            self._mudar(nome, "erro", f"resultado inválido: {type(resultado).__name__}")

    def _registrar_pendencias(self, nome: str, pendencias: Any) -> None:
        if not isinstance(pendencias, list | tuple):
            veio = type(pendencias).__name__
        else:
            estranhos = (type(p).__name__ for p in pendencias if not isinstance(p, Pendencia))
            veio = next((f"item {tipo}" for tipo in estranhos), None)
        if veio is not None:
            motivo = f"resultado inválido: Aguardando.pendencias precisa ser lista de Pendencia (veio {veio})"
            self._mudar(nome, "erro", motivo)
            return
        if not pendencias:
            self._mudar(nome, "erro", "Aguardando sem pendências")
            return
        ids = [p.id for p in pendencias]
        if repetidas := sorted({i for i in ids if ids.count(i) > 1}):
            self._mudar(nome, "erro", f"pendência repetida no Aguardando: {', '.join(repetidas)}")
            return
        for pid in ids:
            dono = self._dono(pid)
            if dono is not None and dono != nome:
                self._mudar(nome, "erro", f"a pendência {pid} já pertence ao nó {dono}")
                return
        sem_resposta = {pid for pid in ids if self._julgamento_ativo(pid) is None}
        if not sem_resposta:
            # reexecutar o nó de novo com as mesmas respostas daria o mesmo Aguardando, sem fim
            self._mudar(nome, "erro", f"Aguardando só com pendências já respondidas: {', '.join(ids)}")
            return
        for p in pendencias:
            # o dono é quem pediu, seja qual for o `no_origem` que veio preenchido
            self._pendencias[p.id] = p if p.no_origem == nome else p.model_copy(update={"no_origem": nome})
        self._mudar(nome, "aguardando")
        # as que o nó deixou de pedir fecham; as pedidas sem resposta abrem
        self._abertas = {pid for pid in self._abertas if self._dono(pid) != nome} | sem_resposta

    # --- respostas --------------------------------------------------------------------------

    def _conferir_resposta(self, pendencia_id: str, resposta: Resposta) -> dict | None:
        """Regras de id do julgamento. Devolve o julgamento ativo que a resposta substitui."""
        if pendencia_id not in self._pendencias:
            raise ValueError(f"pendência desconhecida: {pendencia_id}")
        ativo = self._julgamento_ativo(pendencia_id)
        if resposta.substitui is None:
            if ativo is not None:
                raise ValueError(
                    f"a pendência {pendencia_id} já tem resposta ativa ({ativo['id']}); "
                    f"para corrigir, envie a resposta com substitui={ativo['id']!r}"
                )
            return None
        if ativo is None:
            raise ValueError(
                f"substitui={resposta.substitui!r}, mas a pendência {pendencia_id} "
                "não tem resposta ativa para substituir"
            )
        if resposta.substitui != ativo["id"]:
            raise ValueError(
                f"substitui={resposta.substitui!r}: {resposta.substitui} não é o julgamento ativo "
                f"da pendência {pendencia_id} (o ativo é {ativo['id']})"
            )
        return ativo

    def _reavaliar_dono(self, dono: str) -> None:
        status = self._status.get(dono)
        if status == "aguardando":
            if not any(self._dono(pid) == dono for pid in self._abertas):
                self._mudar(dono, "pendente")  # todas respondidas: roda de novo nesta passada
        elif status in _TERMINAIS:
            self._reiniciar(dono)
        # `pendente`: vai rodar e já recebe a resposta; `None`: o dono não está neste DAG

    def _reiniciar(self, nome: str) -> None:
        """Volta `nome` e todos os descendentes já executados a `pendente`."""
        fila, vistos = [nome], {nome}
        while fila:
            atual = fila.pop()
            if self._status[atual] != "pendente":
                self._mudar(atual, "pendente")
            for sucessor in self._sucessores[atual] - vistos:
                vistos.add(sucessor)
                fila.append(sucessor)

    def _julgamento_ativo(self, pendencia_id: str) -> dict | None:
        return next(
            (j for j in self._julgamentos if j["pendencia"] == pendencia_id and j["ativa"]), None
        )

    def _dono(self, pendencia_id: str) -> str | None:
        pendencia = self._pendencias.get(pendencia_id)
        return pendencia.no_origem if pendencia is not None else None

    # --- estado -----------------------------------------------------------------------------

    def _mudar(self, nome: str, status: StatusNo, motivo: str | None = None) -> None:
        self._status[nome] = status
        self._motivo[nome] = motivo if status in _COM_MOTIVO else None
        if status != "feito" and self._saidas.pop(nome, None) is not None:
            self._evidencias_sujas = True
        if status != "aguardando":
            self._abertas = {pid for pid in self._abertas if self._dono(pid) != nome}

    def _estado_json(self) -> dict:
        return {
            "contexto": self.ctx.model_dump(mode="json"),
            "nos": {n: {"status": self._status[n], "motivo": self._motivo[n]} for n in self._nos},
            "pendencias": {
                pid: {**p.model_dump(mode="json"), "aberta": pid in self._abertas}
                for pid, p in self._pendencias.items()
            },
        }

    def _salvar(self) -> None:
        """Evidências antes do estado (um `feito` no disco sempre tem as saídas) e julgamentos
        por último (o estado já marca o que a resposta reexecuta)."""
        pasta = Path(self.ctx.pasta)
        with trava(pasta / "motor.lock"):
            if self._evidencias_sujas:
                evidencias = {n: self._saidas[n] for n in self._nos if n in self._saidas}
                gravar_json_atomico(pasta / "evidencias.json", evidencias)
                self._evidencias_sujas = False
            gravar_json_atomico(pasta / "estado.json", self._estado_json())
            if self._julgamentos_sujos:
                gravar_json_atomico(pasta / "julgamentos.json", self._julgamentos)
                self._julgamentos_sujos = False

    @classmethod
    def carregar(cls, pasta: Path, nos: list[NoBase], servicos: Servicos) -> Motor:
        """Reconstrói a execução gravada em `pasta`.

        O contexto vem de `estado.json`, com `pasta` apontando para onde a execução está agora.
        `executando` volta a `pendente`; um `feito` sem saídas no `evidencias.json` também, com os
        descendentes; um `aguardando` sem pendência aberta fica pronto para rodar de novo.
        """
        pasta = Path(pasta)
        estado = ler_json(pasta / "estado.json")
        if estado is None:
            raise FileNotFoundError(f"execução sem estado.json: {pasta}")
        ctx = Contexto.model_validate({**estado["contexto"], "pasta": str(pasta)})
        motor = cls(ctx, nos, servicos)
        motor._julgamentos = ler_json(pasta / "julgamentos.json", [])
        saidas = ler_json(pasta / "evidencias.json", {})

        for nome, salvo in estado["nos"].items():
            if nome not in motor._nos:
                continue
            status = salvo["status"]
            if status not in _STATUS:
                raise ValueError(f"status desconhecido em estado.json: {nome}={status!r}")
            motor._status[nome] = status
            motor._motivo[nome] = salvo.get("motivo") if status in _COM_MOTIVO else None
        for pid, salvo in estado["pendencias"].items():
            motor._pendencias[pid] = Pendencia.model_validate(
                {k: v for k, v in salvo.items() if k != "aberta"}
            )
            if salvo["aberta"]:
                motor._abertas.add(pid)

        for nome in motor._nos:
            if motor._status[nome] == "executando":
                motor._mudar(nome, "pendente")
            elif motor._status[nome] == "feito":
                if nome in saidas:
                    motor._saidas[nome] = saidas[nome]
                else:
                    motor._reiniciar(nome)
        # queda entre gravar a resposta e o estado: a pendência já respondida não fica aberta
        motor._abertas = {
            pid
            for pid in motor._abertas
            if motor._status.get(motor._dono(pid)) == "aguardando"
            and motor._julgamento_ativo(pid) is None
        }
        for nome in motor._nos:
            if motor._status[nome] == "aguardando":
                motor._reavaliar_dono(nome)
        return motor
