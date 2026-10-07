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


def params_indice(dominio: str, to: str) -> list[tuple[str, str]]:
    """A consulta de listagem do domínio (R-T7-cdx): sem `collapse`, só HTML, `filter` repetido."""
    return [
        ("url", dominio),
        ("matchType", "domain"),
        ("output", "json"),
        ("fl", "timestamp,original"),
        ("filter", "statuscode:200"),
        ("filter", "mimetype:text/html"),
        ("limit", "10000"),
        ("to", to),
    ]


def params_home(dominio: str, to: str) -> dict[str, str]:
    return {
        "url": f"{dominio}/",
        "to": to,
        "filter": "statuscode:200",
        "fl": "timestamp,original",
        "output": "json",
    }


def rota_cdx(respx_mock, params: dict[str, str] | list[tuple[str, str]], corpo):
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
    assert set(saidas) == {"primeiro", "ultimo", "total", "por_mes", "truncado"}
    # total = capturas HTML (as linhas do CDX sem o cabeçalho); as linhas vêm ordenadas por URL,
    # não por data, então primeiro/ultimo são o mínimo e o máximo, não a primeira e a última linha
    assert saidas["total"] == len(fixture("cdx_dominio")) - 1 == 22
    assert (saidas["primeiro"], saidas["ultimo"]) == ("2002-01-20", "2015-10-31")
    por_mes = saidas["por_mes"]
    assert (por_mes["2002-01"], por_mes["2005-11"], por_mes["2013-08"], por_mes["2014-12"]) == (1, 2, 2, 2)
    assert sum(por_mes.values()) == saidas["total"]
    assert len(por_mes) == 18  # 22 capturas, quatro meses com duas
    assert list(por_mes) == sorted(por_mes)  # chaves AAAA-MM em ordem
    assert saidas["truncado"] is False


async def test_indice_primeiro_e_ultimo_nao_dependem_da_ordem_das_linhas(respx_mock, ctx_2019, serv):
    linhas = fixture("cdx_dominio")
    linhas[1:] = list(reversed(linhas[1:]))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), linhas)
    saidas = (await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)).saidas
    assert (saidas["primeiro"], saidas["ultimo"], saidas["total"]) == ("2002-01-20", "2015-10-31", 22)


async def test_indice_pede_o_cdx_com_os_parametros_da_spec(respx_mock, ctx_2019, serv):
    rota = rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_vazio"))
    await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    pedido = rota.calls.last.request.url
    # `filter` aparece duas vezes e não há `collapse`: o índice conta capturas, não URLs por dia
    assert pedido.params.multi_items() == params_indice("example.com", "20190606")
    assert "collapse" not in pedido.params
    (registro,) = log_custodia(ctx_2019.pasta)  # o CDX bruto vai para a custódia
    assert registro["tipo"] == "api"
    assert registro["origem"] == (
        f"{CDX}?url=example.com&matchType=domain&output=json&fl=timestamp,original"
        "&filter=statuscode:200&filter=mimetype:text/html&limit=10000&to=20190606"
    )
    assert json.loads(serv.custodia.ler(f"sha256:{registro['sha256']}")) == []


async def test_indice_to_vem_do_as_of(respx_mock, ctx_hoje, serv):
    rota = rota_cdx(respx_mock, params_indice("example.com", "20261007"), fixture("cdx_vazio"))
    await WaybackIndiceNo().executar(ctx_hoje, entrada_alvo(), {}, serv)
    assert rota.calls.last.request.url.params["to"] == "20261007"


@pytest.mark.parametrize("corpo", [[], [["timestamp", "original"]]], ids=["lista_vazia", "so_cabecalho"])
async def test_indice_sem_capturas(respx_mock, ctx_2019, serv, corpo):
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), corpo)
    resultado = await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert resultado == Feito(
        {"primeiro": None, "ultimo": None, "total": 0, "por_mes": {}, "truncado": False}
    )


def _linhas_do_cdx(n: int) -> list[list[str]]:
    return [["timestamp", "original"], *([["20190101120000", f"http://example.com/p{i}"] for i in range(n)])]


@pytest.mark.parametrize(
    "linhas_de_dados,truncado", [(9999, False), (10000, True), (10001, True)], ids=["9999", "10000", "10001"]
)
async def test_indice_truncado_quando_o_cdx_chega_ao_limite(respx_mock, ctx_2019, serv, linhas_de_dados, truncado):
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), _linhas_do_cdx(linhas_de_dados))
    saidas = (await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)).saidas
    assert saidas["truncado"] is truncado
    assert saidas["total"] == linhas_de_dados


