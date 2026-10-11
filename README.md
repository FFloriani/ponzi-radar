# piramide-pentest

Estudo de pirâmides financeiras e esquemas Ponzi, principalmente no Brasil, e projeto de um **radar** que analisa sites suspeitos e gera um dossiê de risco.

O ponto de vista é o de quem observa de fora: entender como esses esquemas funcionam, quanto duram e que sinais aparecem antes do colapso.

## Conteúdo

| Pasta | O que tem |
|---|---|
| `reports/` | Dois relatórios com fontes. **Pirâmides financeiras no Brasil** cobre conceitos, enquadramento legal, órgãos, casos de 1990 a 2026, sinais de alerta e o que a vítima pode fazer. **Duração e colapso das pirâmides** cobre a linha do tempo de cerca de 70 esquemas no Brasil e no mundo, os padrões de duração e de colapso, o modelo de estágios E0–E7 e a matriz de risco em dois eixos. |
| `research_notes/` | Notas de pesquisa que sustentam os relatórios. |
| `docs/superpowers/specs/` | Especificação do radar. O primeiro subprojeto é o Núcleo. |
| `radar/` | Código do radar (em construção). |

## Radar (em construção)

O radar é um pipeline DAG em Python com servidor MCP:

1. Recebe a URL de uma oferta suspeita.
2. Coleta dados públicos por fontes passivas: RDAP, DNS, certificados, Wayback, CNPJ, cadastros e alertas da CVM e do BCB.
3. Captura o site como um visitante faria.
4. Abre "pendências" que um cliente MCP (Claude) responde. Toda resposta precisa de fonte verificável.
5. Pontua a oferta numa matriz de dois eixos: a chance de ser pirâmide ou Ponzi e o estágio no ciclo de vida.

Cada execução fica salva com cadeia de custódia (hash SHA-256 encadeado). Analisar o mesmo alvo de novo mostra o que mudou.

**A matriz de risco é uma heurística ainda não validada.** O subprojeto de calibração vai medir a acurácia com casos históricos e controles negativos antes de os pesos ganharem valor estatístico.

## Como usar

### Instalação

Precisa de Python 3.12 ou mais novo. Dentro de `radar/`:

```bash
cd radar
python -m venv .venv
source .venv/Scripts/activate    # Git Bash; no PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
```

Para conferir: `python -m pytest -q` roda a suíte sem internet. Os testes ao vivo, que consultam as fontes de verdade, rodam à parte com `python -m pytest -m rede -v`.

A configuração fica em `radar/config.toml`, com os padrões comentados (proxy, limites por host, timeouts, número de subpáginas). Para mudar um valor só na sua máquina, use `radar/config.local.toml`, que fica fora do git.

### No Claude Code

O `.mcp.json` da raiz registra o servidor `radar`, que roda com `radar/.venv/Scripts/python.exe -m radar.mcp_server`:

1. Abra o Claude Code na raiz do repositório e aprove o servidor do projeto quando ele perguntar.
2. Confira com `/mcp`: o `radar` aparece conectado.
3. Para analisar um site, use o prompt do servidor:

   ```
   /mcp__radar__analisar_site https://site-suspeito.com.br
   ```

   O Claude segue o roteiro: inicia a análise, responde cada pendência com evidência, gera o dossiê e resume os dois eixos e as lacunas.

O caminho do `.mcp.json` é o do venv no Windows. Em Linux ou macOS, o interpretador é `radar/.venv/bin/python`.

### No Claude Desktop

