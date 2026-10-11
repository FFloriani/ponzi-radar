# Radar — melhorias do primeiro aceite: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: superpowers:subagent-driven-development. Os passos usam checkbox (`- [ ]`).

**Objetivo:** corrigir o que o aceite manual de 08/10/2026 (`phinv.link` → `phinvestimentos.com`) mostrou: o radar analisava o domínio do redirecionador, não sinalizava domínio expirado registrado de novo, não lia os textos internos do aplicativo embutidos na página, recusava `valor: null` em "não encontrado" e falhava sem explicar quando o servidor não achava o navegador.

**Arquitetura:** um nó novo, `destino`, decide qual domínio os coletores analisam (o do alvo ou o domínio final depois de um redirect para outro domínio registrável). A pontuação ganha a detecção de domínio reaproveitado, que entra como nota do D3 e como aviso no dossiê. A extração passa a ler as strings dos scripts embutidos no HTML capturado, num artefato derivado e citável. O resto são ajustes pequenos e documentação.

**Stack:** a do Núcleo (Python 3.14, Playwright 1.63, httpx, pydantic, mcp 2.3, pytest/respx).

**Spec:** `docs/superpowers/specs/2026-10-07-radar-nucleo-design.md`. Este plano é um adendo: a Tarefa 4 grava na spec a seção "Adendo 2026-10-11" com as decisões abaixo.

## Restrições globais

- Valem todas as do Núcleo: `radar/radar/` com Python ≥ 3.12. Toda saída de rede passa por `Rede`, exceto o Playwright da captura. **Só o nó `captura` toca o site do alvo, e agora também o do destino.** Nada de contornar anti-bot. Sem CPF nas saídas. Conteúdo do site é dado não confiável. Datas em ISO.
- Commits só via `tools/publicar.py` (sem git local). Arquivos em LF, conferidos com `count(b"\r") == 0`.
- Nada muda nos pesos nem nos itens da matriz (`matriz.yaml`): a calibração é do subprojeto 3.
- O ouro do ponta a ponta (`radar/tests/ouro/dossie_sintetico.md`) só é regravado quando a tarefa exige, e cada diferença é explicada no relatório.

## Foco de revisão

1. **Redirect para plataforma ou serviço de estacionamento** (t.me, wa.me, instagram, sedoparking...): o destino não pode virar o alvo; o radar continua no domínio informado e registra o redirect.
2. **Opsec do destino:** o `arquivar_fonte` e a validação recusam o domínio do destino como recusam o do alvo. Com isso, só a captura toca os dois.
3. **Modo cego:** o domínio do destino é mascarado como `[ALVO]`.
4. **Textos internos hostis** (strings enormes, milhares de chaves, escapes quebrados, `</script>` dentro de string): teto de tamanho, sem travar a extração e sem vazar HTML para o texto.
5. **Domínio reaproveitado sem RDAP** (RDAP em erro) ou sem CT/Wayback: a detecção fica quieta e não acusa nada.

---

### Tarefa 1: Destino depois de redirect

**Arquivos:** criar `radar/radar/nos/destino.py`; modificar `nos/__init__.py`, `nos/captura.py`, `nos/rdap.py`, `nos/dns.py`, `nos/ct.py`, `nos/wayback.py`, `nos/cvm.py` (registros e alertas por domínio), `nos/alvo.py` (constante nova), `pendencias/validacao.py`, `pendencias/mascara.py`, `mcp_server.py` (onde monta `ips_do_alvo`/máscara), `dossie/__init__.py`, `dossie/dossie.md.j2`, `diff.py`; testes em `radar/tests/`.

**Decisões:**
- **`captura`.** Depois da página inicial, se o host final (`inicio.url`) tem domínio registrável diferente do alvo, e esse domínio não está em `PLATAFORMAS` nem em `SERVICOS_DE_ESTACIONAMENTO`, as subpáginas passam a ser escolhidas nos hosts do destino.
  - `SERVICOS_DE_ESTACIONAMENTO` é uma constante nova em `nos/alvo.py`: sedoparking.com, parkingcrew.net, bodis.com, dan.com, afternic.com, hugedomains.com, above.com, parklogic.com, undeveloped.com.
  - A captura ganha a saída `destino`: `{"url": <url final da página inicial>, "dominio": <registrável>}`, ou `None` quando não há troca de domínio.
  - Quando o redirect vai para plataforma ou estacionamento, `destino` fica `None` e `redirect_ignorado` traz `{"url":..., "dominio":..., "motivo": "plataforma"|"estacionamento"}`.
  - `terceiros` passa a excluir também o domínio do destino.
