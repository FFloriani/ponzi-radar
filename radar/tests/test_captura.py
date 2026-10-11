"""Nó `captura`: visita passiva com o Chromium, artefatos na custódia e detecção de anti-bot (Tarefa 8).

Os testes com `@lento` abrem o Chromium de verdade, só contra 127.0.0.1 (`servidor_local`) ou contra
sockets locais. Rodam na suíte padrão; para pulá-los: `-m "not lento"`.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.async_api import Browser, BrowserType
from playwright.async_api import Error as PlaywrightError

from radar.config import UA_NAVEGADOR, CapturaConfig, Config, RedeConfig
from radar.custodia import Custodia, verificar
from radar.modelos import Contexto, ErroNo, Feito, Pulado
from radar.motor import Servicos
from radar.nos import captura as modulo_captura
from radar.nos.alvo import SERVICOS_DE_ESTACIONAMENTO, SERVICOS_DE_TERCEIROS
from radar.nos.captura import (
    CapturaNo,
    dominios_visitados,
    _bytes,
    _destino_do_redirect,
    _e_desafio,
    _e_erro_http,
    _escolher_links,
    _opcoes_do_contexto,
    _terceiros,
)
from radar.pontuacao import PREFIXO_CAPTURA_INDISPONIVEL, PREFIXO_FALHA_NAVEGACAO

AGORA = datetime(2026, 10, 7, 12, 0, 0)
SITE = Path(__file__).parent / "fixtures" / "site_sintetico"
PNG = b"\x89PNG\r\n\x1a\n"

lento = pytest.mark.lento  # abre o Chromium de verdade: 1 a 3 s cada


def contexto(pasta: Path, url: str, modo_contato: str = "captura", alvo: str = "127.0.0.1") -> Contexto:
    slug = alvo.replace(".", "-")
    return Contexto(
        alvo=alvo,
        slug=slug,
        url_inicial=url,
        as_of=date(2026, 10, 7),
        data_execucao=AGORA,
        modo_contato=modo_contato,
        modo_cego=False,
        run_id=f"{slug}/2026-10-07_120000",
        pasta=pasta,
    )


def entrada_alvo(url: str, alvo: str = "127.0.0.1") -> dict[str, dict]:
    return {"alvo": {"dominio": alvo, "slug": alvo.replace(".", "-"), "url_inicial": url}}


async def capturar(
    pasta: Path,
    url: str,
    *,
    modo_contato: str = "captura",
    rede: RedeConfig | None = None,
    alvo: str = "127.0.0.1",
    **captura,
):
    """Roda o nó e devolve `(resultado, servicos)`.

    A captura não usa a `Rede` (o Playwright tem a pilha de rede própria): `rede=None` faz qualquer
    uso dela falhar o teste.
    """
    config = Config(rede=rede or RedeConfig(), captura=CapturaConfig(**captura))
    serv = Servicos(config=config, rede=None, custodia=Custodia(pasta))
    resultado = await CapturaNo().executar(
        contexto(pasta, url, modo_contato, alvo), entrada_alvo(url, alvo), {}, serv
    )
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
    assert set(no.saidas) == {"paginas", "terceiros", "bloqueada", "falhas", "destino", "redirect_ignorado", "saltos"}


async def test_pulado_sem_contato(tmp_path, monkeypatch):
    def nao_deve_abrir_o_navegador():
        raise AssertionError("modo_contato=nenhum não pode abrir o navegador")

    monkeypatch.setattr(modulo_captura, "async_playwright", nao_deve_abrir_o_navegador)
    resultado, _ = await capturar(tmp_path, "http://127.0.0.1:1/", modo_contato="nenhum")
    assert resultado == Pulado("modo_contato=nenhum")
    assert not (tmp_path / "custodia.log").exists()


# ---------------------------------------------------------------------------- regra do desafio anti-bot

MARCAS = ["cf-chl", "_cf_chl_opt", "cf-turnstile", "challenge-form", "g-recaptcha", "h-captcha"]
STATUS_DE_BLOQUEIO = [403, 429, 503]
LOGIN_COM_RECAPTCHA = '<form><div class="g-recaptcha" data-sitekey="chave"></div><button>Entrar</button></form>'
TEXTO_DO_LOGIN = "Entrar\nE-mail\nSenha\nEsqueci minha senha\nNão tem conta? Cadastre-se"  # 66 caracteres


def html_com(marca: str) -> str:
    return f'<html><body><div class="{marca}"></div></body></html>'


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
@pytest.mark.parametrize("status", [200, 403, None])
def test_titulo_de_desafio_basta_com_qualquer_status_texto_ou_html(titulo, status):
    assert _e_desafio(titulo, "<html><body>nada de especial</body></html>", "x" * 5000, status, {}) is True


@pytest.mark.parametrize(
    "titulo",
    ["", "InvestMax Brasil", "Um momento de atenção", "Verifique seus dados", "Você é humano? Cadastre-se"],
)
def test_titulo_comum_nao_e_desafio(titulo):
    assert _e_desafio(titulo, "<html></html>", "", 403, {}) is False


def test_login_com_recaptcha_e_status_200_nao_e_desafio():
    # o falso positivo medido na revisão: pouco texto + g-recaptcha, mas é uma página de verdade
    assert len(TEXTO_DO_LOGIN) == 66
    assert _e_desafio("Entrar - InvestMax", LOGIN_COM_RECAPTCHA, TEXTO_DO_LOGIN, 200, {}) is False


def test_o_mesmo_login_com_status_403_e_desafio():
    assert _e_desafio("Entrar - InvestMax", LOGIN_COM_RECAPTCHA, TEXTO_DO_LOGIN, 403, {}) is True


@pytest.mark.parametrize("marca", MARCAS)
@pytest.mark.parametrize("status", STATUS_DE_BLOQUEIO)
def test_marca_com_status_de_bloqueio_e_texto_curto_e_desafio(marca, status):
    assert _e_desafio("Entrar", html_com(marca), "Verificando...", status, {}) is True
    assert _e_desafio("Entrar", html_com(marca), "", status, {}) is True


@pytest.mark.parametrize("marca", MARCAS)
@pytest.mark.parametrize("status", [200, 301, 404, 500, None])
def test_marca_sem_sinal_de_bloqueio_nao_e_desafio(marca, status):
    assert _e_desafio("Entrar", html_com(marca), "Verificando...", status, {}) is False


@pytest.mark.parametrize("marca", MARCAS)
def test_marca_com_cf_mitigated_challenge_e_texto_curto_e_desafio(marca):
    # o segundo sinal pode ser o cabeçalho, mesmo com status 200
    assert _e_desafio("Entrar", html_com(marca), "Verificando...", 200, {"cf-mitigated": "challenge"}) is True
    assert _e_desafio("Entrar", html_com(marca), "Verificando...", None, {"cf-mitigated": "challenge"}) is True


@pytest.mark.parametrize(
    "cabecalhos",
    [{"cf-mitigated": "block"}, {"cf-mitigated": ""}, {"cf-ray": "abc"}, {"server": "cloudflare"}, {}],
)
def test_outros_cabecalhos_nao_sao_segundo_sinal(cabecalhos):
    assert _e_desafio("Entrar", html_com("g-recaptcha"), "Verificando...", 200, cabecalhos) is False


def test_cf_mitigated_ignora_caixa_do_nome_e_do_valor():
    assert _e_desafio("Entrar", html_com("cf-chl"), "curto", 200, {"CF-Mitigated": " Challenge "}) is True


def test_challenge_platform_nao_e_mais_marca():
    # aparece em qualquer página atrás da Cloudflare: nem com status de bloqueio nem com texto curto
    html = '<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script>'
    assert _e_desafio("Entrar", html, "Olá", 200, {}) is False
    assert _e_desafio("Entrar", html, "Olá", 403, {}) is False
    assert _e_desafio("Entrar", html, "Olá", 200, {"cf-mitigated": "challenge"}) is False


@pytest.mark.parametrize("marca", MARCAS)
def test_marca_com_status_de_bloqueio_e_texto_longo_nao_e_desafio(marca):
    assert _e_desafio("Entrar", html_com(marca), "a" * 200, 403, {}) is False
    assert _e_desafio("Entrar", html_com(marca), "a" * 5000, 403, {}) is False
    assert _e_desafio("Entrar", html_com(marca), "a" * 5000, 200, {"cf-mitigated": "challenge"}) is False


def test_desafio_fronteira_de_200_caracteres():
    html = html_com("cf-chl")
    assert _e_desafio("Entrar", html, "a" * 199, 403, {}) is True
    assert _e_desafio("Entrar", html, "a" * 200, 403, {}) is False


def test_desafio_espacos_nas_pontas_do_texto_nao_contam():
    assert _e_desafio("Entrar", html_com("g-recaptcha"), "\n\n" + "a" * 150 + "\n" * 100, 403, {}) is True


def test_status_de_bloqueio_sozinho_nao_e_desafio():
    assert _e_desafio("Entrar", "<html><body>Olá</body></html>", "Olá", 403, {}) is False
    assert _e_desafio("Entrar", "<html><body>Olá</body></html>", "Olá", 503, {"cf-mitigated": "challenge"}) is False


def test_marca_em_maiusculas_tambem_vale():
    assert _e_desafio("Entrar", '<div class="G-Recaptcha"></div>', "curto", 403, {}) is True


def test_erro_http_e_status_400_ou_mais():
    assert [_e_erro_http(s) for s in (None, 200, 204, 301, 399, 400, 404, 500, 503)] == [
        False, False, False, False, False, True, True, True, True,
    ]


# ---------------------------------------------------------------------------- opções do contexto


def test_opcoes_do_contexto_sem_proxy(tmp_path):
    opcoes = _opcoes_do_contexto(RedeConfig(), tmp_path / "captura.har")
    # I5: sem `user_agent`: o navegador usa o UA nativo, coerente com o `sec-ch-ua` (o `ua_navegador` é da Rede)
    assert opcoes == {
        "accept_downloads": False,
        "service_workers": "block",
        "record_har_path": str(tmp_path / "captura.har"),
        "record_har_content": "embed",
    }


def test_opcoes_do_contexto_com_proxy(tmp_path):
    rede = RedeConfig(proxy="socks5://127.0.0.1:9050", ua_navegador="radar-teste/1.0")
    opcoes = _opcoes_do_contexto(rede, tmp_path / "captura.har")
    assert opcoes["proxy"] == {"server": "socks5://127.0.0.1:9050"}
    assert "user_agent" not in opcoes
    assert opcoes["accept_downloads"] is False and opcoes["service_workers"] == "block"


def test_o_webrtc_so_sai_pelo_proxy():
    # I5: o UDP do WebRTC não passa pelo proxy HTTP/SOCKS e revelaria o IP do analista a um STUN do site
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in modulo_captura.ARGS_DO_NAVEGADOR
    assert "--webrtc-ip-handling-policy=disable_non_proxied_udp" in modulo_captura.ARGS_DO_NAVEGADOR
    # e nada de esconder a automação: não contornamos anti-bot
    assert not any("AutomationControlled" in a for a in modulo_captura.ARGS_DO_NAVEGADOR)


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("http://127.0.0.1:8000/x", True), ("http://localhost/x", True), ("http://app.localhost/", True),
        ("http://192.168.0.10/", True), ("http://10.0.0.1/", True), ("http://[::1]/", True),
        ("http://169.254.169.254/latest", True), ("http://100.64.0.1/", True),
        ("https://exemplo.com.br/", False), ("http://203.0.113.9/", True), ("http://8.8.8.8/", False),
        ("data:text/plain,x", False), ("about:blank", False),
    ],
)  # fmt: skip
def test_host_local(url, local):
    # 203.0.113.0/24 é de documentação: não é global, conta como local
    assert modulo_captura._endereco_local(url) is local


def test_guarda_so_libera_o_proprio_host_da_url_inicial():
    publico = modulo_captura._Guarda("https://exemplo.com.br/")
    assert publico.permitido("https://cdn.exemplo.com.br/a.js")
    assert not publico.permitido("http://127.0.0.1:8080/admin") and not publico.permitido("http://192.168.0.1/")
    local = modulo_captura._Guarda("http://127.0.0.1:5000/")
    # o site de teste local: o próprio host e o resto do loopback (a mesma máquina) passam; a rede privada não
    assert local.permitido("http://127.0.0.1:9/x") and local.permitido("http://localhost:5000/pixel.gif")
    assert not local.permitido("http://192.168.0.1/")


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
    # googleapis.com é sufixo privado da PSL: o domínio do terceiro é fonts.googleapis.com (C1 da revisão final)
    assert saida == ["doubleclick.net", "facebook.com", "fonts.googleapis.com", "googletagmanager.com"]


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

def escolher(*hrefs, limite=10, inicial="http://exemplo.com/", final=None, alvo="exemplo.com", destino=None):
    """`final` é a URL em que a página inicial terminou depois dos redirects (padrão: a própria inicial); `destino`,
    o domínio registrável dela quando o redirect trocou de domínio (a saída `destino` da captura)."""
    return _escolher_links(list(hrefs), inicial, final or inicial, alvo, limite, destino)


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


def test_pagina_inicial_depois_do_redirect_nao_e_revisitada():
    # a URL inicial foi redirecionada para outra do mesmo site: nenhuma das duas é subpágina
    assert escolher(
        "https://www.exemplo.com/inicio",
        "https://www.exemplo.com/termos",
        "http://exemplo.com/planos",
        final="https://www.exemplo.com/inicio",
    ) == ["http://exemplo.com/planos", "https://www.exemplo.com/termos"]


def test_redirect_para_subdominio_do_alvo_aceita_tambem_o_host_final():
    assert escolher(
        "https://app.exemplo.com/termos",
        "http://exemplo.com/planos",
        "http://outro.com/x",
        final="https://app.exemplo.com/inicio",
    ) == ["https://app.exemplo.com/termos", "http://exemplo.com/planos"]


@pytest.mark.parametrize(
    "final",
    [
        "https://t.me/golpe",
        "https://wa.me/5511999999999",
        "https://www.facebook.com/golpe",
        "https://naoexemplo.com/",  # termina igual ao alvo, mas é outro domínio
        "https://exemplo.com.evil.net/",  # contém o alvo, mas o registrável é outro
    ],
)
def test_redirect_para_outro_dominio_nao_leva_os_links_junto(final):
    # os links da plataforma de destino não são seguidos; só os do host da url_inicial
    host = final.split("/")[2]
    assert escolher(
        f"https://{host}/termos",
        f"https://{host}/outra",
        final,
        "http://exemplo.com/planos",
        final=final,
    ) == ["http://exemplo.com/planos"]


def test_so_a_url_inicial_define_o_host_quando_o_redirect_vai_para_fora():
    assert escolher("https://t.me/termos", final="https://t.me/golpe") == []
    assert escolher("http://exemplo.com/termos", final="https://t.me/golpe") == ["http://exemplo.com/termos"]


# ---------------------------------------------------------------------------- destino depois do redirect


@pytest.mark.parametrize(
    ("final", "dominio"),
    [
        ("https://phinvestimentos.com/login", "phinvestimentos.com"),
        ("https://app.phinvestimentos.com.br/entrar?x=1", "phinvestimentos.com.br"),
        ("http://WWW.Destino.com.br:8080/", "destino.com.br"),
        ("https://golpe.github.io/", "golpe.github.io"),  # sufixo privado da PSL: o site é o perfil, não o github.io
    ],
)
def test_redirect_para_outro_dominio_registravel_vira_destino(final, dominio):
    assert _destino_do_redirect(final, "phinv.link") == ({"url": final, "dominio": dominio}, None)


@pytest.mark.parametrize(
    "final",
    [
        "https://phinv.link/",
        "https://www.phinv.link/login",
        "https://app.PHINV.link/",  # subdomínio do próprio alvo
        "http://127.0.0.1:8080/",  # IP não tem domínio registrável
        "http://[2606:4700::1]/",
        "http://localhost:3000/",
        "http://intranet/",  # nome sem sufixo público
        "about:blank",
        "chrome-error://chromewebdata/",
        "data:text/html,oi",
        "ftp://destino.com.br/",  # só http(s) é página
        "http://[::1",  # URL quebrada
        "",
    ],
)
def test_sem_troca_de_dominio_registravel_nao_ha_destino(final):
    assert _destino_do_redirect(final, "phinv.link") == (None, None)


@pytest.mark.parametrize(
    ("final", "dominio"),
    [
        ("https://t.me/golpe", "t.me"),
        ("https://wa.me/5511999999999", "wa.me"),
        ("https://www.instagram.com/golpe/", "instagram.com"),
        ("https://linktr.ee/golpe", "linktr.ee"),
    ],
)
def test_redirect_para_plataforma_nao_troca_o_alvo(final, dominio):
    assert _destino_do_redirect(final, "phinv.link") == (
        None, {"url": final, "dominio": dominio, "motivo": "plataforma"}
    )  # fmt: skip


@pytest.mark.parametrize(
    ("final", "dominio"),
    [
        ("https://sedoparking.com/frmpark.php?d=phinv.link", "sedoparking.com"),
        ("http://ww1.parkingcrew.net/", "parkingcrew.net"),
        ("https://www.bodis.com/", "bodis.com"),
        ("https://dan.com/buy-domain/phinv.link", "dan.com"),
        ("https://www.afternic.com/forsale/phinv.link", "afternic.com"),
        ("https://www.hugedomains.com/domain_profile.cfm?d=phinv.link", "hugedomains.com"),
        ("http://above.com/", "above.com"),
        ("http://parklogic.com/", "parklogic.com"),
        ("http://undeveloped.com/", "undeveloped.com"),
    ],
)
def test_redirect_para_estacionamento_nao_troca_o_alvo(final, dominio):
    assert _destino_do_redirect(final, "phinv.link") == (
        None, {"url": final, "dominio": dominio, "motivo": "estacionamento"}
    )  # fmt: skip


@pytest.mark.parametrize(
    ("final", "dominio"),
    [
        ("https://apps.apple.com/br/app/golpe/id123", "apple.com"),
        ("https://discord.com/invite/golpe", "discord.com"),
        ("https://discord.gg/golpe", "discord.gg"),
        ("https://pay.hotmart.com/X123", "hotmart.com"),
        ("https://pay.kiwify.com.br/abc", "kiwify.com.br"),
        ("https://sun.eduzz.com/123", "eduzz.com"),
        ("https://app.monetizze.com.br/checkout/X", "monetizze.com.br"),
        ("https://www.mediafire.com/file/x/app.apk", "mediafire.com"),
        ("https://mega.nz/file/abc", "mega.nz"),
        ("https://www.dropbox.com/s/x/contrato.pdf", "dropbox.com"),
    ],
)
def test_redirect_para_servico_de_terceiro_nao_troca_o_alvo(final, dominio):
    # loja de app, comunidade, checkout e hospedagem de arquivo: o domínio é do serviço, não do esquema
    assert _destino_do_redirect(final, "phinv.link") == (
        None, {"url": final, "dominio": dominio, "motivo": "servico_de_terceiro"}
    )  # fmt: skip


def test_servicos_de_terceiros_sao_os_da_lista():
    assert SERVICOS_DE_TERCEIROS == {
        "apple.com", "discord.com", "discord.gg", "hotmart.com", "kiwify.com.br", "eduzz.com", "monetizze.com.br",
        "mediafire.com", "mega.nz", "dropbox.com",
    }  # fmt: skip


def test_servicos_de_estacionamento_sao_os_da_lista():
    assert SERVICOS_DE_ESTACIONAMENTO == {
        "sedoparking.com", "parkingcrew.net", "bodis.com", "dan.com", "afternic.com", "hugedomains.com", "above.com",
        "parklogic.com", "undeveloped.com",
    }  # fmt: skip


def test_com_destino_as_subpaginas_sao_do_host_do_destino():
    escolhidas = escolher(
        "https://phinvestimentos.com/termos",
        "https://www.phinvestimentos.com/planos",  # www é o mesmo site
        "https://app.phinvestimentos.com/regras",  # outro host do destino
        "https://phinv.link/regulamento",  # o redirecionador
        "https://t.me/golpe",
        "https://phinvestimentos.com/login",  # a própria página inicial
        inicial="https://phinv.link/",
        final="https://phinvestimentos.com/login",
        alvo="phinv.link",
        destino="phinvestimentos.com",
    )
    assert sorted(escolhidas) == ["https://phinvestimentos.com/termos", "https://www.phinvestimentos.com/planos"]


def test_com_destino_num_subdominio_as_subpaginas_sao_desse_host():
    assert escolher(
        "https://app.destino.com.br/termos",
        "https://destino.com.br/planos",
        "https://exemplo.com/faq",
        final="https://app.destino.com.br/entrar",
        destino="destino.com.br",
    ) == ["https://app.destino.com.br/termos"]


def test_terceiros_excluem_o_alvo_e_o_destino():
    har = {"log": {"entries": [
        {"request": {"url": "https://phinv.link/"}},
        {"request": {"url": "https://phinvestimentos.com/login"}},
        {"request": {"url": "https://cdn.phinvestimentos.com/app.js"}},
        {"request": {"url": "https://www.googletagmanager.com/gtm.js"}},
    ]}}  # fmt: skip
    dados = json.dumps(har).encode()
    assert _terceiros(dados, "phinv.link", "phinvestimentos.com") == ["googletagmanager.com"]
    assert _terceiros(dados, "phinv.link") == ["googletagmanager.com", "phinvestimentos.com"]


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
    inicial = "http://planofacil.com.br/"
    assert escolher(
        "http://planofacil.com.br/contato", "http://planofacil.com.br/faq", inicial=inicial, alvo="planofacil.com.br"
    ) == [
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
    assert list(pagina) == ["url", "status", "html", "texto", "screenshot", "har"]
    assert pagina["url"] == url and pagina["status"] == 200
    assert r.saidas["terceiros"] == [] and r.saidas["bloqueada"] is False

    assert b"Plano Ouro" in serv.custodia.ler(pagina["html"])
    texto = texto_de(serv, pagina)
    assert "Plano Bronze" in texto and "1,5% ao dia" in texto and "<h2>" not in texto
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
        assert set(p) == {"url", "status", "html", "texto", "screenshot", "har"} and p["status"] == 200
        assert all(v.startswith("sha256:") for k, v in p.items() if k not in ("url", "status"))
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
async def test_navegador_usa_o_proprio_user_agent(servidor_local, pedidos_locais, tmp_path):
    # I5: o UA do contexto mentiria a versão que o `sec-ch-ua` conta; o `ua_navegador` da config fica só para a Rede
    rede = RedeConfig(ua_navegador="radar-teste/1.0 (config)")
    await capturar(tmp_path, servidor_local + "/index.html", rede=rede, max_subpaginas=1)
    assert len(pedidos_locais) >= 2
    (ua,) = {p.user_agent for p in pedidos_locais}
    assert "Chrome/" in ua and "radar-teste" not in ua and ua != UA_NAVEGADOR


@lento
async def test_opcoes_do_contexto_chegam_ao_new_context(servidor_local, tmp_path, monkeypatch):
    chamadas = []
    original = Browser.new_context

    async def espiao(self, **kwargs):
        chamadas.append(kwargs)
        return await original(self, **kwargs)

    monkeypatch.setattr(Browser, "new_context", espiao)
    r, _ = await capturar(tmp_path, servidor_local + "/planos.html", max_subpaginas=0)
    assert len(r.saidas["paginas"]) == 1
    (kwargs,) = chamadas
    assert "proxy" not in kwargs  # sem proxy na config, conexão direta
    assert kwargs["accept_downloads"] is False and kwargs["service_workers"] == "block"
    assert "user_agent" not in kwargs
    assert kwargs["record_har_content"] == "embed" and kwargs["record_har_path"].endswith(".har")


@lento
async def test_proxy_da_config_e_usado_pelo_navegador(proxy_local, tmp_path):
    # o Chromium manda até as requisições de 127.0.0.1 pelo proxy do contexto: este proxy responde por
    # um site que não existe, então a página só pode ter vindo dele
    rede = RedeConfig(proxy=f"http://127.0.0.1:{proxy_local.server_port}")
    url = "http://alvo-atras-do-proxy.test/index.html"
    r, serv = await capturar(tmp_path, url, rede=rede, max_subpaginas=0)
    (pagina,) = r.saidas["paginas"]
    assert pagina["url"] == url
    assert "Conteúdo servido pelo proxy" in texto_de(serv, pagina)
    assert proxy_local.requisicoes == [url]
    # R4: o documento sai pela pilha do Chromium, como GET absoluto; nada de túnel CONNECT para http
    assert proxy_local.tuneis == []


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
    # falha de alcance do site: a forma que o E6 conta (I2)
    assert e.value.mensagem == "captura falhou: navegação: net::ERR_CONNECTION_REFUSED"
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
    assert e.value.mensagem == "captura falhou: navegação: timeout"


@lento
async def test_proxy_fora_do_ar_e_falha_do_analista_nao_do_site(tmp_path):
    # I2: o proxy (ou o Tor) do analista caído não diz nada do site
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]  # ninguém escuta: o proxy está fora
    rede = RedeConfig(proxy=f"http://127.0.0.1:{porta}")
    with pytest.raises(ErroNo) as e:
        await capturar(tmp_path, "http://alvo-atras-do-proxy.test/", rede=rede, max_subpaginas=0)
    assert e.value.permanente is False
    assert e.value.mensagem.startswith("captura indisponível: ") and "ERR_PROXY_CONNECTION_FAILED" in e.value.mensagem
    assert "\n" not in e.value.mensagem


MENSAGEM_NAVEGADOR_AUSENTE = (
    'captura indisponível: navegador do Playwright não encontrado; rode "playwright install chromium" no venv do '
    "radar ou confira PLAYWRIGHT_BROWSERS_PATH no ambiente do servidor MCP"
)
# o que o Playwright 1.63 devolve quando o Chromium não está onde procura (o caminho e o aviso mudam, a 1ª linha não)
ERRO_DO_PLAYWRIGHT_SEM_NAVEGADOR = (
    "BrowserType.launch: Executable doesn't exist at C:\\Users\\Analista\\AppData\\Local\\ms-playwright\\"
    "chromium_headless_shell-1200\\chrome-headless-shell-win64\\chrome-headless-shell.exe\n"
    "╔════════════════════════════════════════════════════════════╗\n"
    "║ Looks like Playwright was just installed or updated.       ║\n"
    "║ Please run the following command to download new browsers: ║\n"
    "║     playwright install                                     ║\n"
    "╚════════════════════════════════════════════════════════════╝"
)


async def test_navegador_que_nao_inicia_e_captura_indisponivel(tmp_path, monkeypatch):
    # o Chromium não instalado (depois de um `pip install -U playwright`) não pode virar "site fora do ar"
    async def sem_navegador(self, **kwargs):
        raise PlaywrightError(ERRO_DO_PLAYWRIGHT_SEM_NAVEGADOR)

    monkeypatch.setattr(BrowserType, "launch", sem_navegador)
    with pytest.raises(ErroNo) as e:
        await capturar(tmp_path, "https://exemplo.com.br/", max_subpaginas=0)
    assert e.value.permanente is False
    assert e.value.mensagem == MENSAGEM_NAVEGADOR_AUSENTE


@pytest.mark.parametrize(
    "mensagem",
    [
        ERRO_DO_PLAYWRIGHT_SEM_NAVEGADOR,
        "BrowserType.launch: Executable doesn't exist at /ms-playwright/chromium",
        "BrowserType.launch: Executable doesn't exist at /ms-playwright/chromium\nlog",
        "BrowserType.launch_persistent_context: Executable doesn't exist at /ms-playwright/chromium",
    ],
)
def test_navegador_ausente_tem_mensagem_propria_sem_o_caminho_e_sem_quebra_de_linha(mensagem):
    erro = modulo_captura._erro_da_captura(PlaywrightError(mensagem))
    assert (erro.mensagem, erro.permanente) == (MENSAGEM_NAVEGADOR_AUSENTE, False)
    assert "\n" not in erro.mensagem and "ms-playwright" not in erro.mensagem and "Analista" not in erro.mensagem
    # continua sendo falha do lado do analista: o prefixo é o que o E6 e o dossiê (lacunas) reconhecem
    assert erro.mensagem.startswith(PREFIXO_CAPTURA_INDISPONIVEL)
    assert not erro.mensagem.startswith(PREFIXO_FALHA_NAVEGACAO)


@pytest.mark.parametrize(
    "erro",
    [
        PlaywrightError("BrowserType.launch: Timeout 180000ms exceeded."),
        PlaywrightError("BrowserType.launch: Browser closed unexpectedly\nlog"),
        PlaywrightError("Page.goto: net::ERR_PROXY_CONNECTION_FAILED at https://x.com.br/"),
        ValueError("Executable doesn't exist"),
        # o texto vem do site investigado: uma URL que o repita, no erro de navegação, não é navegador ausente
        modulo_captura._FalhaDeNavegacao(
            PlaywrightError("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://x.com.br/Executable doesn't exist")
        ),
        PlaywrightError("Page.screenshot: falhou em https://x.com.br/Executable doesn't exist at /x"),
    ],
)
def test_outras_falhas_nao_viram_navegador_ausente(erro):
    assert modulo_captura._erro_da_captura(erro).mensagem != MENSAGEM_NAVEGADOR_AUSENTE


@lento
async def test_erro_inesperado_na_captura_e_captura_indisponivel(servidor_local, tmp_path, monkeypatch):
    def quebra(har, dominio):
        raise ValueError("HAR ilegível")

    monkeypatch.setattr(modulo_captura, "_terceiros", quebra)
    with pytest.raises(ErroNo) as e:
        await capturar(tmp_path, servidor_local + "/index.html", max_subpaginas=0)
    assert e.value.mensagem == "captura indisponível: ValueError: HAR ilegível"


_NAVEGACAO = "captura falhou: navegação: net::"
_LOCAL = "captura indisponível: Page.goto: net::"


@pytest.mark.parametrize(
    "codigo,esperado",
    [
        ("ERR_NAME_NOT_RESOLVED", _NAVEGACAO + "ERR_NAME_NOT_RESOLVED"),
        ("ERR_CONNECTION_REFUSED", _NAVEGACAO + "ERR_CONNECTION_REFUSED"),
        ("ERR_CONNECTION_RESET", _NAVEGACAO + "ERR_CONNECTION_RESET"),
        ("ERR_CONNECTION_CLOSED", _NAVEGACAO + "ERR_CONNECTION_CLOSED"),
        ("ERR_CONNECTION_TIMED_OUT", _NAVEGACAO + "ERR_CONNECTION_TIMED_OUT"),
        ("ERR_ADDRESS_UNREACHABLE", _NAVEGACAO + "ERR_ADDRESS_UNREACHABLE"),
        ("ERR_TIMED_OUT", _NAVEGACAO + "ERR_TIMED_OUT"),
        ("ERR_PROXY_CONNECTION_FAILED", _LOCAL + "ERR_PROXY_CONNECTION_FAILED at https://x.com.br/"),
        ("ERR_TUNNEL_CONNECTION_FAILED", _LOCAL + "ERR_TUNNEL_CONNECTION_FAILED at https://x.com.br/"),
        ("ERR_CERT_AUTHORITY_INVALID", _LOCAL + "ERR_CERT_AUTHORITY_INVALID at https://x.com.br/"),
        ("ERR_INTERNET_DISCONNECTED", _LOCAL + "ERR_INTERNET_DISCONNECTED at https://x.com.br/"),
        ("ERR_SSL_PROTOCOL_ERROR", _LOCAL + "ERR_SSL_PROTOCOL_ERROR at https://x.com.br/"),
    ],
)
def test_classificacao_da_falha_de_navegacao(codigo, esperado):
    mensagem = f"Page.goto: net::{codigo} at https://x.com.br/"
    erro = modulo_captura._erro_da_captura(modulo_captura._FalhaDeNavegacao(PlaywrightError(mensagem)))
    assert (erro.mensagem, erro.permanente) == (esperado, False)
    # a mesma mensagem fora do `goto` (screenshot, conteúdo) é do lado do analista
    fora = modulo_captura._erro_da_captura(PlaywrightError(mensagem))
    assert fora.mensagem == f"captura indisponível: {mensagem}"


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
    assert set(pagina) == {"url", "status", "screenshot", "har"} and pagina["url"] == url
    assert pagina["status"] == 200  # o título da verificação basta: vale com qualquer status
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


@lento
async def test_login_com_recaptcha_e_status_200_nao_e_desafio(servidor_local, pedidos_locais, tmp_path):
    # R-T8-desafio: pouco texto + g-recaptcha, mas o servidor respondeu 200: é a página de verdade
    url = servidor_local + "/login.html"
    r, serv = await capturar(tmp_path, url)
    assert r.saidas["bloqueada"] is False and r.saidas["falhas"] == []
    paginas = r.saidas["paginas"]
    # e a captura segue os links dela (regras primeiro)
    assert [p["url"][len(servidor_local) :] for p in paginas] == ["/login.html", "/termos.html", "/cadastro.html"]
    assert [p["status"] for p in paginas] == [200, 200, 200]
    assert "Esqueci minha senha" in texto_de(serv, paginas[0]) and len(texto_de(serv, paginas[0])) < 200
    assert b"g-recaptcha" in serv.custodia.ler(paginas[0]["html"])
    assert not any(e["tipo"] == "desafio" for e in log_custodia(tmp_path))


@lento
async def test_o_mesmo_login_com_status_403_e_desafio(servidor_local, pedidos_locais, tmp_path):
    url = servidor_local + "/status/403/login.html"
    r, serv = await capturar(tmp_path, url)
    assert r.saidas["bloqueada"] is True and r.saidas["falhas"] == []
    (pagina,) = r.saidas["paginas"]
    assert set(pagina) == {"url", "status", "screenshot", "har"}
    assert (pagina["url"], pagina["status"]) == (url, 403)
    (desafio,) = (e for e in log_custodia(tmp_path) if e["tipo"] == "desafio")
    assert b"g-recaptcha" in serv.custodia.ler(f"sha256:{desafio['sha256']}")
    assert caminhos(pedidos_locais) == ["/status/403/login.html"]  # não seguiu os links


@lento
async def test_login_com_cabecalho_cf_mitigated_challenge_e_desafio(servidor_local, pedidos_locais, tmp_path):
    # o servidor respondeu 200, mas avisou que a resposta foi um desafio
    url = servidor_local + "/mitigado/login.html"
    r, _ = await capturar(tmp_path, url)
    assert r.saidas["bloqueada"] is True
    (pagina,) = r.saidas["paginas"]
    assert (pagina["url"], pagina["status"]) == (url, 200)
    assert caminhos(pedidos_locais) == ["/mitigado/login.html"]


@lento
@pytest.mark.parametrize("status", [403, 404, 429, 500, 503])
async def test_home_com_erro_http_vira_erro_do_no_com_o_html_como_prova(servidor_local, tmp_path, status):
    # R-T8-status: sem título nem marca de desafio, a página de erro não é conteúdo do site
    url = f"{servidor_local}/status/{status}"
    with pytest.raises(ErroNo) as e:
        await capturar(tmp_path, url)
    assert e.value.mensagem == f"captura falhou: HTTP {status}" and e.value.permanente is False
    (registro,) = log_custodia(tmp_path)  # só o HTML da página de erro: sem texto, screenshot nem HAR
    assert (registro["tipo"], registro["origem"]) == ("pagina", url)
    assert "Página de erro do servidor".encode() in Custodia(tmp_path).ler(f"sha256:{registro['sha256']}")


@lento
async def test_subpagina_com_erro_http_vai_para_falhas(servidor_local, tmp_path):
    r, serv = await capturar(tmp_path, servidor_local + "/liga_status.html")
    paginas = r.saidas["paginas"]
    assert [p["url"][len(servidor_local) :] for p in paginas] == ["/liga_status.html", "/termos.html"]
    assert [p["status"] for p in paginas] == [200, 200]
    assert r.saidas["falhas"] == [{"url": servidor_local + "/status/500", "motivo": "HTTP 500"}]
    assert not any(e["origem"].endswith("/status/500") for e in log_custodia(tmp_path))  # a página de erro não vira prova
    assert r.saidas["bloqueada"] is False
    assert verificar(tmp_path) == []


@lento
async def test_redirect_para_outro_dominio_nao_rastreia_o_destino(servidor_local, pedidos_locais, tmp_path):
    # "/saida" manda de 127.0.0.1 para localhost (outro host, outro domínio): como um golpe que redireciona
    # para o Telegram. O alvo é 127.0.0.1, então os links do destino não são seguidos.
    r, _ = await capturar(tmp_path, servidor_local + "/saida")
    (pagina,) = r.saidas["paginas"]
    assert pagina["url"] == servidor_local.replace("127.0.0.1", "localhost") + "/index.html"
    assert r.saidas["falhas"] == []
    assert caminhos(pedidos_locais) == ["/saida", "/index.html"]  # nem termos.html nem planos.html
    assert r.saidas["terceiros"] == ["localhost"]
    # localhost não tem domínio registrável: não é destino, e não há o que ignorar
    assert (r.saidas["destino"], r.saidas["redirect_ignorado"]) == (None, None)


# Dois nomes locais (o Chromium resolve os dois para 127.0.0.1 com `--host-resolver-rules`): o alvo só redireciona
# para a página de entrada do destino, que é o site sintético
ALVO_LOCAL = "alvo-sintetico.com.br"
DESTINO_LOCAL = "destino-sintetico.com.br"


class _DoisNomes(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        host = (self.headers.get("Host") or "").rpartition(":")[0]
        self.server.pedidos.append((host, self.path))
        if host == ALVO_LOCAL:
            self.send_response(302)
            self.send_header("Location", f"http://{DESTINO_LOCAL}:{self.server.server_port}/index.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *a) -> None:
        pass


@contextmanager
def _alvo_que_redireciona(monkeypatch):
    regras = f"--host-resolver-rules=MAP {ALVO_LOCAL} 127.0.0.1, MAP {DESTINO_LOCAL} 127.0.0.1"
    monkeypatch.setattr(modulo_captura, "ARGS_DO_NAVEGADOR", (*modulo_captura.ARGS_DO_NAVEGADOR, regras))
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), partial(_DoisNomes, directory=str(SITE)))
    servidor.daemon_threads = True
    servidor.pedidos = []
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        yield servidor
    finally:
        servidor.shutdown()
        servidor.server_close()


@lento
async def test_redirect_para_outro_dominio_captura_as_subpaginas_do_destino(tmp_path, monkeypatch):
    with _alvo_que_redireciona(monkeypatch) as servidor:
        porta = servidor.server_port
        r, serv = await capturar(tmp_path, f"http://{ALVO_LOCAL}:{porta}/", alvo=ALVO_LOCAL, max_subpaginas=2)
    destino = f"http://{DESTINO_LOCAL}:{porta}"
    assert r.saidas["destino"] == {"url": f"{destino}/index.html", "dominio": DESTINO_LOCAL}
    assert r.saidas["redirect_ignorado"] is None
    assert [p["url"] for p in r.saidas["paginas"]] == [
        f"{destino}/index.html", f"{destino}/planos.html", f"{destino}/termos.html"
    ]  # fmt: skip
    # o alvo recebeu só a visita inicial; as subpáginas foram pedidas ao destino
    assert sorted(set(servidor.pedidos)) == [
        (ALVO_LOCAL, "/"), (DESTINO_LOCAL, "/index.html"), (DESTINO_LOCAL, "/planos.html"),
        (DESTINO_LOCAL, "/termos.html"),
    ]  # fmt: skip
    # o alvo e o destino são o site: nenhum dos dois é terceiro
    assert r.saidas["terceiros"] == []
    assert r.saidas["falhas"] == [] and r.saidas["bloqueada"] is False
    assert verificar(tmp_path) == []


# Três nomes locais: o alvo redireciona para um rastreador, que redireciona para o destino (F1 da revisão final)
TRK_LOCAL = "trk-sintetico.net"


class _TresNomes(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        host = (self.headers.get("Host") or "").rpartition(":")[0]
        self.server.pedidos.append((host, self.path))
        saltos = {
            ALVO_LOCAL: f"http://{TRK_LOCAL}:{self.server.server_port}/r?c=1",
            TRK_LOCAL: f"http://{DESTINO_LOCAL}:{self.server.server_port}/index.html",
        }
        if host in saltos:
            self.send_response(302)
            self.send_header("Location", saltos[host])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *a) -> None:
        pass


@lento
async def test_redirect_em_varios_saltos_grava_a_cadeia_da_pagina_inicial(tmp_path, monkeypatch):
    regras = f"--host-resolver-rules=MAP {ALVO_LOCAL} 127.0.0.1, MAP {TRK_LOCAL} 127.0.0.1, MAP {DESTINO_LOCAL} 127.0.0.1"
    monkeypatch.setattr(modulo_captura, "ARGS_DO_NAVEGADOR", (*modulo_captura.ARGS_DO_NAVEGADOR, regras))
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), partial(_TresNomes, directory=str(SITE)))
    servidor.daemon_threads = True
    servidor.pedidos = []
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        porta = servidor.server_port
        r, _ = await capturar(tmp_path, f"http://{ALVO_LOCAL}:{porta}/", alvo=ALVO_LOCAL, max_subpaginas=0)
    finally:
        servidor.shutdown()
        servidor.server_close()
    # a cadeia, na ordem e sem a URL final; o destino é o do fim dela
    assert r.saidas["saltos"] == [f"http://{ALVO_LOCAL}:{porta}/", f"http://{TRK_LOCAL}:{porta}/r?c=1"]
    assert r.saidas["destino"] == {"url": f"http://{DESTINO_LOCAL}:{porta}/index.html", "dominio": DESTINO_LOCAL}
    # o rastreador e o destino são o site; o alvo já é recusado pelo `ctx.alvo`
    assert dominios_visitados(r.saidas, ALVO_LOCAL) == {TRK_LOCAL, DESTINO_LOCAL}


@lento
async def test_sem_redirect_nao_ha_saltos(servidor_local, tmp_path):
    r, _ = await capturar(tmp_path, servidor_local + "/index.html", max_subpaginas=0)
    assert r.saidas["saltos"] == []


@lento
async def test_redirect_no_mesmo_host_tambem_e_salto(servidor_local, tmp_path):
    r, _ = await capturar(tmp_path, servidor_local + "/inicio", max_subpaginas=0)
    assert r.saidas["saltos"] == [servidor_local + "/inicio"]


def test_dominios_visitados_pela_pagina_inicial_e_pelos_saltos():
    captura = {
        "paginas": [
            {"url": "https://phinvestimentos.com/login"},  # a página inicial, onde ela terminou
            {"url": "https://www.phinvestimentos.com/planos"},
            {"url": "https://www.reclameaqui.com.br/empresa/ph/"},  # uma subpágina que redirecionou para fora
        ],
        "saltos": ["https://phinv.link/", "https://trk.example.net/c?id=1", "https://sedoparking.com/x"],
    }
    assert dominios_visitados(captura, "phinv.link") == {"phinvestimentos.com", "example.net"}


def test_subpagina_que_redireciona_para_um_terceiro_nao_o_torna_o_site():
    # N1 da re-revisão final (ruling R-A-F-n1): `/reclamacoes` que vai para o Reclame Aqui não faz o Reclame Aqui ser
    # recusado como fonte; só a página inicial e a cadeia de redirect dela dizem onde o site está
    captura = {
        "paginas": [
            {"url": "https://exemplo.com.br/"},
            {"url": "https://www.reclameaqui.com.br/empresa/exemplo/"},
            {"url": "https://g1.globo.com/economia/noticia/golpe.ghtml"},
            {"url": "https://medium.com/@exemplo/blog"},
        ],
        "saltos": [],
    }
    assert dominios_visitados(captura, "exemplo.com.br") == set()
    # a página inicial que terminou fora do alvo continua contando, como na execução gravada antes do nó `destino`
    inicial_fora = {**captura, "paginas": [{"url": "https://phinvestimentos.com/login"}, *captura["paginas"][1:]]}
    assert dominios_visitados(inicial_fora, "exemplo.com.br") == {"phinvestimentos.com"}


@pytest.mark.parametrize(
    "captura",
    [
        None,
        {},
        {"paginas": None, "saltos": None},
        {"paginas": [None, 7, {"url": None}, {"url": "não é url"}, {"url": "http://[::1"}], "saltos": [None, 3, ""]},
        {"paginas": [{"url": "https://exemplo.com.br/"}, {"url": "http://127.0.0.1:8080/"}]},  # o alvo e um IP
    ],
)
def test_dominios_visitados_de_captura_estranha_ou_antiga(captura):
    assert dominios_visitados(captura, "exemplo.com.br") == set()


def test_dominios_visitados_de_captura_antiga_sem_saltos():
    # a captura gravada antes da T1 não tem `destino` nem `saltos`, mas a página dela já é do site para onde o alvo foi
    assert dominios_visitados({"paginas": [{"url": "https://phinvestimentos.com/login"}]}, "phinv.link") == {
        "phinvestimentos.com"
    }


def _visita(url: str, links: list[str] | None = None) -> modulo_captura._Visita:
    return modulo_captura._Visita(url, 200, {}, "pagina", "<html>x</html>", "texto da pagina", PNG, links or [])


@lento
@pytest.mark.parametrize(
    ("final", "dominio", "motivo"),
    [
        ("https://t.me/golpe_oficial", "t.me", "plataforma"),
        ("https://www.instagram.com/golpe/", "instagram.com", "plataforma"),
        ("https://sedoparking.com/frmpark.php?d=exemplo.com.br", "sedoparking.com", "estacionamento"),
        ("http://ww1.parkingcrew.net/", "parkingcrew.net", "estacionamento"),
        ("https://pay.hotmart.com/X123", "hotmart.com", "servico_de_terceiro"),
    ],
)
async def test_redirect_para_plataforma_ou_estacionamento_mantem_o_alvo(tmp_path, monkeypatch, final, dominio, motivo):
    host = final.split("/")[2]
    visitadas = []

    async def visitar(contexto, url, cfg, com_links, guarda):
        visitadas.append(url)
        if url == "https://exemplo.com.br/":
            return _visita(final, [f"https://{host}/termos", "https://exemplo.com.br/planos"])
        return _visita(url)

    monkeypatch.setattr(modulo_captura, "_visitar", visitar)
    r, _ = await capturar(tmp_path, "https://exemplo.com.br/", alvo="exemplo.com.br", max_subpaginas=5)
    assert r.saidas["destino"] is None
    assert r.saidas["redirect_ignorado"] == {"url": final, "dominio": dominio, "motivo": motivo}
    assert r.saidas["saltos"] == []  # o `_visitar` trocado não informa a cadeia
    # a plataforma e o estacionamento não são rastreados: só os links do alvo
    assert visitadas == ["https://exemplo.com.br/", "https://exemplo.com.br/planos"]


@lento
async def test_destino_tambem_vale_quando_a_pagina_do_destino_e_um_desafio(tmp_path, monkeypatch):
    async def visitar(contexto, url, cfg, com_links, guarda):
        return modulo_captura._Visita(
            "https://phinvestimentos.com/login", 403, {}, "Just a moment...", "<html>cf-chl</html>", "", PNG, [],
            ["https://phinv.link/", "https://trk.example.net/c"],
        )

    monkeypatch.setattr(modulo_captura, "_visitar", visitar)
    r, _ = await capturar(tmp_path, "https://phinv.link/", alvo="phinv.link")
    assert r.saidas["bloqueada"] is True
    # o redirect foi visto antes do desafio: o Wayback e os coletores olham o destino
    assert r.saidas["destino"] == {"url": "https://phinvestimentos.com/login", "dominio": "phinvestimentos.com"}
    assert r.saidas["redirect_ignorado"] is None
    assert r.saidas["saltos"] == ["https://phinv.link/", "https://trk.example.net/c"]  # a cadeia vale no desafio


# ---------------------------------------------------------------------------- opsec da captura (I5)


@lento
async def test_com_proxy_o_rtcpeerconnection_nao_existe(proxy_local, tmp_path):
    rede = RedeConfig(proxy=f"http://127.0.0.1:{proxy_local.server_port}")
    r, serv = await capturar(tmp_path, "http://alvo-atras-do-proxy.test/webrtc.html", rede=rede, max_subpaginas=0)
    (pagina,) = r.saidas["paginas"]
    assert "webrtc:undefined" in texto_de(serv, pagina)


@lento
async def test_sem_proxy_o_webrtc_fica_com_a_politica_do_navegador(servidor_local, tmp_path):
    # sem proxy não há IP a esconder: a página continua como um navegador comum a veria
    r, serv = await capturar(tmp_path, servidor_local + "/webrtc.html", max_subpaginas=0)
    (pagina,) = r.saidas["paginas"]
    assert "webrtc:function" in texto_de(serv, pagina)


@lento
async def test_navegador_sobe_com_a_politica_de_webrtc(servidor_local, tmp_path, monkeypatch):
    chamadas = []
    original = BrowserType.launch

    async def espiao(self, **kwargs):
        chamadas.append(kwargs)
        return await original(self, **kwargs)

    monkeypatch.setattr(BrowserType, "launch", espiao)
    await capturar(tmp_path, servidor_local + "/index.html", max_subpaginas=0)
    (kwargs,) = chamadas
    assert list(kwargs["args"]) == list(modulo_captura.ARGS_DO_NAVEGADOR)


# ---------------------------------------------------------------------------- endereços locais e popups


@lento
async def test_site_nao_alcanca_enderecos_locais_do_analista(proxy_local, tmp_path):
    # o site (público, atrás do proxy) pede recursos de 127.0.0.1, localhost e da rede privada: nenhum sai
    rede = RedeConfig(proxy=f"http://127.0.0.1:{proxy_local.server_port}")
    url = "http://alvo-atras-do-proxy.test/com_locais.html"
    r, serv = await capturar(tmp_path, url, rede=rede, max_subpaginas=0)
    assert "Página com recursos locais" in texto_de(serv, r.saidas["paginas"][0])
    assert proxy_local.requisicoes == [url]


@lento
async def test_popup_aberto_pelo_site_nao_navega(servidor_local, pedidos_locais, tmp_path):
    r, _ = await capturar(tmp_path, servidor_local + "/popup.html", max_subpaginas=0)
    assert len(r.saidas["paginas"]) == 1
    assert caminhos(pedidos_locais) == ["/popup.html"]  # o /planos.html?popup=1 nunca foi pedido


# ---------------------------------------------------------------------------- redirect para endereço local (R4)


def _ip_da_lan() -> str:
    """Um IPv4 da máquina que não é loopback: o "site" do teste precisa estar fora do loopback, senão a exceção do
    site de teste local libera o 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))  # UDP: nada sai, só escolhe a interface
            ip = s.getsockname()[0]
        except OSError:
            ip = "127.0.0.1"
    if ip.startswith("127."):
        pytest.skip("sem endereço IPv4 fora do loopback")
    return ip


