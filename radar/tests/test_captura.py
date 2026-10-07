"""Nó `captura`: visita passiva com o Chromium, artefatos na custódia e detecção de anti-bot (Tarefa 8).

Os testes com `@lento` abrem o Chromium de verdade, só contra 127.0.0.1 (`servidor_local`) ou contra
sockets locais. Rodam na suíte padrão; para pulá-los: `-m "not lento"`.
"""

from __future__ import annotations

import json
import re
import socket
import time
from datetime import date, datetime
from pathlib import Path

import pytest
from playwright.async_api import Browser

from radar.config import UA_NAVEGADOR, CapturaConfig, Config, RedeConfig
from radar.custodia import Custodia, verificar
from radar.modelos import Contexto, ErroNo, Feito, Pulado
from radar.motor import Servicos
from radar.nos import captura as modulo_captura
from radar.nos.captura import (
    CapturaNo,
    _bytes,
    _e_desafio,
    _escolher_links,
    _opcoes_do_contexto,
    _terceiros,
)

AGORA = datetime(2026, 10, 7, 12, 0, 0)
SITE = Path(__file__).parent / "fixtures" / "site_sintetico"
PNG = b"\x89PNG\r\n\x1a\n"

lento = pytest.mark.lento  # abre o Chromium de verdade: 1 a 3 s cada


def contexto(pasta: Path, url: str, modo_contato: str = "captura") -> Contexto:
    return Contexto(
        alvo="127.0.0.1",
        slug="127-0-0-1",
        url_inicial=url,
        as_of=date(2026, 10, 7),
        data_execucao=AGORA,
        modo_contato=modo_contato,
        modo_cego=False,
        run_id="127-0-0-1/2026-10-07_120000",
        pasta=pasta,
    )


def entrada_alvo(url: str) -> dict[str, dict]:
    return {"alvo": {"dominio": "127.0.0.1", "slug": "127-0-0-1", "url_inicial": url}}


async def capturar(
    pasta: Path, url: str, *, modo_contato: str = "captura", rede: RedeConfig | None = None, **captura
):
    """Roda o nó e devolve `(resultado, servicos)`.

    A captura não usa a `Rede` (o Playwright tem a pilha de rede própria): `rede=None` faz qualquer
    uso dela falhar o teste.
    """
    config = Config(rede=rede or RedeConfig(), captura=CapturaConfig(**captura))
    serv = Servicos(config=config, rede=None, custodia=Custodia(pasta))
    resultado = await CapturaNo().executar(contexto(pasta, url, modo_contato), entrada_alvo(url), {}, serv)
    return resultado, serv


def log_custodia(pasta: Path) -> list[dict]:
    texto = (pasta / "custodia.log").read_text(encoding="utf-8")
    return [json.loads(linha) for linha in texto.split("\n") if linha]


def texto_de(serv: Servicos, pagina: dict) -> str:
    return serv.custodia.ler(pagina["texto"]).decode("utf-8")


def caminhos(pedidos) -> list[str]:
    return [p.caminho for p in pedidos]


# ---------------------------------------------------------------------------- declaração e modo


def test_declaracao():
    no = CapturaNo()
    assert (no.nome, no.entradas, no.opcionais, no.exige_um_de, no.toca_alvo, no.as_of) == (
        "captura",
        ("alvo",),
        (),
        (),
        True,
        "so_atual",
    )
    assert set(no.saidas) == {"paginas", "terceiros", "bloqueada", "falhas"}


async def test_pulado_sem_contato(tmp_path, monkeypatch):
    def nao_deve_abrir_o_navegador():
        raise AssertionError("modo_contato=nenhum não pode abrir o navegador")

    monkeypatch.setattr(modulo_captura, "async_playwright", nao_deve_abrir_o_navegador)
    resultado, _ = await capturar(tmp_path, "http://127.0.0.1:1/", modo_contato="nenhum")
    assert resultado == Pulado("modo_contato=nenhum")
    assert not (tmp_path / "custodia.log").exists()