async def test_indice_truncado_conta_as_linhas_antes_de_descartar_as_invalidas(respx_mock, ctx_2019, serv):
    linhas = _linhas_do_cdx(9900) + [["lixo", "http://example.com/x"]] * 100  # 10000 linhas de dados
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), linhas)
    saidas = (await WaybackIndiceNo().executar(ctx_2019, entrada_alvo(), {}, serv)).saidas
    assert saidas["total"] == 9900 and saidas["truncado"] is True


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
        "truncado": False,
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
    assert set(no.saidas) == {"primeiro", "ultimo", "total", "por_mes", "truncado"}


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
    assert resultado.saidas["falhas"] == [] and resultado.saidas["truncado"] is False
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
    ["20190410000000", "http://[::1/termos"],  # URL que nem o urlsplit aceita: o CDX traz o que o site serviu
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
    # a home primeiro; depois as subpáginas sem query, das mais rasas e curtas para as mais fundas;
    # as que dependem de query ficam para o fim
    assert [(p["timestamp"], p["url"]) for p in paginas] == [
        (HOME_TS, HOME_ORIGINAL),
        ("20190401000000", "http://example.com/faq"),
        ("20190406000000", "http://blog.example.com/indicacao"),
        ("20190301120000", "https://www.example.com/termos-de-uso/"),  # http/https/www/:80 viraram uma
        ("20190405000000", "http://example.com/como-funciona.html"),
        ("20190407000000", "http://example.com/blog/2019/como-funciona-o-saque"),
        ("20190408000000", "http://example.com/?page=termos"),
    ]
    assert resultado.saidas["falhas"] == [] and resultado.saidas["truncado"] is False
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
        "http://example.com/faq",
        "http://blog.example.com/indicacao",
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


async def test_snapshot_falha_que_nao_e_erro_no_numa_subpagina_vai_para_falhas(
    respx_mock, ctx_2019, serv, monkeypatch
):
    montar_subpaginas(respx_mock)
    guardar = serv.custodia.guardar

    def guardar_com_defeito(dados, ext, tipo, origem):
        if "/faq" in origem:
            raise ValueError("custódia recusou")
        return guardar(dados, ext, tipo, origem)

    monkeypatch.setattr(serv.custodia, "guardar", guardar_com_defeito)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)

    urls = [p["url"] for p in resultado.saidas["paginas"]]
    assert HOME_ORIGINAL in urls and "http://example.com/faq" not in urls and len(urls) == 6
    (falha,) = resultado.saidas["falhas"]
    assert (falha["url"], falha["timestamp"]) == ("http://example.com/faq", "20190401000000")
    assert falha["motivo"] == "ValueError: custódia recusou"


async def test_snapshot_listagem_do_dominio_com_erro_vira_falha_e_mantem_a_home(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    rota = respx_mock.get(CDX, params=params_indice("example.com", "20190606")).mock(
        return_value=httpx.Response(503)
    )
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)

    assert rota.call_count == 4  # esgotou as tentativas antes de desistir da listagem
    (pagina,) = resultado.saidas["paginas"]  # a home já baixada não se perde
    assert (pagina["url"], pagina["timestamp"]) == (HOME_ORIGINAL, HOME_TS)
    assert serv.custodia.ler(pagina["html"]) == html_home()
    (falha,) = resultado.saidas["falhas"]
    assert falha["url"] is None and falha["timestamp"] is None
    assert "wayback cdx" in falha["motivo"].lower() and "503" in falha["motivo"]
    assert resultado.saidas["truncado"] is False


async def test_snapshot_listagem_com_formato_inesperado_tambem_vira_falha(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), {"erro": "manutencao"})
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert len(resultado.saidas["paginas"]) == 1
    (falha,) = resultado.saidas["falhas"]
    assert falha["url"] is None and "wayback cdx" in falha["motivo"].lower()


async def test_snapshot_truncado_quando_a_listagem_chegou_ao_limite(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), _linhas_do_cdx(10000))
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    assert resultado.saidas["truncado"] is True
    assert resultado.saidas["falhas"] == [] and len(resultado.saidas["paginas"]) == 1