class _ServicoLocal(ThreadingHTTPServer):
    """Um serviço do analista (em 127.0.0.1, ou no `host` dado): guarda cada pedido que recebe."""

    daemon_threads = True

    def __init__(self, host: str = "127.0.0.1") -> None:
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                servidor.pedidos.append(self.path)
                corpo = b"<html><body>servico local do analista</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *a) -> None:
                pass

        super().__init__((host, 0), Handler)
        self.pedidos: list[str] = []


def _resposta(handler: BaseHTTPRequestHandler, status: int, corpo: bytes = b"", local: str | None = None) -> None:
    handler.send_response(status)
    if local:
        handler.send_header("Location", local)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(corpo)))
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.wfile.write(corpo)


_JS_PARA_O_SALTO = "<script>setTimeout(() => { location.href = '/2saltos-b'; }, 50);</script>"


def _pagina_do_site(caminho: str, local: str, porta_ws: int, porta: int = 0) -> tuple[int, bytes, str | None]:
    """O site hostil (`local` é o serviço do analista; `porta`, a do próprio site):

    - `/` e `/redir`: 302 para o serviço local; `/2saltos`: 302 para o próprio site, e de lá (`/2saltos-b`) para ele;
    - `/home`: link para a `/2saltos` (a subpágina); `/js`: a página navega sozinha para a `/2saltos-b`;
    - `/ws`: um WebSocket para o loopback; `/iframe`: um iframe de outro site (`localhost`) com a `/pagina`;
    - o resto (`/pagina`): uma imagem que redireciona para o serviço local.
    """
    if caminho in ("/", "/redir"):
        return 302, b"", f"{local}/segredo"
    if caminho == "/2saltos":
        return 302, b"", "/2saltos-b"
    if caminho == "/2saltos-b":
        return 302, b"", f"{local}/segredo-2saltos"
    if caminho.endswith("/img-redir"):
        return 302, b"", f"{local}/img"
    if caminho == "/home":
        return 200, b"<html><body><p>home publica</p><a href='/2saltos'>regras</a></body></html>", None
    if caminho == "/js":
        return 200, f"<html><body><p>pagina publica</p>{_JS_PARA_O_SALTO}</body></html>".encode(), None
    if caminho == "/iframe":
        iframe = f"<iframe src='http://localhost:{porta}/pagina'></iframe>"
        return 200, f"<html><body><p>pagina publica</p>{iframe}</body></html>".encode(), None
    if caminho.endswith("/ws"):
        corpo = f"<html><body><p>conversa</p><script>new WebSocket('ws://127.0.0.1:{porta_ws}/');</script></body></html>"
        return 200, corpo.encode(), None
    return 200, b"<html><body><p>pagina publica</p><img src='/img-redir'></body></html>", None


