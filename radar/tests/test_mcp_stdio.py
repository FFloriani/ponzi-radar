"""O servidor MCP de verdade, por stdio (Tarefa 18): o que o Claude Code sobe a partir do `.mcp.json` da raiz do
repositório responde com as 10 ferramentas da spec 7.2 e com o prompt `analisar_site`.

O processo é o do registro (`radar/.venv/Scripts/python.exe -m radar.mcp_server`, a partir da raiz do repositório,
como o Claude Code o inicia). Listar ferramentas e ler o prompt não tocam a rede nem `casos/`.
"""

from __future__ import annotations

import json

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from radar.config import RAIZ_REPO

REGISTRO = RAIZ_REPO / ".mcp.json"
ESPERADO = {"mcpServers": {"radar": {"command": "radar/.venv/Scripts/python.exe", "args": ["-m", "radar.mcp_server"]}}}
# spec 7.2
FERRAMENTAS = {
    "iniciar_analise", "status", "listar_pendencias", "ver_pendencia", "ver_artefato", "arquivar_fonte",
    "responder_pendencia", "gerar_dossie", "comparar_execucoes", "listar_casos",
}  # fmt: skip
URL = "https://exemplo.com.br/oferta"
_PRAZO_S = 120  # subir o processo e importar o SDK leva alguns segundos; um travamento não pode prender a suíte


def test_mcp_json_registra_o_servidor_do_radar():
    dados = REGISTRO.read_bytes()
    assert b"\r" not in dados  # LF, como o resto do repositório
    assert json.loads(dados) == ESPERADO


async def test_servidor_por_stdio_tem_as_10_ferramentas_e_o_prompt(tmp_path):
    servidor = json.loads(REGISTRO.read_bytes())["mcpServers"]["radar"]
    executavel = RAIZ_REPO / servidor["command"]
    if not executavel.is_file():
        pytest.skip(f"sem o venv do registro: {executavel}")
    parametros = StdioServerParameters(command=str(executavel), args=servidor["args"], cwd=RAIZ_REPO)
    log = tmp_path / "servidor.stderr"
    with anyio.fail_after(_PRAZO_S), log.open("w", encoding="utf-8") as erros:
        async with stdio_client(parametros, errlog=erros) as (leitura, escrita):
            async with ClientSession(leitura, escrita) as sessao:
                inicio = await sessao.initialize()
                listadas = await sessao.list_tools()
                prompts = await sessao.list_prompts()
                prompt = await sessao.get_prompt("analisar_site", {"url": URL})

    assert inicio.server_info.name == "radar"
    nomes = [ferramenta.name for ferramenta in listadas.tools]
    assert sorted(nomes) == sorted(FERRAMENTAS), log.read_text(encoding="utf-8")
    # as descrições repetem a regra do conteúdo não confiável onde o texto do site chega ao Claude
    descricoes = {ferramenta.name: ferramenta.description or "" for ferramenta in listadas.tools}
    for nome in ("iniciar_analise", "ver_pendencia", "ver_artefato"):
        assert "não confiável" in descricoes[nome]
    assert [p.name for p in prompts.prompts] == ["analisar_site"]
    (mensagem,) = prompt.messages
    texto = mensagem.content.text
    assert URL in texto
    for passo in ("iniciar_analise", "ver_pendencia", "responder_pendencia", "gerar_dossie", "as_of"):
        assert passo in texto
