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