async def test_snapshot_variantes_de_query_nao_ocupam_os_slots(respx_mock, ctx_2019, serv):
    # reprodução da revisão: 9 + 5 variantes de query e 3 páginas de regras reais, limite 10
    listagem = [
        ["timestamp", "original"],
        *([f"201904{n:02d}000000", f"http://example.com/?indicacao=user{n}"] for n in range(1, 10)),
        *([f"201905{n:02d}000000", f"http://example.com/cadastro?indicador=u{n}"] for n in range(1, 6)),
        ["20190301000000", "http://example.com/termos"],
        ["20190302000000", "http://example.com/faq"],
        ["20190303000000", "http://example.com/saque"],
    ]
    rota = montar_subpaginas(respx_mock, listagem)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)

    # sem query primeiro (rasas e curtas antes), depois no máximo 1 variante por caminho: a mais recente
    assert [(p["timestamp"], p["url"]) for p in resultado.saidas["paginas"][1:]] == [
        ("20190302000000", "http://example.com/faq"),
        ("20190303000000", "http://example.com/saque"),
        ("20190301000000", "http://example.com/termos"),
        ("20190409000000", "http://example.com/?indicacao=user9"),
        ("20190505000000", "http://example.com/cadastro?indicador=u5"),
    ]
    assert rota.call_count == 5


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


# o charset vem do site investigado: nome que o Python não conhece (LookupError) e codec que não
# decodifica texto (`idna`, `undefined`: UnicodeError) têm de cair no UTF-8, nunca derrubar o nó
CHARSETS_HOSTIS = ["nao-existe", "idna", "undefined", "rot13", "base64"]


@pytest.mark.parametrize("charset", CHARSETS_HOSTIS)
async def test_snapshot_com_charset_hostil_no_meta_cai_no_utf8(respx_mock, ctx_2019, serv, charset):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_vazio"))
    corpo = f"<html><head><meta charset={charset}></head><body><p>Saque rápido</p></body></html>".encode()
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL, corpo, {"content-type": "text/html"})
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    (pagina,) = resultado.saidas["paginas"]
    assert serv.custodia.ler(pagina["texto"]).decode("utf-8") == "Saque rápido"


@pytest.mark.parametrize("charset", CHARSETS_HOSTIS)
async def test_snapshot_com_charset_hostil_no_cabecalho_cai_no_utf8(respx_mock, ctx_2019, serv, charset):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), fixture("cdx_vazio"))
    corpo = "<html><body><p>Saque rápido</p></body></html>".encode()
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL, corpo, {"content-type": f"text/html; charset={charset}"})
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)
    (pagina,) = resultado.saidas["paginas"]
    assert serv.custodia.ler(pagina["texto"]).decode("utf-8") == "Saque rápido"


async def test_snapshot_subpagina_com_charset_hostil_nao_derruba_o_no(respx_mock, ctx_2019, serv):
    rota_cdx(respx_mock, params_home("example.com", "20190606"), fixture("cdx_home"))
    rota_cdx(respx_mock, params_indice("example.com", "20190606"), LISTAGEM)
    rota_snapshot(respx_mock, HOME_TS, HOME_ORIGINAL)

    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/faq"):
            corpo = "<meta charset=idna><p>Perguntas frequentes</p>".encode()
            return httpx.Response(200, content=corpo, headers={"content-type": "text/html"})
        return _paginas_fake(request)

    respx_mock.get(url__startswith="https://web.archive.org/web/2019").mock(side_effect=responder)
    resultado = await WaybackSnapshotNo().executar(ctx_2019, entrada_alvo(), {}, serv)

    assert len(resultado.saidas["paginas"]) == 7 and resultado.saidas["falhas"] == []
    faq = next(p for p in resultado.saidas["paginas"] if p["url"].endswith("/faq"))
    assert serv.custodia.ler(faq["texto"]).decode("utf-8") == "Perguntas frequentes"


def test_snapshot_declaracao():
    no = WaybackSnapshotNo()
    assert (no.nome, no.entradas, no.opcionais, no.as_of, no.toca_alvo) == (
        "wayback_snapshot",
        ("alvo",),
        ("captura",),
        "exato",
        False,
    )
    assert set(no.saidas) == {"paginas", "falhas", "truncado"}


@pytest.mark.parametrize(
    "caminho",
    ["/termos", "/Termos-de-Uso", "/contrato", "/planos", "/FAQ", "/como-funciona", "/saque", "/indicacao", "/rentabilidade", "/sobre", "/quem-somos"],
)
def test_prioridade_casa_as_paginas_de_regras(caminho):
    assert PRIORIDADE.search(caminho)


@pytest.mark.parametrize("caminho", ["/", "/contato", "/blog", "/login", "/img/logo.png"])
def test_prioridade_nao_casa_o_resto(caminho):
    assert not PRIORIDADE.search(caminho)
