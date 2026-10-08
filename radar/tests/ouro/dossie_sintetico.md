# Dossiê de risco: piramide-sintetica.com.br

## 1. Identificação

- **Alvo:** piramide-sintetica.com.br (`http://127.0.0.1:<PORTA>/`)
- **Execução:** <DATA_HORA> (`<RUN_ID>`)
- **as_of:** 2026-10-08
- **Modo de contato:** captura
- **Modo cego:** não
- **Matriz:** versão 2026-10-07, hash `<HASH>`
- **Hash final da custódia:** `<HASH>`

## 2. Veredito

> Heurística não validada: os pesos ainda não foram calibrados.

### Eixo 1: probabilidade de pirâmide ou Ponzi

- **Escore:** 15–17 de 34. É um intervalo: o item não verificado entra com 0 no mínimo e com o máximo dele no máximo.
- **Classe:** provável (pode chegar a característico)
- **Regras de corte disparadas:** R1: classe mínima provável

### Eixo 2: estágio do ciclo de vida

- **Estágio:** E2
- **Sinal que o define:** expansao_acelerada, 2026-10-08, fonte operador `texto: http://127.0.0.1:<PORTA>/`
- **Janela observada:** a mais incerta: depende da velocidade de captação; o corte estatal pode vir sem aviso
- **Modificadores:**
  - retorno_alto: encurta a janela (origem A1) — `texto: http://127.0.0.1:<PORTA>/planos.html`
  - identidade_nova: encurta a janela (origem D3)
  - carencia_longa: alonga a janela (origem B3) — `texto: http://127.0.0.1:<PORTA>/planos.html`

Não há previsão numérica de tempo até a calibração (subprojeto 3). A janela descreve o que se observou em casos anteriores; não é uma previsão para este.

## 3. Itens da matriz

O item `não verificado` ou `inconclusivo` aparece como intervalo de pontos (de 0 ao máximo dele) e nunca como zero. Só o item confirmado traz evidências. A coluna Hash mostra o começo do hash do artefato; o hash inteiro está no anexo (seção 9).

| Item | Estado | Pontos | Origem | Marcas | Trecho | Fonte | Hash | Nota |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 — Retorno fixo ou garantido | confirmado | 4/4 | regex confirmada | — | Rendimento de 1,5% ao dia garantido | operador, 2026-10-08 — `texto: http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |  |
| A2 — Série de retornos lisa | não se aplica | 0/2 | — | — | — |  |  | P-A2 não gerada: sem histórico de rentabilidade |
| A3 — Origem do retorno não verificável e sem custodiante | confirmado | 2/2 | regex confirmada | — | aluga as suas moedas para operações de arbitragem | operador, 2026-10-08 — `texto: http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |  |
| B1 — Remuneração por captar ou indicar | confirmado | 2/3 | regex confirmada | — | bônus de indicação em 3 níveis | operador, 2026-10-08 — `texto: http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |  |
| B2 — Pagamento em token ou moeda interna | não se aplica | 0/2 | Claude | — | — |  |  |  |
| B3 — Carência com multa pesada | confirmado | 1/1 | regex confirmada | — | carência de 12 meses e multa de 30% no resgate antecipado | operador, 2026-10-08 — `texto: http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |  |
| B4 — Cobrança para liberar saque | não se aplica | 0/3 | Claude | — | — |  |  |  |
| C1 — Sem registro ou autorização (CVM/BCB) | confirmado | 3/3 | coletor | — | — | coletor: registros |  | oferta de investimento sem registro na CVM nem no BCB |
| C2 — Contrato com nome atípico | confirmado | 2/2 | regex confirmada | — | O contrato é de aluguel de criptomoedas | operador, 2026-10-08 — `texto: http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |  |
| C3 — Conta de PF/terceiro, sem CNPJ, atividade incoerente ou offshore | não se aplica | 0/2 | Claude | — | — |  |  |  |
| C4 — Alerta oficial vigente | não encontrado | 0/3 | Claude | — | — |  |  |  |
| D1 — Responsáveis com histórico de fraude | não encontrado | 0/3 | Claude | — | — |  |  |  |
| D2 — Clone de esquema conhecido | não verificado | 0–2 | — | — | — |  |  | clone de esquema conhecido: o Núcleo não verifica |
| D3 — Identidade nova | confirmado | 1/1 | coletor | — | — | coletor: rdap, cnpj |  | domínio registrado em 2026-08-09 |
| D4 — Credibilidade emprestada | não encontrado | 0/1 | Claude | — | — |  |  |  |

## 4. Linha do tempo

| Data | Evento | Fonte |
| --- | --- | --- |
| 2024-10-08 | CNPJ aberto | Receita Federal (brasilapi) |
| 2026-08-09 | Domínio registrado | RDAP |
| 2026-08-10 | Primeiro certificado TLS | crt.sh |
| 2026-08-15 | Primeiro snapshot no Wayback | Wayback CDX |
| 2026-09-20 | Último snapshot no Wayback | Wayback CDX |
| 2026-10-08 | Sinal saques_funcionando (E1) | operador `texto: http://127.0.0.1:<PORTA>/planos.html` |
| 2026-10-08 | Sinal expansao_acelerada (E2) | operador `texto: http://127.0.0.1:<PORTA>/` |

