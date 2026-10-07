"""Execução em disco e nós de infraestrutura: alvo, rdap, dns e ct (Tarefa 6)."""

from __future__ import annotations

import copy
import json
import shutil
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from radar.arquivos import gravar_json_atomico
from radar.config import Config, RedeConfig
from radar.custodia import Custodia, verificar
from radar.execucao import (
    ExecucaoSalva,
    carregar_execucao,
    criar_contexto,
    criar_servicos,
    execucao_anterior,
    listar_casos,
)
from radar.modelos import Aguardando, Contexto, ErroNo, Evidencia, Feito, Pendencia, Resposta
from radar.motor import Motor, NoBase, Servicos
from radar.nos import nos_do_nucleo
from radar.nos.alvo import AlvoNo, normalizar_alvo
from radar.nos.captura import CapturaNo
from radar.nos.ct import CtNo
from radar.nos.dns import DnsNo
from radar.nos.rdap import RdapNo
from radar.nos.wayback import WaybackIndiceNo, WaybackSnapshotNo
from radar.rede import Rede

FIXTURES = Path(__file__).parent / "fixtures" / "api"
URL_RDAP_BR = "https://rdap.registro.br/domain/petrobras.com.br"
URL_DOH = "https://cloudflare-dns.com/dns-query"
URL_CRTSH = "https://crt.sh/"
URL_CDX = "https://web.archive.org/cdx/search/cdx"
URL_SNAPSHOTS = "https://web.archive.org/web/"
AGORA = datetime(2026, 10, 7, 12, 0, 0)


def fixture(nome: str):
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


async def _nao_dormir(s: float) -> None:
    return None


def contexto(pasta: Path, as_of: date, alvo: str = "petrobras.com.br") -> Contexto:
    slug = alvo.replace(".", "-")
    return Contexto(
        alvo=alvo,
        slug=slug,
        url_inicial=f"https://{alvo}/",
        as_of=as_of,
        data_execucao=AGORA,
        modo_contato="captura",
        modo_cego=False,
        run_id=f"{slug}/2026-10-07_120000",
        pasta=pasta,
    )


def entrada_alvo(dominio: str = "petrobras.com.br") -> dict[str, dict]:
    return {
        "alvo": {
            "dominio": dominio,
            "slug": dominio.replace(".", "-"),
            "url_inicial": f"https://{dominio}/",
        }
    }


@pytest.fixture
def ctx_hoje(tmp_path):
    return contexto(tmp_path, date(2026, 10, 7))


@pytest.fixture
def ctx_2019(tmp_path):
    return contexto(tmp_path, date(2019, 6, 6))


@pytest.fixture
async def serv(tmp_path):
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    yield Servicos(config=config, rede=rede, custodia=Custodia(tmp_path))
    await rede.fechar()


def log_custodia(pasta: Path) -> list[dict]:
    texto = (pasta / "custodia.log").read_text(encoding="utf-8")
    return [json.loads(linha) for linha in texto.split("\n") if linha]


# ---------------------------------------------------------------------------- alvo


@pytest.mark.parametrize(
    "entrada,dominio,slug",
    [
        ("https://www.Exemplo.com.br/promo?ref=1#x", "exemplo.com.br", "exemplo-com-br"),
        ("app.exemplo.com.br", "exemplo.com.br", "exemplo-com-br"),
        ("exemplo.com.br.", "exemplo.com.br", "exemplo-com-br"),
        (
            "http://xn--investimento-fcil-lsb.com/",
            "xn--investimento-fcil-lsb.com",
            "xn--investimento-fcil-lsb-com",
        ),
        ("invest.io", "invest.io", "invest-io"),
        ("  https://exemplo.com.br:8443/x  ", "exemplo.com.br", "exemplo-com-br"),
        ("investimento-fácil.com", "xn--investimento-fcil-kpb.com", "xn--investimento-fcil-kpb-com"),  # IDN → punycode
    ],
)
def test_normalizar_alvo(entrada, dominio, slug):
    assert normalizar_alvo(entrada)[:2] == (dominio, slug)


@pytest.mark.parametrize(
    "entrada,url_inicial",
    [
        ("https://www.Exemplo.com.br/promo?ref=1#x", "https://www.Exemplo.com.br/promo?ref=1"),
        ("app.exemplo.com.br", "https://app.exemplo.com.br"),
        ("exemplo.com.br/a/b?c=1#topo", "https://exemplo.com.br/a/b?c=1"),
        ("http://xn--investimento-fcil-lsb.com/", "http://xn--investimento-fcil-lsb.com/"),
    ],
)
def test_normalizar_alvo_url_inicial(entrada, url_inicial):
    assert normalizar_alvo(entrada)[2] == url_inicial