# ---------------------------------------------------------------------------- regra do desafio anti-bot


@pytest.mark.parametrize(
    "titulo",
    [
        "Just a moment...",
        "just a moment",
        "Attention Required! | Cloudflare",
        "ATTENTION REQUIRED",
        "Verifique que você é humano",
        "Verifique você é humano",
        "VERIFIQUE QUE VOCÊ É HUMANO",
    ],
)
def test_desafio_pelo_titulo_vale_com_texto_longo_e_sem_marcas(titulo):
    assert _e_desafio(titulo, "<html><body>nada de especial</body></html>", "x" * 5000) is True


@pytest.mark.parametrize(
    "titulo",
    ["", "InvestMax Brasil", "Um momento de atenção", "Verifique seus dados", "Você é humano? Cadastre-se"],
)
def test_titulo_comum_nao_e_desafio(titulo):
    assert _e_desafio(titulo, "<html></html>", "") is False


@pytest.mark.parametrize("marca", ["cf-chl", "challenge-platform", "g-recaptcha", "h-captcha"])
def test_marca_com_texto_curto_e_desafio(marca):
    html = f'<html><body><div class="{marca}"></div></body></html>'
    assert _e_desafio("Entrar", html, "Verificando...") is True
    assert _e_desafio("Entrar", html, "") is True


@pytest.mark.parametrize("marca", ["cf-chl", "challenge-platform", "g-recaptcha", "h-captcha"])
def test_marca_com_texto_longo_nao_e_desafio(marca):
    html = f'<html><body><div class="{marca}"></div></body></html>'
    assert _e_desafio("Entrar", html, "a" * 200) is False
    assert _e_desafio("Entrar", html, "a" * 5000) is False


def test_desafio_fronteira_de_200_caracteres():
    html = '<script src="/cdn-cgi/challenge-platform/h/b/orchestrate"></script>'
    assert _e_desafio("Entrar", html, "a" * 199) is True
    assert _e_desafio("Entrar", html, "a" * 200) is False


def test_desafio_espacos_nas_pontas_do_texto_nao_contam():
    html = '<div class="g-recaptcha"></div>'
    assert _e_desafio("Entrar", html, "\n\n" + "a" * 150 + "\n" * 100) is True


def test_marca_sem_texto_curto_e_texto_curto_sem_marca_nao_sao_desafio():
    assert _e_desafio("Entrar", "<html><body>Olá</body></html>", "Olá") is False


def test_marca_em_maiusculas_tambem_vale():
    assert _e_desafio("Entrar", '<div class="G-Recaptcha"></div>', "curto") is True


# ---------------------------------------------------------------------------- opções do contexto


def test_opcoes_do_contexto_sem_proxy(tmp_path):
    opcoes = _opcoes_do_contexto(RedeConfig(), tmp_path / "captura.har")
    assert opcoes == {
        "accept_downloads": False,
        "service_workers": "block",
        "user_agent": UA_NAVEGADOR,
        "record_har_path": str(tmp_path / "captura.har"),
        "record_har_content": "embed",
    }


def test_opcoes_do_contexto_com_proxy_e_ua_da_config(tmp_path):
    rede = RedeConfig(proxy="socks5://127.0.0.1:9050", ua_navegador="radar-teste/1.0")
    opcoes = _opcoes_do_contexto(rede, tmp_path / "captura.har")
    assert opcoes["proxy"] == {"server": "socks5://127.0.0.1:9050"}
    assert opcoes["user_agent"] == "radar-teste/1.0"
    assert opcoes["accept_downloads"] is False and opcoes["service_workers"] == "block"


def test_texto_com_surrogate_solitario_nao_derruba_a_gravacao():
    # UTF-16 inválido no texto do site: o `encode("utf-8")` puro levantaria UnicodeEncodeError
    assert _bytes("Saque \ud800 liberado") == b"Saque ? liberado"
    assert _bytes("Saque rápido") == "Saque rápido".encode()