- **Nó `destino`** (`nos/destino.py`):
  - entradas `("alvo",)`, opcionais `("captura",)`, `as_of = "exato"`;
  - saídas `dominio`, `redirecionado_de` e `url_destino`;
  - com `captura` feita e `destino` presente: `dominio` é o do destino, `redirecionado_de` é o domínio do alvo e `url_destino` é a URL;
  - nos outros casos (captura pulada, em erro ou bloqueada, ou sem destino): `dominio` é o do alvo e os outros dois ficam `None`;
  - nunca falha.
- **Coletores de domínio.** `rdap`, `dns`, `ct`, `wayback_indice` e `wayback_snapshot` passam a ler o domínio de `entradas["destino"]["dominio"]`, com entrada `destino` no lugar de `alvo`. O `wayback_snapshot` mantém `captura` como opcional.
  - `registros` e `cvm_alertas` usam o domínio do `destino` (opcional) na chave por domínio; sem ele, o do alvo.
  - Consequência aceita: no modo com captura, esses coletores esperam a captura, entre 30 e 90 s a mais. Nos modos `nenhum` e retroativo nada muda, porque a captura é pulada.
- **Opsec.** A validação de fonte (`pendencias/validacao.py`) e o `arquivar_fonte` recusam o domínio registrável do alvo **e** o do destino, e os IPs do destino (o `dns` agora resolve o destino) entram em `ips_do_alvo`.
- **Modo cego.** O domínio do destino e o host da `url_destino` entram na máscara como `[ALVO]`.
- **Dossiê.** Quando há redirect, a seção 1 ganha a linha `Redirecionamento: <alvo> → <url_destino>; os coletores analisaram <dominio do destino>`. Com `redirect_ignorado`, a linha é `Redireciona para <url> (<motivo>): análise mantida em <alvo>`.
- **Diff.** Mostra "destino mudou" quando o domínio do destino difere entre as execuções.
- **Testes.** Use dois nomes locais com `--host-resolver-rules`, ou o padrão que os testes da captura já usam:
  - a página do alvo dá 302 para o destino e as subpáginas do destino são capturadas;
  - o `rdap`, o `dns` e o `ct` recebem o domínio do destino;
  - redirect para `t.me` ou para um serviço de estacionamento não troca o alvo;
  - a validação recusa uma fonte no domínio do destino;
  - o modo cego mascara o destino;
  - o dossiê traz a linha nova;
  - sem redirect, nada muda; o ponta a ponta continua verde, e o ouro só muda se a linha nova aparecer, o que não deve acontecer.

- [ ] Testes que falham → implementar → testes passam → suíte inteira → commit `feat: radar segue o domínio final depois de um redirect`

### Tarefa 2: Domínio reaproveitado

**Arquivos:** `radar/radar/pontuacao.py`, `dossie/__init__.py`, `dossie/dossie.md.j2` e testes.

**Decisões:**
- **Função pura** `dominio_reaproveitado(ex) -> dict | None` em `pontuacao.py`.
  - Usa o `rdap.registro` e o histórico mais antigo entre `ct.primeiro_certificado` e `wayback_indice.primeiro`, ambos do mesmo domínio analisado (o do `destino`).
  - Se o histórico for mais de 30 dias anterior ao registro, devolve `{"registro": AAAA-MM-DD, "historico_desde": AAAA-MM-DD, "fonte_historico": "crt.sh"|"Wayback"}`.
  - Sem RDAP, ou sem histórico anterior, devolve `None`.
- **D3.** Pontos e estado não mudam: a matriz fica como está. Quando a função devolve algo, a nota do D3 ganha: `domínio registrado de novo em <registro>; há histórico desde <historico_desde> (<fonte>), que pode ser de outro dono`.
- **Dossiê.**
  - Na linha do tempo, os eventos anteriores ao registro aparecem com o sufixo ` (registro anterior do domínio)`, e entra o evento `<registro> — Domínio registrado de novo; o histórico anterior pode ser de outro dono`.
  - Na seção 6, o Wayback e os certificados ganham a linha `Atenção: antes de <registro>, o domínio tinha outro registro (possível outro dono).`
- **Testes.** O caso do aceite (registro 2026-09-29, CT 2020-11-11, Wayback 2014-09-27); um histórico só 10 dias antes (não sinaliza); RDAP em erro; CT e Wayback vazios; e o dossiê com o aviso.