## 5. Empresa e pessoas

- **CNPJ:** 11.222.333/0001-81
- **Razão social:** INVESTMAX BRASIL INTERMEDIACAO DE NEGOCIOS LTDA
- **Nome fantasia:** INVESTMAX BRASIL
- **Abertura:** 2024-10-08
- **CNAE:** 6619399 — Outras atividades auxiliares dos serviços financeiros não especificadas anteriormente
- **Situação:** ATIVA
- **Fonte dos dados:** brasilapi

**Sócios (quadro da Receita)**

| Nome | Qualificação | Entrada |
| --- | --- | --- |
| JOAO FICTICIO DA SILVA | Sócio-Administrador | 2024-10-08 |

**Registros oficiais**

- **Registro na CVM:** nenhum
- **Instituição autorizada pelo BCB:** nenhum
- **Domínio verificado pelo BCB:** nenhum

## 6. Infraestrutura

### Domínio (RDAP)

- **Registro:** 2026-08-09
- **Expiração:** 2027-08-09
- **Registrador:** —

### DNS e hospedagem

- **Hospedagem (A e AAAA):** 203.0.113.50
- **MX:** —
- **NS:** ns1.hospedagem.example., ns2.hospedagem.example.
- **Domínio inexistente (NXDOMAIN):** não

### Certificados (crt.sh)

- **Primeiro certificado:** 2026-08-10
- **Certificados até o as_of:** 2
- **Nomes nos certificados:** app.piramide-sintetica.com.br, piramide-sintetica.com.br, www.piramide-sintetica.com.br

### Wayback

- **Primeiro snapshot:** 2026-08-15
- **Último snapshot:** 2026-09-20
- **Capturas HTML:** 3
- **Meses com captura:** 2 (de 2026-08 a 2026-09)

### Captura do site

- **Bloqueada por verificação anti-bot:** não
- **Páginas capturadas:** 4
  - `http://127.0.0.1:<PORTA>/` (HTTP 200)
  - `http://127.0.0.1:<PORTA>/planos.html` (HTTP 200)
  - `http://127.0.0.1:<PORTA>/termos.html` (HTTP 200)
  - `http://127.0.0.1:<PORTA>/contato.html` (HTTP 200)
- **Domínios de terceiros carregados:** 127.0.0.1

## 7. Lacunas

O que não pôde ser verificado nunca vale zero: abre o intervalo do escore (seção 2).

**Nós sem resultado**

Todos os nós terminaram.

**Itens em aberto**

- D2 — não verificado: clone de esquema conhecido: o Núcleo não verifica