def test_captura_so_navega_nunca_interage_com_a_pagina():
    codigo = Path(modulo_captura.__file__).read_text(encoding="utf-8")
    interacoes = re.findall(
        r"\.(click|dblclick|fill|check|uncheck|tap|press|type|select_option|set_input_files|"
        r"drag_and_drop|dispatch_event|hover|submit|focus)\(",
        codigo,
    )
    assert interacoes == []


# ---------------------------------------------------------------------------- terceiros (HAR)


def har(*urls: str) -> bytes:
    return json.dumps({"log": {"entries": [{"request": {"url": u}} for u in urls]}}).encode()


def test_terceiros_sao_dominios_registraveis_sem_repeticao_e_em_ordem():
    saida = _terceiros(
        har(
            "https://exemplo.com.br/",
            "https://cdn.exemplo.com.br/app.js",  # subdomínio do alvo
            "https://www.googletagmanager.com/gtm.js?id=GTM-1",
            "https://stats.g.doubleclick.net/collect",
            "https://fonts.googleapis.com/css",
            "https://www.googletagmanager.com/gtm.js?id=GTM-2",
            "https://WWW.Facebook.com/tr",
        ),
        "exemplo.com.br",
    )
    assert saida == ["doubleclick.net", "facebook.com", "googleapis.com", "googletagmanager.com"]


def test_terceiros_ip_e_nome_sem_sufixo_valem_pelo_proprio_host():
    saida = _terceiros(
        har("http://127.0.0.1:8000/", "http://localhost:8000/x.gif", "http://203.0.113.9/y", "http://[::1]/z"),
        "127.0.0.1",
    )
    assert saida == ["203.0.113.9", "::1", "localhost"]


def test_terceiros_ignora_o_que_nao_e_url_com_host():
    saida = _terceiros(
        har("data:image/png;base64,AAAA", "about:blank", "http://[::1/quebrada", "", "https://cdn.exemplo.org/a"),
        "exemplo.com",
    )
    assert saida == ["exemplo.org"]


def test_terceiros_sem_entradas():
    assert _terceiros(har(), "exemplo.com") == []
    assert _terceiros(b'{"log": {"entries": []}}', "exemplo.com") == []


# ---------------------------------------------------------------------------- escolha dos links

SITE_EXEMPLO = ["http://exemplo.com/"]


def escolher(*hrefs, limite=10, site=SITE_EXEMPLO):
    return _escolher_links(list(hrefs), site, limite)


def test_links_so_do_mesmo_host_com_esquema_http():
    assert escolher(
        "http://exemplo.com/a",
        "https://exemplo.com/b",
        "http://www.exemplo.com/c",  # www é o mesmo site
        "http://blog.exemplo.com/d",  # subdomínio é outro host
        "http://outro.com/e",
        "mailto:suporte@exemplo.com",
        "javascript:void(0)",
        "ftp://exemplo.com/f",
        "tel:+5511999999999",
        "",
    ) == ["http://exemplo.com/a", "https://exemplo.com/b", "http://www.exemplo.com/c"]


@pytest.mark.parametrize(
    "href",
    [
        "http://exemplo.com/kit.zip",
        "http://exemplo.com/Manual.PDF",
        "http://exemplo.com/setup.exe",
        "http://exemplo.com/app.apk",
        "http://exemplo.com/dados.rar",
        "http://exemplo.com/dados.7z",
        "http://exemplo.com/instalador.dmg",
        "http://exemplo.com/instalador.msi",
        "http://exemplo.com/pasta/kit.zip?versao=2",
        "http://exemplo.com/kit.zip#baixar",
    ],
)
def test_links_para_arquivos_ficam_de_fora(href):
    assert escolher(href, "http://exemplo.com/termos") == ["http://exemplo.com/termos"]


def test_links_extensao_no_meio_do_caminho_nao_e_arquivo():
    assert escolher("http://exemplo.com/kit.zip/leia-me", "http://exemplo.com/dados.rarefeito") == [
        "http://exemplo.com/dados.rarefeito",
        "http://exemplo.com/kit.zip/leia-me",
    ]