def test_normalizar_alvo_invalido():
    with pytest.raises(ErroNo):
        normalizar_alvo("isso não é url")


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "   ",
        "localhost",
        "http://192.168.0.1/",
        "https://",
        "ftp://exemplo.com.br/",
        "mailto:fulano@exemplo.com.br",
        "https://usuario:senha@exemplo.com.br/",
        "exemplo.com.br:porta",
        "semponto",
        ".com.br",
        "https://-.com",
        "https://-exemplo.com.br",
        "exemplo!.com.br",
        "https://exemplo..com.br",
        "../../etc/passwd",
        r"https://a\..\b.com/",
        r"x\..\..\evil.com",
        "https://exemplo.com.br:99999/",
    ],
)
def test_normalizar_alvo_invalido_e_permanente_com_mensagem(entrada):
    with pytest.raises(ErroNo) as e:
        normalizar_alvo(entrada)
    assert e.value.permanente is True
    assert e.value.mensagem


async def test_no_alvo_repassa_dominio_slug_e_url(ctx_hoje, serv):
    resultado = await AlvoNo().executar(ctx_hoje, {}, {}, serv)
    assert resultado == Feito(
        {"dominio": "petrobras.com.br", "slug": "petrobras-com-br", "url_inicial": "https://petrobras.com.br/"}
    )
    no = AlvoNo()
    assert (no.nome, no.entradas, no.toca_alvo) == ("alvo", (), False)
    assert set(no.saidas) == {"dominio", "slug", "url_inicial"}


# ---------------------------------------------------------------------------- rdap


async def test_rdap_br_extrai_cnpj(respx_mock, ctx_hoje, serv):
    rota = respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(200, json=fixture("rdap_registrobr_petrobras")))
    resultado = await RdapNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert resultado == Feito(
        {
            "registro": "1996-06-14",  # o evento do domínio, não o da entidade titular (1998-01-12)
            "expiracao": "2030-06-14",
            "registrador": None,  # o registro.br não lista registrador
            "cnpj_titular": "33000167000101",
            "vazamento_temporal": [],
        }
    )
    assert rota.call_count == 1
    # o JSON bruto vai para a custódia, com a URL de origem
    (registro,) = log_custodia(ctx_hoje.pasta)
    assert (registro["tipo"], registro["origem"]) == ("api", URL_RDAP_BR)
    assert json.loads(serv.custodia.ler(f"sha256:{registro['sha256']}")) == fixture("rdap_registrobr_petrobras")


async def test_rdap_retroativo_sem_titular(respx_mock, ctx_2019, serv):
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(200, json=fixture("rdap_registrobr_petrobras")))
    resultado = await RdapNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    saidas = resultado.saidas
    assert saidas["cnpj_titular"] is None
    assert saidas["vazamento_temporal"] == ["cnpj_titular"]
    assert saidas["registro"] == "1996-06-14"  # a data de criação é exata, não vaza


async def test_rdap_com_via_rdap_org(respx_mock, tmp_path, serv):
    ctx = contexto(tmp_path, date(2026, 10, 7), "example.com")
    destino = "https://rdap.verisign.com/com/v1/domain/example.com"
    respx_mock.get("https://rdap.org/domain/example.com").mock(
        return_value=httpx.Response(302, headers={"location": destino})
    )
    respx_mock.get(destino).mock(return_value=httpx.Response(200, json=fixture("rdap_org_example")))
    resultado = await RdapNo().executar(ctx, entrada_alvo("example.com"), {}, serv)
    assert resultado.saidas == {
        "registro": "1995-08-14",
        "expiracao": "2027-08-13",
        "registrador": "RESERVED-Internet Assigned Numbers Authority",
        "cnpj_titular": None,
        "vazamento_temporal": [],
    }


async def test_rdap_registrador_cai_no_handle_sem_vcard(respx_mock, tmp_path, serv):
    ctx = contexto(tmp_path, date(2026, 10, 7), "example.com")
    dados = copy.deepcopy(fixture("rdap_org_example"))
    dados["entities"][0].pop("vcardArray")
    respx_mock.get("https://rdap.org/domain/example.com").mock(return_value=httpx.Response(200, json=dados))
    resultado = await RdapNo().executar(ctx, entrada_alvo("example.com"), {}, serv)
    assert resultado.saidas["registrador"] == "376"


async def test_rdap_titular_pessoa_fisica_nao_vira_cnpj_nas_saidas(respx_mock, ctx_hoje, serv):
    dados = copy.deepcopy(fixture("rdap_registrobr_petrobras"))
    dados["entities"][0]["publicIds"] = [{"type": "cpf", "identifier": "123.456.789-09"}]
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(200, json=dados))
    resultado = await RdapNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert resultado.saidas["cnpj_titular"] is None
    assert "12345678909" not in json.dumps(resultado.saidas)


