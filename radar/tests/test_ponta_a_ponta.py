"""Ponta a ponta (Tarefa 18): a pirâmide sintética passa por todos os nós reais e o dossiê sai igual ao ouro.

- O site é o `servidor_local` (127.0.0.1). O `normalizar_alvo` recusa IP: o contexto é criado para
  `piramide-sintetica.com.br` e só a `url_inicial` aponta para o servidor local (R-T18-contexto). O Chromium visita só
  127.0.0.1.
- As APIs (RDAP, DoH, crt.sh, CDX, BrasilAPI, CVM, BCB) respondem pelo respx, com `assert_all_mocked` (nada sai para
  a internet) e `assert_all_called` (toda rota mocada é usada). Com a captura ok, o `wayback_snapshot` fica pulado e
  só o `wayback_indice` consulta o CDX.
- Cada pendência recebe a resposta roteirizada, que cita o texto das páginas capturadas (`sha256:` da custódia) e
  passa por `validar`, como no servidor MCP, antes de `motor.responder`. O fluxo MCP é coberto pelos testes da T16 e
  por `test_mcp_stdio.py`.
- O dossiê é comparado com `ouro/dossie_sintetico.md` depois de `normalizar_dossie` (porta, caminhos, `run_id`,
  data e hora da execução, hashes e a ordem do anexo, que depende de quem gravou antes na custódia entre os nós que
  rodam juntos). Para regravar o ouro depois de uma mudança intencional no dossiê:
  `RADAR_GRAVAR_OURO=1 .venv/Scripts/python -m pytest tests/test_ponta_a_ponta.py`, e revise o diff do arquivo à mão.
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from radar.config import Config, RedeConfig
from radar.custodia import verificar
from radar.dossie import gerar_dossie
from radar.execucao import criar_contexto, criar_indices, criar_servicos
from radar.indices import _CADASTROS, URL_CVM, URL_DELIBERACOES_PAGINAS, URL_DELIBERACOES_PARTIDA
from radar.modelos import Resposta
from radar.motor import Motor
from radar.nos import nos_do_nucleo
from radar.pendencias.validacao import validar
from radar.pontuacao import carregar_matriz
from radar.rede import Rede
from tests.mocks_cvm import URL_SANCIONADOR, fixture_bytes, mocar_olinda

ALVO = "piramide-sintetica.com.br"
CNPJ = "11222333000181"
AGORA = datetime(2026, 10, 8, 12, 0, 0)
AS_OF = AGORA.date()
FIXTURES = Path(__file__).parent / "fixtures" / "ponta_a_ponta"
OURO = Path(__file__).parent / "ouro" / "dossie_sintetico.md"

URL_RDAP = f"https://rdap.registro.br/domain/{ALVO}"
URL_DOH = "https://cloudflare-dns.com/dns-query"
URL_CRTSH = "https://crt.sh/"
URL_CDX = "https://web.archive.org/cdx/search/cdx"
URL_BRASILAPI = f"https://brasilapi.com.br/api/cnpj/v1/{CNPJ}"
URL_INVOLUCRO_905 = "https://conteudo.cvm.gov.br/legislacao/deliberacoes/deli0900/deli905.html"
URL_DOCUMENTO_905 = "https://conteudo.cvm.gov.br/legislacao/deliberacoes/anexos/0900/deli905.htm"

# status final de cada nó: tudo feito, menos o snapshot (a captura deu certo) e a P-A2 (sem histórico na página)
STATUS_FINAL = {
    "alvo": "feito", "destino": "feito", "rdap": "feito", "dns": "feito", "ct": "feito", "wayback_indice": "feito", "captura": "feito",
    "wayback_snapshot": "pulado", "extracao": "feito", "cnpj": "feito", "registros": "feito",
    "cvm_sancionador": "feito", "cvm_alertas": "feito", "pend_a1": "feito", "pend_a2": "pulado", "pend_a3": "feito",
    "pend_b": "feito", "pend_c": "feito", "pend_c4": "feito", "pend_d1": "feito", "pend_d4": "feito",
    "pend_e": "feito",
}  # fmt: skip
# (estado, pontos) de cada item: a tabela da Tarefa 18, refeita com as decisões vigentes
ITENS_ESPERADOS = {
    "A1": ("confirmado", 4), "A2": ("nao_se_aplica", 0), "A3": ("confirmado", 2), "B1": ("confirmado", 2),
    "B2": ("nao_se_aplica", 0), "B3": ("confirmado", 1), "B4": ("nao_se_aplica", 0), "C1": ("confirmado", 3),
    "C2": ("confirmado", 2), "C3": ("nao_se_aplica", 0), "C4": ("nao_encontrado", 0), "D1": ("nao_encontrado", 0),
    "D2": ("nao_verificado", 0), "D3": ("confirmado", 1), "D4": ("nao_encontrado", 0),
}  # fmt: skip


# ---------------------------------------------------------------------------- APIs (respx)


def _api(nome: str):
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


_TIPOS_DNS = {"A": 1, "AAAA": 28, "MX": 15, "NS": 2, "TXT": 16}
_REGISTROS_DNS = {"A": ["203.0.113.50"], "NS": ["ns1.hospedagem.example.", "ns2.hospedagem.example."]}


def _doh(request: httpx.Request) -> httpx.Response:
    tipo = request.url.params["type"]
    codigo = _TIPOS_DNS[tipo]
    corpo: dict = {"Status": 0, "TC": False, "RD": True, "RA": True, "Question": [{"name": ALVO, "type": codigo}]}
    if registros := _REGISTROS_DNS.get(tipo):
        corpo["Answer"] = [{"name": ALVO, "type": codigo, "TTL": 300, "data": dado} for dado in registros]
    return httpx.Response(200, json=corpo)


def _cdx(request: httpx.Request) -> httpx.Response:
    # só a listagem do domínio (wayback_indice): com a captura ok, o wayback_snapshot não lista a home
    if request.url.params.get("matchType") != "domain":
        return httpx.Response(500, text="consulta inesperada ao CDX")
    return httpx.Response(200, json=_api("cdx_dominio"))


def _zip(arquivos: dict[str, str]) -> httpx.Response:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for nome, conteudo in arquivos.items():
            zf.writestr(nome, conteudo.encode("latin-1"))
    return httpx.Response(200, content=buffer.getvalue(), headers={"content-type": "application/zip"})


def _mocar_apis(respx_mock) -> None:
    respx_mock.get(URL_RDAP).mock(return_value=httpx.Response(200, json=_api("rdap")))
    respx_mock.get(URL_DOH).mock(side_effect=_doh)
    respx_mock.get(URL_CRTSH, params={"q": ALVO, "output": "json"}).mock(
        return_value=httpx.Response(200, json=_api("crtsh"))
    )
    respx_mock.get(URL_CDX).mock(side_effect=_cdx)
    respx_mock.get(URL_BRASILAPI).mock(return_value=httpx.Response(200, json=_api("brasilapi")))


def _mocar_indices(respx_mock) -> None:
    """As quatro listagens da CVM e o processo sancionador só com o cabeçalho, as sedes e os domínios do BCB sem a
    raiz 11222333 (as respostas gravadas) e a busca de deliberações com uma página e uma deliberação, que não cita a
    empresa."""
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
    respx_mock.get(URL_DOCUMENTO_905).mock(
        return_value=httpx.Response(200, content=fixture_bytes("deli905.htm"), headers=html)
    )


# ---------------------------------------------------------------------------- respostas roteirizadas


def _evidencia(fonte: str, trecho: str, *itens: str) -> dict:
    """A evidência citada; `itens`, os itens que ela sustenta (I3: na P-B e na P-C cada item cita a sua)."""
    evidencia = {"fonte": fonte, "trecho": trecho, "data_fonte": AS_OF.isoformat(), "tipo_fonte": "operador"}
    return {**evidencia, "itens": list(itens)} if itens else evidencia


def respostas_roteirizadas(planos: str, inicio: str) -> dict[str, dict]:
    """As respostas da Tarefa 18. `planos` e `inicio` são as refs `sha256:` do texto de `planos.html` e da página
    inicial capturadas; cada trecho é literal delas."""
    return {
        "P-A1": {
            "status": "confirmado",
            "valor": {"pct_mes": 56.308, "taxa_diaria": True, "garantido": True},
            "evidencias": [_evidencia(planos, "Rendimento de 1,5% ao dia garantido", "A1")],
        },
        "P-A3": {
            "status": "confirmado",
            "valor": {"origem_verificavel": False, "custodiante_independente": False},
            "evidencias": [_evidencia(planos, "aluga as suas moedas para operações de arbitragem", "A3")],
        },
        "P-B": {
            "status": "confirmado",
            "valor": {
                "indicacao": "indicacao_remunerada",
                "token_proprio": False,
                "carencia_com_multa": True,
                "taxa_para_sacar": False,
            },
            "evidencias": [
                _evidencia(planos, "bônus de indicação em 3 níveis", "B1"),
                _evidencia(planos, "carência de 12 meses e multa de 30% no resgate antecipado", "B3"),
            ],
        },
        "P-C": {
            "status": "confirmado",
            "valor": {
                "contrato_atipico": True,
                "tipo_contrato": "locacao_cripto",
                "conta_pf_ou_terceiro": False,
                "offshore_alegado": False,
            },
            "evidencias": [_evidencia(planos, "O contrato é de aluguel de criptomoedas", "C2")],
        },
        # sem alerta e sem figura pública: procurado e não achado (não "confirmado" com valor falso)
        "P-C4": {"status": "nao_encontrado", "onde_procurou": ["I-SCAN", "CVM", "busca roteirizada"]},
        "P-D1": {"status": "nao_encontrado", "onde_procurou": ["busca roteirizada"]},
        "P-D4": {"status": "nao_encontrado", "onde_procurou": ["páginas do site", "busca roteirizada"]},
        "P-E": {
            "status": "confirmado",
            "valor": {
                "sinais": [
                    {"tipo": "saques_funcionando", "data": AS_OF.isoformat(), "evidencia": 0},
                    {"tipo": "expansao_acelerada", "data": AS_OF.isoformat(), "evidencia": 1},
                ],
                "modificadores": [],
            },
            "evidencias": [
                _evidencia(planos, "Saques pagos em até 24 horas"),
                _evidencia(inicio, "Já são 12 mil investidores e 8 escritórios novos"),
            ],
        },
    }


# a pendência sem resposta no roteiro: procurada e não achada
_SEM_ROTEIRO = {"status": "nao_encontrado", "onde_procurou": ["busca roteirizada"]}


# ---------------------------------------------------------------------------- dossiê normalizado

_PORTA = re.compile(r"(127\.0\.0\.1|localhost):\d+")
_HASH = re.compile(r"sha256:[0-9a-f]+")
_HEX = re.compile(r"\b[0-9a-f]{64}\b")
_RUN_ID = re.compile(r"[a-z0-9_-]+/\d{4}-\d{2}-\d{2}_\d{6}")
_DATA_HORA = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
_SEQ_DO_ANEXO = re.compile(r"^\| \d+ \|")
_ANEXO = "## 9. Anexo"


def normalizar_dossie(texto: str, pasta: Path) -> str:
    """O dossiê sem o que muda de uma execução para outra: caminhos, porta do servidor local, `run_id`, data e hora
    da execução e hashes (o HAR, o screenshot e os julgamentos mudam a cada vez). As linhas da tabela do anexo ficam
    sem o `seq` e em ordem alfabética: a ordem da custódia depende de qual nó gravou antes."""
    for caminho in {str(pasta), pasta.as_posix()}:
        texto = texto.replace(caminho, "<PASTA>")
    texto = _PORTA.sub(r"\1:<PORTA>", texto)
    texto = _HASH.sub("sha256:<HASH>", texto)
    texto = _HEX.sub("<HASH>", texto)
    texto = _RUN_ID.sub("<RUN_ID>", texto)
    texto = _DATA_HORA.sub("<DATA_HORA>", texto)
    antes, separador, anexo = texto.partition(_ANEXO)
    linhas = anexo.split("\n")
    tabela = [i for i, linha in enumerate(linhas) if _SEQ_DO_ANEXO.match(linha)]
    if tabela:
        ordenadas = sorted(_SEQ_DO_ANEXO.sub("| <SEQ> |", linhas[i]) for i in tabela)
        linhas[tabela[0] : tabela[-1] + 1] = ordenadas
    return antes + separador + "\n".join(linhas)


# ---------------------------------------------------------------------------- o teste


def _texto_da_pagina(captura: dict, caminho: str) -> str:
    """A ref `sha256:` do texto da página capturada cujo caminho é `caminho`."""
    (pagina,) = [p for p in captura["paginas"] if httpx.URL(p["url"]).path == caminho]
    return pagina["texto"]


@pytest.mark.lento
@pytest.mark.respx(assert_all_mocked=True, assert_all_called=True)
async def test_piramide_sintetica_ponta_a_ponta(respx_mock, servidor_local, pedidos_locais, tmp_path):
    _mocar_apis(respx_mock)
    _mocar_indices(respx_mock)
    config = Config(rede=RedeConfig(limites={"*": 0}), casos_dir=tmp_path / "casos")
    matriz = carregar_matriz()
    ctx = criar_contexto(ALVO, None, "captura", False, config.casos_dir, AGORA)
    ctx = ctx.model_copy(update={"url_inicial": servidor_local + "/"})
    rede = Rede(config.rede)
    try:
        servicos = criar_servicos(config, ctx.pasta, rede, criar_indices(config, rede), matriz)
        motor = Motor(ctx, nos_do_nucleo(), servicos)
        await motor.executar()
        assert sorted(p.id for p in motor.pendencias_abertas()) == [
            "P-A1", "P-B", "P-C", "P-C4", "P-D1", "P-D4", "P-E"
        ]  # fmt: skip
        captura = motor.saidas("captura")
        roteiro = respostas_roteirizadas(_texto_da_pagina(captura, "/planos.html"), _texto_da_pagina(captura, "/"))
        dns = motor.saidas("dns")
        ips_do_alvo = {*dns["A"], *dns["AAAA"]}

        respondidas = []
        while abertas := motor.pendencias_abertas():
            assert len(respondidas) < 20, f"pendências sem fim: {respondidas}"
            pendencia = abertas[0]
            resposta = Resposta.model_validate(roteiro.get(pendencia.id, _SEM_ROTEIRO))
            validacao = await validar(resposta, pendencia, motor.ctx, servicos, ips_do_alvo=ips_do_alvo)
            assert validacao.aceita, (pendencia.id, validacao.motivo, validacao.campo)
            assert validacao.marcas == []  # todo trecho conferido na fonte, toda evidência com data
            await motor.responder(pendencia.id, resposta, marcas=validacao.marcas)
            respondidas.append(pendencia.id)
    finally:
        await rede.fechar()

    # a P-A3 só abre depois da P-A1 (a promessa de retorno); a P-CNPJ nunca abre: o titular do RDAP é o CNPJ da página
    assert sorted(respondidas) == ["P-A1", "P-A3", "P-B", "P-C", "P-C4", "P-D1", "P-D4", "P-E"]
    assert motor.status() == STATUS_FINAL
    assert motor.saidas("cnpj")["cnpj"] == CNPJ
    assert motor.saidas("extracao")["fonte"] == "captura"
    # a página do site sintético não redireciona para outro domínio: os coletores analisaram o próprio alvo
    assert motor.saidas("destino") == {"dominio": ALVO, "redirecionado_de": None, "url_destino": None}
    assert (captura["destino"], captura["redirect_ignorado"]) == (None, None)
    # o navegador só pediu as páginas do site sintético: a inicial e as três subpáginas que ela liga
    assert sorted({p.caminho for p in pedidos_locais}) == ["/", "/contato.html", "/planos.html", "/termos.html"]

    caminho = gerar_dossie(ctx.pasta, matriz)
    pontuacao = json.loads((ctx.pasta / "pontuacao.json").read_text(encoding="utf-8"))
    assert {i: (item["estado"], item["pontos"]) for i, item in pontuacao["itens"].items()} == ITENS_ESPERADOS
    eixo1 = pontuacao["eixo1"]
    assert (eixo1["minimo"], eixo1["maximo"]) == (15, 17)
    assert (eixo1["classe"], eixo1["pode_chegar_a"]) == ("provável", "característico")
    assert eixo1["regras_disparadas"] == ["R1"]
    assert pontuacao["eixo2"]["estagio"] == "E2"
    assert pontuacao["eixo2"]["sinal"]["tipo"] == "expansao_acelerada"

    gerado = normalizar_dossie(caminho.read_bytes().decode("utf-8"), ctx.pasta)
    assert "15–17 de 34" in gerado and "provável (pode chegar a característico)" in gerado
    if os.environ.get("RADAR_GRAVAR_OURO"):
        OURO.parent.mkdir(exist_ok=True)
        OURO.write_bytes(gerado.encode("utf-8"))
    assert OURO.is_file(), f"falta o ouro {OURO}: gere com RADAR_GRAVAR_OURO=1 e revise à mão"
    assert gerado == normalizar_dossie(OURO.read_bytes().decode("utf-8"), ctx.pasta)
    # a custódia tem registros: um `verificar` vazio sem log seria "íntegro" no vazio
    assert (ctx.pasta / "custodia.log").stat().st_size > 0
    assert verificar(ctx.pasta) == []