def test_links_repetidos_depois_de_tirar_o_fragmento():
    assert escolher(
        "http://exemplo.com/planos.html",
        "http://exemplo.com/planos.html#topo",
        "http://exemplo.com/planos.html#fim",
        "http://exemplo.com/outra#topo",
    ) == ["http://exemplo.com/planos.html", "http://exemplo.com/outra"]


def test_link_que_so_difere_pelo_fragmento_sai_sem_o_fragmento():
    assert escolher("http://exemplo.com/planos.html#topo") == ["http://exemplo.com/planos.html"]


def test_a_propria_pagina_inicial_nao_e_subpagina():
    assert escolher(
        "http://exemplo.com/",
        "http://exemplo.com",
        "http://exemplo.com/#topo",
        "https://www.exemplo.com/",
        "http://exemplo.com/termos",
    ) == ["http://exemplo.com/termos"]


def test_pagina_inicial_depois_do_redirect_tambem_conta():
    # a URL inicial foi redirecionada para outra: as duas são "o site" e nenhuma é subpágina
    site = ["http://exemplo.com/", "https://www.exemplo.com/inicio"]
    assert escolher(
        "https://www.exemplo.com/inicio",
        "https://www.exemplo.com/termos",
        "http://exemplo.com/planos",
        site=site,
    ) == ["http://exemplo.com/planos", "https://www.exemplo.com/termos"]


def test_redirect_para_outro_host_leva_o_filtro_junto():
    site = ["http://exemplo.com/", "https://novo-nome.com.br/"]
    assert escolher("https://novo-nome.com.br/termos", "http://exemplo.com/planos", "http://outro.com/x", site=site) == [
        "http://exemplo.com/planos",
        "https://novo-nome.com.br/termos",
    ]


def test_links_de_regras_vem_primeiro_e_o_resto_depois():
    # PRIORIDADE olha o caminho: "contato" e "blog" não casam; "termos", "planos" e "faq" casam
    assert escolher(
        "http://exemplo.com/contato",
        "http://exemplo.com/blog",
        "http://exemplo.com/planos",
        "http://exemplo.com/termos-de-uso",
        "http://exemplo.com/faq",
    ) == [
        "http://exemplo.com/faq",
        "http://exemplo.com/planos",
        "http://exemplo.com/termos-de-uso",
        "http://exemplo.com/blog",
        "http://exemplo.com/contato",
    ]


def test_prioridade_olha_o_caminho_e_nao_o_dominio():
    site = ["http://planofacil.com.br/"]
    assert escolher("http://planofacil.com.br/contato", "http://planofacil.com.br/faq", site=site) == [
        "http://planofacil.com.br/faq",
        "http://planofacil.com.br/contato",
    ]


def test_sem_query_antes_de_com_query_dentro_de_cada_grupo():
    assert escolher(
        "http://exemplo.com/?pagina=termos",  # casa na query, mas depende dela
        "http://exemplo.com/termos/avancado/detalhes",
        "http://exemplo.com/blog/post",
        "http://exemplo.com/blog?id=7",
    ) == [
        "http://exemplo.com/termos/avancado/detalhes",
        "http://exemplo.com/?pagina=termos",
        "http://exemplo.com/blog/post",
        "http://exemplo.com/blog?id=7",
    ]


def test_no_maximo_uma_variante_de_query_por_caminho():
    assert escolher(
        "http://exemplo.com/cadastro?indicacao=user1",
        "http://exemplo.com/cadastro?indicacao=user2",
        "http://exemplo.com/cadastro?indicacao=user3",
        "http://exemplo.com/?ref=a",
        "http://exemplo.com/?ref=b",
        "http://exemplo.com/termos",
    ) == [
        "http://exemplo.com/termos",
        "http://exemplo.com/cadastro?indicacao=user1",  # a primeira do documento
        "http://exemplo.com/?ref=a",
    ]


