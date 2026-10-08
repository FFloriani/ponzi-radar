"""Rede (ponto único de saída HTTP) e utilitários de texto (Tarefa 4)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

import radar.rede as modulo_rede
from radar.config import UA_API, RedeConfig
from radar.rede import ErroRede, Rede, RespostaRede
from radar.texto import normalizar, texto_de_html


def cfg(**kw) -> RedeConfig:
    return RedeConfig(**kw)


async def registrar(esperas: list[float], s: float) -> None:
    esperas.append(s)


async def _nao_dormir(s: float) -> None:
    return None


def rede_sem_espera(**kw) -> Rede:
    kw.setdefault("limites", {"*": 0})
    return Rede(cfg(**kw), dormir=_nao_dormir)


class Relogio:
    """Relógio manual: só anda quando o teste manda."""

    def __init__(self, t: float = 100.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


# ---------------------------------------------------------------- retry / erros


async def test_retry_429_depois_sucesso(respx_mock):
    rota = respx_mock.get("https://api.x/a").mock(side_effect=[httpx.Response(429), httpx.Response(429), httpx.Response(200, json={"ok": 1})])
    esperas = []; rede = Rede(cfg(limites={"*": 0}), dormir=lambda s: registrar(esperas, s))
    assert await rede.get_json("https://api.x/a") == {"ok": 1}
    assert rota.call_count == 3 and esperas == [1.0, 2.0]


async def test_desiste_apos_4_tentativas(respx_mock):
    rota = respx_mock.get("https://api.x/b").mock(return_value=httpx.Response(503))
    with pytest.raises(ErroRede) as e: await rede_sem_espera().get("https://api.x/b")
    assert e.value.permanente is False and rota.call_count == 4


async def test_404_permanente(respx_mock):
    rota = respx_mock.get("https://api.x/c").mock(return_value=httpx.Response(404))
    with pytest.raises(ErroRede) as e: await rede_sem_espera().get("https://api.x/c")
    assert e.value.permanente is True and rota.call_count == 1


async def test_limite_por_host(respx_mock):  # relógio parado: 2ª requisição espera o limite inteiro
    respx_mock.get(url__startswith="https://lento.x/").mock(return_value=httpx.Response(200))
    esperas = []; rede = Rede(cfg(limites={"*": 0, "lento.x": 2.0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    await rede.get("https://lento.x/1"); await rede.get("https://lento.x/2")
    assert esperas == [2.0]


async def test_cache(respx_mock):
    rota = respx_mock.get("https://api.x/d").mock(return_value=httpx.Response(200, text="x"))
    r = rede_sem_espera(); await r.get("https://api.x/d"); r2 = await r.get("https://api.x/d")
    assert rota.call_count == 1 and r2.de_cache is True


async def test_user_agent_por_tipo(respx_mock):
    rota = respx_mock.get("https://site.x/").mock(return_value=httpx.Response(200))
    c = cfg(); await Rede(c).get("https://site.x/", tipo="navegador")
    assert rota.calls[0].request.headers["user-agent"] == c.ua_navegador


def test_normalizar():
    assert normalizar("  “Rendimento”\n  GARANTIDO, sem riscos ") == normalizar('"rendimento" garantido, sem riscos')


def test_texto_de_html_descarta_script():
    assert texto_de_html("<p>Olá</p><script>var x='lucro'</script><p>mundo</p>").split() == ["Olá", "mundo"]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 418, 451])
async def test_status_4xx_e_permanente_sem_nova_tentativa(respx_mock, status):
    rota = respx_mock.get("https://api.x/p").mock(return_value=httpx.Response(status))
    with pytest.raises(ErroRede) as e:
        await rede_sem_espera().get("https://api.x/p")
    assert e.value.permanente is True and e.value.status == status and rota.call_count == 1


async def test_5xx_esgotado_espera_backoff_1_2_4(respx_mock):
    rota = respx_mock.get("https://api.x/q").mock(return_value=httpx.Response(500))
    esperas = []; rede = Rede(cfg(limites={"*": 0}), dormir=lambda s: registrar(esperas, s))
    with pytest.raises(ErroRede) as e:
        await rede.get("https://api.x/q")
    assert rota.call_count == 4 and esperas == [1.0, 2.0, 4.0]
    assert e.value.permanente is False and e.value.status == 500


async def test_respeita_numero_de_tentativas_da_config(respx_mock):
    rota = respx_mock.get("https://api.x/t").mock(return_value=httpx.Response(502))
    with pytest.raises(ErroRede):
        await rede_sem_espera(tentativas=2).get("https://api.x/t")
    assert rota.call_count == 2


async def test_retry_after_numerico_tem_prioridade(respx_mock):
    respx_mock.get("https://api.x/r").mock(side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)])
    esperas = []; rede = Rede(cfg(limites={"*": 0}), dormir=lambda s: registrar(esperas, s))
    assert (await rede.get("https://api.x/r")).status == 200
    assert esperas == [7.0]


async def test_retry_after_tem_teto_de_60s(respx_mock):
    respx_mock.get("https://api.x/r2").mock(side_effect=[httpx.Response(503, headers={"Retry-After": "3600"}), httpx.Response(200)])
    esperas = []; rede = Rede(cfg(limites={"*": 0}), dormir=lambda s: registrar(esperas, s))
    await rede.get("https://api.x/r2")
    assert esperas == [60.0]


@pytest.mark.parametrize("valor", ["Wed, 21 Oct 2026 07:28:00 GMT", "abc", "nan", "-5", ""])
async def test_retry_after_nao_numerico_ou_invalido_cai_no_backoff(respx_mock, valor):
    respx_mock.get("https://api.x/r3").mock(side_effect=[httpx.Response(429, headers={"Retry-After": valor}), httpx.Response(200)])
    esperas = []; rede = Rede(cfg(limites={"*": 0}), dormir=lambda s: registrar(esperas, s))
    await rede.get("https://api.x/r3")
    assert esperas == [1.0]


async def test_erro_de_transporte_tem_nova_tentativa(respx_mock):
    rota = respx_mock.get("https://api.x/u").mock(side_effect=[httpx.ConnectError("recusou"), httpx.ReadTimeout("lento"), httpx.Response(200, text="ok")])
    esperas = []; rede = Rede(cfg(limites={"*": 0}), dormir=lambda s: registrar(esperas, s))
    assert (await rede.get("https://api.x/u")).texto == "ok"
    assert rota.call_count == 3 and esperas == [1.0, 2.0]


async def test_timeout_esgotado_e_transitorio_e_diz_o_motivo(respx_mock):
    rota = respx_mock.get("https://api.x/v").mock(side_effect=httpx.ReadTimeout("lento"))
    with pytest.raises(ErroRede) as e:
        await rede_sem_espera().get("https://api.x/v")
    assert rota.call_count == 4
    assert e.value.permanente is False and e.value.status is None
    assert e.value.url == "https://api.x/v"
    assert "https://api.x/v" in str(e.value) and "ReadTimeout" in str(e.value)


async def test_mensagem_do_erro_traz_url_e_status(respx_mock):
    respx_mock.get("https://api.x/w").mock(return_value=httpx.Response(403))
    with pytest.raises(ErroRede) as e:
        await rede_sem_espera().get("https://api.x/w", params={"q": "1"})
    assert e.value.url == "https://api.x/w?q=1"
    assert "https://api.x/w?q=1" in str(e.value) and "403" in str(e.value)


async def test_url_sem_protocolo_e_permanente_sem_nova_tentativa():
    rede = rede_sem_espera()
    with pytest.raises(ErroRede) as e:
        await rede.get("site.x/sem-esquema")
    assert e.value.permanente is True and e.value.status is None
    await rede.fechar()


async def test_get_json_com_corpo_invalido_vira_erro_rede(respx_mock):
    respx_mock.get("https://api.x/j").mock(return_value=httpx.Response(200, text="<html>nao e json</html>"))
    with pytest.raises(ErroRede) as e:
        await rede_sem_espera().get_json("https://api.x/j")
    assert e.value.permanente is True and e.value.status == 200 and "https://api.x/j" in str(e.value)


# ---------------------------------------------------------------- limite por host


async def test_limite_desconta_o_tempo_decorrido_desde_o_fim_da_anterior(respx_mock):
    respx_mock.get(url__startswith="https://lento.x/").mock(return_value=httpx.Response(200))
    relogio = Relogio(100.0)
    esperas = []; rede = Rede(cfg(limites={"*": 0, "lento.x": 2.0}), dormir=lambda s: registrar(esperas, s), relogio=relogio)
    await rede.get("https://lento.x/1")
    relogio.t = 100.5
    await rede.get("https://lento.x/2")
    relogio.t = 103.0  # passou mais que o limite: não espera
    await rede.get("https://lento.x/3")
    assert esperas == [1.5]


async def test_limite_e_independente_por_host_e_usa_curinga(respx_mock):
    respx_mock.get(url__regex=r"https://(a|b)\.x/.*").mock(return_value=httpx.Response(200))
    esperas = []; rede = Rede(cfg(limites={"*": 5.0, "b.x": 0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    await rede.get("https://a.x/1")
    await rede.get("https://b.x/1")  # outro host: não espera pelo a.x
    await rede.get("https://b.x/2")  # b.x tem limite 0
    assert esperas == []
    await rede.get("https://a.x/2")  # a.x cai no "*" de 5 s
    assert esperas == [5.0]


async def test_limite_tambem_vale_entre_tentativas_do_mesmo_host(respx_mock):
    respx_mock.get("https://api.x/l").mock(side_effect=[httpx.Response(503), httpx.Response(200)])
    esperas = []; rede = Rede(cfg(limites={"*": 3.0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    await rede.get("https://api.x/l")
    # relógio parado: o backoff (1 s) vem primeiro e a 2ª tentativa ainda espera o limite inteiro do host
    assert esperas == [1.0, 3.0]


async def test_requisicoes_concorrentes_ao_mesmo_host_sao_serializadas(respx_mock):
    respx_mock.get(url__startswith="https://lento.x/").mock(return_value=httpx.Response(200))
    esperas = []; rede = Rede(cfg(limites={"*": 0, "lento.x": 2.0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    await asyncio.gather(*(rede.get(f"https://lento.x/{i}") for i in range(3)))
    assert esperas == [2.0, 2.0]  # sem a trava por host, as três saíam juntas e ninguém esperava


# ---------------------------------------------------------------- cache


async def test_cache_por_params_ordenados(respx_mock):
    rota = respx_mock.get("https://api.x/e").mock(return_value=httpx.Response(200, text="x"))
    r = rede_sem_espera()
    a = await r.get("https://api.x/e", params={"a": "1", "b": "2"})
    b = await r.get("https://api.x/e", params={"b": "2", "a": "1"})
    assert rota.call_count == 1 and a.de_cache is False and b.de_cache is True
    await r.get("https://api.x/e", params={"a": "9"})
    assert rota.call_count == 2


async def test_cache_nunca_guarda_erro(respx_mock):
    rota = respx_mock.get("https://api.x/f").mock(side_effect=[httpx.Response(503), httpx.Response(200, text="voltou")])
    r = rede_sem_espera(tentativas=1)
    with pytest.raises(ErroRede):
        await r.get("https://api.x/f")
    resposta = await r.get("https://api.x/f")
    assert resposta.texto == "voltou" and resposta.de_cache is False and rota.call_count == 2


async def test_usar_cache_false_vai_a_rede_e_renova_o_cache(respx_mock):
    # quem precisa de dado fresco (índices com validade) não pode receber a resposta de horas atrás
    rota = respx_mock.get("https://api.x/fresco").mock(
        side_effect=[httpx.Response(200, text="velho"), httpx.Response(200, text="novo")]
    )
    rota.side_effect = [httpx.Response(200, text=t) for t in ("velho", "novo", "depois")]
    r = rede_sem_espera()
    assert (await r.get("https://api.x/fresco")).texto == "velho"
    fresca = await r.get("https://api.x/fresco", usar_cache=False)
    assert (fresca.texto, fresca.de_cache, rota.call_count) == ("novo", False, 2)
    # I4: `usar_cache=False` não guarda (os ZIPs e PDFs dos índices não ficam na memória) e tira a velha do cache
    seguinte = await r.get("https://api.x/fresco")
    assert (seguinte.texto, seguinte.de_cache, rota.call_count) == ("depois", False, 3)


async def test_cache_e_por_instancia(respx_mock):
    rota = respx_mock.get("https://api.x/g").mock(return_value=httpx.Response(200))
    await rede_sem_espera().get("https://api.x/g")
    await rede_sem_espera().get("https://api.x/g")
    assert rota.call_count == 2


async def test_cache_distingue_tipo_e_redirect(respx_mock):
    rota = respx_mock.get("https://site.x/h").mock(return_value=httpx.Response(200))
    r = rede_sem_espera()
    await r.get("https://site.x/h")
    await r.get("https://site.x/h", tipo="navegador")
    await r.get("https://site.x/h", seguir_redirect=False)
    assert rota.call_count == 3
    assert (await r.get("https://site.x/h", tipo="navegador")).de_cache is True


# ---------------------------------------------------------------- requisição


async def test_headers_do_chamador_vao_junto_e_ua_api_e_o_padrao(respx_mock):
    rota = respx_mock.get("https://api.x/i").mock(return_value=httpx.Response(200))
    c = cfg(limites={"*": 0})
    await Rede(c).get("https://api.x/i", headers={"Accept": "application/json"})
    enviados = rota.calls[0].request.headers
    assert enviados["accept"] == "application/json" and enviados["user-agent"] == c.ua_api


async def test_params_vao_na_query(respx_mock):
    rota = respx_mock.get("https://api.x/k").mock(return_value=httpx.Response(200))
    await rede_sem_espera().get("https://api.x/k", params={"q": "a b", "n": 2})
    assert rota.calls[0].request.url.params["q"] == "a b" and rota.calls[0].request.url.params["n"] == "2"


async def test_segue_redirect_por_padrao(respx_mock):
    respx_mock.get("https://api.x/o").mock(return_value=httpx.Response(301, headers={"Location": "https://api.x/novo"}))
    respx_mock.get("https://api.x/novo").mock(return_value=httpx.Response(200, text="fim"))
    r = await rede_sem_espera().get("https://api.x/o")
    assert r.status == 200 and r.url == "https://api.x/novo" and r.texto == "fim"


async def test_nao_segue_redirect_quando_pedido(respx_mock):
    respx_mock.get("https://api.x/o2").mock(return_value=httpx.Response(301, headers={"Location": "https://api.x/novo2"}))
    r = await rede_sem_espera().get("https://api.x/o2", seguir_redirect=False)
    assert r.status == 301 and r.headers["location"] == "https://api.x/novo2"


async def test_tipo_desconhecido_e_erro_de_programacao():
    rede = rede_sem_espera()
    with pytest.raises(ValueError, match="Navegador"):
        await rede.get("https://site.x/", tipo="Navegador")
    await rede.fechar()


async def test_proxy_e_timeout_vao_para_o_cliente_httpx(monkeypatch):
    recebidos = {}
    original = httpx.AsyncClient

    def espiao(*args, **kwargs):
        recebidos.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(modulo_rede.httpx, "AsyncClient", espiao)
    rede = Rede(cfg(proxy="socks5://127.0.0.1:9050", timeout_s=12.0))
    assert recebidos["proxy"] == "socks5://127.0.0.1:9050" and recebidos["timeout"] == 12.0
    # redirect é seguido por Rede (cada salto passa pelo limite do host) e o ambiente não manda no proxy
    assert recebidos["follow_redirects"] is False and recebidos["trust_env"] is False
    await rede.fechar()


async def test_sem_proxy_nao_configura_proxy(monkeypatch):
    recebidos = {}
    original = httpx.AsyncClient

    def espiao(*args, **kwargs):
        recebidos.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(modulo_rede.httpx, "AsyncClient", espiao)
    await Rede(cfg()).fechar()
    assert recebidos.get("proxy") is None


# ---------------------------------------------------------------- timeout por host


def _espiar_timeouts(respx_mock, *urls: str) -> list[tuple[str, float]]:
    """Registra `(host, timeout de leitura)` que o httpx recebeu em cada requisição."""
    vistos: list[tuple[str, float]] = []

    def responder(request: httpx.Request) -> httpx.Response:
        vistos.append((request.url.host, request.extensions["timeout"]["read"]))
        return httpx.Response(200, text="ok")

    for url in urls:
        respx_mock.get(url).mock(side_effect=responder)
    return vistos


async def test_timeout_especifico_do_host_vale_em_cada_requisicao(respx_mock):
    vistos = _espiar_timeouts(respx_mock, "https://lento.x/a", "https://rapido.x/b")
    rede = rede_sem_espera(timeout_s=30.0, timeouts={"lento.x": 90.0})
    await rede.get("https://lento.x/a")
    await rede.get("https://rapido.x/b")
    assert vistos == [("lento.x", 90.0), ("rapido.x", 30.0)]
    await rede.fechar()


async def test_timeout_do_wayback_e_120s_por_padrao_e_outros_hosts_usam_timeout_s(respx_mock):
    vistos = _espiar_timeouts(respx_mock, "https://web.archive.org/x", "https://api.x/y")
    rede = rede_sem_espera()
    await rede.get("https://web.archive.org/x")
    await rede.get("https://api.x/y")
    assert vistos == [("web.archive.org", 120.0), ("api.x", 30.0)]
    await rede.fechar()


async def test_timeout_do_wayback_pode_ser_trocado_na_config(respx_mock):
    vistos = _espiar_timeouts(respx_mock, "https://web.archive.org/x")
    rede = rede_sem_espera(timeouts={"web.archive.org": 7.0})
    await rede.get("https://web.archive.org/x")
    assert vistos == [("web.archive.org", 7.0)]
    await rede.fechar()


async def test_timeout_acompanha_o_host_de_cada_salto_do_redirect(respx_mock):
    vistos: list[tuple[str, float]] = []

    def salto(request: httpx.Request) -> httpx.Response:
        vistos.append((request.url.host, request.extensions["timeout"]["read"]))
        if request.url.host == "api.x":
            return httpx.Response(302, headers={"Location": "https://web.archive.org/web/2020id_/alvo.x"})
        return httpx.Response(200, text="snapshot")

    respx_mock.get("https://api.x/ir").mock(side_effect=salto)
    respx_mock.get("https://web.archive.org/web/2020id_/alvo.x").mock(side_effect=salto)
    rede = rede_sem_espera()
    resposta = await rede.get("https://api.x/ir")
    assert resposta.texto == "snapshot"
    assert vistos == [("api.x", 30.0), ("web.archive.org", 120.0)]  # cada salto leva o timeout do seu host
    await rede.fechar()


async def test_timeout_vale_tambem_nas_novas_tentativas(respx_mock):
    vistos: list[float] = []

    def responder(request: httpx.Request) -> httpx.Response:
        vistos.append(request.extensions["timeout"]["read"])
        return httpx.Response(503)

    respx_mock.get("https://web.archive.org/x").mock(side_effect=responder)
    rede = rede_sem_espera()
    with pytest.raises(ErroRede):
        await rede.get("https://web.archive.org/x")
    assert vistos == [120.0] * 4
    await rede.fechar()


# ---------------------------------------------------------------- redirects


async def test_redirect_no_mesmo_host_respeita_o_limite_no_segundo_salto(respx_mock):
    a = respx_mock.get("https://web.archive.org/web/2020/alvo.x").mock(return_value=httpx.Response(302, headers={"Location": "/web/20200102/alvo.x"}))
    b = respx_mock.get("https://web.archive.org/web/20200102/alvo.x").mock(return_value=httpx.Response(200, text="snapshot"))
    esperas = []; rede = Rede(cfg(limites={"*": 0, "web.archive.org": 2.0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    r = await rede.get("https://web.archive.org/web/2020/alvo.x")
    assert (r.status, r.url, r.texto) == (200, "https://web.archive.org/web/20200102/alvo.x", "snapshot")
    assert a.call_count == 1 and b.call_count == 1
    assert esperas == [2.0]  # o 2º salto espera o limite do host, como qualquer outra requisição


async def test_redirect_para_outro_host_respeita_o_limite_do_destino(respx_mock):
    respx_mock.get("https://b.x/2").mock(return_value=httpx.Response(200))
    respx_mock.get("https://a.x/1").mock(return_value=httpx.Response(302, headers={"Location": "https://b.x/destino"}))
    respx_mock.get("https://b.x/destino").mock(return_value=httpx.Response(200, text="chegou"))
    esperas = []; rede = Rede(cfg(limites={"*": 0, "b.x": 5.0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    await rede.get("https://b.x/2")
    assert esperas == []
    r = await rede.get("https://a.x/1")  # a.x não tem limite; o salto para b.x espera os 5 s de b.x
    assert r.url == "https://b.x/destino" and r.texto == "chegou"
    assert esperas == [5.0]


async def test_loop_de_redirect_vira_erro_permanente_e_cada_salto_respeita_o_limite(respx_mock):
    rota = respx_mock.get("https://l.x/loop").mock(return_value=httpx.Response(302, headers={"Location": "/loop"}))
    esperas = []; rede = Rede(cfg(limites={"*": 1.0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    with pytest.raises(ErroRede) as e:
        await rede.get("https://l.x/loop")
    assert e.value.permanente is True and e.value.status == 302 and e.value.url == "https://l.x/loop"
    assert "redirect" in str(e.value) and "https://l.x/loop" in str(e.value)
    assert rota.call_count == 11  # a requisição original + 10 saltos
    assert esperas == [1.0] * 10


async def test_cadeia_de_redirects_longa_mas_dentro_do_teto_funciona(respx_mock):
    for i in range(10):
        respx_mock.get(f"https://c.x/{i}").mock(return_value=httpx.Response(301, headers={"Location": f"/{i + 1}"}))
    respx_mock.get("https://c.x/10").mock(return_value=httpx.Response(200, text="fim"))
    r = await rede_sem_espera().get("https://c.x/0")
    assert r.status == 200 and r.url == "https://c.x/10"


async def test_redirect_nao_seguido_nao_toca_o_destino(respx_mock):
    origem = respx_mock.get("https://api.x/o3").mock(return_value=httpx.Response(302, headers={"Location": "https://outro.x/"}))
    r = await rede_sem_espera().get("https://api.x/o3", seguir_redirect=False)
    assert r.status == 302 and r.headers["location"] == "https://outro.x/" and origem.call_count == 1


async def test_3xx_sem_location_e_devolvido_como_esta(respx_mock):
    respx_mock.get("https://api.x/o4").mock(return_value=httpx.Response(300))
    assert (await rede_sem_espera().get("https://api.x/o4")).status == 300


async def test_cache_guarda_o_resultado_final_do_redirect(respx_mock):
    a = respx_mock.get("https://api.x/o5").mock(return_value=httpx.Response(302, headers={"Location": "/o6"}))
    b = respx_mock.get("https://api.x/o6").mock(return_value=httpx.Response(200, text="fim"))
    r = rede_sem_espera()
    primeira = await r.get("https://api.x/o5")
    segunda = await r.get("https://api.x/o5")
    assert (a.call_count, b.call_count) == (1, 1)
    assert primeira.de_cache is False and segunda.de_cache is True and segunda.url == "https://api.x/o6"


async def test_novas_tentativas_valem_dentro_de_cada_salto(respx_mock):
    respx_mock.get("https://api.x/o7").mock(return_value=httpx.Response(302, headers={"Location": "/o8"}))
    destino = respx_mock.get("https://api.x/o8").mock(side_effect=[httpx.Response(503), httpx.Response(200, text="ok")])
    esperas = []; rede = Rede(cfg(limites={"*": 0}), dormir=lambda s: registrar(esperas, s))
    r = await rede.get("https://api.x/o7")
    assert r.texto == "ok" and r.url == "https://api.x/o8" and destino.call_count == 2 and esperas == [1.0]


async def test_erro_permanente_no_salto_aponta_a_url_do_salto(respx_mock):
    respx_mock.get("https://api.x/o9").mock(return_value=httpx.Response(302, headers={"Location": "/o10"}))
    respx_mock.get("https://api.x/o10").mock(return_value=httpx.Response(404))
    with pytest.raises(ErroRede) as e:
        await rede_sem_espera().get("https://api.x/o9")
    assert e.value.permanente is True and e.value.status == 404 and e.value.url == "https://api.x/o10"


async def test_redirect_para_outro_protocolo_e_erro_permanente(respx_mock):
    rota = respx_mock.get("https://api.x/o11").mock(return_value=httpx.Response(302, headers={"Location": "ftp://x.x/y"}))
    with pytest.raises(ErroRede) as e:
        await rede_sem_espera().get("https://api.x/o11")
    assert e.value.permanente is True and e.value.status == 302 and e.value.url == "https://api.x/o11"
    assert "redirect" in str(e.value) and "ftp://x.x/y" in str(e.value) and rota.call_count == 1


@pytest.mark.parametrize("location", ["javascript:alert(1)", "http://[::1"])
async def test_location_que_nao_e_url_e_erro_permanente_sem_nova_tentativa(respx_mock, location):
    # o httpx resolve o Location na hora e rejeita; repetir só devolveria o mesmo Location
    rota = respx_mock.get("https://api.x/o12").mock(return_value=httpx.Response(302, headers={"Location": location}))
    with pytest.raises(ErroRede) as e:
        await rede_sem_espera().get("https://api.x/o12")
    assert e.value.permanente is True and e.value.url == "https://api.x/o12" and rota.call_count == 1


async def test_credenciais_nao_acompanham_redirect_para_outra_origem(respx_mock):
    primeira = respx_mock.get("https://a.x/1").mock(return_value=httpx.Response(302, headers={"Location": "https://b.x/2"}))
    segunda = respx_mock.get("https://b.x/2").mock(return_value=httpx.Response(200))
    sensiveis = {"Authorization": "Bearer segredo", "Cookie": "sessao=1", "X-Chave": "v"}
    await rede_sem_espera().get("https://a.x/1", headers=sensiveis)
    enviados = segunda.calls[0].request.headers
    assert primeira.calls[0].request.headers["authorization"] == "Bearer segredo"
    assert "authorization" not in enviados and "cookie" not in enviados and enviados["x-chave"] == "v"


async def test_credenciais_acompanham_redirect_na_mesma_origem(respx_mock):
    respx_mock.get("https://a.x/1").mock(return_value=httpx.Response(302, headers={"Location": "/2"}))
    segunda = respx_mock.get("https://a.x/2").mock(return_value=httpx.Response(200))
    await rede_sem_espera().get("https://a.x/1", headers={"Authorization": "Bearer segredo"})
    assert segunda.calls[0].request.headers["authorization"] == "Bearer segredo"


async def _servidor_local(recebidos: list[bytes]):
    """Servidor HTTP mínimo em 127.0.0.1 que registra o cabeçalho de cada requisição e responde `ok`."""
    async def atender(leitor, escritor):
        try:
            recebidos.append(await leitor.readuntil(b"\r\n\r\n"))
            escritor.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            await escritor.drain()
        finally:
            escritor.close()

    servidor = await asyncio.start_server(atender, "127.0.0.1", 0)
    return servidor, servidor.sockets[0].getsockname()[1]


async def test_proxy_das_variaveis_de_ambiente_e_ignorado(monkeypatch):
    no_alvo, no_proxy = [], []
    alvo, porta_alvo = await _servidor_local(no_alvo)
    proxy, porta_proxy = await _servidor_local(no_proxy)
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(var, f"http://127.0.0.1:{porta_proxy}")
    for var in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(var, raising=False)
    try:
        rede = rede_sem_espera()  # config.proxy = None: conexão direta, nunca o proxy do ambiente
        resposta = await rede.get(f"http://127.0.0.1:{porta_alvo}/x")
        await rede.fechar()
    finally:
        for servidor in (alvo, proxy):
            servidor.close()
            await servidor.wait_closed()
    assert resposta.texto == "ok"
    assert len(no_alvo) == 1 and no_proxy == []


# ---------------------------------------------------------------- RespostaRede


def _resp(conteudo: bytes, content_type: str | None = None) -> RespostaRede:
    headers = {} if content_type is None else {"content-type": content_type}
    return RespostaRede(status=200, url="https://x/", conteudo=conteudo, headers=headers, de_cache=False)


def test_texto_usa_o_charset_do_content_type():
    assert _resp("ação".encode("latin-1"), "text/html; charset=ISO-8859-1").texto == "ação"
    assert _resp("ação".encode("utf-16"), 'text/plain; charset="utf-16"').texto == "ação"


def test_texto_sem_charset_e_utf8_com_replace():
    assert _resp("ação".encode("utf-8")).texto == "ação"
    assert _resp(b"ok \xff fim", "text/html").texto == "ok � fim"


def test_texto_com_charset_desconhecido_cai_em_utf8():
    assert _resp("ação".encode("utf-8"), "text/html; charset=nao-existe").texto == "ação"


@pytest.mark.parametrize("charset", ["idna", "undefined"])
def test_texto_com_charset_que_nao_decodifica_texto_cai_em_utf8(charset):
    # o cabeçalho vem do servidor investigado: o codec `idna` e o `undefined` levantam UnicodeError
    assert _resp("ação".encode("utf-8"), f"text/html; charset={charset}").texto == "ação"


def test_texto_acha_content_type_em_qualquer_caixa():
    r = RespostaRede(status=200, url="u", conteudo="ação".encode("latin-1"), headers={"Content-Type": "text/html; charset=latin-1"}, de_cache=False)
    assert r.texto == "ação"


def test_json_da_resposta():
    assert _resp(b'{"a": [1, 2]}', "application/json").json() == {"a": [1, 2]}
    assert _resp(b"\xef\xbb\xbf" + b'{"a": 1}').json() == {"a": 1}  # BOM


async def test_resposta_expoe_status_url_headers_minusculos(respx_mock):
    respx_mock.get("https://api.x/m").mock(return_value=httpx.Response(200, text="oi", headers={"X-Teste": "1", "Content-Type": "text/plain; charset=utf-8"}))
    r = await rede_sem_espera().get("https://api.x/m")
    assert (r.status, r.url, r.conteudo, r.de_cache) == (200, "https://api.x/m", b"oi", False)
    assert r.headers["x-teste"] == "1" and isinstance(r.headers, dict)


# ---------------------------------------------------------------- texto.py


def test_normalizar_tira_acento_caixa_e_espaco():
    assert normalizar("  AÇÃO   Lucrativa \tgarantida\n") == "acao lucrativa garantida"


def test_normalizar_aspas_tipograficas():
    assert normalizar("‘a’ “b” „c“") == "'a' \"b\" \"c\""
    assert normalizar("D’Água") == "d'agua"


def test_normalizar_vazio_e_so_espaco():
    assert normalizar("") == "" and normalizar(" \n\t ") == ""


def test_normalizar_nfkd_e_idempotente():
    assert normalizar("ﬁnanças ①") == "financas 1"
    assert normalizar(normalizar("  “Ação”  ")) == normalizar("  “Ação”  ")


def test_texto_de_html_blocos_viram_linhas_e_inline_continua_na_linha():
    html = "<h1>Título</h1><p>Ganhe <b>10%</b> ao dia!</p><ul><li>um</li><li>dois</li></ul>linha<br>quebrada"
    assert texto_de_html(html) == "Título\nGanhe 10% ao dia!\num\ndois\nlinha\nquebrada"


def test_texto_de_html_descarta_style_noscript_template_e_comentarios():
    html = (
        "<style>.a{color:red}</style><noscript>ative o JS</noscript><template><p>molde</p></template>"
        "<!-- escondido --><p>visível</p><script>if (a < b) { x = '</p>'; }</script>"
    )
    assert texto_de_html(html) == "visível"


def test_texto_de_html_entidades_e_espacos():
    assert texto_de_html("<p>  R$ 1.000 &amp;\n  mais&nbsp;tudo  </p>") == "R$ 1.000 & mais tudo"


def test_texto_de_html_tolera_html_quebrado_e_vazio():
    assert texto_de_html("") == ""
    assert texto_de_html("<div><p>aberto<div>outro") == "aberto\noutro"


# ---------------------------------------------------------------- sessão por execução (I4)


async def test_sessao_tem_cache_proprio(respx_mock):
    rota = respx_mock.get("https://dns.x/q").mock(side_effect=[httpx.Response(200, text=t) for t in ("1", "2", "3")])
    raiz = rede_sem_espera()
    a, b = raiz.sessao(), raiz.sessao()
    assert (await a.get("https://dns.x/q")).texto == "1"
    assert (await a.get("https://dns.x/q")).texto == "1"  # a mesma execução: do cache
    assert (await b.get("https://dns.x/q")).texto == "2"  # outra execução: resposta nova
    assert rota.call_count == 2
    for rede in (a, b, raiz):
        await rede.fechar()


async def test_sessao_divide_o_limite_por_host(respx_mock):
    respx_mock.get(url__startswith="https://lento.x/").mock(return_value=httpx.Response(200))
    esperas = []
    raiz = Rede(cfg(limites={"*": 0, "lento.x": 2.0}), dormir=lambda s: registrar(esperas, s), relogio=lambda: 100.0)
    await raiz.sessao().get("https://lento.x/1")
    await raiz.sessao().get("https://lento.x/2")  # outra sessão, o mesmo host: a cortesia com a fonte continua
    assert esperas == [2.0]


async def test_sessao_tem_cookies_proprios(respx_mock):
    respx_mock.get("https://fonte.x/entrar").mock(
        return_value=httpx.Response(200, headers={"set-cookie": "rastreio=analista-1; Path=/"})
    )
    rota = respx_mock.get("https://fonte.x/pagina").mock(return_value=httpx.Response(200))
    raiz = rede_sem_espera()
    a, b = raiz.sessao(), raiz.sessao()
    await a.get("https://fonte.x/entrar")
    await a.get("https://fonte.x/pagina")
    await b.get("https://fonte.x/pagina")
    assert "rastreio=analista-1" in rota.calls[0].request.headers.get("cookie", "")
    assert "cookie" not in rota.calls[1].request.headers  # a outra execução não leva o cookie
    for rede in (a, b, raiz):
        await rede.fechar()


async def test_cache_tem_teto_de_memoria_e_descarta_os_mais_antigos(respx_mock, monkeypatch):
    monkeypatch.setattr(modulo_rede, "TETO_DO_CACHE_BYTES", 250)
    rotas = {n: respx_mock.get(f"https://api.x/{n}").mock(return_value=httpx.Response(200, content=b"x" * 100))
             for n in "abc"}  # fmt: skip
    r = rede_sem_espera()
    for n in "abc":
        await r.get(f"https://api.x/{n}")
    assert (await r.get("https://api.x/c")).de_cache is True
    assert (await r.get("https://api.x/a")).de_cache is False  # o mais antigo saiu para caber o terceiro
    assert rotas["a"].call_count == 2


async def test_resposta_grande_demais_para_o_cache_nao_e_guardada(respx_mock, monkeypatch):
    monkeypatch.setattr(modulo_rede, "TETO_DO_CACHE_BYTES", 50)
    rota = respx_mock.get("https://api.x/grande").mock(return_value=httpx.Response(200, content=b"x" * 100))
    r = rede_sem_espera()
    await r.get("https://api.x/grande")
    await r.get("https://api.x/grande")
    assert rota.call_count == 2


async def test_cabecalhos_do_cache_nao_mudam_com_quem_os_le(respx_mock):
    respx_mock.get("https://api.x/h").mock(return_value=httpx.Response(200, headers={"x-a": "1"}))
    r = rede_sem_espera()
    (await r.get("https://api.x/h")).headers["x-a"] = "alterado"
    assert (await r.get("https://api.x/h")).headers["x-a"] == "1"


async def test_ua_de_api_neutro_com_proxy(monkeypatch):
    # com proxy (ou Tor) o UA padrão das APIs não pode dizer quem é o analista
    com_proxy = Rede(cfg(proxy="socks5://127.0.0.1:9050"))
    sem_proxy = Rede(cfg())
    escolhido = Rede(cfg(proxy="socks5://127.0.0.1:9050", ua_api="meu-ua/1.0"))
    assert com_proxy.ua_api == "radar/0.1"
    assert sem_proxy.ua_api == UA_API and escolhido.ua_api == "meu-ua/1.0"
    assert com_proxy.sessao().ua_api == "radar/0.1"
    for rede in (com_proxy, sem_proxy, escolhido):
        await rede.fechar()


# ---------------------------------------------------------------- teto do corpo (item barato da revisão final)


async def test_max_bytes_corta_a_leitura_e_e_erro_permanente(respx_mock):
    rota = respx_mock.get("https://api.x/enorme").mock(return_value=httpx.Response(200, content=b"x" * 5000))
    r = rede_sem_espera()
    with pytest.raises(ErroRede) as e:
        await r.get("https://api.x/enorme", max_bytes=1000)
    assert e.value.permanente is True and "corpo acima do teto de 1000 bytes" in str(e.value)
    assert rota.call_count == 1  # sem nova tentativa
    ok = await r.get("https://api.x/enorme", max_bytes=5000)
    assert len(ok.conteudo) == 5000 and ok.status == 200


async def test_max_bytes_conta_o_corpo_descomprimido(respx_mock):
    import gzip

    corpo = gzip.compress(b"a" * 20_000)  # pequeno na rede, grande na memória
    respx_mock.get("https://api.x/bomba").mock(
        return_value=httpx.Response(200, content=corpo, headers={"content-encoding": "gzip"})
    )
    with pytest.raises(ErroRede):
        await rede_sem_espera().get("https://api.x/bomba", max_bytes=10_000)
    ok = await rede_sem_espera().get("https://api.x/bomba", max_bytes=30_000)
    assert ok.conteudo == b"a" * 20_000