@contextmanager
def _site_hostil(host: str, porta_ws: int = 9, servico_em: str = "127.0.0.1"):
    """O serviço do analista (em `servico_em`) e o site hostil (em `host`)."""
    servico = _ServicoLocal(servico_em)
    local = f"http://{servico_em}:{servico.server_port}"

    class Site(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            _resposta(self, *_pagina_do_site(self.path, local, porta_ws, self.server.server_port))

        def log_message(self, *a) -> None:
            pass

    site = ThreadingHTTPServer((host, 0), Site)
    site.daemon_threads = True
    for servidor in (servico, site):
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        yield servico, f"http://{host}:{site.server_port}"
    finally:
        for servidor in (servico, site):
            servidor.shutdown()
            servidor.server_close()


@lento
async def test_redirect_da_pagina_inicial_para_endereco_local_e_barrado(tmp_path):
    with _site_hostil(_ip_da_lan()) as (servico, site):
        with pytest.raises(ErroNo) as e:
            await capturar(tmp_path, site + "/", max_subpaginas=0)
    assert servico.pedidos == []  # o serviço local nunca recebeu o pedido
    assert e.value.mensagem == (
        f"captura falhou: redirect para endereço local bloqueado: http://127.0.0.1:{servico.server_port}/segredo"
    )
    assert e.value.permanente is False
    assert not (tmp_path / "custodia.log").exists()  # nada do serviço local na custódia


@lento
@pytest.mark.parametrize(
    ("caminho", "motivo"),
    [("/2saltos", "redirect para endereço local bloqueado"), ("/js", "navegação para endereço local bloqueada")],
)
async def test_pagina_inicial_que_chega_ao_endereco_local_por_outro_salto_e_barrada(tmp_path, caminho, motivo):
    # o salto que a rota do contexto não vê: o segundo de uma cadeia de redirect, ou o da navegação que a página faz
    # sozinha depois de carregar (a página de erro do Chromium que fica no lugar dela não é página do site)
    with _site_hostil(_ip_da_lan()) as (servico, site):
        with pytest.raises(ErroNo) as e:
            await capturar(tmp_path, site + caminho, max_subpaginas=0)
    assert servico.pedidos == []
    assert e.value.mensagem == f"captura falhou: {motivo}: http://127.0.0.1:{servico.server_port}/segredo-2saltos"
    assert not (tmp_path / "custodia.log").exists()


@lento
async def test_subpagina_que_chega_ao_endereco_local_em_dois_saltos_vai_para_falhas_sem_entrar_no_har(tmp_path):
    with _site_hostil(_ip_da_lan()) as (servico, site):
        r, serv = await capturar(tmp_path, site + "/home", max_subpaginas=1)
    assert servico.pedidos == []
    assert [p["url"] for p in r.saidas["paginas"]] == [site + "/home"]
    destino = f"http://127.0.0.1:{servico.server_port}/segredo-2saltos"
    motivo = f"redirect para endereço local bloqueado: {destino}"
    assert r.saidas["falhas"] == [{"url": site + "/2saltos", "motivo": motivo}]
    assert b"servico local" not in serv.custodia.ler(r.saidas["paginas"][0]["har"])


@lento
async def test_redirect_de_imagem_para_endereco_local_e_barrado(tmp_path):
    # o site de teste em 127.0.0.1 (o loopback é dele) e o serviço do analista na rede privada: o Chromium deixa o
    # loopback pedir à rede privada (a checagem de rede privada dele só barra o contrário), então só a guarda segura
    with _site_hostil("127.0.0.1", servico_em=_ip_da_lan()) as (servico, site):
        r, serv = await capturar(tmp_path, site + "/pagina", max_subpaginas=0)
    assert servico.pedidos == []
    (pagina,) = r.saidas["paginas"]
    assert "pagina publica" in texto_de(serv, pagina)
    assert b"servico local" not in serv.custodia.ler(pagina["har"])


@lento
async def test_imagem_num_iframe_de_outro_site_com_redirect_para_endereco_local_e_barrada(tmp_path):
    # o iframe de localhost numa página de 127.0.0.1 é de outro site (o Chromium o roda em outro processo): a sessão do
    # navegador inteiro também vê os pedidos e os saltos dele
    with _site_hostil("127.0.0.1", servico_em=_ip_da_lan()) as (servico, site):
        r, serv = await capturar(tmp_path, site + "/iframe", max_subpaginas=0)
    assert servico.pedidos == []
    (pagina,) = r.saidas["paginas"]
    assert b"servico local" not in serv.custodia.ler(pagina["har"])


@lento
async def test_websocket_para_endereco_local_e_barrado(tmp_path):
    with socket.socket() as ouvinte:
        ouvinte.bind(("127.0.0.1", 0))
        ouvinte.listen()
        ouvinte.settimeout(0.5)
        with _site_hostil(_ip_da_lan(), porta_ws=ouvinte.getsockname()[1]) as (_, site):
            r, _ = await capturar(tmp_path, site + "/ws", max_subpaginas=0)
        assert len(r.saidas["paginas"]) == 1
        with pytest.raises(TimeoutError):
            ouvinte.accept()  # nenhuma conexão chegou ao ouvinte local


class _ProxyHostil(ThreadingHTTPServer):
    """Um proxy que responde pelo site hostil `alvo.test` (GET absoluto e CONNECT) e guarda o que recebeu."""

    daemon_threads = True

    def __init__(self, local: str) -> None:
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                servidor.vistos.append(self.path)
                _resposta(self, *_pagina_do_site(urlsplit(self.path).path, local, 9))

            def do_CONNECT(self) -> None:
                servidor.vistos.append(f"CONNECT {self.path}")
                self.send_response(200, "Connection established")
                self.end_headers()
                linha = self.rfile.readline().decode("latin-1").split()
                while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                    pass
                caminho = linha[1] if len(linha) > 1 else "/"
                servidor.vistos.append(f"(túnel) {caminho}")
                status, corpo, destino = _pagina_do_site(caminho, local, 9)
                cabecalho = f"HTTP/1.1 {status} X\r\nContent-Type: text/html\r\nContent-Length: {len(corpo)}\r\n"
                cabecalho += f"Location: {destino}\r\n" if destino else ""
                self.wfile.write((cabecalho + "Connection: close\r\n\r\n").encode() + corpo)
                self.close_connection = True

            def log_message(self, *a) -> None:
                pass

        super().__init__(("127.0.0.1", 0), Handler)
        self.vistos: list[str] = []


@lento
@pytest.mark.parametrize("caminho", ["/redir", "/2saltos"])
@pytest.mark.parametrize("host_local", ["127.0.0.1", "[::ffff:127.0.0.1]"])
async def test_com_proxy_redirects_para_endereco_local_nao_saem_do_navegador(tmp_path, caminho, host_local):
    # um proxy local (Burp, mitmproxy) repassaria ao serviço do analista o que recebesse. [::ffff:127.0.0.1] é o
    # loopback escrito como IPv6 (o Chromium o mostra como [::ffff:7f00:1])
    servico = _ServicoLocal()
    proxy = _ProxyHostil(f"http://{host_local}:{servico.server_port}")
    for servidor in (servico, proxy):
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
    rede = RedeConfig(proxy=f"http://127.0.0.1:{proxy.server_port}")
    try:
        with pytest.raises(ErroNo) as e:
            await capturar(tmp_path / "a", f"http://alvo.test{caminho}", rede=rede, max_subpaginas=0)
        r, _ = await capturar(tmp_path / "b", "http://alvo.test/pagina", rede=rede, max_subpaginas=0)
    finally:
        for servidor in (servico, proxy):
            servidor.shutdown()
            servidor.server_close()
    assert e.value.mensagem.startswith("captura falhou: redirect para endereço local bloqueado: http://")
    assert len(r.saidas["paginas"]) == 1
    # nem o serviço local nem o proxy viram um pedido para o loopback: o navegador não seguiu os saltos
    assert servico.pedidos == []
    assert not [v for v in proxy.vistos if "127.0.0.1" in v or "7f00" in v or "ffff" in v], proxy.vistos


@lento
async def test_pagina_que_termina_em_endereco_local_nao_vai_para_a_custodia(tmp_path, monkeypatch):
    # defesa em profundidade: mesmo que um salto escapasse da guarda, a página com URL final local não é guardada
    async def visitar(contexto, url, cfg, com_links, guarda):
        destino = "http://127.0.0.1:8080/segredo" if url.endswith("/") else "http://192.168.0.1/admin"
        links = ["https://exemplo.com.br/termos"] if com_links else []
        return modulo_captura._Visita(destino, 200, {}, "local", "<html>x</html>", "segredo", PNG, links)

    monkeypatch.setattr(modulo_captura, "_visitar", visitar)
    with pytest.raises(ErroNo) as e:
        await capturar(tmp_path, "https://exemplo.com.br/", max_subpaginas=1)
    assert e.value.mensagem == "captura falhou: página em endereço local bloqueada: http://127.0.0.1:8080/segredo"
    assert not (tmp_path / "custodia.log").exists()


@lento
async def test_subpagina_que_termina_em_endereco_local_vai_para_falhas(tmp_path, monkeypatch):
    async def visitar(contexto, url, cfg, com_links, guarda):
        if url == "https://exemplo.com.br/":
            return modulo_captura._Visita(url, 200, {}, "home", "<html>h</html>", "home", PNG,
                                          ["https://exemplo.com.br/termos"])  # fmt: skip
        return modulo_captura._Visita("http://192.168.0.1/admin", 200, {}, "x", "<html>x</html>", "x", PNG)

    monkeypatch.setattr(modulo_captura, "_visitar", visitar)
    r, serv = await capturar(tmp_path, "https://exemplo.com.br/", max_subpaginas=1)
    assert [p["url"] for p in r.saidas["paginas"]] == ["https://exemplo.com.br/"]
    assert r.saidas["falhas"] == [
        {"url": "https://exemplo.com.br/termos", "motivo": "página em endereço local bloqueada: http://192.168.0.1/admin"}
    ]


def _pausa_no_fetch(url: str) -> bool:
    """O `urlPattern` do `Fetch` do CDP casa com `url`: `*` é qualquer sequência (até vazia), `?` é um caractere."""
    return any(
        re.fullmatch("".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in padrao), url)
        for padrao in modulo_captura._PADROES_DO_FETCH
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080/admin", "http://0.0.0.0/", "http://10.1.2.3/", "http://192.168.0.1/",
        "http://172.20.0.1/", "http://169.254.169.254/latest", "http://100.64.0.1/", "https://203.0.113.9/",
        "http://[::1]:9/",
        "http://[::ffff:7f00:1]:9/img", "http://[fd00::1]/", "http://[fe80::1]/", "http://localhost/",
        "http://localhost.:8080/", "http://app.localhost/x", "http://usuario:senha@127.0.0.1:9/",
    ],
)  # fmt: skip
def test_o_fetch_pausa_todo_endereco_local_que_a_guarda_barra(url):
    assert not modulo_captura._Guarda("https://exemplo.com.br/").permitido(url)
    assert _pausa_no_fetch(url)


def test_o_fetch_nao_pausa_nome_comum_e_o_que_pausa_sem_ser_local_segue():
    guarda = modulo_captura._Guarda("https://exemplo.com.br/")
    for url in ("https://exemplo.com.br/termos", "https://cdn.exemplo.com.br/a.js", "https://www.google.com/"):
        assert not _pausa_no_fetch(url) and guarda.permitido(url)
    # pausa, mas a guarda deixa seguir: nome que começa com dígito, IP global e e-mail na query
    for url in ("https://123exemplo.com.br/", "https://8.8.8.8/", "https://exemplo.com.br/?email=a@b.com.br"):
        assert _pausa_no_fetch(url) and guarda.permitido(url)
    # o site de teste local: o loopback dele pausa e segue; a rede privada não segue
    local = modulo_captura._Guarda("http://127.0.0.1:5000/")
    assert _pausa_no_fetch("http://localhost:9/x") and local.permitido("http://localhost:9/x")
    assert not local.permitido("http://192.168.0.1/")