def test_variante_que_casa_com_a_prioridade_vence_a_que_nao_casa():
    assert escolher("http://exemplo.com/?aba=contato", "http://exemplo.com/?aba=termos") == [
        "http://exemplo.com/?aba=termos"
    ]


def test_a_variante_sem_query_nao_e_substituida_pelas_com_query():
    assert escolher("http://exemplo.com/termos?v=1", "http://exemplo.com/termos", "http://exemplo.com/termos?v=2") == [
        "http://exemplo.com/termos",
        "http://exemplo.com/termos?v=1",
    ]


def test_limite_corta_depois_de_ordenar():
    hrefs = [f"http://exemplo.com/blog/{i}" for i in range(5)] + ["http://exemplo.com/termos"]
    assert escolher(*hrefs, limite=2) == ["http://exemplo.com/termos", "http://exemplo.com/blog/0"]
    assert escolher(*hrefs, limite=0) == []
    assert escolher(*hrefs, limite=-3) == []
    assert len(escolher(*hrefs, limite=100)) == 6


def test_links_invalidos_ou_que_nao_sao_texto_nao_derrubam_a_escolha():
    assert escolher("http://[::1/quebrado", None, 42, ["lista"], "http://exemplo.com:porta/x", "http://exemplo.com/ok") == [
        "http://exemplo.com/ok"
    ]


# ---------------------------------------------------------------------------- navegador: o que guarda


@lento
async def test_captura_prioriza_e_limita(servidor_local, pedidos_locais, tmp_path):
    url = servidor_local + "/index.html"
    r, _ = await capturar(tmp_path, url, max_subpaginas=2)
    assert isinstance(r, Feito)
    urls = [p["url"] for p in r.saidas["paginas"]]
    assert urls[0].endswith("/index.html")
    assert {u.rsplit("/", 1)[1] for u in urls[1:]} == {"termos.html", "planos.html"}
    assert not any("externo" in u or u.endswith(".zip") for u in urls)
    # as duas de regras empatam em profundidade e tamanho: vale a ordem alfabética
    assert urls == [url, servidor_local + "/planos.html", servidor_local + "/termos.html"]
    # o que o navegador pediu de verdade: nada de arquivo, de link externo nem da página que não entrou
    assert sorted(set(caminhos(pedidos_locais))) == ["/index.html", "/planos.html", "/termos.html"]
    assert r.saidas["bloqueada"] is False and r.saidas["falhas"] == []


@lento
async def test_captura_com_o_limite_padrao_deixa_as_paginas_comuns_para_o_fim(
    servidor_local, pedidos_locais, tmp_path
):
    url = servidor_local + "/index.html"
    r, _ = await capturar(tmp_path, url)  # max_subpaginas = 10
    assert [p["url"].rsplit("/", 1)[1] for p in r.saidas["paginas"]] == [
        "index.html",
        "planos.html",
        "termos.html",
        "contato.html",
    ]
    assert "/kit.zip" not in caminhos(pedidos_locais)


@lento
async def test_redirect_da_pagina_inicial_vale_a_url_final(servidor_local, tmp_path):
    r, serv = await capturar(tmp_path, servidor_local + "/inicio", max_subpaginas=1)
    final = servidor_local + "/index.html"
    # a pagina é a do destino, e o link dela para si mesma (index.html) não vira subpágina
    assert [p["url"] for p in r.saidas["paginas"]] == [final, servidor_local + "/planos.html"]
    log = [(e["tipo"], e["origem"]) for e in log_custodia(tmp_path)]
    assert log[0] == ("pagina", final)  # origem = URL da página
    assert log[-1] == ("har", servidor_local + "/inicio")  # o HAR é da execução: a URL que foi aberta


@lento
async def test_max_subpaginas_zero_so_visita_a_pagina_inicial(servidor_local, pedidos_locais, tmp_path):
    r, _ = await capturar(tmp_path, servidor_local + "/index.html", max_subpaginas=0)
    assert len(r.saidas["paginas"]) == 1
    assert set(caminhos(pedidos_locais)) == {"/index.html"}


