"""Nó `destino` (melhorias do aceite, Tarefa 1): o domínio que os coletores analisam depois de um redirect.

O aceite de 08/10/2026 mostrou o radar analisando `phinv.link`, que só redirecionava para `phinvestimentos.com/login`.
O `destino` lê a saída `destino` da captura e entrega aos coletores de domínio (`rdap`, `dns`, `ct`, `wayback_*`) o
domínio final; sem captura (modo `nenhum`, retroativo, erro), o do alvo.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from radar.config import Config, RedeConfig
from radar.custodia import Custodia
from radar.modelos import Contexto, Feito, Pulado
from radar.motor import Motor, NoBase, Servicos
from radar.nos import nos_do_nucleo
from radar.nos.alvo import AlvoNo
from radar.nos.ct import CtNo
from radar.nos.destino import DestinoNo
from radar.nos.dns import DnsNo
from radar.nos.rdap import RdapNo
from radar.nos.wayback import WaybackIndiceNo
from radar.rede import Rede

AGORA = datetime(2026, 10, 11, 12, 0, 0)
ALVO = "phinv.link"
DESTINO = "phinvestimentos.com"
URL_DESTINO = f"https://{DESTINO}/login"
SEM_REDIRECT = {"dominio": ALVO, "redirecionado_de": None, "url_destino": None}


def contexto(pasta: Path, *, modo_contato: str = "captura", as_of: date | None = None) -> Contexto:
    return Contexto(
        alvo=ALVO, slug="phinv-link", url_inicial=f"https://{ALVO}/", as_of=as_of or AGORA.date(),
        data_execucao=AGORA, modo_contato=modo_contato, modo_cego=False, run_id="phinv-link/2026-10-11_120000",
        pasta=pasta,
    )  # fmt: skip


def entrada_alvo() -> dict:
    return {"alvo": {"dominio": ALVO, "slug": "phinv-link", "url_inicial": f"https://{ALVO}/"}}


def captura(destino: object = None, redirect_ignorado: object = None) -> dict:
    return {
        "paginas": [], "terceiros": [], "bloqueada": False, "falhas": [],
        "destino": destino, "redirect_ignorado": redirect_ignorado,
    }  # fmt: skip


async def rodar_destino(tmp_path: Path, entradas: dict) -> Feito:
    serv = Servicos(config=Config(), rede=None, custodia=Custodia(tmp_path))
    return await DestinoNo().executar(contexto(tmp_path), entradas, {}, serv)


# ---------------------------------------------------------------------------- declaração


def test_declaracao():
    no = DestinoNo()
    assert (no.nome, no.entradas, no.opcionais, no.exige_um_de, no.toca_alvo, no.as_of) == (
        "destino", ("alvo",), ("captura",), (), False, "exato"
    )  # fmt: skip
    assert no.saidas == ("dominio", "redirecionado_de", "url_destino")


def test_destino_esta_no_nucleo_depois_da_captura_e_antes_dos_coletores_de_dominio():
    nos = {n.nome: n for n in nos_do_nucleo()}
    assert isinstance(nos["destino"], DestinoNo)
    nomes = list(nos)
    assert nomes.index("captura") < nomes.index("destino") < nomes.index("rdap")
    for coletor in ("rdap", "dns", "ct", "wayback_indice", "wayback_snapshot"):
        assert nos[coletor].entradas == ("destino",), coletor
    assert nos["wayback_snapshot"].opcionais == ("captura",)
    # os da CVM/BCB só trocam a chave por domínio: o `destino` é opcional e o alvo continua obrigatório
    assert (nos["registros"].entradas, nos["registros"].opcionais) == (("alvo", "cnpj"), ("destino",))
    assert (nos["cvm_alertas"].entradas, nos["cvm_alertas"].opcionais) == (("alvo",), ("cnpj", "destino"))


# ---------------------------------------------------------------------------- o nó


async def test_com_destino_da_captura_os_coletores_analisam_o_destino(tmp_path):
    entradas = {**entrada_alvo(), "captura": captura({"url": URL_DESTINO, "dominio": DESTINO})}
    resultado = await rodar_destino(tmp_path, entradas)
    assert resultado == Feito({"dominio": DESTINO, "redirecionado_de": ALVO, "url_destino": URL_DESTINO})


async def test_sem_captura_vale_o_alvo(tmp_path):
    # captura pulada (modo nenhum, retroativo), em erro ou bloqueada: o motor não a passa nas entradas
    assert await rodar_destino(tmp_path, entrada_alvo()) == Feito(SEM_REDIRECT)


async def test_captura_sem_troca_de_dominio_vale_o_alvo(tmp_path):
    assert await rodar_destino(tmp_path, {**entrada_alvo(), "captura": captura()}) == Feito(SEM_REDIRECT)


async def test_redirect_ignorado_pela_captura_mantem_o_alvo(tmp_path):
    ignorado = {"url": "https://t.me/golpe", "dominio": "t.me", "motivo": "plataforma"}
    entradas = {**entrada_alvo(), "captura": captura(redirect_ignorado=ignorado)}
    assert await rodar_destino(tmp_path, entradas) == Feito(SEM_REDIRECT)


@pytest.mark.parametrize(
    "destino",
    [
        "phinvestimentos.com",  # não é objeto
        {"url": URL_DESTINO},  # sem domínio
        {"dominio": DESTINO},  # sem URL
        {"url": URL_DESTINO, "dominio": ""},
        {"url": URL_DESTINO, "dominio": 7},
        {"url": None, "dominio": DESTINO},
        {"url": f"https://{ALVO}/", "dominio": ALVO},  # o próprio alvo
        {"url": "https://t.me/golpe", "dominio": "t.me"},  # plataforma: nunca vira alvo
        {"url": "https://sedoparking.com/x", "dominio": "sedoparking.com"},  # estacionamento
    ],
)
async def test_destino_malformado_ou_proibido_nunca_falha_e_vale_o_alvo(tmp_path, destino):
    assert await rodar_destino(tmp_path, {**entrada_alvo(), "captura": captura(destino)}) == Feito(SEM_REDIRECT)


async def test_captura_estranha_nao_derruba_o_no(tmp_path):
    for saida in ({}, {"destino": None}, {"destino": []}):
        assert await rodar_destino(tmp_path, {**entrada_alvo(), "captura": saida}) == Feito(SEM_REDIRECT)




# ---------------------------------------------------------------------------- no DAG: os coletores recebem o destino


class CapturaFalsa(NoBase):
    """Faz o papel da captura, sem navegador: pula no modo `nenhum` (e o motor a pula no retroativo, pelo `so_atual`)
    e, senão, devolve a saída `destino` dada."""

    nome = "captura"
    entradas = ("alvo",)
    toca_alvo = True
    as_of = "so_atual"

    def __init__(self, destino: dict | None) -> None:
        super().__init__()
        self.destino = destino

    async def executar(self, ctx, entradas, respostas, s):
        if ctx.modo_contato == "nenhum":
            return Pulado("modo_contato=nenhum")
        return Feito(captura(self.destino))


def _doh(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 1, "data": "203.0.113.9"}]})


def mocar_coletores(respx_mock, dominio: str, *, com_dns: bool = True) -> dict:
    """As rotas de RDAP, DoH, crt.sh e CDX, só para `dominio`: um pedido para outro domínio não tem rota e o respx o
    recusa (o nó cai em erro)."""
    cdx = "https://web.archive.org/cdx/search/cdx"
    rotas = {
        "rdap": respx_mock.get(f"https://rdap.org/domain/{dominio}").mock(
            return_value=httpx.Response(200, json={"events": [{"eventAction": "registration", "eventDate": "2026-09-29"}]})
        ),
        "ct": respx_mock.get("https://crt.sh/", params={"q": dominio, "output": "json"}).mock(
            return_value=httpx.Response(200, json=[])
        ),
        "wayback_indice": respx_mock.get(cdx, params={"url": dominio, "matchType": "domain"}).mock(
            return_value=httpx.Response(200, json=[])
        ),
    }
    if com_dns:
        rotas["dns"] = respx_mock.get("https://cloudflare-dns.com/dns-query", params={"name": dominio}).mock(
            side_effect=_doh
        )
    return rotas


async def rodar_dag(tmp_path: Path, destino: dict | None, **contexto_) -> Motor:
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede)
    nos = [AlvoNo(), CapturaFalsa(destino), DestinoNo(), RdapNo(), DnsNo(), CtNo(), WaybackIndiceNo()]
    try:
        motor = Motor(contexto(tmp_path, **contexto_), nos, Servicos(config, rede, Custodia(tmp_path)))
        await motor.executar()
    finally:
        await rede.fechar()
    return motor


REDIRECT = {"url": URL_DESTINO, "dominio": DESTINO}


@pytest.mark.respx(assert_all_mocked=True, assert_all_called=True)
async def test_rdap_dns_ct_e_wayback_recebem_o_dominio_do_destino(respx_mock, tmp_path):
    mocar_coletores(respx_mock, DESTINO)
    motor = await rodar_dag(tmp_path, REDIRECT)
    assert set(motor.status().values()) == {"feito"}, motor.status()
    assert motor.saidas("destino") == {"dominio": DESTINO, "redirecionado_de": ALVO, "url_destino": URL_DESTINO}
    assert motor.saidas("rdap")["registro"] == "2026-09-29"
    assert motor.saidas("dns")["A"] == ["203.0.113.9"]
    # nenhum coletor consultou o redirecionador
    assert not [c for c in respx_mock.calls if ALVO in str(c.request.url)]


@pytest.mark.respx(assert_all_mocked=True, assert_all_called=True)
async def test_sem_redirect_os_coletores_analisam_o_alvo(respx_mock, tmp_path):
    mocar_coletores(respx_mock, ALVO)
    motor = await rodar_dag(tmp_path, None)
    assert set(motor.status().values()) == {"feito"}, motor.status()
    assert motor.saidas("destino") == SEM_REDIRECT


@pytest.mark.respx(assert_all_mocked=True, assert_all_called=True)
async def test_modo_nenhum_pula_a_captura_e_os_coletores_analisam_o_alvo(respx_mock, tmp_path):
    mocar_coletores(respx_mock, ALVO)
    motor = await rodar_dag(tmp_path, REDIRECT, modo_contato="nenhum")
    assert motor.status()["captura"] == "pulado"
    assert {n: s for n, s in motor.status().items() if n != "captura"} == dict.fromkeys(
        ("alvo", "destino", "rdap", "dns", "ct", "wayback_indice"), "feito"
    )
    assert motor.saidas("destino") == SEM_REDIRECT


@pytest.mark.respx(assert_all_mocked=True, assert_all_called=True)
async def test_retroativo_pula_a_captura_e_os_coletores_analisam_o_alvo(respx_mock, tmp_path):
    mocar_coletores(respx_mock, ALVO, com_dns=False)  # o dns só responde o presente: pulado no retroativo
    motor = await rodar_dag(tmp_path, REDIRECT, as_of=date(2026, 1, 1))
    assert (motor.status()["captura"], motor.status()["dns"]) == ("pulado", "pulado")
    assert motor.saidas("destino") == SEM_REDIRECT
    assert motor.status()["rdap"] == motor.status()["ct"] == motor.status()["wayback_indice"] == "feito"