async def test_rdap_sem_eventos_devolve_none(respx_mock, ctx_hoje, serv):
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(200, json={"objectClassName": "domain"}))
    resultado = await RdapNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert resultado.saidas == {
        "registro": None,
        "expiracao": None,
        "registrador": None,
        "cnpj_titular": None,
        "vazamento_temporal": [],
    }


async def test_rdap_404_vira_erro_permanente_com_mensagem(respx_mock, ctx_hoje, serv):
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(404))
    with pytest.raises(ErroNo) as e:
        await RdapNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is True
    assert "rdap" in e.value.mensagem.lower() and "404" in e.value.mensagem


async def test_rdap_503_esgotado_vira_erro_nao_permanente(respx_mock, ctx_hoje, serv):
    rota = respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo) as e:
        await RdapNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is False
    assert rota.call_count == 4


@pytest.mark.parametrize("corpo", [b"<html>manutencao</html>", b"[1, 2]"])
async def test_rdap_formato_inesperado_e_erro_permanente(respx_mock, ctx_hoje, serv, corpo):
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(200, content=corpo))
    with pytest.raises(ErroNo) as e:
        await RdapNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is True and e.value.mensagem
    assert len(log_custodia(ctx_hoje.pasta)) == 1  # o bruto fica guardado mesmo assim


def test_rdap_declaracao():
    no = RdapNo()
    assert (no.nome, no.entradas, no.toca_alvo) == ("rdap", ("alvo",), False)
    assert set(no.saidas) == {"registro", "expiracao", "registrador", "cnpj_titular", "vazamento_temporal"}


# ---------------------------------------------------------------------------- dns


def _doh(status: int, tipo: int, *dados: tuple[int, str]) -> dict:
    corpo: dict = {"Status": status, "Question": [{"name": "petrobras.com.br", "type": tipo}]}
    if dados:
        corpo["Answer"] = [
            {"name": "petrobras.com.br", "type": t, "TTL": 60, "data": d} for t, d in dados
        ]
    return corpo


def _rota_doh(respx_mock, respostas: dict[str, dict]):
    return respx_mock.get(URL_DOH).mock(
        side_effect=lambda req: httpx.Response(200, json=respostas[req.url.params["type"]])
    )


async def test_dns_mx_e_nxdomain(respx_mock, ctx_hoje, serv):
    mx = fixture("doh_mx")
    rota = _rota_doh(
        respx_mock,
        {
            # CNAME (tipo 5) na resposta do A não conta como endereço
            "A": _doh(0, 1, (5, "alias.petrobras.com.br."), (1, "203.0.113.10"), (1, "203.0.113.11")),
            "AAAA": _doh(0, 28),
            "MX": mx,
            "NS": _doh(0, 2, (2, "ns-187.awsdns-23.com."), (2, "ns-828.awsdns-39.net.")),
            "TXT": _doh(0, 16, (16, '"v=spf1 include:spf.protection.outlook.com -all"')),
        },
    )
    resultado = await DnsNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert resultado.saidas == {
        "A": ["203.0.113.10", "203.0.113.11"],
        "AAAA": [],
        "MX": ["20 petrobras-com-br.mail.protection.outlook.com."],
        "NS": ["ns-187.awsdns-23.com.", "ns-828.awsdns-39.net."],
        "TXT": ['"v=spf1 include:spf.protection.outlook.com -all"'],
        "nxdomain": False,
    }
    assert rota.call_count == 5
    consultas = [c.request for c in rota.calls]
    assert {r.url.params["type"] for r in consultas} == {"A", "AAAA", "MX", "NS", "TXT"}
    assert {r.url.params["name"] for r in consultas} == {"petrobras.com.br"}
    assert {r.headers["accept"] for r in consultas} == {"application/dns-json"}
    # as 5 respostas brutas ficam na custódia, cada uma com a sua URL
    registros = log_custodia(ctx_hoje.pasta)
    assert [r["tipo"] for r in registros] == ["api"] * 5
    assert sorted(r["origem"] for r in registros) == sorted(
        f"{URL_DOH}?name=petrobras.com.br&type={t}" for t in ("A", "AAAA", "MX", "NS", "TXT")
    )


async def test_dns_status_3_na_consulta_a_e_nxdomain(respx_mock, ctx_hoje, serv):
    nx = fixture("doh_nxdomain")
    assert nx["Status"] == 3
    _rota_doh(respx_mock, dict.fromkeys(("A", "AAAA", "MX", "NS", "TXT"), nx))
    resultado = await DnsNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert resultado.saidas == {
        "A": [],
        "AAAA": [],
        "MX": [],
        "NS": [],
        "TXT": [],
        "nxdomain": True,
    }