@lento
async def test_artefatos_na_custodia(servidor_local, tmp_path):
    url = servidor_local + "/planos.html"
    r, serv = await capturar(tmp_path, url, max_subpaginas=0)

    (pagina,) = r.saidas["paginas"]
    assert list(pagina) == ["url", "html", "texto", "screenshot", "har"]
    assert pagina["url"] == url
    assert r.saidas["terceiros"] == [] and r.saidas["bloqueada"] is False

    assert b"Plano Ouro" in serv.custodia.ler(pagina["html"])
    texto = texto_de(serv, pagina)
    assert "Plano Bronze" in texto and "3% ao dia" in texto and "<h2>" not in texto
    assert serv.custodia.ler(pagina["screenshot"]).startswith(PNG)
    entradas_har = json.loads(serv.custodia.ler(pagina["har"]))["log"]["entries"]
    assert [e["request"]["url"] for e in entradas_har] == [url]
    assert "Plano Bronze" in entradas_har[0]["response"]["content"]["text"]  # conteúdo embutido

    # extensão e tipo de cada artefato, sempre com a URL da página como origem
    refs = (pagina["html"], pagina["texto"], pagina["screenshot"], pagina["har"])
    assert [serv.custodia.caminho(ref).suffix for ref in refs] == [".html", ".txt", ".png", ".har"]
    assert [(e["tipo"], e["origem"]) for e in log_custodia(tmp_path)] == [
        ("pagina", url),
        ("texto", url),
        ("screenshot", url),
        ("har", url),
    ]
    assert verificar(tmp_path) == []


@lento
async def test_saidas_sao_json_e_o_har_e_um_so_para_todas_as_paginas(servidor_local, tmp_path):
    r, serv = await capturar(tmp_path, servidor_local + "/index.html", max_subpaginas=2)
    assert json.loads(json.dumps(r.saidas)) == r.saidas  # o motor grava assim em evidencias.json
    paginas = r.saidas["paginas"]
    assert len(paginas) == 3
    assert len({p["har"] for p in paginas}) == 1  # um HAR por execução, a mesma ref em todas
    assert sum(e["tipo"] == "har" for e in log_custodia(tmp_path)) == 1
    pedidas = {e["request"]["url"] for e in json.loads(serv.custodia.ler(paginas[0]["har"]))["log"]["entries"]}
    assert {p["url"] for p in paginas} <= pedidas
    for p in paginas:
        assert set(p) == {"url", "html", "texto", "screenshot", "har"}
        assert all(v.startswith("sha256:") for k, v in p.items() if k != "url")
    assert verificar(tmp_path) == []


@lento
async def test_spa_texto_renderizado(servidor_local, tmp_path):
    assert "rendimento diário" not in (SITE / "spa.html").read_text(encoding="utf-8")  # o HTML cru não tem
    r, serv = await capturar(tmp_path, servidor_local + "/spa.html", max_subpaginas=0)
    (pagina,) = r.saidas["paginas"]
    assert "rendimento diário" in texto_de(serv, pagina)
    assert b"rendimento di" in serv.custodia.ler(pagina["html"])  # e o DOM guardado também
    entradas_har = json.loads(serv.custodia.ler(pagina["har"]))["log"]["entries"]
    assert any(e["request"]["url"].endswith("/spa.json") for e in entradas_har)


@lento
async def test_networkidle_que_nao_chega_nao_derruba_a_captura(servidor_local, tmp_path):
    inicio = time.monotonic()
    r, serv = await capturar(tmp_path, servidor_local + "/ocupada.html", max_subpaginas=0, networkidle_s=1.0)
    assert time.monotonic() - inicio < 20  # o teto de 1 s vale; senão ficaria preso à rede
    (pagina,) = r.saidas["paginas"]
    assert "Cotações atualizadas" in texto_de(serv, pagina)