- [ ] TDD → suíte → commit `feat: radar sinaliza domínio expirado registrado de novo`

### Tarefa 3: Textos internos do aplicativo

**Arquivos:** `radar/radar/nos/extracao.py`, `custodia.py` (só se o tipo novo precisar ser aceito), `pendencias/definicoes.py` (critérios), `mcp_server.py` (só se o `ver_artefato` filtrar por tipo) e testes.

**Decisões:**
- **O que ler.** Para cada página com `html` (da captura ou do `wayback_snapshot`), extrair as strings literais dos `<script>` embutidos, os que não têm `src`, incluindo JSON e o payload do Next.js (`self.__next_f.push`).
  - Desfazer os escapes de JS e de JSON (`\"`, `\\`, `\n`, `\uXXXX`), também em camadas, quando o JSON vem dentro de string.
  - Manter só texto de linguagem natural: pelo menos 2 palavras com letras, de 12 a 300 caracteres, sem cara de código, URL, hash ou base64.
  - Remover duplicatas.
- **Formato e teto.** Uma string por linha, com o formato `<chave> = <texto>` quando a string é o valor de uma chave de objeto (`"Saque.rendimento":"..."`) e só `<texto>` nos outros casos. O teto é de 5.000 linhas e 300 mil caracteres por página; acima disso, corta e registra em `truncado`.
- **Artefato.** O texto vai para a custódia como artefato derivado: `tipo="texto_interno"`, `origem=<url da página>`, extensão `.txt`. Assim ele pode ser citado pelo `sha256` e conferido pela validação.
- **Candidatos.** As mesmas regex de candidatos rodam sobre esse texto, com `artefato` igual à ref do texto interno e `extra.origem = "texto_interno"`. Eles entram depois dos candidatos do texto visível e respeitam os tetos que já existem.
- **Critérios.** P-A1, P-B, P-C, P-A3 e P-E ganham a frase: "Candidatos com extra.origem=texto_interno vêm de textos internos do aplicativo embutidos na página (mensagens de telas que o visitante não vê): mostram o que o sistema faz ou pode fazer, não que já aconteceu."
- **Testes.**
  - Fixture com HTML que tem um `<script>` com dicionário i18n, com o trecho do aceite: `bônus de indicação ({nivel}º nível)`, `Saques de rendimento estão bloqueados.`.
  - Fixture com `self.__next_f.push`.
  - Strings hostis: 1 MB numa string, `</script>` escapado e escapes inválidos.
  - Um teste de validação que aceita um trecho citado do texto interno.
  - O ouro do ponta a ponta deve mudar só se o site sintético tiver script embutido com texto; se mudar, regravar uma vez e explicar.

- [ ] TDD → suíte → commit `feat: extração lê os textos internos do aplicativo embutidos na página`

### Tarefa 4: Ajustes pequenos e documentação

**Arquivos:** `radar/radar/mcp_server.py` ou `pendencias/validacao.py` (onde o formato do `valor` é checado), `nos/captura.py` (`_erro_da_captura`), `README.md`, a spec (adendo) e testes.

**Decisões:**
- **`valor: null`.** Com status `nao_encontrado` ou `inconclusivo`, `valor: null` é tratado como `{}`. Com `confirmado` ou `corrigido`, continua exigindo objeto. Teste nos dois sentidos.
- **Navegador não encontrado.** Quando o Playwright não acha o executável (`Executable doesn't exist`), a mensagem passa a ser: `captura indisponível: navegador do Playwright não encontrado; rode "playwright install chromium" no venv do radar ou confira PLAYWRIGHT_BROWSERS_PATH no ambiente do servidor MCP`. Continua não contando para o E6. Teste.
- **README.** Em "Como usar", uma nota curta:
  - o Claude Code passa o ambiente inteiro ao servidor;
  - outros clientes (Claude Desktop, SDKs) podem passar um ambiente reduzido;
  - quem instalou os navegadores do Playwright num caminho próprio põe `"env": {"PLAYWRIGHT_BROWSERS_PATH": "<caminho>"}` na configuração do servidor.

  Uma linha sobre o redirect: "se o endereço leva a outro domínio, o radar analisa o destino e registra o redirecionamento no dossiê".
- **Spec.** Seção nova "Adendo 2026-10-11", no fim, com as decisões das Tarefas 1 a 4, uma linha por decisão.

- [ ] TDD onde couber → suíte → commit `fix: valor nulo em não encontrado, mensagem do navegador ausente e documentação`