O Claude Desktop não roda a partir da pasta do projeto, então o caminho do interpretador precisa ser absoluto. Acrescente o servidor ao `claude_desktop_config.json` (no Windows, em `%APPDATA%\Claude\`) e reinicie o aplicativo:

```json
{
  "mcpServers": {
    "radar": {
      "command": "E:\\Trabalho\\Floriani\\investimentos\\radar\\.venv\\Scripts\\python.exe",
      "args": ["-m", "radar.mcp_server"]
    }
  }
}
```

O prompt `analisar_site` aparece no menu de prompts do servidor `radar`.

### Navegador do Playwright

A captura usa o Chromium que o `playwright install chromium` baixa. O servidor MCP o procura pelo ambiente que o cliente lhe passa:

- o Claude Code passa o ambiente inteiro ao servidor, então o `PLAYWRIGHT_BROWSERS_PATH` do seu usuário chega;
- outros clientes (Claude Desktop, SDKs) podem passar um ambiente reduzido, sem essa variável;
- quem instalou os navegadores do Playwright num caminho próprio põe `"env": {"PLAYWRIGHT_BROWSERS_PATH": "<caminho>"}` na configuração do servidor, ao lado de `command` e `args`.

Sem o navegador, o nó `captura` falha com a mensagem `captura indisponível: navegador do Playwright não encontrado; rode "playwright install chromium" no venv do radar ou confira PLAYWRIGHT_BROWSERS_PATH no ambiente do servidor MCP`. Isso não conta como "site fora do ar" e aparece nas lacunas do dossiê.

### Redirecionamentos

Se o endereço leva a outro domínio, o radar analisa o destino e registra o redirecionamento no dossiê. O redirecionamento para uma plataforma (Telegram, WhatsApp, Instagram), para um serviço de estacionamento de domínio ou para um serviço de terceiro (loja de aplicativos, Discord, checkout, hospedagem de arquivos) não troca o domínio analisado: o dossiê só registra o redirecionamento.

O destino só é seguido no modo com captura, porque é a captura que vê o redirecionamento. Sem contato ou no modo retroativo, o radar não o vê e analisa o endereço dado: se ele é só um encurtador ou redirecionador, informe o domínio final.

Só a captura toca o site. O `arquivar_fonte` e a validação das respostas recusam o domínio do alvo, o do destino, o de cada página que a captura visitou e o de cada salto do redirecionamento, além dos IPs do domínio analisado e do redirecionador.

### Linha de comando

Com o venv ativo, o comando `radar` serve para usar o radar sem o Claude e para conferir a custódia:

| Comando | O que faz |
|---|---|
| `radar coletar URL [--as-of AAAA-MM-DD] [--sem-contato] [--cego]` | Roda os coletores e imprime o `run_id` e as pendências que ficaram abertas. |
| `radar verificar RUN_ID` | Refaz a cadeia de custódia e confere o hash de cada artefato. |
| `radar dossie RUN_ID [--forcar]` | Gera o dossiê. Com pendências abertas, só com `--forcar`, e os itens delas viram "não verificado". |
| `radar diff SLUG [--a RUN_ID] [--b RUN_ID]` | Compara duas execuções do mesmo alvo. Sem `--a` e `--b`, compara as duas últimas em modo atual. |
| `radar mcp` | Sobe o servidor MCP em stdio, como o `.mcp.json` faz. |

O `RUN_ID` tem a forma `<slug>/<AAAA-MM-DD_HHMMSS>`. A CLI não responde pendências: quem as responde é o Claude, pelo servidor MCP. Os códigos de saída são 0 (ok), 1 (custódia com problema ou falha inesperada) e 2 (pedido inválido ou pendências abertas).

### Modos

- **Sem contato** (`modo_contato="nenhum"`, `--sem-contato`): o radar não visita o site e analisa a página arquivada no Wayback. Sem a captura, um redirecionamento não é visto (ver Redirecionamentos).
- **Retroativo** (`as_of` no passado, `--as-of`): analisa o site como ele era na data. As fontes que só mostram o presente (DNS e captura ao vivo) ficam de fora; os dados que só existem como são hoje (sócios, CNAE, listas do BCB) aparecem marcados como "dado de hoje" e não pontuam; e a execução não é comparada com as execuções atuais.
- **Cego** (`modo_cego=true`, `--cego`): serve para calibração, quando o Claude não pode saber qual é o alvo. O slug da pasta, e com ele o `run_id`, vira `cego-` mais o começo do HMAC-SHA256 do domínio, calculado com o segredo local `casos/.segredo_cego` (32 bytes, criado na primeira execução cega). Toda saída do servidor passa pela máscara (`[ALVO]`, `[EMPRESA]`, `[CNPJ]` e `[CNPJ_n]`, `[PESSOA_n]`), as screenshots não são entregues e o `comparar_execucoes` fica indisponível. Se o segredo se perder, as execuções cegas antigas ficam com o slug órfão.

  **O modo cego protege o canal MCP, não o disco.** O `estado.json` de cada execução tem o alvo. O Claude Code aberto na raiz do repositório lê arquivos, então ele acharia o alvo em `casos/cego-*/`. Para calibrar com o Claude Code, ponha as execuções fora do projeto aberto, em `radar/config.local.toml` (por exemplo `casos_dir = "D:/radar-calibracao/casos"`), ou use um cliente sem acesso a arquivos.

### Onde ficam as execuções

Cada execução fica em `casos/<slug>/<AAAA-MM-DD_HHMMSS>/`, na raiz do repositório. A pasta guarda os artefatos, o `custodia.log`, o estado dos nós, os julgamentos e o `dossie.md`. **`casos/` fica fora do git**: a pasta pode ter dados pessoais coletados, e o `tools/publicar.py` recusa qualquer caminho dentro dela.

O dossiê é um apoio à análise, não uma prova nem uma acusação. A matriz que o pontua é uma heurística ainda não validada.