async def test_dns_um_tipo_com_erro_derruba_o_no(respx_mock, ctx_hoje, serv):
    def responder(req):
        if req.url.params["type"] == "TXT":
            return httpx.Response(403)
        return httpx.Response(200, json=_doh(0, 1))

    respx_mock.get(URL_DOH).mock(side_effect=responder)
    with pytest.raises(ErroNo) as e:
        await DnsNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is True
    assert "TXT" in e.value.mensagem


@pytest.mark.parametrize("tipo", ["A", "MX"])
@pytest.mark.parametrize("status", [1, 2, 5])  # FORMERR, SERVFAIL, REFUSED
async def test_dns_status_de_falha_de_resolucao_vira_erro(respx_mock, ctx_hoje, serv, tipo, status):
    # lista vazia e `nxdomain=False` seriam "sem registros", e o resolvedor não disse isso
    def responder(req):
        consultado = req.url.params["type"]
        return httpx.Response(200, json=_doh(status if consultado == tipo else 0, 1))

    respx_mock.get(URL_DOH).mock(side_effect=responder)
    with pytest.raises(ErroNo) as e:
        await DnsNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is False
    assert f"DNS {tipo}: Status {status}" in e.value.mensagem
    assert "petrobras.com.br" in e.value.mensagem
    # a resposta bruta que causou o erro fica na custódia
    assert log_custodia(ctx_hoje.pasta)[-1]["origem"] == f"{URL_DOH}?name=petrobras.com.br&type={tipo}"


@pytest.mark.parametrize("status", [None, 4, "2", []])
async def test_dns_status_ausente_ou_estranho_tambem_e_erro(respx_mock, ctx_hoje, serv, status):
    corpo = _doh(0, 1)
    if status is None:
        del corpo["Status"]
    else:
        corpo["Status"] = status
    respx_mock.get(URL_DOH).mock(return_value=httpx.Response(200, json=corpo))
    with pytest.raises(ErroNo) as e:
        await DnsNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is False
    assert "DNS A: Status" in e.value.mensagem


async def test_dns_corpo_que_nao_e_json_e_erro_permanente(respx_mock, ctx_hoje, serv):
    respx_mock.get(URL_DOH).mock(return_value=httpx.Response(200, content=b"<html>"))
    with pytest.raises(ErroNo) as e:
        await DnsNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is True and e.value.mensagem


def test_dns_declaracao():
    no = DnsNo()
    assert (no.nome, no.entradas, no.as_of, no.toca_alvo) == ("dns", ("alvo",), "so_atual", False)
    assert set(no.saidas) == {"A", "AAAA", "MX", "NS", "TXT", "nxdomain"}


# ---------------------------------------------------------------------------- ct


def _rota_crtsh(respx_mock, corpo):
    return respx_mock.get(URL_CRTSH, params={"q": "petrobras.com.br", "output": "json"}).mock(
        return_value=httpx.Response(200, json=corpo)
    )


async def test_ct_filtra_por_as_of(respx_mock, ctx_2019, serv):
    rota = _rota_crtsh(respx_mock, fixture("crtsh"))
    resultado = await CtNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    # as_of 2019-06-06 é o not_before de um dos certificados: o limite entra (<=)
    assert resultado.saidas == {
        "primeiro_certificado": "2004-02-17",
        "total": 6,
        "sans": [
            "cma-mobile.petrobras.com.br",
            "comunidadecientifica.petrobras.com.br",
            "cotacoes.petrobras.com.br",
            "panm-dsv.petrobras.com.br",
            "panm.petrobras.com.br",
            "rpad.petrobras.com.br",
            "vc.petrobras.com.br",
            "www.comunidadecientifica.petrobras.com.br",
            "www2.petrobras.com.br",
        ],
    }
    assert rota.call_count == 1
    (registro,) = log_custodia(ctx_2019.pasta)
    assert (registro["tipo"], registro["origem"]) == ("api", f"{URL_CRTSH}?q=petrobras.com.br&output=json")


async def test_ct_no_dia_anterior_ao_limite_exclui_o_certificado_do_dia(respx_mock, tmp_path, serv):
    _rota_crtsh(respx_mock, fixture("crtsh"))
    ctx = contexto(tmp_path, date(2019, 6, 5))
    saidas = (await CtNo().executar(ctx, entrada_alvo(), {}, serv)).saidas
    assert saidas["total"] == 5
    assert "panm.petrobras.com.br" not in saidas["sans"]


