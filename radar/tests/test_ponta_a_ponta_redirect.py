"""Ponta a ponta com redirect permanente (F5 da revisão final das melhorias do aceite): o caso do aceite de 08/10/2026,
com tudo o que a rodada mudou funcionando junto.

- `phinv.link` (o redirecionador) responde 302 para `phinvestimentos.com/index.html`. Os dois nomes resolvem para
  127.0.0.1 no Chromium (`--host-resolver-rules`); o servidor local responde pelo nome do `Host`.
- O destino é o site sintético com a marca "PH Investimentos" e, no `<script>` da home e de planos, um dicionário i18n
  e um payload do Next.js (`self.__next_f.push`), com um CNPJ de exemplo só no texto interno (11.444.777/0001-61).
- O domínio do destino foi registrado de novo (RDAP de 2026-09-29, certificado de 2020, Wayback desde 2014).
- A deliberação 905 de verdade foi editada para citar só o redirecionador (`https://phinv.link/`).
- Há uma execução anterior do `phinv.link`, gravada antes da T1 (sem o nó `destino`, com a página no destino): a seção 8
  do dossiê compara as duas.
- As APIs respondem pelo respx com `assert_all_mocked`: nada sai para a internet.

Variantes: na `v1` a página não mostra CNPJ nenhum e o único é o de exemplo, interno; na `v2` o rodapé de planos mostra o
CNPJ de verdade (11.222.333/0001-81) e o texto interno continua com o de exemplo.

O segundo teste faz o mesmo pelo servidor MCP no modo cego, como o Claude faria, e varre todas as saídas atrás do que
identifica o alvo. O ouro do `test_ponta_a_ponta.py` não muda: este arquivo não compara com ouro.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from radar import cli, mcp_server
from radar.config import Config, RedeConfig
from radar.custodia import verificar
from radar.dossie import gerar_dossie
from radar.execucao import criar_contexto, criar_indices, criar_servicos
from radar.indices import _CADASTROS, URL_CVM, URL_DELIBERACOES_PAGINAS, URL_DELIBERACOES_PARTIDA
from radar.mcp_server import criar_servidor
from radar.modelos import ErroNo, Resposta
from radar.motor import Motor
from radar.nos import captura as modulo_captura
from radar.nos import nos_do_nucleo
from radar.nos.captura import dominios_visitados
from radar.pendencias import validacao as modulo_validacao
from radar.pendencias.validacao import arquivar_fonte, validar
from radar.pontuacao import carregar_matriz
from radar.rede import Rede
from tests.execucao_em_disco import antes_da_t1, gravar, saidas_base
from tests.mocks_cvm import URL_SANCIONADOR, fixture_bytes, mocar_olinda
from tests.test_ponta_a_ponta import URL_DOCUMENTO_905, URL_INVOLUCRO_905, _zip, respostas_roteirizadas

SITE = Path(__file__).parent / "fixtures" / "site_sintetico"
ALVO = "phinv.link"
DESTINO = "phinvestimentos.com"
CNPJ_REAL = "11222333000181"
CNPJ_EXEMPLO = "11444777000161"
IP_DESTINO = "104.21.32.5"
IP_REDIRECIONADOR = "172.67.140.9"
AGORA = datetime(2026, 10, 11, 12, 0, 0)
AS_OF = AGORA.date()
ANTES_DA_T1 = datetime(2026, 10, 8, 17, 51, 2)  # a execução do aceite, gravada antes da rodada

URL_RDAP = f"https://rdap.org/domain/{DESTINO}"
URL_DOH = "https://cloudflare-dns.com/dns-query"
URL_CRTSH = "https://crt.sh/"
URL_CDX = "https://web.archive.org/cdx/search/cdx"
URL_BRASILAPI = f"https://brasilapi.com.br/api/cnpj/v1/{CNPJ_REAL}"
RECUSA_DO_ALVO = "fonte recusada: o alvo só é acessado pela captura; cite o sha256 da captura ou o snapshot do Wayback"

lento = pytest.mark.lento  # abre o Chromium de verdade, só contra 127.0.0.1

I18N = (
    '<script>window.__I18N__={"saque.backend.bloqueado":"Saques de rendimento estão bloqueados.",'
    '"indicacao.bonus":"bônus de indicação ({nivel}º nível)",'
    '"cadastro.cnpj.ajuda":"Informe o CNPJ da sua empresa, por exemplo 11.444.777/0001-61",'
    '"inicio.boas_vindas":"Bem-vindo à PH Investimentos, acesse phinvestimentos.com/app",'
    '"suporte.contato":"Fale com o suporte em suporte@phinvestimentos.com ou em phinv.link/ajuda",'
    '"saldo.rende":"Seu saldo rende 2% ao dia enquanto o plano estiver ativo"};</script>'
    '<script>self.__next_f.push([1,"{\\"deposito.desativado\\":\\"Depósitos estão temporariamente desativados.\\"}"])'
    "</script>"
)
INDEX = (
    "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
    "<title>PH Investimentos - rendimento garantido</title></head><body>"
    "<h1>PH Investimentos</h1>"
    "<p>Plataforma de investimentos com rendimento garantido todos os dias. Conheça os nossos planos, convide amigos e "
    "comece a lucrar ainda hoje, sem burocracia e sem risco.</p>"
    "<p>Já são 12 mil investidores e 8 escritórios novos abertos este ano.</p>"
    "<nav><a href='termos.html'>Termos de uso</a> <a href='planos.html'>Planos</a> <a href='contato.html'>Contato</a></nav>"
    f"{I18N}</body></html>"
)


def _site(pasta: Path, variante: str) -> None:
    """O site sintético com a marca do destino; a `v1` tira o CNPJ visível do rodapé de planos."""
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "index.html").write_bytes(INDEX.encode("utf-8"))
    planos = (SITE / "planos.html").read_text(encoding="utf-8").replace("InvestMax Brasil", "PH Investimentos")
    planos = planos.replace("a InvestMax aluga", "a PH Investimentos aluga")
    if variante == "v1":
        planos = planos.replace(" CNPJ 11.222.333/0001-81", "")
    (pasta / "planos.html").write_bytes((planos + I18N).encode("utf-8"))
    for nome in ("termos.html", "contato.html"):
        texto = (SITE / nome).read_text(encoding="utf-8").replace("InvestMax Brasil", "PH Investimentos")
        (pasta / nome).write_bytes(texto.encode("utf-8"))


class _DoisNomes(SimpleHTTPRequestHandler):
    """Responde pelo nome do `Host`: o redirecionador dá 302 para o destino, o destino serve o site."""

    def do_GET(self) -> None:
        host = (self.headers.get("Host") or "").rpartition(":")[0]
        self.server.pedidos.append((host, self.path))
        if host == ALVO:
            self.send_response(302)
            self.send_header("Location", f"http://{DESTINO}:{self.server.server_port}/index.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if host != DESTINO:
            self.send_error(404)
            return
        super().do_GET()

    def log_message(self, *a) -> None:
        pass


@pytest.fixture
def servidor(tmp_path, monkeypatch, request):
    variante = request.param
    pasta_site = tmp_path / "site"
    _site(pasta_site, variante)
    regras = f"--host-resolver-rules=MAP {ALVO} 127.0.0.1, MAP {DESTINO} 127.0.0.1"
    monkeypatch.setattr(modulo_captura, "ARGS_DO_NAVEGADOR", (*modulo_captura.ARGS_DO_NAVEGADOR, regras))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(_DoisNomes, directory=str(pasta_site)))
    srv.daemon_threads = True
    srv.pedidos = []
    srv.variante = variante
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------------------- APIs (respx)

_TIPOS = {"A": 1, "AAAA": 28, "MX": 15, "NS": 2, "TXT": 16}
_DNS = {
    DESTINO: {"A": [IP_DESTINO], "NS": ["ns1.hospedagem.example.", "ns2.hospedagem.example."],
              "MX": ["10 mx.phinvestimentos.com."]},
    ALVO: {"A": [IP_REDIRECIONADOR]},
}  # fmt: skip
RDAP = {
    "objectClassName": "domain",
    "ldhName": DESTINO.upper(),
    "events": [
        {"eventAction": "registration", "eventDate": "2026-09-29T18:22:10Z"},
        {"eventAction": "expiration", "eventDate": "2027-09-29T18:22:10Z"},
    ],
    "entities": [
        {
            "objectClassName": "entity",
            "roles": ["registrar"],
            "vcardArray": ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "Registrador Exemplo LLC"]]],
        }
    ],
}
CRTSH = [
    {"issuer_name": "C=US, O=Let's Encrypt, CN=R3", "common_name": DESTINO, "name_value": DESTINO, "id": 1,
     "not_before": "2020-11-11T00:00:00", "not_after": "2021-02-09T00:00:00", "serial_number": "01"},
    {"issuer_name": "C=US, O=Let's Encrypt, CN=R11", "common_name": DESTINO,
     "name_value": f"{DESTINO}\nwww.{DESTINO}\napp.{DESTINO}", "id": 2,
     "not_before": "2026-09-30T00:00:00", "not_after": "2026-12-29T00:00:00", "serial_number": "02"},
]  # fmt: skip
BRASILAPI = {
    "cnpj": CNPJ_REAL,
    "razao_social": "PH INVESTIMENTOS INTERMEDIACAO DE NEGOCIOS LTDA",
    "nome_fantasia": "PH INVESTIMENTOS",
    "data_inicio_atividade": "2024-10-08",
    "cnae_fiscal": 6619399,
    "cnae_fiscal_descricao": "Outras atividades auxiliares dos serviços financeiros",
    "capital_social": 10000,
    "situacao_cadastral": 2,
    "descricao_situacao_cadastral": "ATIVA",
    "natureza_juridica": "Sociedade Empresária Limitada",
    "porte": "MICRO EMPRESA",
    "identificador_matriz_filial": 1,
    "uf": "SP",
    "municipio": "SAO PAULO",
    "cnaes_secundarios": [],
    "qsa": [{"nome_socio": "FULANO FICTICIO DE TAL", "qualificacao_socio": "Sócio-Administrador",
             "cnpj_cpf_do_socio": "***123456**", "data_entrada_sociedade": "2024-10-08"}],
}  # fmt: skip


class _Apis:
    """As rotas do respx e os pedidos ao DoH e ao CDX, para conferir o domínio que cada coletor consultou."""

    def __init__(self, respx_mock) -> None:
        self.doh: list[tuple[str, str]] = []
        self.cdx: list[dict] = []
        respx_mock.get(URL_RDAP).mock(return_value=httpx.Response(200, json=RDAP))
        respx_mock.get(URL_DOH).mock(side_effect=self._doh)
        respx_mock.get(URL_CRTSH, params={"q": DESTINO, "output": "json"}).mock(
            return_value=httpx.Response(200, json=CRTSH)
        )
        respx_mock.get(URL_CDX).mock(side_effect=self._cdx)
        respx_mock.get(URL_BRASILAPI).mock(return_value=httpx.Response(200, json=BRASILAPI))
        for _, caminho, arquivo in _CADASTROS:
            respx_mock.get(URL_CVM + caminho).mock(
                return_value=_zip({arquivo: "CNPJ;DENOM_SOCIAL;DENOM_COMERC;DT_REG;DT_CANCEL;SIT;DT_INI_SIT\r\n"})
            )
        respx_mock.get(URL_SANCIONADOR).mock(
            return_value=_zip(
                {
                    "processo_sancionador.csv": "NUP;Objeto;Ementa;Data_Abertura;Fase_Atual\r\n",
                    "processo_sancionador_acusado.csv": "NUP;Nome_Acusado;Situacao\r\n",
                }
            )
        )
        mocar_olinda(respx_mock)
        html = {"content-type": "text/html;charset=UTF-8"}
        pagina = (
            "<span>1 resultado encontrado</span><span>Páginas 1/1</span>"
            '<a href="/legislacao/deliberacoes/deli0900/deli905.html">Deliberação CVM 905</a>'
        )
        respx_mock.get(URL_DELIBERACOES_PARTIDA).mock(return_value=httpx.Response(200, text="<html></html>"))
        respx_mock.get(URL_DELIBERACOES_PAGINAS).mock(
            return_value=httpx.Response(200, content=pagina.encode(), headers=html)
        )
        respx_mock.get(URL_INVOLUCRO_905).mock(
            return_value=httpx.Response(200, content=fixture_bytes("deli905.html"), headers=html)
        )
        # a 905 de verdade com um dos sites trocado pelo redirecionador: ela cita só o `phinv.link`
        deli905 = fixture_bytes("deli905.htm").replace(b"https://santotrader.me/", b"https://phinv.link/")
        respx_mock.get(URL_DOCUMENTO_905).mock(return_value=httpx.Response(200, content=deli905, headers=html))

    def _doh(self, request: httpx.Request) -> httpx.Response:
        nome, tipo = request.url.params["name"], request.url.params["type"]
        self.doh.append((nome, tipo))
        codigo = _TIPOS[tipo]
        corpo: dict = {"Status": 0, "Question": [{"name": nome, "type": codigo}]}
        if registros := _DNS.get(nome, {}).get(tipo):
            corpo["Answer"] = [{"name": nome, "type": codigo, "TTL": 300, "data": d} for d in registros]
        return httpx.Response(200, json=corpo)

    def _cdx(self, request: httpx.Request) -> httpx.Response:
        self.cdx.append(dict(request.url.params))
        if request.url.params.get("matchType") != "domain" or request.url.params.get("url") != DESTINO:
            return httpx.Response(500, text="consulta inesperada ao CDX")
        linhas = [["20140927101500", f"http://{DESTINO}/"], ["20190301000000", f"http://www.{DESTINO}/"],
                  ["20261001120000", f"https://{DESTINO}/login"]]  # fmt: skip
        return httpx.Response(200, json=[["timestamp", "original"], *linhas])


async def _ip_publico(host: str, timeout: float):
    import ipaddress

    return [ipaddress.ip_address("93.184.216.34")]


def _execucao_antes_da_t1(casos: Path) -> Path:
    """A execução do aceite como foi gravada antes da rodada: o mesmo alvo, a página no destino, sem o nó `destino`."""
    captura = {**saidas_base()["captura"], "paginas": [{"url": f"https://{DESTINO}/login", "status": 200}]}
    return antes_da_t1(gravar(casos, agora=ANTES_DA_T1, slug="phinv-link", alvo=ALVO, saidas={"captura": captura}))


def _evidencia(fonte: str, trecho: str) -> dict:
    return {"fonte": fonte, "trecho": trecho, "data_fonte": AS_OF.isoformat(), "tipo_fonte": "operador"}


def _texto_da_pagina(captura: dict, caminho: str) -> str:
    (pagina,) = [p for p in captura["paginas"] if httpx.URL(p["url"]).path == caminho]
    return pagina["texto"]


def _cli(config: Config, monkeypatch, capsys, *args: str) -> int:
    monkeypatch.setattr(cli, "carregar_config", lambda: config)
    codigo = cli.main(list(args))
    capsys.readouterr()
    return codigo


# ---------------------------------------------------------------------------- 1. o motor, o dossiê e o CLI


@lento
@pytest.mark.parametrize("servidor", ["v1", "v2"], indirect=True)
@pytest.mark.respx(assert_all_mocked=True, assert_all_called=False)
async def test_ponta_a_ponta_com_redirect(respx_mock, servidor, tmp_path, monkeypatch, capsys):
    apis = _Apis(respx_mock)
    variante = servidor.variante
    casos = tmp_path / "casos"
    _execucao_antes_da_t1(casos)
    config = Config(rede=RedeConfig(limites={"*": 0}), casos_dir=casos)
    matriz = carregar_matriz()
    porta = servidor.server_port
    ctx = criar_contexto(ALVO, None, "captura", False, config.casos_dir, AGORA)
    ctx = ctx.model_copy(update={"url_inicial": f"http://{ALVO}:{porta}/"})
    rede = Rede(config.rede)
    try:
        servicos = criar_servicos(config, ctx.pasta, rede, criar_indices(config, rede), matriz)
        motor = Motor(ctx, nos_do_nucleo(), servicos)
        await motor.executar()
        destino, captura = motor.saidas("destino"), motor.saidas("captura")

        # os coletores analisam o destino; do redirecionador, só o A e o AAAA por DoH
        url_destino = f"http://{DESTINO}:{porta}/index.html"
        assert destino == {"dominio": DESTINO, "redirecionado_de": ALVO, "url_destino": url_destino}
        assert captura["saltos"] == [f"http://{ALVO}:{porta}/"]
        assert {n for n, _ in apis.doh} == {DESTINO, ALVO}
        assert {t for n, t in apis.doh if n == ALVO} == {"A", "AAAA"}
        assert apis.cdx and all(p.get("url") == DESTINO for p in apis.cdx)
        assert motor.saidas("rdap")["registro"] == "2026-09-29"
        assert motor.saidas("ct")["primeiro_certificado"].startswith("2020-11-11")
        # só a captura tocou o site: o redirecionador recebeu só a visita inicial
        assert [caminho for host, caminho in servidor.pedidos if host == ALVO] == ["/"]
        assert captura["terceiros"] == []

        # o texto interno: candidatos no fim da lista e o artefato .txt, sem HTML
        extracao = motor.saidas("extracao")
        internos = [c for c in extracao["candidatos"] if c["extra"].get("origem") == "texto_interno"]
        assert internos and extracao["candidatos"][-len(internos) :] == internos
        for ref in {c["artefato"] for c in internos}:
            texto = servicos.custodia.ler(ref).decode("utf-8")
            assert "Saques de rendimento estão bloqueados." in texto
            assert "Depósitos estão temporariamente desativados." in texto
            assert "<" not in texto
        assert ("cnpj", CNPJ_EXEMPLO) in {(c["categoria"], c["valor"]) for c in internos}

        # o CNPJ de exemplo não é escolhido sozinho: a P-CNPJ abre com ele marcado como interno
        abertas = {p.id: p for p in motor.pendencias_abertas()}
        assert "P-CNPJ" in abertas and "P-A2" not in abertas
        por_valor = {c.valor: c for c in abertas["P-CNPJ"].candidatos}
        assert por_valor[CNPJ_EXEMPLO].extra.get("origem") == "texto_interno"
        if variante == "v2":
            assert por_valor[CNPJ_REAL].extra.get("origem") != "texto_interno"
        assert motor.status()["cnpj"] == "aguardando"

        # as respostas: a P-CNPJ conforme a variante (v1: null em nao_encontrado) e o roteiro do ponta a ponta
        planos = _texto_da_pagina(captura, "/planos.html")
        roteiro = respostas_roteirizadas(planos, _texto_da_pagina(captura, "/index.html"))
        if variante == "v2":
            roteiro["P-CNPJ"] = {"status": "confirmado", "valor": {"cnpj": CNPJ_REAL},
                                 "evidencias": [_evidencia(planos, "CNPJ 11.222.333/0001-81")]}  # fmt: skip
        else:
            roteiro["P-CNPJ"] = {"status": "nao_encontrado", "valor": None,
                                 "onde_procurou": ["rodapé", "termos", "texto interno: só o exemplo do cadastro"]}  # fmt: skip
        dns = motor.saidas("dns")
        ips = {*dns["A"], *dns["AAAA"], *dns["redirecionador"]["A"], *dns["redirecionador"]["AAAA"]}
        do_site = {destino["dominio"], *dominios_visitados(captura, ALVO)}
        respondidas: list[str] = []
        while abertas_agora := motor.pendencias_abertas():
            assert len(respondidas) < 20, respondidas
            pendencia = abertas_agora[0]
            internos_p = [c for c in pendencia.candidatos if c.extra.get("origem") == "texto_interno"]
            if internos_p:
                assert ", texto interno]" in pendencia.conteudo_do_alvo
            bruta = roteiro.get(pendencia.id, {"status": "nao_encontrado", "onde_procurou": ["busca roteirizada"]})
            resposta = Resposta.model_validate(bruta)
            v = await validar(resposta, pendencia, motor.ctx, servicos, ips_do_alvo=ips, dominio_destino=do_site)
            assert v.aceita, (pendencia.id, v.motivo, v.campo)
            await motor.responder(pendencia.id, resposta, marcas=v.marcas)
            respondidas.append(pendencia.id)
        # a deliberação que cita só o redirecionador casa (R-A-T1-cvm)
        correspondencias = motor.saidas("cvm_alertas")["correspondencias"]
        assert ("dominio", ALVO) in {(c["tipo"], c["valor"]) for c in correspondencias}
        if variante == "v1":
            assert motor.saidas("cnpj").get("cnpj") is None

        # opsec: o destino, o redirecionador, os IPs dos dois e os encurtadores que levam a eles são recusados
        monkeypatch.setattr(modulo_validacao, "_enderecos_do_nome", _ip_publico)
        respx_mock.get("https://encurtador.example/abc").mock(
            return_value=httpx.Response(302, headers={"location": f"https://app.{DESTINO}/termos"})
        )
        respx_mock.get("https://encurtador.example/redir").mock(
            return_value=httpx.Response(302, headers={"location": f"http://{IP_REDIRECIONADOR}/"})
        )
        for url in (
            f"https://{DESTINO}/termos", f"https://APP.{DESTINO.upper()}:8443/x", f"https://www.{DESTINO}./",
            f"https://{ALVO}/ajuda", f"http://{IP_DESTINO}/", f"http://{IP_REDIRECIONADOR}/",
            f"http://[::ffff:{IP_DESTINO}]/", "https://encurtador.example/abc", "https://encurtador.example/redir",
        ):  # fmt: skip
            with pytest.raises(ErroNo) as erro:
                await arquivar_fonte(url, motor.ctx, servicos, ips_do_alvo=ips, dominio_destino=do_site)
            assert erro.value.mensagem == RECUSA_DO_ALVO, url
        evidencia = Resposta.model_validate(
            {"status": "inconclusivo", "evidencias": [_evidencia(f"https://{DESTINO}/termos", "taxa de saque de 8%")]}
        )
        pendencia_e = motor._pendencias["P-E"]
        v = await validar(evidencia, pendencia_e, motor.ctx, servicos, ips_do_alvo=ips, dominio_destino=do_site)
        assert (v.aceita, v.motivo) == (False, RECUSA_DO_ALVO)
    finally:
        await rede.fechar()

    # o dossiê: o redirect, o domínio reaproveitado, a deliberação do redirecionador e o diff com a execução antiga
    dossie = gerar_dossie(ctx.pasta, matriz).read_bytes().decode("utf-8")
    pontuacao = json.loads((ctx.pasta / "pontuacao.json").read_bytes())
    assert f"**Redirecionamento:** {ALVO} → `{url_destino}`; os coletores analisaram {DESTINO}" in dossie
    d3 = pontuacao["itens"]["D3"]["nota"]
    assert "domínio registrado de novo em 2026-09-29" in d3 and "2014-09-27 (Wayback)" in d3
    assert dossie.count("Atenção: antes de 2026-09-29, o domínio tinha outro registro (possível outro dono).") == 2
    assert "(registro anterior do domínio)" in dossie
    assert "cita o domínio phinv.link" in pontuacao["itens"]["C4"]["nota"]
    diff_md = (ctx.pasta / "diff.md").read_bytes().decode("utf-8")
    assert f"domínio analisado mudou: {ALVO} → {DESTINO}" in diff_md
    assert "Capturas novas no Wayback: não comparável (domínio analisado mudou)" in diff_md

    # o CLI: a custódia íntegra e o diff entre a execução antiga e a nova
    assert _cli(config, monkeypatch, capsys, "verificar", ctx.run_id) == 0 and verificar(ctx.pasta) == []
    assert _cli(config, monkeypatch, capsys, "diff", "phinv-link") == 0


# ---------------------------------------------------------------------------- 2. o modo cego pelo MCP

_VAZAMENTO = re.compile(
    r"phinv|ph\s*investimentos|11[\s./-]?444[\s./-]?777|11[\s./-]?222[\s./-]?333|fulano\s+ficticio|"
    + re.escape(IP_DESTINO) + "|" + re.escape(IP_REDIRECIONADOR),
    re.IGNORECASE,
)  # fmt: skip


async def _chamar(srv, nome: str, **args):
    r = await srv.call_tool(nome, args)
    assert not r.is_error, r
    if any(b.type == "image" for b in r.content):
        return {"_imagem": True}
    return json.loads(r.content[0].text)


@lento
@pytest.mark.parametrize("servidor", ["v1", "v2"], indirect=True)
@pytest.mark.respx(assert_all_mocked=True, assert_all_called=False)
async def test_modo_cego_com_redirect_e_texto_interno(respx_mock, servidor, tmp_path, monkeypatch):
    _Apis(respx_mock)
    variante = servidor.variante
    monkeypatch.setattr(mcp_server, "ESPERA_S", 5)
    monkeypatch.setattr(modulo_validacao, "_enderecos_do_nome", _ip_publico)
    srv = criar_servidor(Config(rede=RedeConfig(limites={"*": 0}), casos_dir=tmp_path / "casos"))
    saidas: list[tuple[str, object]] = []

    def guardar(rotulo: str, valor):
        saidas.append((rotulo, valor))
        return valor

    async with srv.settings.lifespan(srv):
        alvo = f"http://{ALVO}:{servidor.server_port}/"
        run_id = guardar("iniciar", await _chamar(srv, "iniciar_analise", alvo=alvo, modo_cego=True))["run_id"]
        assert run_id.startswith("cego-")
        for _ in range(60):
            st = guardar("status", await _chamar(srv, "status", run_id=run_id))
            if not st.get("em_andamento") and st.get("pendencias_abertas"):
                break
        # o destino e o redirecionador: recusados sem dizer que são o alvo
        for url in (f"https://{DESTINO}/termos", f"https://{ALVO}/"):
            r = guardar("arquivar", await _chamar(srv, "arquivar_fonte", run_id=run_id, url=url))
            assert r == {"erro": "fonte recusada: domínio não permitido"}, (url, r)
        vistas: set[str] = set()
        respondidas: list[str] = []
        for _ in range(25):
            lista = guardar("listar", await _chamar(srv, "listar_pendencias", run_id=run_id))
            ids = [p["id"] for p in lista["pendencias"]]
            if not ids:
                break
            pid = ids[0]
            p = guardar(f"ver_pendencia {pid}", await _chamar(srv, "ver_pendencia", run_id=run_id, id=pid))
            if p.get("em_andamento") and "id" not in p:
                await _chamar(srv, "status", run_id=run_id)
                continue
            for c in p.get("candidatos", []):
                ref = c.get("artefato")
                if isinstance(ref, str) and ref.startswith("sha256:") and ref not in vistas:
                    vistas.add(ref)
                    guardar(f"ver_artefato {ref[:20]}", await _chamar(srv, "ver_artefato", run_id=run_id, sha256=ref))
            if pid == "P-CNPJ" and variante == "v2":
                # o candidato visível, pelo token que o Claude vê
                visivel = next(c for c in p["candidatos"] if c.get("extra", {}).get("origem") != "texto_interno")
                evidencia = {"fonte": visivel["artefato"], "trecho": visivel["trecho"].strip()[:40],
                             "data_fonte": AS_OF.isoformat(), "tipo_fonte": "operador"}  # fmt: skip
                resposta = {"status": "confirmado", "valor": {"cnpj": visivel["valor"]}, "evidencias": [evidencia]}
            elif pid == "P-CNPJ":
                resposta = {"status": "nao_encontrado", "valor": None, "onde_procurou": ["texto interno"]}
            else:
                resposta = {"status": "nao_encontrado", "onde_procurou": ["busca roteirizada"]}
            if pid == "P-E":  # a evidência no destino é recusada, com a mensagem neutra
                no_destino = {"status": "inconclusivo",
                              "evidencias": [_evidencia(f"https://{DESTINO}/termos", "taxa de saque de 8%")]}  # fmt: skip
                r = guardar("responder destino", await _chamar(srv, "responder_pendencia", run_id=run_id, id=pid,
                                                                resposta=no_destino))  # fmt: skip
                assert (r["aceita"], r["motivo"]) == (False, "fonte recusada: domínio não permitido"), r
            r = guardar(f"responder {pid}", await _chamar(srv, "responder_pendencia", run_id=run_id, id=pid,
                                                          resposta=resposta))  # fmt: skip
            assert r.get("aceita") is not False, (pid, r)
            respondidas.append(pid)
            for _ in range(20):
                if not guardar("status", await _chamar(srv, "status", run_id=run_id)).get("em_andamento"):
                    break
        assert "P-CNPJ" in respondidas
        guardar("dossie", await _chamar(srv, "gerar_dossie", run_id=run_id, forcar=False))
        guardar("casos", await _chamar(srv, "listar_casos"))
        guardar("comparar", await _chamar(srv, "comparar_execucoes", alvo=run_id.split("/")[0]))

    vazamentos = []
    for rotulo, valor in saidas:
        texto = json.dumps(valor, ensure_ascii=False)
        for m in _VAZAMENTO.finditer(texto):
            vazamentos.append(f"{rotulo}: ...{texto[max(0, m.start() - 80) : m.end() + 80]}...")
    assert not vazamentos, vazamentos[:5]
    # o texto interno chegou ao Claude mascarado
    artefatos = [json.dumps(v, ensure_ascii=False) for r, v in saidas if r.startswith("ver_artefato")]
    assert any("bloqueados" in a and "[ALVO]" in a for a in artefatos)