@lento
async def test_user_agent_da_config(servidor_local, pedidos_locais, tmp_path):
    rede = RedeConfig(ua_navegador="radar-teste/1.0 (config)")
    await capturar(tmp_path, servidor_local + "/index.html", rede=rede, max_subpaginas=1)
    assert len(pedidos_locais) >= 2
    assert {p.user_agent for p in pedidos_locais} == {"radar-teste/1.0 (config)"}


@lento
async def test_opcoes_e_proxy_da_config_chegam_ao_new_context(servidor_local, tmp_path, monkeypatch):
    chamadas = []
    original = Browser.new_context

    async def espiao(self, **kwargs):
        chamadas.append(kwargs)
        return await original(self, **kwargs)

    monkeypatch.setattr(Browser, "new_context", espiao)
    # o Chromium não usa proxy para 127.0.0.1: a página carrega mesmo com este proxy que não existe
    rede = RedeConfig(proxy="http://127.0.0.1:8080")
    r, _ = await capturar(tmp_path, servidor_local + "/planos.html", rede=rede, max_subpaginas=0)
    assert len(r.saidas["paginas"]) == 1
    (kwargs,) = chamadas
    assert kwargs["proxy"] == {"server": "http://127.0.0.1:8080"}
    assert kwargs["accept_downloads"] is False and kwargs["service_workers"] == "block"
    assert kwargs["user_agent"] == UA_NAVEGADOR
    assert kwargs["record_har_content"] == "embed" and kwargs["record_har_path"].endswith(".har")


# ---------------------------------------------------------------------------- navegador: terceiros e falhas


@lento
async def test_terceiros_vem_do_har(servidor_local, tmp_path):
    r, serv = await capturar(tmp_path, servidor_local + "/terceiros.html", max_subpaginas=0)
    # o alvo é 127.0.0.1; o pixel é pedido a "localhost", outro host
    assert r.saidas["terceiros"] == ["localhost"]
    (pagina,) = r.saidas["paginas"]
    urls_do_har = [e["request"]["url"] for e in json.loads(serv.custodia.ler(pagina["har"]))["log"]["entries"]]
    assert any(u.endswith("/pixel.gif") and "localhost" in u for u in urls_do_har)


@lento
async def test_site_sem_recursos_de_fora_nao_tem_terceiros(servidor_local, tmp_path):
    r, _ = await capturar(tmp_path, servidor_local + "/index.html")
    assert r.saidas["terceiros"] == []  # o link para externo.example nunca foi aberto


@lento
async def test_falha_de_subpagina_vai_para_falhas_e_nao_derruba_o_no(servidor_local, pedidos_locais, tmp_path):
    url = servidor_local + "/com_falhas.html"
    r, serv = await capturar(tmp_path, url)
    assert isinstance(r, Feito)
    assert [p["url"] for p in r.saidas["paginas"]] == [url, servidor_local + "/planos.html"]
    falhas = {f["url"]: f["motivo"] for f in r.saidas["falhas"]}
    assert set(falhas) == {servidor_local + "/baixar", "http://127.0.0.1:9/termos"}
    assert all(set(f) == {"url", "motivo"} and f["motivo"] for f in r.saidas["falhas"])
    assert "download" in falhas[servidor_local + "/baixar"].lower()  # o download foi recusado
    assert "\n" not in "".join(falhas.values())  # só a primeira linha da mensagem do Playwright
    assert "/baixar" in caminhos(pedidos_locais)
    # as páginas boas têm tudo, com o mesmo HAR
    assert len({p["har"] for p in r.saidas["paginas"]}) == 1
    assert verificar(tmp_path) == []


@lento
async def test_falha_na_pagina_inicial_vira_erro_nao_permanente(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]  # fecha ao sair: ninguém escuta nessa porta
    with pytest.raises(ErroNo) as e:
        await capturar(tmp_path, f"http://127.0.0.1:{porta}/", max_subpaginas=0)
    assert e.value.permanente is False
    assert e.value.mensagem.startswith("captura falhou: ")
    assert "ERR_CONNECTION_REFUSED" in e.value.mensagem and "\n" not in e.value.mensagem
    assert not (tmp_path / "custodia.log").exists()  # nada foi capturado