async def test_ct_hoje_conta_tudo_e_tira_o_curinga(respx_mock, ctx_hoje, serv):
    _rota_crtsh(respx_mock, fixture("crtsh"))
    saidas = (await CtNo().executar(ctx_hoje, entrada_alvo(), {}, serv)).saidas
    assert saidas["total"] == 10
    assert saidas["primeiro_certificado"] == "2004-02-17"
    assert "petrobras.com.br" in saidas["sans"]  # veio de "*.petrobras.com.br" e do apex
    assert "aprendi.petrobras.com.br" in saidas["sans"]
    assert not any(san.startswith("*") for san in saidas["sans"])
    assert saidas["sans"] == sorted(set(saidas["sans"]))


async def test_ct_antes_do_primeiro_certificado(respx_mock, tmp_path, serv):
    _rota_crtsh(respx_mock, fixture("crtsh"))
    ctx = contexto(tmp_path, date(2000, 1, 1))
    resultado = await CtNo().executar(ctx, entrada_alvo(), {}, serv)
    assert resultado.saidas == {"primeiro_certificado": None, "total": 0, "sans": []}


async def test_ct_normaliza_sans_e_ignora_certificado_sem_data(respx_mock, ctx_hoje, serv):
    _rota_crtsh(
        respx_mock,
        [
            {"not_before": "2024-03-01T10:00:00", "name_value": "WWW.Petrobras.COM.br\n*.Petrobras.com.br\n\nwww.petrobras.com.br"},
            {"not_before": "2023-01-02T00:00:00", "name_value": "  api.petrobras.com.br  "},
            {"not_before": "", "name_value": "sem-data.petrobras.com.br"},
            {"not_before": None, "name_value": "nulo.petrobras.com.br"},
            {"name_value": "sem-campo.petrobras.com.br"},
        ],
    )
    resultado = await CtNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert resultado.saidas == {
        "primeiro_certificado": "2023-01-02",
        "total": 2,
        "sans": ["api.petrobras.com.br", "petrobras.com.br", "www.petrobras.com.br"],
    }


async def test_ct_lista_vazia(respx_mock, ctx_hoje, serv):
    _rota_crtsh(respx_mock, [])
    resultado = await CtNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert resultado.saidas == {"primeiro_certificado": None, "total": 0, "sans": []}


@pytest.mark.parametrize("corpo", [b"<html>502 Bad Gateway</html>", b'{"erro": 1}'])
async def test_ct_formato_inesperado_e_erro_permanente(respx_mock, ctx_hoje, serv, corpo):
    respx_mock.get(URL_CRTSH).mock(return_value=httpx.Response(200, content=corpo))
    with pytest.raises(ErroNo) as e:
        await CtNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is True and e.value.mensagem


async def test_ct_503_esgotado_vira_erro_nao_permanente(respx_mock, ctx_hoje, serv):
    respx_mock.get(URL_CRTSH).mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo) as e:
        await CtNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert e.value.permanente is False and "crt.sh" in e.value.mensagem


def test_ct_declaracao():
    no = CtNo()
    assert (no.nome, no.entradas, no.as_of, no.toca_alvo) == ("ct", ("alvo",), "exato", False)
    assert set(no.saidas) == {"primeiro_certificado", "total", "sans"}


# ---------------------------------------------------------------------------- execucao


def test_criar_contexto_e_listar(tmp_path):
    ctx = criar_contexto("https://www.Exemplo.com.br/promo#x", None, "captura", False, tmp_path, AGORA)
    assert ctx.run_id == "exemplo-com-br/2026-10-07_120000"
    assert ctx.pasta == tmp_path / "exemplo-com-br" / "2026-10-07_120000"
    assert ctx.pasta.is_dir()
    assert (ctx.alvo, ctx.slug, ctx.url_inicial) == (
        "exemplo.com.br",
        "exemplo-com-br",
        "https://www.Exemplo.com.br/promo",
    )
    assert ctx.as_of == date(2026, 10, 7)  # sem as_of: hoje
    assert ctx.data_execucao == AGORA
    assert (ctx.modo_contato, ctx.modo_cego, ctx.retroativo) == ("captura", False, False)
    # `_indices` e arquivos soltos não são alvos
    (tmp_path / "_indices").mkdir()
    (tmp_path / "anotacao.txt").write_text("x", encoding="utf-8")
    assert listar_casos(tmp_path) == {"exemplo-com-br": ["2026-10-07_120000"]}


def test_criar_contexto_retroativo_e_modos(tmp_path):
    ctx = criar_contexto("invest.io", date(2019, 6, 6), "nenhum", True, tmp_path, AGORA)
    assert ctx.as_of == date(2019, 6, 6)
    assert (ctx.modo_contato, ctx.modo_cego, ctx.retroativo) == ("nenhum", True, True)