## 8. Mudanças desde a execução anterior

Não há execução anterior deste alvo em modo atual para comparar.

## 9. Anexo: artefatos e verificação

Hash final da cadeia: `<HASH>`

| Seq | Tipo | Origem | Hash |
| --- | --- | --- | --- |
| <SEQ> | api | `https://brasilapi.com.br/api/cnpj/v1/11222333000181` | `sha256:<HASH>` |
| <SEQ> | api | `https://cloudflare-dns.com/dns-query?name=piramide-sintetica.com.br&type=AAAA` | `sha256:<HASH>` |
| <SEQ> | api | `https://cloudflare-dns.com/dns-query?name=piramide-sintetica.com.br&type=A` | `sha256:<HASH>` |
| <SEQ> | api | `https://cloudflare-dns.com/dns-query?name=piramide-sintetica.com.br&type=MX` | `sha256:<HASH>` |
| <SEQ> | api | `https://cloudflare-dns.com/dns-query?name=piramide-sintetica.com.br&type=NS` | `sha256:<HASH>` |
| <SEQ> | api | `https://cloudflare-dns.com/dns-query?name=piramide-sintetica.com.br&type=TXT` | `sha256:<HASH>` |
| <SEQ> | api | `https://crt.sh/?q=piramide-sintetica.com.br&output=json` | `sha256:<HASH>` |
| <SEQ> | api | `https://rdap.registro.br/domain/piramide-sintetica.com.br` | `sha256:<HASH>` |
| <SEQ> | api | `https://web.archive.org/cdx/search/cdx?url=piramide-sintetica.com.br&matchType=domain&output=json&fl=timestamp,original&filter=statuscode:200&filter=mimetype:text/html&limit=10000&to=20261008` | `sha256:<HASH>` |
| <SEQ> | har | `http://127.0.0.1:<PORTA>/` | `sha256:<HASH>` |
| <SEQ> | indice | `cadastros_cvm` | `sha256:<HASH>` |
| <SEQ> | indice | `deliberacoes` | `sha256:<HASH>` |
| <SEQ> | indice | `dominios_bcb` | `sha256:<HASH>` |
| <SEQ> | indice | `instituicoes_bcb` | `sha256:<HASH>` |
| <SEQ> | indice | `sancionador` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-A1#1` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-A3#1` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-B#1` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-C#1` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-C4#1` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-D1#1` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-D4#1` | `sha256:<HASH>` |
| <SEQ> | julgamento | `P-E#1` | `sha256:<HASH>` |
| <SEQ> | pagina | `http://127.0.0.1:<PORTA>/` | `sha256:<HASH>` |
| <SEQ> | pagina | `http://127.0.0.1:<PORTA>/contato.html` | `sha256:<HASH>` |
| <SEQ> | pagina | `http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |
| <SEQ> | pagina | `http://127.0.0.1:<PORTA>/termos.html` | `sha256:<HASH>` |
| <SEQ> | screenshot | `http://127.0.0.1:<PORTA>/` | `sha256:<HASH>` |
| <SEQ> | screenshot | `http://127.0.0.1:<PORTA>/contato.html` | `sha256:<HASH>` |
| <SEQ> | screenshot | `http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |
| <SEQ> | screenshot | `http://127.0.0.1:<PORTA>/termos.html` | `sha256:<HASH>` |
| <SEQ> | texto | `http://127.0.0.1:<PORTA>/` | `sha256:<HASH>` |
| <SEQ> | texto | `http://127.0.0.1:<PORTA>/contato.html` | `sha256:<HASH>` |
| <SEQ> | texto | `http://127.0.0.1:<PORTA>/planos.html` | `sha256:<HASH>` |
| <SEQ> | texto | `http://127.0.0.1:<PORTA>/termos.html` | `sha256:<HASH>` |

Para refazer a cadeia e conferir o hash de cada arquivo: `radar verificar <RUN_ID>`
