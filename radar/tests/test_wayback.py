"""Nós do Wayback: índice de capturas do domínio e snapshots da página (Tarefa 7)."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from radar.config import CapturaConfig, Config, RedeConfig
from radar.custodia import Custodia
from radar.modelos import Contexto, ErroNo, Feito, Pulado
from radar.motor import Servicos
from radar.nos.wayback import PRIORIDADE, WaybackIndiceNo, WaybackSnapshotNo
from radar.rede import Rede
from radar.texto import texto_de_html

FIXTURES = Path(__file__).parent / "fixtures" / "api"
CDX = "https://web.archive.org/cdx/search/cdx"
AGORA = datetime(2026, 10, 7, 12, 0, 0)
HOME_ORIGINAL = "http://www.example.com/"
HOME_TS = "20190606235936"  # a última linha de cdx_home.json: é o snapshot de snapshot_home.html
HTML_UTF8 = {"content-type": "text/html; charset=UTF-8"}


def fixture(nome: str):
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


def html_home() -> bytes:
    return (FIXTURES / "snapshot_home.html").read_bytes()


async def _nao_dormir(s: float) -> None:
    return None


def contexto(
    pasta: Path, as_of: date, alvo: str = "example.com", modo_contato: str = "captura"
) -> Contexto:
    slug = alvo.replace(".", "-")
    return Contexto(
        alvo=alvo,
        slug=slug,
        url_inicial=f"https://{alvo}/",
        as_of=as_of,
        data_execucao=AGORA,
        modo_contato=modo_contato,
        modo_cego=False,
        run_id=f"{slug}/2026-10-07_120000",
        pasta=pasta,
    )


def entrada_alvo(dominio: str = "example.com") -> dict[str, dict]:
    return {
        "alvo": {
            "dominio": dominio,
            "slug": dominio.replace(".", "-"),
            "url_inicial": f"https://{dominio}/",
        }
    }


@asynccontextmanager
async def servicos(pasta: Path, **captura):
    config = Config(rede=RedeConfig(limites={"*": 0}), captura=CapturaConfig(**captura))
    rede = Rede(config.rede, dormir=_nao_dormir)
    try:
        yield Servicos(config=config, rede=rede, custodia=Custodia(pasta))
    finally:
        await rede.fechar()


@pytest.fixture
def ctx_hoje(tmp_path):
    return contexto(tmp_path, date(2026, 10, 7))


@pytest.fixture
def ctx_2019(tmp_path):
    return contexto(tmp_path, date(2019, 6, 6))


@pytest.fixture
async def serv(tmp_path):
    async with servicos(tmp_path) as s:
        yield s


def log_custodia(pasta: Path) -> list[dict]:
    texto = (pasta / "custodia.log").read_text(encoding="utf-8")
    return [json.loads(linha) for linha in texto.split("\n") if linha]


def params_indice(dominio: str, to: str) -> dict[str, str]:
    return {
        "url": dominio,
        "matchType": "domain",
        "output": "json",
        "fl": "timestamp,original",
        "filter": "statuscode:200",
        "collapse": "timestamp:8",
        "limit": "10000",
        "to": to,
    }


def params_home(dominio: str, to: str) -> dict[str, str]:
    return {
        "url": f"{dominio}/",
        "to": to,
        "filter": "statuscode:200",
        "fl": "timestamp,original",
        "output": "json",
    }


def rota_cdx(respx_mock, params: dict[str, str], corpo):
    return respx_mock.get(CDX, params=params).mock(return_value=httpx.Response(200, json=corpo))


def url_snapshot(ts: str, original: str) -> str:
    return f"https://web.archive.org/web/{ts}id_/{original}"


def rota_snapshot(respx_mock, ts: str, original: str, corpo: bytes | None = None, headers=None):
    return respx_mock.get(url_snapshot(ts, original)).mock(
        return_value=httpx.Response(
            200, content=html_home() if corpo is None else corpo, headers=headers or HTML_UTF8
        )
    )


def _paginas_fake(request: httpx.Request) -> httpx.Response:
    corpo = f"<p>conteudo de {request.url.path}</p>".encode()
    return httpx.Response(200, content=corpo, headers=HTML_UTF8)


# ---------------------------------------------------------------------------- índice


async def test_indice_por_mes(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_dominio"))
    resultado = await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    saidas = resultado.saidas
    assert set(saidas) == {"primeiro", "ultimo", "total", "por_mes"}
    # total = linhas do CDX sem o cabeçalho; as linhas vêm ordenadas por URL, não por data,
    # então primeiro/ultimo são o mínimo e o máximo, não a primeira e a última linha
    assert saidas["total"] == len(fixture("cdx_dominio")) - 1 == 24
    assert (saidas["primeiro"], saidas["ultimo"]) == ("2002-01-20", "2018-03-23")
    por_mes = saidas["por_mes"]
    assert (por_mes["2002-01"], por_mes["2004-10"], por_mes["2005-05"], por_mes["2007-08"]) == (1, 2, 2, 2)
    assert sum(por_mes.values()) == saidas["total"]
    assert len(por_mes) == 21  # 24 linhas, três meses com duas
    assert list(por_mes) == sorted(por_mes)  # chaves AAAA-MM em ordem


async def test_indice_pede_o_cdx_com_os_parametros_da_spec(respx_mock, ctx_2019, serv):
    rota = rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_vazio"))
    await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    pedido = rota.calls.last.request.url
    assert dict(pedido.params) == params_indice("example.com", "20190606")
    (registro,) = log_custodia(ctx_2019.pasta)  # o CDX bruto vai para a custódia
    assert registro["tipo"] == "api"
    assert registro["origem"].startswith(f"{CDX}?url=example.com&matchType=domain&")
    assert json.loads(serv.custodia.ler(f"sha256:{registro['sha256']}")) == []


async def test_indice_to_vem_do_as_of(respx_mock, ctx_hoje, serv):
    rota = rota_cdx(respx_mock, params_indice("example.com", "20261007"), fixture("cdx_vazio"))
    await WaybackIndiceNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert rota.calls.last.request.url.params["to"] == "20261007"


@pytest.mark.parametrize("corpo", [[], [["timestamp", "original"]]], ids=["lista_vazia", "so_cabecalho"])
async def test_indice_sem_capturas(respx_mock, ctx_2019, serv, corpo):
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), corpo)
    resultado = await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert resultado == Feito({"primeiro": None, "ultimo": None, "total": 0, "por_mes": {}})


async def test_indice_ignora_linhas_invalidas_e_respeita_a_ordem_das_colunas(respx_mock, ctx_2019, serv):
    rota_cdx(
        respx_mock,
        params_indice("example.com", "20190606"),
        [
            ["original", "timestamp"],
            ["http://example.com/", "20190501120000"],
            ["http://example.com/a", "2019"],  # curto
            ["http://example.com/b", None],
            ["http://example.com/c", "20190230000000"],  # 30 de fevereiro
            ["http://example.com/d"],  # sem a coluna do timestamp
            "lixo",
            ["", "20190503120000"],  # sem URL
            ["http://example.com/e", "20190510080000"],
        ],
    )
    resultado = await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert resultado.saidas == {
        "primeiro": "2019-05-01",
        "ultimo": "2019-05-10",
        "total": 2,
        "por_mes": {"2019-05": 2},
    }


@pytest.mark.parametrize(
    "corpo",
    [b"<html>manutencao</html>", b'{"erro": 1}', b'[["a", "b"], ["1", "2"]]', b'[["timestamp"], ["20190501120000"]]'],
    ids=["html", "objeto", "cabecalho_sem_colunas", "cabecalho_sem_original"],
)
async def test_indice_formato_inesperado_e_erro_permanente(respx_mock, ctx_2019, serv, corpo):
    respx_mock.get(CDX).mock(return_value=httpx.Response(200, content=corpo))
    with pytest.raises(ErroNo) as e:
        await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert e.value.permanente is True
    assert "wayback" in e.value.mensagem.lower()
    assert len(log_custodia(ctx_2019.pasta)) == 1  # o bruto fica guardado mesmo assim


async def test_indice_503_esgotado_vira_erro_nao_permanente(respx_mock, ctx_2019, serv):
    rota = respx_mock.get(CDX).mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo) as e:
        await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert e.value.permanente is False
    assert "wayback" in e.value.mensagem.lower() and "503" in e.value.mensagem
    assert rota.call_count == 4


def test_indice_declaracao():
    no = WaybackIndiceNo()
    assert (no.nome, no.entradas, no.opcionais, no.as_of, no.toca_alvo) == (
        "wayback_indice",
        ("alvo",),
        (),
        "exato",
        False,
    )
    assert set(no.saidas) == {"primeiro", "ultimo", "total", "por_mes"}


# ---------------------------------------------------------------------------- snapshot: quando roda


async def test_snapshot_pulado_quando_captura_ok(respx_mock, ctx_hoje, serv):
    entradas = {**entrada_alvo(), "captura": {"bloqueada": False}}
    resultado = await WaybackSnapshotNo().executar(ctx_hoje, entradas, {}, serv)
    assert resultado == Pulado("captura ok")
    assert len(respx_mock.calls) == 0  # nem o CDX é consultado


async def test_snapshot_roda_quando_captura_bloqueada(respx_mock, ctx_hoje, serv):
    rota_cdx(respx_mock, params_home("example.com", "20261007"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20261007"), fixture("cdx_vazio"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    entradas = {**entrada_alvo(), "captura": {"bloqueada": True}}
    resultado = await WaybackSnapshotNo().executar(ctx_hoje, entradas, {}, serv)
    assert isinstance(resultado, Feito)
    assert [p["url"] for p in resultado.saidas["paginas"]] == [HOME_ORIGINAL]


@pytest.mark.parametrize(
    "as_of,modo_contato,extras",
    [
        (date(2026, 10, 7), "captura", {}),
        (date(2026, 10, 7), "nenhum", {"captura": {"bloqueada": False}}),
        (date(2019, 6, 6), "captura", {"captura": {"bloqueada": False}}),
    ],
    ids=["sem_captura_nas_entradas", "modo_contato_nenhum", "retroativo"],
)
async def test_snapshot_roda_fora_do_caso_captura_ok(respx_mock, tmp_path, serv, as_of, modo_contato, extras):
    ctx = contexto(tmp_path, as_of, modo_contato=modo_contato)
    to = as_of.strftime("%Y%m%d")
    rota_cdx(respx_mock, params_home("example.com", to), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", to), fixture("cdx_vazio"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    resultado = await WaybackSnapshotNo().executar(ctx, {**entrada_alvo(), **extras}, {}, serv)
    assert isinstance(resultado, Feito)
    assert len(resultado.saidas["paginas"]) == 1


# ---------------------------------------------------------------------------- snapshot: página inicial


async def test_snapshot_ate_as_of_usa_id_(respx_mock, ctx_2019, serv):
    rota_home = rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_dominio"))
    rota = rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)

    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)

    # o último registro do CDX da home (a lista vem em ordem crescente de data)
    assert dict(rota_home.calls.last.request.url.params) == params_home("example.com", "20190606")
    # pede o snapshot cru (`id_`), sem a barra do Wayback nem links reescritos
    assert str(rota.calls.last.request.url) == url_snapshot(HOME_TS, HOME_ORIGINAL)
    assert resultado.saidas["falhas"] == []
    (pagina,) = resultado.saidas["paginas"]
    assert set(pagina) == {"url", "timestamp", "html", "texto"}
    assert (pagina["url"], pagina["timestamp"]) == (HOME_ORIGINAL, HOME_TS)
    assert serv.custodia.ler(pagina["html"]) == html_home()
    texto = serv.custodia.ler(pagina["texto"]).decode("utf-8")
    assert texto == texto_de_html(html_home().decode("utf-8"))
    assert "illustrative examples" in texto and "background-color" not in texto  # sem o <style>
    por_tipo = {r["tipo"]: r["origem"] for r in log_custodia(ctx_2019.pasta) if r["tipo"] != "api"}
    assert por_tipo == {
        "snapshot": url_snapshot(HOME_TS, HOME_ORIGINAL),
        "texto": url_snapshot(HOME_TS, HOME_ORIGINAL),
    }


async def test_snapshot_home_escolhe_o_registro_de_data_maxima_mesmo_fora_de_ordem(respx_mock, ctx_2019, serv):
    linhas = fixture("cdx_home")
    linhas[1:] = list(reversed(linhas[1:]))
    rota_cdx(respx_mock, params_home("example.com", "20190606"), linhas)
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_vazio"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert resultado.saidas["paginas"][0]["timestamp"] == HOME_TS


@pytest.mark.parametrize("corpo", [[], [["timestamp", "original"]]], ids=["lista_vazia", "so_cabecalho"])
async def test_sem_snapshot_ate_as_of(respx_mock, ctx_2019, serv, corpo):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), corpo)
    with pytest.raises(ErroNo, match="sem snapshot até 2019-06-06") as e:
        await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert e.value.permanente is True
    assert len(respx_mock.calls) == 1  # sem home, nem procura as subpáginas


async def test_snapshot_da_home_com_404_e_erro_permanente(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    respx_mock.get(url_snapshot(HOME_TS, HOME_ORIGINAL)).mock(return_value=httpx.Response(404))
    with pytest.raises(ErroNo) as e:
        await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert e.value.permanente is True
    assert "wayback" in e.value.mensagem.lower() and "404" in e.value.mensagem


async def test_snapshot_da_home_com_503_esgotado_nao_e_permanente(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota = respx_mock.get(url_snapshot(HOME_TS, HOME_ORIGINAL)).mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo) as e:
        await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert e.value.permanente is False
    assert rota.call_count == 4


@pytest.mark.parametrize("corpo", [b"<html>manutencao</html>", b'{"erro": 1}'])
async def test_cdx_da_home_com_formato_inesperado_e_erro_permanente(respx_mock, ctx_2019, serv, corpo):
    respx_mock.get(CDX).mock(return_value=httpx.Response(200, content=corpo))
    with pytest.raises(ErroNo) as e:
        await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert e.value.permanente is True and "wayback" in e.value.mensagem.lower()


# ---------------------------------------------------------------------------- snapshot: subpáginas

LISTAGEM = [
    ["timestamp", "original"],
    ["20190101000000", "http://example.com/"],  # a home não é subpágina
    ["20180101000000", "http://example.com/termos-de-uso"],  # versão antiga da mesma página
    ["20190210000000", "http://example.com:80/termos-de-uso"],
    ["20190301120000", "https://www.example.com/termos-de-uso/"],  # a mais recente: é a escolhida
    ["20190401000000", "http://example.com/faq"],
    ["20190402000000", "http://example.com/contato"],  # fora da PRIORIDADE
    ["20190403000000", "http://example.com/assets/plano.png"],  # casa, mas é imagem
    ["20190404000000", "http://example.com/js/saque.js"],  # casa, mas é script
    ["20190405000000", "http://example.com/como-funciona.html"],
    ["20190406000000", "http://blog.example.com/indicacao"],  # subdomínio do mesmo domínio
    ["20190407000000", "http://example.com/blog/2019/como-funciona-o-saque"],
    ["20190408000000", "http://example.com/?page=termos"],  # roteamento por query
    ["20190409000000", "http://example.com/termos.pdf"],  # casa, mas é documento
]


def montar_subpaginas(respx_mock, listagem=None, to="20190606"):
    rota_cdx(respx_mock, params_home("example.com", to), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", to), LISTAGEM if listagem is None else listagem)
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    return respx_mock.get(url__startswith="https://web.archive.org/web/2019").mock(side_effect=_paginas_fake)


async def test_snapshot_subpaginas_prioritarias_mais_recentes_ate_o_as_of(respx_mock, ctx_2019, serv):
    rota = montar_subpaginas(respx_mock)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)

    paginas = resultado.saidas["paginas"]
    # a home primeiro; depois as subpáginas, das mais rasas e curtas para as mais fundas
    assert [(p["timestamp"], p["url"]) for p in paginas] == [
        (HOME_TS, HOME_ORIGINAL),
        ("20190408000000", "http://example.com/?page=termos"),
        ("20190401000000", "http://example.com/faq"),
        ("20190406000000", "http://blog.example.com/indicacao"),
        ("20190301120000", "https://www.example.com/termos-de-uso/"),  # http/https/www/:80 viraram uma
        ("20190405000000", "http://example.com/como-funciona.html"),
        ("20190407000000", "http://example.com/blog/2019/como-funciona-o-saque"),
    ]
    assert resultado.saidas["falhas"] == []
    pedidos = [str(c.request.url) for c in rota.calls]
    assert pedidos == [url_snapshot(p["timestamp"], p["url"]) for p in paginas[1:]]
    # cada subpágina tem o HTML e o texto na custódia
    for p in paginas[1:]:
        assert serv.custodia.ler(p["html"]).startswith(b"<p>conteudo de /web/")
        assert serv.custodia.ler(p["texto"]).decode().startswith("conteudo de /web/")


async def test_snapshot_prioridade_olha_o_caminho_e_nao_o_dominio(respx_mock, tmp_path):
    ctx = contexto(tmp_path, date(2019, 6, 6), alvo="planofacil.com.br")
    rota_cdx(respx_mock, params_home("planofacil.com.br", "20190606"), [["timestamp", "original"], [HOME_TS, "http://planofacil.com.br/"]])
    rota_cdx(
        respx_mock,
        params_indice("planofacil.com.br", "20190606"),
        [
            ["timestamp", "original"],
            ["20190401000000", "http://planofacil.com.br/contato"],  # só o domínio casa com "plano"
            ["20190402000000", "http://planofacil.com.br/faq"],
        ],
    )
    rota_snapshot(respx_mock, HOME_TS, "http://planofacil.com.br/")
    rota = respx_mock.get(url__startswith="https://web.archive.org/web/2019040").mock(side_effect=_paginas_fake)
    async with servicos(tmp_path) as s:
        resultado = await WaybackSnapshotNo().executar(ctx, entrada_alvo("planofacil.com.br"), {}, s)
    assert [p["url"] for p in resultado.saidas["paginas"]] == [
        "http://planofacil.com.br/",
        "http://planofacil.com.br/faq",
    ]
    assert rota.call_count == 1


async def test_snapshot_limita_ao_max_subpaginas_da_config(respx_mock, ctx_2019, tmp_path):
    rota = montar_subpaginas(respx_mock)
    async with servicos(tmp_path, max_subpaginas=2) as s:
        resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, s)
    assert [p["url"] for p in resultado.saidas["paginas"]] == [
        HOME_ORIGINAL,
        "http://example.com/?page=termos",
        "http://example.com/faq",
    ]
    assert rota.call_count == 2


async def test_snapshot_com_max_subpaginas_zero_so_busca_a_home(respx_mock, ctx_2019, tmp_path):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)  # nenhuma outra rota: o CDX do domínio nem é pedido
    async with servicos(tmp_path, max_subpaginas=0) as s:
        resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, s)
    assert [p["url"] for p in resultado.saidas["paginas"]] == [HOME_ORIGINAL]


async def test_snapshot_falha_de_subpagina_so_descarta_a_subpagina(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), LISTAGEM)
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)

    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/faq"):
            return httpx.Response(404)
        return _paginas_fake(request)

    respx_mock.get(url__startswith="https://web.archive.org/web/2019").mock(side_effect=responder)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)

    urls = [p["url"] for p in resultado.saidas["paginas"]]
    assert HOME_ORIGINAL in urls and "http://example.com/faq" not in urls
    assert len(urls) == 6  # a home e as 5 subpáginas que sobraram das 6
    (falha,) = resultado.saidas["falhas"]
    assert (falha["url"], falha["timestamp"]) == ("http://example.com/faq", "20190401000000")
    assert "404" in falha["motivo"] and "wayback" in falha["motivo"].lower()


async def test_snapshot_listagem_do_dominio_com_erro_derruba_o_no(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    respx_mock.get(CDX, params=params_indice("example.com", "20190606")).mock(return_value=httpx.Response(503))
    with pytest.raises(ErroNo) as e:
        await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert e.value.permanente is False
    assert "wayback cdx" in e.value.mensagem.lower() and "503" in e.value.mensagem


async def test_snapshot_reaproveita_a_listagem_pedida_pelo_indice(respx_mock, ctx_2019, serv):
    listagem = rota_cdx(respx_mock, params_indice("example.com", "20190606"), LISTAGEM)
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    respx_mock.get(url__startswith="https://web.archive.org/web/2019").mock(side_effect=_paginas_fake)
    await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert listagem.call_count == 1  # mesma URL, mesma Rede: o cache responde a segunda


@pytest.mark.parametrize(
    "corpo,headers",
    [
        # sem charset no cabeçalho: vale o <meta> do próprio HTML
        ("<html><head><meta charset=iso-8859-1></head><body><p>Indicação de amigos</p></body></html>", {"content-type": "text/html"}),
        ("<html><head><meta http-equiv='Content-Type' content='text/html; charset=ISO-8859-1'></head><body><p>Indicação de amigos</p></body></html>", {"content-type": "text/html"}),
        # com charset no cabeçalho: vale o cabeçalho
        ("<html><body><p>Indicação de amigos</p></body></html>", {"content-type": "text/html; charset=iso-8859-1"}),
    ],
    ids=["meta_charset", "meta_http_equiv", "cabecalho"],
)
async def test_snapshot_decodifica_pelo_charset_da_pagina(respx_mock, ctx_2019, serv, corpo, headers):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_vazio"))
    bruto = corpo.encode("latin-1")
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL, bruto, headers)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    (pagina,) = resultado.saidas["paginas"]
    assert serv.custodia.ler(pagina["html"]) == bruto  # o HTML é guardado como veio
    assert serv.custodia.ler(pagina["texto"]).decode("utf-8") == "Indicação de amigos"


async def test_snapshot_com_charset_desconhecido_cai_no_utf8(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_vazio"))
    corpo = "<html><head><meta charset=nao-existe></head><body><p>Saque rápido</p></body></html>".encode()
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL, corpo, {"content-type": "text/html"})
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    (pagina,) = resultado.saidas["paginas"]
    assert serv.custodia.ler(pagina["texto"]).decode("utf-8") == "Saque rápido"


def test_snapshot_declaracao():
    no = WaybackSnapshotNo()
    assert (no.nome, no.entradas, no.opcionais, no.as_of, no.toca_alvo) == (
        "wayback_snapshot",
        ("alvo",),
        ("captura",),
        "exato",
        False,
    )
    assert set(no.saidas) == {"paginas", "falhas"}


@pytest.mark.parametrize(
    "caminho",
    ["/termos", "/Termos-de-Uso", "/contrato", "/planos", "/FAQ", "/como-funciona", "/saque", "/indicacao", "/rentabilidade", "/sobre", "/quem-somos"],
)
def test_prioridade_casa_as_paginas_de_regras(caminho):
    assert PRIORIDADE.search(caminho)


@pytest.mark.parametrize("caminho", ["/", "/contato", "/blog", "/login", "/img/logo.png"])
def test_prioridade_nao_casa_o_resto(caminho):
    assert not PRIORIDADE.search(caminho)