def test_criar_contexto_timestamp_repetido_levanta_file_exists(tmp_path):
    criar_contexto("exemplo.com.br", None, "captura", False, tmp_path, AGORA)
    with pytest.raises(FileExistsError):
        criar_contexto("exemplo.com.br", None, "captura", False, tmp_path, AGORA)


def test_criar_contexto_invalido_nao_cria_pasta(tmp_path):
    casos = tmp_path / "casos"
    with pytest.raises(ErroNo):
        criar_contexto("isso não é url", None, "captura", False, casos, AGORA)
    with pytest.raises(ValidationError):
        criar_contexto("exemplo.com.br", None, "telepatia", False, casos, AGORA)
    assert not casos.exists()


def test_listar_casos_varios_alvos_em_ordem(tmp_path):
    for alvo, agora in [
        ("b.com.br", datetime(2026, 10, 7, 12, 0, 0)),
        ("a.com.br", datetime(2026, 10, 7, 9, 30, 5)),
        ("a.com.br", datetime(2026, 10, 1, 23, 59, 59)),
    ]:
        criar_contexto(alvo, None, "captura", False, tmp_path, agora)
    (tmp_path / "_indices").mkdir()
    (tmp_path / "a-com-br" / "rascunho").mkdir()  # não é uma execução
    assert listar_casos(tmp_path) == {
        "a-com-br": ["2026-10-01_235959", "2026-10-07_093005"],
        "b-com-br": ["2026-10-07_120000"],
    }
    assert listar_casos(tmp_path / "nao-existe") == {}


def test_criar_servicos_liga_a_custodia_na_pasta(tmp_path):
    config = Config()
    rede = object()
    s = criar_servicos(config, tmp_path, rede)
    assert s.config is config and s.rede is rede
    assert isinstance(s.custodia, Custodia) and s.custodia.pasta == tmp_path
    assert (s.indices, s.matriz) == (None, None)
    s2 = criar_servicos(config, tmp_path, rede, indices="i", matriz="m")
    assert (s2.indices, s2.matriz) == ("i", "m")


def _gravar_estado(ctx: Contexto) -> None:
    gravar_json_atomico(
        ctx.pasta / "estado.json", {"contexto": ctx.model_dump(mode="json"), "nos": {}, "pendencias": {}}
    )


def test_execucao_anterior(tmp_path):
    def nova(dia: int, as_of: date | None = None, alvo: str = "exemplo.com.br") -> Contexto:
        return criar_contexto(alvo, as_of, "captura", False, tmp_path, datetime(2026, 10, dia, 10, 0, 0))

    r1 = nova(1)
    r2 = nova(2, date(2019, 1, 1))  # retroativa: não vale como anterior
    r3 = nova(3)  # caiu antes de gravar o estado.json
    r4 = nova(4)
    r5 = nova(5)
    r6 = nova(6)
    outro = nova(4, alvo="outro.com.br")  # outro slug nunca entra
    for r in (r1, r2, r4, r5, r6, outro):
        _gravar_estado(r)
    assert execucao_anterior(r5.pasta) == r4.pasta
    # r3 sem estado e r2 retroativa ficam de fora
    assert execucao_anterior(r4.pasta) == r1.pasta
    assert execucao_anterior(r1.pasta) is None
    assert execucao_anterior(outro.pasta) is None  # a mais nova do slug é a dela mesma
    # a posterior não conta, mesmo sendo a mais recente
    assert execucao_anterior(r4.pasta) != r6.pasta
    # estado ilegível ou sem contexto é pulado, não derruba
    (r4.pasta / "estado.json").write_text("{quebrado", encoding="utf-8")
    assert execucao_anterior(r5.pasta) == r1.pasta
    (r4.pasta / "estado.json").write_text("{}", encoding="utf-8")
    assert execucao_anterior(r5.pasta) == r1.pasta


def test_carregar_execucao_sem_estado(tmp_path):
    with pytest.raises(FileNotFoundError):
        carregar_execucao(tmp_path)


class _Pergunta(NoBase):
    nome = "pergunta"
    entradas = ("alvo",)

    async def executar(self, ctx, entradas, respostas, s):
        if "P-X" not in respostas:
            return Aguardando(
                [
                    Pendencia(
                        id="P-X",
                        itens=["A1"],
                        pergunta="?",
                        criterios="",
                        candidatos=[],
                        formato_resposta={},
                        restricoes={},
                        conteudo_do_alvo="",
                        no_origem="pergunta",
                    )
                ]
            )
        return Feito({"resposta": respostas["P-X"].status})