@lento
async def test_pagina_inicial_que_nao_responde_estoura_o_timeout_da_pagina(tmp_path):
    with socket.socket() as mudo:  # aceita a conexão (backlog) e nunca responde
        mudo.bind(("127.0.0.1", 0))
        mudo.listen()
        inicio = time.monotonic()
        with pytest.raises(ErroNo) as e:
            await capturar(tmp_path, f"http://127.0.0.1:{mudo.getsockname()[1]}/", timeout_pagina_s=1.0)
    assert time.monotonic() - inicio < 20
    assert e.value.permanente is False
    assert e.value.mensagem.startswith("captura falhou: ") and "Timeout" in e.value.mensagem


@lento
async def test_variantes_de_query_nao_ocupam_os_slots(servidor_local, pedidos_locais, tmp_path):
    url = servidor_local + "/variantes.html"
    r, _ = await capturar(tmp_path, url)
    assert [p["url"][len(servidor_local) :] for p in r.saidas["paginas"]] == [
        "/variantes.html",
        "/termos.html",
        "/cadastro.html?indicacao=user1",  # uma só das três variantes
        "/contato.html",
    ]
    assert not any("user2" in p.caminho or "user3" in p.caminho for p in pedidos_locais)


# ---------------------------------------------------------------------------- navegador: desafio anti-bot


@lento
async def test_desafio_antibot(servidor_local, pedidos_locais, tmp_path):
    url = servidor_local + "/desafio.html"
    r, serv = await capturar(tmp_path, url)
    assert isinstance(r, Feito)
    assert r.saidas["bloqueada"] is True and r.saidas["falhas"] == []
    (pagina,) = r.saidas["paginas"]  # só a página inicial
    assert "texto" not in pagina and "html" not in pagina
    assert set(pagina) == {"url", "screenshot", "har"} and pagina["url"] == url
    assert serv.custodia.ler(pagina["screenshot"]).startswith(PNG)
    assert json.loads(serv.custodia.ler(pagina["har"]))["log"]["entries"]

    # o HTML do desafio vai para a custódia como prova (tipo "desafio"), fora de `paginas`
    log = log_custodia(tmp_path)
    assert sorted(e["tipo"] for e in log) == ["desafio", "har", "screenshot"]
    (desafio,) = (e for e in log if e["tipo"] == "desafio")
    assert desafio["origem"] == url
    html = serv.custodia.ler(f"sha256:{desafio['sha256']}")
    assert b"Just a moment" in html and b"cf-chl" in html
    assert f"sha256:{desafio['sha256']}" not in pagina.values()
    # não segue links: a página liga a /termos.html e o navegador nunca pediu
    assert set(caminhos(pedidos_locais)) == {"/desafio.html"}
    assert verificar(tmp_path) == []


@lento
async def test_desafio_numa_subpagina_vira_falha_e_a_captura_nao_insiste(servidor_local, pedidos_locais, tmp_path):
    url = servidor_local + "/liga_desafio.html"
    r, serv = await capturar(tmp_path, url)
    assert r.saidas["bloqueada"] is False  # a página inicial foi capturada
    assert [p["url"][len(servidor_local) :] for p in r.saidas["paginas"]] == ["/liga_desafio.html", "/termos.html"]
    (falha,) = r.saidas["falhas"]
    assert falha["url"] == servidor_local + "/desafio.html" and "desafio" in falha["motivo"].lower()
    assert "/ocupada.html" not in caminhos(pedidos_locais)  # depois do desafio, para
    assert "Just a moment" not in "".join(texto_de(serv, p) for p in r.saidas["paginas"])
    assert any(e["tipo"] == "desafio" for e in log_custodia(tmp_path))