async def test_carregar_execucao_le_o_que_o_motor_grava(tmp_path):
    ctx = criar_contexto("exemplo.com.br", None, "captura", False, tmp_path, AGORA)
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        motor = Motor(ctx, [AlvoNo(), _Pergunta()], criar_servicos(config, ctx.pasta, rede))
        await motor.executar()

        aguardando = carregar_execucao(ctx.pasta)
        assert isinstance(aguardando, ExecucaoSalva)
        assert aguardando.ctx == ctx
        assert aguardando.status["alvo"] == {"status": "feito", "motivo": None}
        assert aguardando.status["pergunta"]["status"] == "aguardando"
        assert aguardando.saidas == {"alvo": {"dominio": "exemplo.com.br", "slug": "exemplo-com-br", "url_inicial": "https://exemplo.com.br"}}
        assert aguardando.pendencias["P-X"]["aberta"] is True
        assert aguardando.pendencias["P-X"]["no_origem"] == "pergunta"
        assert aguardando.julgamentos == []

        evidencia = Evidencia(fonte="https://exemplo.com.br/", trecho="x", tipo_fonte="operador")
        await motor.responder("P-X", Resposta(status="confirmado", valor={"a": 1}, evidencias=[evidencia]))

        respondida = carregar_execucao(ctx.pasta)
        assert respondida.status["pergunta"]["status"] == "feito"
        assert respondida.saidas["pergunta"] == {"resposta": "confirmado"}
        assert respondida.pendencias["P-X"]["aberta"] is False
        (julgamento,) = respondida.julgamentos
        assert (julgamento["id"], julgamento["pendencia"], julgamento["ativa"]) == ("P-X#1", "P-X", True)
        assert julgamento["resposta"]["valor"] == {"a": 1}
    finally:
        await rede.fechar()


async def test_carregar_execucao_aponta_para_a_pasta_atual(tmp_path):
    ctx = criar_contexto("exemplo.com.br", None, "captura", False, tmp_path / "casos", AGORA)
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        await Motor(ctx, [AlvoNo()], criar_servicos(config, ctx.pasta, rede)).executar()
    finally:
        await rede.fechar()
    movida = tmp_path / "copia"
    shutil.copytree(ctx.pasta, movida)
    ex = carregar_execucao(movida)
    assert ex.ctx.pasta == movida
    assert ex.ctx.run_id == ctx.run_id and ex.ctx.as_of == ctx.as_of


# ---------------------------------------------------------------------------- núcleo


def test_nos_do_nucleo():
    nos = nos_do_nucleo()
    assert [type(n) for n in nos] == [AlvoNo, RdapNo, DnsNo, CtNo, WaybackIndiceNo, CapturaNo, WaybackSnapshotNo]
    assert [n.nome for n in nos] == [
        "alvo", "rdap", "dns", "ct", "wayback_indice", "captura", "wayback_snapshot"
    ]
    assert nos is not nos_do_nucleo()  # lista nova a cada chamada


def _cdx(request: httpx.Request) -> httpx.Response:
    # a listagem do domínio (índice e subpáginas) tem `matchType`; a consulta da home não
    corpo = fixture("cdx_dominio" if "matchType" in request.url.params else "cdx_home")
    return httpx.Response(200, json=corpo)


def _mocar_wayback(respx_mock) -> None:
    respx_mock.get(URL_CDX).mock(side_effect=_cdx)
    respx_mock.get(url__startswith=URL_SNAPSHOTS).mock(
        return_value=httpx.Response(
            200, content=(FIXTURES / "snapshot_home.html").read_bytes(), headers={"content-type": "text/html; charset=UTF-8"}
        )
    )


def _mocar_apis(respx_mock, *, com_dns: bool) -> None:
    _mocar_wayback(respx_mock)
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(200, json=fixture("rdap_registrobr_petrobras")))
    respx_mock.get(URL_CRTSH, params={"q": "petrobras.com.br", "output": "json"}).mock(
        return_value=httpx.Response(200, json=fixture("crtsh"))
    )
    if com_dns:
        _rota_doh(
            respx_mock,
            {
                "A": _doh(0, 1, (1, "203.0.113.10")),
                "AAAA": _doh(0, 28),
                "MX": fixture("doh_mx"),
                "NS": _doh(0, 2, (2, "ns-187.awsdns-23.com.")),
                "TXT": _doh(0, 16),
            },
        )


async def _rodar_nucleo(tmp_path, as_of: date | None) -> tuple[Contexto, Motor]:
    # modo_contato="nenhum": a `captura` fica pulada e o teste nunca abre o navegador
    ctx = criar_contexto("https://www.petrobras.com.br/", as_of, "nenhum", False, tmp_path, AGORA)
    config = Config(rede=RedeConfig(limites={"*": 0}))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        motor = Motor(ctx, nos_do_nucleo(), criar_servicos(config, ctx.pasta, rede))
        await motor.executar()
    finally:
        await rede.fechar()
    return ctx, motor


async def test_nucleo_ponta_a_ponta_em_modo_atual(respx_mock, tmp_path):
    _mocar_apis(respx_mock, com_dns=True)
    ctx, motor = await _rodar_nucleo(tmp_path, None)
    assert motor.status() == {
        "alvo": "feito", "rdap": "feito", "dns": "feito", "ct": "feito", "wayback_indice": "feito",
        "captura": "pulado", "wayback_snapshot": "feito",
    }

    ex = carregar_execucao(ctx.pasta)
    assert ex.status["captura"] == {"status": "pulado", "motivo": "modo_contato=nenhum"}
    assert "captura" not in ex.saidas
    # sem captura ao vivo, a página vem do Wayback (a home do CDX mockado)
    assert [p["url"] for p in ex.saidas["wayback_snapshot"]["paginas"]] == ["http://www.example.com/"]
    assert ex.saidas["alvo"]["dominio"] == "petrobras.com.br"
    assert ex.saidas["rdap"]["cnpj_titular"] == "33000167000101"
    assert ex.saidas["dns"]["MX"] == ["20 petrobras-com-br.mail.protection.outlook.com."]
    assert ex.saidas["ct"]["total"] == 10
    assert ex.saidas["wayback_indice"]["total"] == 22
    # 1 RDAP + 5 DoH + 1 crt.sh + 2 CDX do Wayback (domínio e home) + snapshot da home (HTML e texto)
    assert len(log_custodia(ctx.pasta)) == 12
    assert verificar(ctx.pasta) == []


async def test_nucleo_retroativo_pula_dns_e_esconde_o_titular(respx_mock, tmp_path):
    _mocar_apis(respx_mock, com_dns=False)
    ctx, motor = await _rodar_nucleo(tmp_path, date(2019, 6, 6))
    assert motor.status() == {
        "alvo": "feito", "rdap": "feito", "dns": "pulado", "ct": "feito", "wayback_indice": "feito",
        "captura": "pulado", "wayback_snapshot": "feito",
    }

    ex = carregar_execucao(ctx.pasta)
    assert ex.status["dns"] == {"status": "pulado", "motivo": "só atual"}
    assert ex.status["captura"] == {"status": "pulado", "motivo": "só atual"}
    assert ex.saidas["rdap"]["cnpj_titular"] is None
    assert ex.saidas["rdap"]["vazamento_temporal"] == ["cnpj_titular"]
    assert ex.saidas["ct"]["total"] == 6
    assert ex.saidas["wayback_indice"]["primeiro"] == "2002-01-20"
    assert "dns" not in ex.saidas


async def test_nucleo_dns_servfail_deixa_o_no_em_erro_e_sem_saidas(respx_mock, tmp_path):
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(200, json=fixture("rdap_registrobr_petrobras")))
    respx_mock.get(URL_CRTSH).mock(return_value=httpx.Response(200, json=fixture("crtsh")))
    _mocar_wayback(respx_mock)
    _rota_doh(respx_mock, dict.fromkeys(("A", "AAAA", "MX", "NS", "TXT"), _doh(2, 1)))
    ctx, motor = await _rodar_nucleo(tmp_path, None)
    assert motor.status() == {
        "alvo": "feito", "rdap": "feito", "dns": "erro", "ct": "feito", "wayback_indice": "feito",
        "captura": "pulado", "wayback_snapshot": "feito",
    }
    ex = carregar_execucao(ctx.pasta)
    assert "Status 2 (SERVFAIL)" in ex.status["dns"]["motivo"]
    assert "dns" not in ex.saidas  # nada de `nxdomain=False` com cara de dado coletado


async def test_nucleo_rdap_em_erro_nao_derruba_dns_e_ct(respx_mock, tmp_path):
    respx_mock.get(URL_RDAP_BR).mock(return_value=httpx.Response(404))
    respx_mock.get(URL_CRTSH).mock(return_value=httpx.Response(200, json=fixture("crtsh")))
    _mocar_wayback(respx_mock)
    _rota_doh(respx_mock, dict.fromkeys(("A", "AAAA", "MX", "NS", "TXT"), fixture("doh_nxdomain")))
    ctx, motor = await _rodar_nucleo(tmp_path, None)
    assert motor.status() == {
        "alvo": "feito", "rdap": "erro", "dns": "feito", "ct": "feito", "wayback_indice": "feito",
        "captura": "pulado", "wayback_snapshot": "feito",
    }
    ex = carregar_execucao(ctx.pasta)
    assert "404" in ex.status["rdap"]["motivo"]
    assert ex.saidas["dns"]["nxdomain"] is True
