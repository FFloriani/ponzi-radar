# Pirâmides financeiras e esquemas Ponzi no Brasil: anatomia, modus operandi, psicologia e sinais de alerta

> Notas de pesquisa, dados até 07/10/2026. Os cálculos marcados como "cálculo próprio" usam como insumo séries oficiais do Banco Central (SGS), com link. Os casos brasileiros aparecem só como ilustração de padrão; a ficha completa de cada caso fica com outros pesquisadores.

## 1. Matemática do colapso: por que pirâmides e Ponzis quebram, e como os retornos prometidos se comparam ao CDI/Selic (out/2026)

### Takeaway
Pirâmide e Ponzi não têm ativo que gere renda. O passivo prometido cresce a juros compostos e só fecha a conta com entrada crescente de dinheiro novo, o que esbarra no limite de pessoas e de capital disponível. Com a Selic em 13,75% a.a. e o CDI em 13,65% a.a. (≈1,07% a.m.) em out/2026, as promessas típicas no Brasil vão de ~2x o CDI mensal (golpes "modestos" de 2–3% a.m.) a ~9x (10% a.m., GAS) e passam de 1.000% a.a. (1% ao dia, Kriptacoin).

### Cited Findings

**Mecânica e definições**
- A SEC define Ponzi como fraude de investimento que paga supostos retornos aos investidores antigos com o dinheiro dos novos. Esses esquemas "tendem a colapsar quando fica difícil recrutar novos investidores ou quando muitos investidores pedem resgate ao mesmo tempo" — [SEC, "Ponzi Schemes" (página arquivada)](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm)
- A CVM define pirâmide como "prática criminosa de captação de recursos do público" que se apresenta como negócio legítimo, promete ganho alto em pouco tempo e paga os antigos com os aportes dos novos. No esquema Ponzi, "os lucros também são pagos com recursos novos", mas o investidor não precisa recrutar ninguém. Os dois quebram quando a expansão desacelera — [CVM/Portal do Investidor, "Pirâmides Financeiras e Esquemas Ponzi"](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi)
- Modelo formal: Artzrouni (2009) descreve um fundo que promete mais do que entrega usando uma equação diferencial linear de 1ª ordem com quatro parâmetros: taxa prometida, taxa nominal efetivamente obtida, ritmo de novos depósitos e taxa de saques. O modelo dá as condições de solvência ou colapso e foi ajustado aos dados do esquema original de Charles Ponzi (1920). Publicado em *Mathematical Social Sciences*, 58(2):190–201 — [Artzrouni, "The mathematics of Ponzi schemes" (MPRA)](https://mpra.ub.uni-muenchen.de/14420/)
- Duração média: na amostra de 376 Ponzis processados pela SEC entre 1988 e 2012, o esquema durou em média cerca de 4 anos — [Deason, Rajgopal & Waymire, "Who Gets Swindled in Ponzi Schemes?" (SSRN, 2015)](https://papers.ssrn.com/abstract=2586490)

**Juros de referência no Brasil (out/2026)**
- Meta Selic de 13,75% a.a. (série SGS 432) — [BCB/SGS 432](https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/3?formato=json)
- O Copom cortou a Selic de 14,00% para 13,75% a.a. na 281ª reunião (16/09/2026), por unanimidade, com corte de 0,25 p.p. — [Atlas Público/BCB](https://atlaspublico.com.br/bcb/noticias/copom-reduz-selic-para-13-75pct-ao-ano-em-decisao-unanime-87748); [Jornal do Comércio (Focus)](https://www.jornaldocomercio.com/economia/2026/09/1262567-selic-no-fim-de-2026-continua-em-1375-pela-quinta-semana-seguida-aponta-focus.html). *Inconsistência:* uma matéria diz que foi o "quinto corte consecutivo de 0,25 p.p. desde abril, a partir de 14,75%"; cinco cortes a partir de 14,75% dariam 13,50%, não 13,75%. A meta atual (13,75%) é a mesma em todas as fontes e no SGS — [Sou Brasília](https://soubrasilia.com/?p=13281)
- Pelas fontes consultadas, não há reunião do Copom em outubro de 2026 — [Renova Invest](https://renovainvest.com.br/?p=106745)
- CDI anualizado (base 252) de 13,65% a.a. em 06/10/2026 — [BCB/SGS 4389](https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/3?formato=json). Selic diária de 0,050788% — [BCB/SGS 11](https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados/ultimos/3?formato=json)
- CDI acumulado em 2025: 14,33%. CDI acumulado em 12 meses (out/2025–set/2026): 14,47%. Cálculo próprio sobre o CDI mensal — [BCB/SGS 4391](https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados?formato=json&dataInicial=01/01/2025&dataFinal=07/10/2026)
- IPCA de 12 meses até ago/2026: 4,22% — [BCB/SGS 13522](https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/2?formato=json). IPCA de 2025: 4,26% (cálculo próprio sobre o IPCA mensal) — [BCB/SGS 433](https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2025&dataFinal=07/10/2026). Juro real do CDI ≈ 9,05% a.a. (cálculo próprio: 1,1365/1,0422)
- Poupança: ≈0,66% a.m. (depósitos de 05–06/10/2026) — [BCB/SGS 195](https://api.bcb.gov.br/dados/serie/bcdata.sgs.195/dados/ultimos/2?formato=json)
- Ativo real (ações): carta de gestor da Previ dá o Ibovespa em +29,66% em 2025. *Não verificado*: o mesmo trecho dá o CDI de 2025 em 13,47%, o que diverge dos 14,33% calculados a partir do BCB. Usar com cautela — [Previ, Carta do gestor dez/2025](https://www.previ.com.br/data/files/B1/F5/E6/BB/CC7BB91053DCEFA91028CCA8/Carta%20do%20gestor%20AGRESSIVO_2025_12.pdf)

**Conversão das promessas típicas (cálculo próprio; CDI de referência = 13,65% a.a. ≈ 1,072% a.m. ≈ 0,0508% por dia útil, [SGS 4389](https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/3?formato=json))**

| Promessa | Equivalente anual composto | Múltiplo do CDI mensal | Tempo para dobrar | Em 24 meses |
|---|---|---|---|---|
| 1% ao dia útil (252 d.u.) | +1.127% a.a. (x12,3) | ~20x o CDI diário | ~70 dias úteis | — |
| 1% ao dia corrido (365 d) | x37,8 no ano; +34,8% em 30 dias | — | — | — |
| 5% a.m. | +79,6% a.a. | 4,7x | 14,2 meses | x3,2 |
| 8% a.m. (Braiscompany) | +151,8% a.a. | 7,5x | 9,0 meses | x6,3 |
| 10% a.m. (GAS) | +213,8% a.a. | 9,3x | 7,3 meses | x9,8 |
| 15% a.m. | +435% a.a. | 14,0x | 5,0 meses | x28,6 |
| 20% a.m. | +791,6% a.a. | 18,7x | 3,8 meses | x79,5 |
| CDI (referência) | 13,65% a.a. | 1x | ~5,4 anos | x1,29 |

**Passivo de um Ponzi a juros compostos (cálculo próprio)**
- R$ 1.000 prometidos a 10% a.m. com reinvestimento viram um passivo de R$ 3.138 em 12 meses, R$ 9.850 em 24 e R$ 30.913 em 36. No CDI de 13,65% a.a., os mesmos R$ 1.000 viram R$ 1.136, R$ 1.292 e R$ 1.468. Sem ativo gerador, toda essa diferença precisa vir de depósitos novos.

**Exemplo de níveis de recrutamento (cálculo próprio; cada participante recruta 6)**
- Nível 1: 1 · nível 4: 216 · nível 7: 46.656 · nível 9: 1.679.616 · nível 10: 10.077.696 · nível 11: 60.466.176 (acumulado de 72,6 milhões) · nível 12: 362.797.056 (acumulado de 435 milhões) · nível 13: 2,18 bilhões.
- Quando o recrutamento para, a última camada não tem a quem recrutar e fica com o prejuízo. Com 6 recrutas por pessoa, a base é 83,3% de todos os participantes. Com 2 recrutas por pessoa, é 50%.

**Retornos prometidos em casos brasileiros (ilustração)**
- Kriptacoin (DF, 2017): "1% de rendimento diário", mais renda extra por trazer novos investidores. Cerca de R$ 250 milhões movimentados e ~40 mil vítimas — [Teletime](https://teletime.com.br/21/09/2017/piramide-financeira-por-meio-de-moeda-digital-e-desbaratada-em-brasilia/)
- Operação da Polícia Civil de SP contra pirâmide de "robô" de criptomoedas que prometia lucro de 1% ao dia, com ~4 mil vítimas na Grande SP e em Sorocaba — [Suno](https://www.suno.com.br/noticias/?p=286876); [Tribuna do Sertão (2022)](https://www.tribunadosertao.com.br/economia/2022/08/23/454118-suspeitos-de-piramide-com-criptomoedas-sao-alvo-de-operacao-em-sp)
- Interior de MG: presos golpistas que prometiam lucro de 2% ao dia — [Itatiaia](https://www.itatiaia.com.br/brasil/sudeste/mg/golpistas-que-prometiam-lucro-de-2-ao-dia-sao-presos-no-interior-de-minas/)
- GAS Consultoria (Cabo Frio/RJ): 10% ao mês em supostos investimentos em bitcoin. R$ 38 bilhões movimentados; segundo a PF, o dinheiro sequer era aplicado em bitcoin — [Tecnoblog](https://tecnoblog.net/noticias/lider-de-piramide-farao-dos-bitcoins-ja-responde-a-quase-300-processos/)
- Braiscompany (Campina Grande/PB): promessa de 8% ao mês — [InfoMoney](https://www.infomoney.com.br/?p=2028161)
- Unick Forex (São Leopoldo/RS): 100% de retorno em 6 meses (≈12,25% a.m., cálculo próprio). Captava cerca de R$ 40 milhões por dia e levantou ~R$ 2,4 bilhões — [Suno](https://www.suno.com.br/noticias/?p=41411)
- "Golpe da Fé"/"Banco do Pastor" (RJ): até 10% ao mês — [CartaCapital](https://www.cartacapital.com.br/?p=304533)
- Na pesquisa da CVM com vítimas, o perfil "movidos pela confiança" caiu em esquemas de rentabilidade "mais modesta", em torno de 2 a 3% ao mês — [CVM/CECOP, Relatório da pesquisa com vítimas de fraudes financeiras (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

### Inferences
- Mesmo a promessa "modesta" de 2–3% a.m. é 1,9–2,8x o CDI mensal atual, sem risco declarado. Como os golpes migraram para taxas menores (ver seção 4), a régua de "retorno absurdo" não basta. A pergunta útil é *de onde vem o retorno, e quem regula*.
- Regra prática para leigos (derivada dos números acima): renda fixa regulada em out/2026 paga perto de 1% a.m. Qualquer oferta que *garanta* bem acima de ~1,1–1,2% a.m. (ou ~15% a.a.) sem explicar o risco merece desconfiança imediata.
- Mesmo com o +29,66% do Ibovespa em 2025 (dado não verificado), o melhor ano recente da bolsa rende menos que 3 meses de uma promessa de 10% a.m., e com volatilidade. Retornos de pirâmide ficam fora de qualquer distribuição histórica de ativo real.
- Nível 12 da progressão (acumulado de ~435 milhões) já é cerca do dobro da população brasileira. O número de ~213 milhões (estimativa IBGE 2025) não foi verificado nesta pesquisa; o ponto qualitativo se mantém.

### Gaps
- Não achei uma série oficial confiável de retorno do Ibovespa/IFIX/ouro em 2025–2026 (B3 ou IBGE) para comparar com fonte primária. O dado da Previ tem inconsistência interna.
- Não achei fonte primária oficial (investor.gov ou FTC) com o exemplo clássico "cada um recruta 6; no 11º nível supera a população" (investor.gov devolveu 403). A tabela acima é cálculo próprio.

## 2. Ciclo de vida típico: credibilidade, aceleração, estresse, colapso e pós-colapso

### Takeaway
O padrão brasileiro se repete. No início há pagamentos em dia e saques que funcionam, para construir prova social. Depois vêm bônus por indicação, contratos com lock-up e multa de saída. No estresse aparecem atrasos, desculpas técnicas, culpa em terceiros (exchange, hacker, regulador), conversão de saldo em token próprio e "auditorias". No colapso os saques param. No pós-colapso a recuperação judicial ou a falência viram palco de promessas de "retomada" e de "canais de transparência".

### Cited Findings

**Fase 1: credibilidade (pagar em dia para criar prova)**
- Nas entrevistas da CVM, as vítimas contam que "tinham ganhos no início, chegando mesmo a fazer saques". Os problemas só vinham depois — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Elementos de credibilidade citados pelas vítimas: atendimento ao cliente, sede física, site profissional, parceria com celebridades e "marcas sólidas". Uma vítima relata uma "nova plataforma" com seguros e viagens e logos de supostos parceiros oficiais, sem vínculo real ("só lá no site deles … existia o logotipo") — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

**Fase 2: aceleração (indicação, reinvestimento, lock-up)**
- Kriptacoin pagava renda adicional a quem trouxesse novos investidores — [Teletime](https://teletime.com.br/21/09/2017/piramide-financeira-por-meio-de-moeda-digital-e-desbaratada-em-brasilia/)
- Braiscompany: contrato de "locação de criptoativos" de 12 meses, com o ativo custodiado e sem saque no período, rentabilidade mensal de 3% a 10% e deságio de 30% em caso de quebra unilateral antes do prazo (segundo reportagens e relatos de clientes) — [Jornal da Paraíba](https://jornaldaparaiba.com.br/_/163550); [Reclame Aqui](https://www.reclameaqui.com.br/braiscompany/valor-do-investimento_S8N7Mgxb9VNGp0bT/)
- Braiscompany: segundo ex-funcionário citado pela imprensa, só ~5% do capital dos clientes era de fato operado, e consultores eram obrigados a investir 30% do salário na empresa (relato de imprensa, não verificado de forma independente) — [O Antagonista](https://oantagonista.com.br/economia/antagonista-docs-exclusivo-o-escandalo-braiscompany/)
- No pico, a Unick captava ~R$ 40 milhões por dia — [Suno](https://www.suno.com.br/noticias/?p=41411)

**Fase 3: sinais de estresse**
- Nas entrevistas da CVM, quando os saques começam a falhar, as empresas alegam "problemas técnicos, troca de sistema, realocação de fundos". Relato: "Eles tinham bloqueado todos os saques. Uma série de desculpas, falando que era sistema, que era a rede de bitcoins…" — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Troca de moeda/"token próprio": vítimas relatam que a empresa de "arbitragem" converteu os bitcoins depositados "em uma moeda própria, um produto novo, com um valor relativamente menor que o original" — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf). A Trust Investing lançou a criptomoeda própria "Truster Coin" e atingiu ~1,3 milhão de pessoas em 80 países, com prejuízo de ~R$ 4,1 bilhões — [Campo Grande News](https://www.campograndenews.com.br/cidades/capital/justica-ouve-o-cabeca-de-grupo-suspeito-de-enganar-1-3-milhao-em-piramide)
- Culpa em terceiros (exchange): a Braiscompany atrasou pagamentos e culpou a Binance — [InfoMoney](https://www.infomoney.com.br/?p=2028161). Parou de pagar em dez/2022 e cessou de vez em jan/2023 — [Jornal da Paraíba](https://jornaldaparaiba.com.br/_/163550)
- Culpa em "volume atípico": depois do stop order da CVM (13/08/2019), a Atlas Quantum alegou que os valores estavam bloqueados nas exchanges por volume atípico de pedidos de saque — [InfoMoney](https://www.infomoney.com.br/mercados/o-nebuloso-caso-da-atlas-quantum-e-o-limbo-juridico-das-criptomoedas/); [Tecnoblog](https://tecnoblog.net/311165/atlas-quantum-arbitragem-bitcoin-saques-bloqueados/)
- Culpa em "hacker": em 2019, o Grupo Bitcoin Banco bloqueou todos os saques alegando ataque hacker — [InfoMoney](https://www.infomoney.com.br/?p=1355525); [Suno](https://www.suno.com.br/noticias/?p=163664)
- "Auditoria" como resposta ao regulador: uma vítima conta que, depois da notificação da CVM, a empresa apresentou uma auditoria aos investidores, "o que deu tranquilidade aos seus clientes para continuar investindo" — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Ataque ao regulador: a Atlas Quantum processou a CVM pedindo mais de R$ 3,16 bilhões por danos causados pelo stop order — [InfoMoney](https://www.infomoney.com.br/?p=1683301). A Unick ignorou o stop order da CVM — [Suno](https://www.suno.com.br/noticias/?p=41411)

**Fase 4: colapso**
- GAS: parou de pagar rendimentos depois da prisão de Glaidson Acácio dos Santos (25/08/2021) — [Suno](https://www.suno.com.br/noticias/?p=185262); segundo a imprensa, a mulher do "faraó" sacou R$ 1 bilhão antes de fugir — [Suno](https://www.suno.com.br/noticias/?p=181219)
- Na pesquisa da CVM, o colapso é percebido por "rumores" de atraso em grupos de investidores, até o bloqueio total dos saques — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

**Fase 5: pós-colapso (retomada, recuperação judicial, falência)**
- Grupo Bitcoin Banco: a Justiça do Paraná aceitou o pedido de recuperação judicial. A dívida declarada passava de R$ 600 milhões, mas o administrador judicial encontrou um rombo de quase R$ 2,7 bilhões — [Suno](https://www.suno.com.br/noticias/?p=45947). Depois veio a Operação Daemon da PF (fraude falimentar, estelionato, lavagem, crimes contra a economia popular e o SFN) — [Suno](https://www.suno.com.br/noticias/?p=163664)
- GAS: abriu um "canal de transparência" com o líder preso — [Suno](https://www.suno.com.br/noticias/?p=253989). Preso, Glaidson se filiou a partido para disputar vaga de deputado — [Suno](https://www.suno.com.br/noticias/?p=257257). A Justiça decretou a falência da GAS — [Folha PE](https://www.folhape.com.br/economia/justica-antecipa-falencia-da-gas-empresa-do-farao-dos-bitcoins/258681/); [Acionista](https://acionista.com.br/justica-decreta-falencia-da-g-a-s-consultoria-do-farao-dos-bitcoins-e-expoe-rombo-de-r-38-bilhoes/). Em ação coletiva, foi ordenado o bloqueio de R$ 17 bilhões em favor de até 300 mil lesados — [Mais Goiás](https://www.maisgoias.com.br/brasil/bloqueio-de-r-17-bilhoes-em-acao-coletiva-pode-favorecer-ate-300-mil-clientes-do-farao-dos-bitcoins/)
- Esquemas longos: a Operação Queops (RJ) mirou uma pirâmide que movimentou ~R$ 1 bilhão em quase 10 anos — [InfoMoney](https://www.infomoney.com.br/?p=2653813)

### Inferences
- O momento mais perigoso para o investidor é o fim da fase 2 e o começo da fase 3. Os primeiros atrasos vêm acompanhados de "novas regras" (token, migração, auditoria) que tentam converter saldo sacável em saldo ilíquido, ganhando tempo e retendo caixa.
- Ao processar ou desqualificar o regulador (Atlas contra a CVM), o esquema reforça a narrativa de perseguição, que ajuda a reter investidores (ver seção 4).
- Recuperação judicial e "canais de transparência" funcionam na prática como instrumento para ganhar tempo e manter a esperança de "retomada". No caso Bitcoin Banco, o rombo apurado foi ~4,5x o declarado.

### Gaps
- Não achei fonte sólida sobre o "golpe da recuperação" (falsos advogados ou empresas cobrando taxa para "recuperar" o dinheiro de vítimas de pirâmide) com caso brasileiro documentado. As buscas trouxeram só referências esparsas.
- Também faltou fonte para "migração de plataforma" como evento nomeado num caso brasileiro específico. A conversão em moeda própria está documentada (CVM/Trust); a migração como evento, não.

## 3. Técnicas de captação: afinidade, influenciadores, jargão técnico e engenharia contratual

### Takeaway
No Brasil, a captação combina confiança interpessoal (igreja, cidade, quartel, colegas de trabalho, amigos via WhatsApp) com verniz de sofisticação: "arbitragem", "robô", forex, cripto e contratos atípicos como locação de cripto, SCP ou "parceria", usados para escapar do enquadramento como valor mobiliário. Influenciadores e celebridades ampliam o alcance. A pesquisa internacional mostra que afinidade, alvo em idosos e incentivo pago a recrutadores tornam o esquema maior e mais duradouro.

### Cited Findings

**Evidência acadêmica**
- Nos 376 Ponzis da SEC (1988–2012), o "sucesso" do esquema (duração, valor captado, fatia dos fraudadores) é maior quando há vínculo de afinidade, quando idosos são o alvo e quando o fraudador paga terceiros para recrutar. Ponzis também são mais prováveis em estados americanos com população mais confiante — [Deason, Rajgopal & Waymire (SSRN, 2015)](https://papers.ssrn.com/abstract=2586490)
- Frankel analisa centenas de casos para explicar como golpistas atraem pessoas ricas, instruídas e até instituições, imitando "sinais" de verdade e honestidade e desviando a atenção dos pontos fracos da história — [Frankel, *The Ponzi Scheme Puzzle* (OUP, 2012)](https://scholarship.law.bu.edu/books/16)

**Afinidade religiosa**
- "Golpe da Fé" (RJ): banco digital falso ligado a uma igreja evangélica ("Banco do Pastor"), que prometia até 10% a.m. O líder religioso usava a posição para conquistar a confiança dos fiéis — [CartaCapital](https://www.cartacapital.com.br/?p=304533); [BP Money](https://bpmoney.com.br/?p=417690)
- Operação "Falso Profeta" (DF e outros estados): grupo liderado pelo pastor Osório José Lopes Júnior, com mais de 50 mil vítimas e ~R$ 156 milhões em prejuízo. Misturava religião evangélica com uma teoria conspiratória sobre "reset financeiro global" e alienígenas — [Correio Braziliense](https://www.correiobraziliense.com.br/cidades-df/2023/09/5127474-pastor-apontado-por-ter-feito-mais-de-50-mil-vitimas-e-preso-no-to.html); [Correio Braziliense (como funcionava)](https://www.correiobraziliense.com.br/cidades-df/2023/09/amp/5127115-entenda-como-funcionava-esquema-de-golpe-milionario-liderado-por-pastor.html)
- Goiás: pastor, o filho (servidor da Polícia Civil) e um membro da igreja foram denunciados pelo MP por pirâmide de mais de R$ 500 mil — [Mais Goiás](https://www.maisgoias.com.br/cidades/pastor-e-outras-tres-pessoas-sao-denunciados-por-aplicar-golpes-atraves-de-piramide-financeira/)
- Segundo a imprensa, Glaidson (GAS) é ex-pastor da Igreja Universal, e as vítimas eram sobretudo famílias, trabalhadores, aposentados e pequenos empresários — [Mais Goiás](https://www.maisgoias.com.br/brasil/bloqueio-de-r-17-bilhoes-em-acao-coletiva-pode-favorecer-ate-300-mil-clientes-do-farao-dos-bitcoins/)
- Na pesquisa da CVM, 2,8% das vítimas investiram por indicação de membro de comunidade religiosa, contra 0,4% das não vítimas — [CVM/CECOP (2021), Tabela 2](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

**Afinidade geográfica (cidades e regiões)**
- Cabo Frio e a Região dos Lagos ganharam o apelido de "Novo Egito" pela concentração de pirâmides — [O Povo](https://www.opovo.com.br/noticias/economia/2021/09/06/com-as-piramides-cabo-frio-se-torna-o-novo-egito.html)
- TelexFree: segundo o MPAC, ~70 mil pessoas investiram só no Acre — [Conjur](https://www.conjur.com.br/?p=471803)
- Braiscompany (Campina Grande/PB): o MPPB fala em pelo menos 3.300 vítimas e prejuízo de US$ 260 milhões — [InfoMoney](https://www.infomoney.com.br/?p=2138909)

**Afinidade profissional/militar**
- Operação Queops (RJ): a rede mirava sobretudo militares, aposentados, pensionistas e servidores públicos, usando 15 empresas abertas só para o golpe — [InfoMoney](https://www.infomoney.com.br/?p=2653813); [Correio da Manhã](https://www.correiodamanha.com.br/rio-de-janeiro/2024/11/165230-piramide-financeira-desaba.html)
- PMDF: um sargento recrutou colegas do 6º Batalhão para a "Liberty Up", suposta rede de investimento em cripto que quebrou. O MP investiga a cooptação — [Correio Braziliense](https://www.correiobraziliense.com.br/cidades-df/2024/06/6875619-mp-investiga-sargento-da-pm-suspeito-de-cooptacao-para-piramide-financeira.html)
- DF: advogados investigados por pirâmide que enganou até policiais civis — [Metrópoles](https://www.metropoles.com/distrito-federal/df-advogados-aplicam-golpe-da-piramide-financeira-e-enganam-ate-policiais)
- Colega de trabalho: uma vítima entrevistada pela CVM conta que o recrutador foi seu ex-chefe, "executivo que ocupou cargos importantes", e que tudo correu "no boca-a-boca" entre ex-colegas — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

**Influenciadores e celebridades**
- A CPI das Pirâmides Financeiras (Câmara, 2023) aprovou relatório de 509 páginas e pediu o indiciamento de 45 pessoas, entre elas Ronaldinho Gaúcho e o irmão Assis, além de Glaidson — [SBT News](https://sbtnews.sbt.com.br/noticia/congresso/262364-cpi-das-piramides-financeiras-aprova-relatorio-final); a CPI convocou celebridades como Cauã Reymond e Tatá Werneck — [B3/Bora Investir](https://borainvestir.b3.com.br/tipos-de-investimentos/renda-variavel/criptoativos/o-que-e-a-cpi-das-piramides-que-ja-convocou-caua-reymond-tata-werneck-e-ronaldinho-gaucho/)
- Na CVM, as vítimas investiram por indicação de youtuber em 29,8% dos casos (não vítimas: 17,2%) e de celebridade em 6,7% (não vítimas: 2,1%) — [CVM/CECOP (2021), Tabela 2](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

**Canais de difusão**
- O canal mais citado pelas vítimas é o WhatsApp (27,5%), seguido de boca a boca presencial (19,7%), e-mail (12,4%) e telefone (12,4%). Metade das vítimas conhecia o fraudador de alguma forma (28,1% pessoalmente; 21,9% por terceiros ou pela mídia) — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

**Jargão técnico e "tecnologia" como isca**
- Mercados citados pelas vítimas: criptomoedas (43,3%), forex (29,8%), opções binárias (16,9%) e ações (15,2%). Os esquemas atraíam por oferecer "solução prática" para quem não queria acompanhar o mercado, e o interesse na tecnologia, sobretudo "arbitragem de criptomoedas", aparece explicitamente — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Atlas Quantum: dizia fazer arbitragem de bitcoin com robô proprietário. A CVM classificou o produto como contrato de investimento coletivo (CIC) sem registro — [InfoMoney](https://www.infomoney.com.br/?p=1683301); [CVM, memorando de 13/08/2019](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2019/20190813_memorando_ger3_sre_atlas.pdf-b64a18938d8144b687a7a991df2d7952)
- Unick Forex: compra e venda de moeda (forex), atividade restrita a instituições autorizadas — [Suno](https://www.suno.com.br/noticias/?p=41411)
- "Robô" com 1% ao dia (SP) — [Suno](https://www.suno.com.br/noticias/?p=286876)

**Engenharia contratual para fugir da CVM**
- Locação de criptoativos (Braiscompany): contratos que, segundo a PF, movimentaram ~R$ 1,5 bilhão de forma irregular — [InfoMoney](https://www.infomoney.com.br/?p=2059498)
- Sociedade em Conta de Participação (SCP): a CVM já suspendeu ofertas de CIC estruturadas como SCP, como Tropical Flora Reflorestadora (reflorestamento) e a plataforma Divi Hub — [OKAI/CVM](https://okai.com.br/noticia/2006-01-03/cvm-determina-suspensao-de-oferta-de-cic-pela-tropical-flora-reflorestadora-ltda); [Monitor Mercantil](https://monitormercantil.com.br/cvm-suspende-oferta-da-plataforma-de-crowdfunding-divi-hub/); [CVM, decisão de 2019](https://conteudo.cvm.gov.br/cvm_institucional/export/sites/cvm/decisoes/anexos/2019/20190312/1340-19.pdf)
- Sede/operação no exterior como justificativa: uma vítima ouviu que "não havia necessidade da CVM, uma vez que as movimentações eram feitas fora do Brasil" — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf). A Trust Investing operava em 80 países — [Campo Grande News](https://www.campograndenews.com.br/cidades/capital/justica-ouve-o-cabeca-de-grupo-suspeito-de-enganar-1-3-milhao-em-piramide)
- Pagamento para conta de pessoa física: no perfil "movidos pela confiança", os pagamentos iam por cartão de crédito ou transferência para conta PF ou PJ — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Capital social baixo: a CPI apontou que a 123 Milhas destinou verba "bilionária" de publicidade a uma agência com capital social de R$ 10 mil. *Ressalva:* a 123 Milhas é caso controverso, e o relator falou em "esquema pirâmide" — [BP Money](https://bpmoney.com.br/mercado/123-milhas-fraude-na-contabilidade-e-esquema-piramide-diz-relator/)

### Inferences
- A afinidade funciona como substituto da due diligence: a confiança no grupo (igreja, batalhão, firma) é transferida para o produto. Isso casa com o achado da CVM de que as vítimas confiam menos nas instituições e mais em indicação.
- O jargão (arbitragem, HFT, robô, IA, blockchain) cumpre dupla função. Explica o retorno impossível ("é a tecnologia") e intimida o questionamento ("você não entende").
- Contratos de "locação", "mútuo", "parceria" ou SCP são indício em si. A CVM olha a substância econômica (oferta pública de investimento com expectativa de lucro gerada pelo esforço de terceiros = CIC/valor mobiliário), não o nome do contrato.

### Gaps
- Não achei caso brasileiro documentado de pirâmide estruturada como "contrato de mútuo" com stop order específico (sei que é padrão comum, mas fica sem fonte).
- Não achei fonte de qualidade para eventos/palestras de luxo e ostentação como técnica sistemática em caso brasileiro. Há só indícios (saque de R$ 1 bi da mulher do "faraó").
- Não achei fonte oficial (CVM/BCB) que liste "CNPJ recém-aberto" e "capital social baixo" como sinal de alerta formal. Sobre pirâmides que usam "IA" como isca em 2025–2026, só achei fontes secundárias fracas.

## 4. Psicologia e perfil das vítimas: vieses, defesa do esquema, vítima-recrutador e risco jurídico

### Takeaway
O dado brasileiro mais robusto (CVM/CECOP, 2020–2021) contraria o estereótipo. A vítima típica é homem, de 30–49 anos, escolarizado, que já investe e não está endividado. Ele confia mais em indicação (amigos, youtubers) do que em instituições, acredita que "os maiores retornos estão fora do regulado" e é mais suscetível ao efeito manada. Os golpes ficaram menos exagerados para parecer plausíveis. Quem recruta, mesmo que tenha sido vítima, pode responder civilmente (CDC, "fornecedor aparente") e penalmente (Lei 1.521/51; art. 171-A do CP).

### Cited Findings

**Pesquisa CVM/CECOP (quantitativa jun–jul/2020; qualitativa nov/2020)**
- Metodologia: questionário online enviado a reclamantes da CVM (2017–2019) e voluntários, com 1.002 respostas, 178 delas de vítimas. Foram feitas 12 entrevistas qualitativas. A amostra não representa a população nacional — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Perfil: 91% homens (90,5% na tabela), 36,5% com 30–39 anos e 26,4% com 40–49. No texto, 23% têm renda de 2–5 salários mínimos e 38% têm pós-graduação. *Divergência interna:* a Tabela 5 do anexo dá 28,5% para renda de 2–5 SM e 42,4% para pós-graduação — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Não é desespero financeiro: 65,7% não estavam endividados. A finalidade era "lucrar, mas sem finalidade definida" para 35%, "diversificar o portfólio" para 17% e pagar dívidas para só 7%. A hipótese H2 (cai quem está em dificuldade) não foi sustentada — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Quem cai já investe: só 9,6% das vítimas não tinham investimentos (não vítimas: 1,3%). As vítimas têm mais cripto (27,5% contra 11,7%) e menos produtos regulados (ações, fundos, Tesouro, CDB) — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- O que contribuiu para cair (múltipla escolha): site com aparência profissional (39,9%), familiares ou amigos que já tinham investido (38,8%, prova social), bom atendimento (35,4%), investimento pequeno exigido (30,9%) e desconhecimento da modalidade (24,7%). Pressão do fraudador foi citada por só 4,5% — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Vieses, em escala de 0 a 10, com diferença significativa entre vítimas e não vítimas (Tabela 4):
  - "Os maiores retornos … vêm de investimentos que não são regulados pelo governo": 4,80 contra 2,87.
  - "Quando quase todo mundo concorda com algo, não faz sentido tentar se opor" (efeito manada): 3,79 contra 2,60.
  - "Gosto de ficar atento a oportunidades que ninguém conhece ainda": 5,97 contra 4,88.
  - "Trabalho demais e sou pouco recompensado": 5,41 contra 4,03.
  - "Confio na minha capacidade de identificar fraudes": 5,20 contra 6,85, ou seja, menor entre as vítimas.
  - Fonte: [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- FOMO medido: "Se vejo uma oferta promissora, ingresso rapidamente para não perder a oportunidade" deu 3,66 contra 3,19, diferença marginal e não significativa (p=0,052) — [CVM/CECOP (2021), Tabela 4](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Três perfis qualitativos: (1) "pagaram para ver", que suspeitavam do golpe e queriam "ser mais esperto" que o fraudador; (2) "movidos pela confiança", em quem indicou ou no produto, com esquemas de 2–3% a.m.; (3) "entusiastas" de mercado atraídos por arbitragem de cripto — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Conclusão-chave: "a fórmula estereotipada dos golpes financeiros (como rentabilidades exorbitantes, bônus por indicação de terceiros e garantia de lucros) não define mais os golpes". Os esquemas "diminuíram os exageros" e incorporaram elementos de credibilidade — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Alertas da CVM não bastam: há quem não entendeu se a empresa estava proibida de operar ou só de captar, quem se tranquilizou com uma "auditoria" apresentada pela empresa e quem não achou a informação no site da CVM e investiu mesmo assim — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Subnotificação: 46,6% registraram reclamação ou denúncia. Quem não denunciou alegou dinheiro dado como perdido, vergonha e "medo de ser considerado cúmplice (o que é comum em casos de investimentos por indicação)" — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Revisão teórica da CVM, com literatura internacional:
  - AARP (2003): vítimas de fraude de investimento acreditam mais que controlam a situação e confiam nos próprios palpites, e fraudadores preferem pessoas inteligentes, vítimas da própria autoconfiança.
  - AARP (2017): homens mais velhos, mais instruídos, mais expostos a vendas, que tratam o acúmulo de dinheiro como medida de sucesso.
  - Titus (1999): em pirâmides, a vítima costuma ser vista como cúmplice, o que a afasta da Justiça.
  - Fonte: [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Experimento da CVM (2024): "quase metade das pessoas que acessaram site de falsa corretora cairia em golpe financeiro" — [CVM, notícia de 2024](https://www.gov.br/cvm/pt-br/assuntos/noticias/2024/quase-metade-das-pessoas-que-acessaram-site-de-falsa-corretora-cairia-em-golpe-financeiro)

**Escala do problema no Brasil**
- O Anuário Brasileiro de Segurança Pública (FBSP, 20ª ed.) registra 2.261.055 estelionatos em 2025 (+3,1% sobre 2024; +429,8% sobre 2018), cerca de 258 por hora. Segundo pesquisa do FBSP, 15,8% da população de 16+ anos (≈26,3 milhões) sofreu golpe ou perdeu dinheiro por internet/celular em 2025 — [Brasil 61](https://brasil61.com/n/anuario-de-seguranca-publica-brasil-registrou-mais-de-2-2-milhoes-de-casos-de-estelionato-em-2025-bras2616801); [BNews](https://www.bnewssaopaulo.com.br/noticias/policia/estelionato-bate-recorde-e-brasil-registra-258-golpes-por-hora-aponta-anuario.html)
- Pelo Raio X do Investidor (ANBIMA/Datafolha, 9ª ed., dados de 2025), 34% dos brasileiros passaram por pelo menos uma tentativa de fraude ou golpe financeiro em 2025. Entre investidores foram 42%; na classe AB, 47% — [ANBIMA, Raio X 9ª ed. (PDF)](https://static.poder360.com.br/uploads/2026/07/Raio-X-do-Investidor-9-edicao-23-jul-2026.pdf); [Finsiders](https://finsidersbrasil.com.br/?p=365771)
- Atuação da CVM: no 2º tri/2025 foram 115 ofícios de alerta (contra 46 no 1º tri), 10 stop orders e 23 comunicações ao MP (7 estaduais e 16 federais) — [CVM](https://www.gov.br/cvm/pt-br/assuntos/noticias/2025/cvm-emite-115-oficios-de-alerta-no-2o-trimestre-de-2025). Em 2020, a CVM mandou 175 casos com indício de pirâmide às promotorias, 75% a mais que em 2019 — [Suno](https://www.suno.com.br/noticias/?p=181385)

**Vítimas que defendem o esquema**
- TelexFree: o MPF recebeu um grupo que protestou *a favor* da empresa — [InfoMoney](https://www.infomoney.com.br/?p=184542)
- A GAS manteve um "canal de transparência" e o líder preso lançou pré-candidatura política, sinal de que restava base de apoio — [Suno](https://www.suno.com.br/noticias/?p=253989); [Suno](https://www.suno.com.br/noticias/?p=257257)

**Vítima que vira recrutador e o risco jurídico**
- Lei 1.521/1951, art. 2º, IX: crime contra a economia popular "obter ou tentar obter ganhos ilícitos em detrimento do povo ou de número indeterminado de pessoas mediante especulações ou processos fraudulentos ('bola de neve', 'cadeias', 'pichardismo' e quaisquer outros equivalentes)" — [Planalto, Lei 1.521/51](https://www.planalto.gov.br/ccivil_03/leis/l1521.htm)
- Lei 14.478/2022 (marco dos criptoativos) criou o art. 171-A do Código Penal. O crime é "organizar, gerir, ofertar ou distribuir carteiras ou intermediar operações" com ativos virtuais, valores mobiliários ou ativos financeiros para obter vantagem ilícita mediante fraude, com pena de reclusão de 4 a 8 anos e multa. A doutrina o vê como crime formal, que dispensa prova de dano econômico — [Empório do Direito](https://emporiododireito.com.br/leitura/o-novo-crime-de-fraude-com-a-utilizacao-de-ativos-virtuais-valores-mobiliarios-ou-ativos-financeiros); [Planalto, Lei 14.478/22](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14478.htm)
- A Comissão de Segurança Pública do Senado aprovou projeto com pena de até 8 anos para o crime de pirâmide (consta apenas o título da notícia; tramitação não verificada) — [Evinis Talon](https://evinistalon.com/senado-csp-aprova-pena-de-ate-8-anos-para-o-crime-de-piramide-financeira)
- Responsabilidade civil de divulgador: o TJPR (2ª Turma Recursal) condenou o influenciador "Sharkão" por divulgar pirâmide. Tratou a publicidade como ato ilícito com responsabilidade objetiva e o enquadrou como "fornecedor aparente" pelo CDC (teoria da aparência), por divulgar o investimento como próprio sem sinalizar publicidade — [Bem Paraná](https://www.bemparana.com.br/justica/justica-do-parana-condena-influenciador-digital-que-divulgou-golpe-de-esquema-de-piramide/). A influenciadora GKay foi processada por suposto envolvimento em pirâmide — [A Tarde](https://atarde.com.br/a-tarde-/entretenimento2/gkay-e-processada-por-suposto-envolvimento-em-piramide-financeira-1226104)
- TelexFree: todos os contratos com divulgadores foram declarados nulos. A empresa foi condenada a devolver os valores investidos, *descontado o que cada um recebeu como lucro*, e a pagar R$ 3 milhões em dano moral coletivo — [Conjur](https://www.conjur.com.br/?p=471803)
- Braiscompany: segundo a imprensa, a Justiça Federal condenou os fundadores Antonio Inácio da Silva Neto (88 anos e 7 meses) e Fabrícia Farias (61 anos e 11 meses) e mais nove réus, com indenização de R$ 277 milhões por danos materiais e R$ 100 milhões por danos coletivos — [A União](https://auniao.pb.gov.br/noticias/caderno_paraiba/justica-federal-condena-ex-diretor-da-braiscompany-a-mais-de-36-anos)
- Trust Investing: a Justiça Federal condenou seis réus. Patrick Abrahão e o pai, Ivonélio, pegaram penas de 12 e 13 anos — [Campo Grande News](https://www.campograndenews.com.br/cidades/capital/justica-ouve-o-cabeca-de-grupo-suspeito-de-enganar-1-3-milhao-em-piramide)
- Recrutador de dentro da corporação: o MP investiga um sargento da PMDF por cooptar colegas para a Liberty Up — [Correio Braziliense](https://www.correiobraziliense.com.br/cidades-df/2024/06/6875619-mp-investiga-sargento-da-pm-suspeito-de-cooptacao-para-piramide-financeira.html)

### Inferences
- O perfil "investidor confiante, escolarizado e desconfiado do sistema" explica por que vítimas atacam a CVM e a Justiça. Quem acredita que "o melhor retorno está fora do regulado" lê o alerta oficial como confirmação de que o esquema é "disruptivo" (viés de confirmação). Quem já recebeu rendimentos e indicou amigos tem custo afundado financeiro e reputacional para admitir a fraude.
- O vínculo recrutador–recrutado cria um "pacto de silêncio". Quem indicou teme ser visto como cúmplice (achado da CVM) e responsabilizado (Sharkão, art. 171-A, Lei 1.521), então tende a defender o esquema até o fim. Isso prolonga a fase de estresse e aumenta o prejuízo.
- Como o FOMO declarado não diferiu de forma significativa e a pressão foi citada por só 4,5%, o gatilho central no Brasil parece ser *confiança + prova social*, não urgência. Campanhas de prevenção focadas em "desconfie da pressa" atacam o vetor menos relevante.
- Ponto jurídico não verificado nesta pesquisa: pela Súmula 498 do STF, crimes contra a economia popular são em regra da Justiça Estadual. A competência vai para a Federal quando há oferta de valor mobiliário/CIC ou crime contra o SFN (Lei 7.492/86). Confirmar com especialista.

### Gaps
- Não achei estudo acadêmico brasileiro que meça custo afundado, viés de confirmação ou "defesa do esquema" em vítimas de pirâmide (só relatos e teoria).
- Não consultei as pesquisas de golpes da Serasa e da Febraban (sem tempo); ficam como lacuna.
- Também ficou sem fonte jurisprudência do STJ sobre responsabilização penal de "líderes de rede" ou top recruiters que também perderam dinheiro, e sobre restituição de lucros recebidos por participantes antigos, salvo o caso TelexFree.

## 5. Sinais de alerta consolidados: checklist único (CVM, SEC, FTC, pesquisa CVM/CECOP e casos)

### Takeaway
Juntando as listas da CVM, da SEC e da FTC com os achados empíricos da CVM e os casos brasileiros, chega-se a ~20 sinais sem duplicação, em cinco blocos: promessa, remuneração, registro/contraparte, credibilidade fabricada e estresse. Pela pesquisa da CVM, os sinais de *estrutura* (registro, origem do retorno, contrato) resistem melhor que os de *exagero*, porque os golpes ficaram mais "modestos".

### Cited Findings

**Fontes oficiais de base**
- CVM: altas taxas de adesão ou investimento inicial; ênfase no recrutamento sobre vendas reais; promessa de rentabilidade acima do mercado; prazos curtos de retorno — [CVM/Portal do Investidor](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi)
- SEC (7 red flags): (1) retorno alto com pouco ou nenhum risco; (2) retornos consistentes demais; (3) investimento não registrado; (4) vendedor sem licença; (5) estratégia secreta ou complexa; (6) problemas com documentação; (7) dificuldade para receber pagamentos ou sacar — [SEC (arquivada)](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm)
- FTC: promessas exageradas de ganho tratadas como fato; recrutamento como "o jeito real de ganhar dinheiro"; táticas de alta pressão; distribuidores comprando estoque além do que conseguem revender — [FTC](https://consumer.ftc.gov/articles/multi-level-marketing-businesses-pyramid-schemes)
- Consulta de irregulares: a CVM mantém a lista de "Ofertas/Atuações irregulares" (alertas e stop orders) — [CVM](https://www.gov.br/cvm/pt-br/assuntos/protecao/alertas/ofertas-atuacoes-irregulares)

**Checklist consolidado (cada item com a origem; sem duplicação)**

*A. A promessa*
1. **Retorno fixo, "garantido" ou "sem risco".** Todo investimento tem risco, e quanto mais retorno, mais risco — [SEC](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm); [CVM](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi)
2. **Rentabilidade acima do mercado e em prazo curto.** Referência de out/2026: CDI ≈ 1,07% a.m. e 13,65% a.a. Promessas de 2–3% a.m. já são 2–3x isso — [CVM](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi); [BCB/SGS 4389](https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/3?formato=json); [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
3. **Retornos sempre positivos e lineares, independentemente do mercado.** A CVM notou que as vítimas não perceberam "os retornos sempre positivos" — [SEC](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm); [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
4. **Estratégia secreta, complexa ou "tecnológica"** (arbitragem, robô, HFT, IA, forex, "mineração") sem explicação verificável de onde vem o lucro. Exemplos: Atlas com arbitragem, Unick com forex, robô de 1% ao dia em SP — [SEC](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm); [InfoMoney/Atlas](https://www.infomoney.com.br/?p=1683301); [Suno/Unick](https://www.suno.com.br/noticias/?p=41411)

*B. A forma de ganhar*
5. **O dinheiro vem principalmente de recrutar**, com bônus por indicação, "níveis" ou "rede" (ex.: Kriptacoin) — [CVM](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi); [FTC](https://consumer.ftc.gov/articles/multi-level-marketing-businesses-pyramid-schemes); [Teletime/Kriptacoin](https://teletime.com.br/21/09/2017/piramide-financeira-por-meio-de-moeda-digital-e-desbaratada-em-brasilia/)
6. **Taxa de adesão ou "kit" alto, ou compra de estoque**, desproporcional ao produto — [CVM](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi); [FTC](https://consumer.ftc.gov/articles/multi-level-marketing-businesses-pyramid-schemes)
7. **Produto de fachada, sem demanda real** fora da rede (ex.: VoIP da TelexFree, que o MPAC tratou como disfarce) — [CVM](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi); [Conjur/TelexFree](https://www.conjur.com.br/?p=471803)

*C. Registro, contrato e contraparte*
8. **Sem registro ou autorização** da CVM (oferta de investimento) ou do BCB (instituição financeira; desde 02/02/2026, prestadora de serviços de ativos virtuais), e vendedor sem habilitação. Consultar a lista de irregulares da CVM. Exemplo: a Unick ignorou stop order — [SEC](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm); [CVM, irregulares](https://www.gov.br/cvm/pt-br/assuntos/protecao/alertas/ofertas-atuacoes-irregulares); [Lefosse/BCB Res. 519–521](https://lefosse.com/noticias/alerta/banco-central-regulamenta-o-uso-de-ativos-virtuais-e-o-funcionamento-das-prestadoras-de-servicos-de-ativos-virtuais/); [Suno/Unick](https://www.suno.com.br/noticias/?p=41411)
9. **Contrato com nome atípico** ("locação de cripto", "parceria", SCP, "mútuo", "consultoria") para algo que é, na prática, oferta pública de investimento (CIC) — [InfoMoney/Braiscompany](https://www.infomoney.com.br/?p=2059498); [CVM/Atlas, memorando](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2019/20190813_memorando_ger3_sre_atlas.pdf-b64a18938d8144b687a7a991df2d7952); [OKAI/SCP](https://okai.com.br/noticia/2006-01-03/cvm-determina-suspensao-de-oferta-de-cic-pela-tropical-flora-reflorestadora-ltda)
10. **Depósito em conta de pessoa física** ou de empresa sem relação com o produto — [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
11. **"Opera no exterior, não precisa de CVM"**, ou sede offshore — [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf); [Campo Grande News/Trust](https://www.campograndenews.com.br/cidades/capital/justica-ouve-o-cabeca-de-grupo-suspeito-de-enganar-1-3-milhao-em-piramide)
12. **Documentação ausente ou vaga**: sem demonstrações, sem contrato claro, sem custodiante identificado — [SEC](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm)
13. **Lock-up longo com multa pesada de saída** (ex.: 12 meses e deságio de 30% na Braiscompany) — [Jornal da Paraíba](https://jornaldaparaiba.com.br/_/163550)

*D. Credibilidade fabricada (não prova nada)*
14. **"Todo mundo que eu conheço está ganhando"**: prova social de amigos, família, igreja, quartel ou colegas. Fator de 38,8% das vítimas — [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf); [Deason et al.](https://papers.ssrn.com/abstract=2586490)
15. **Influenciador, youtuber ou celebridade** promovendo o produto como se fosse investimento próprio — [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf); [Bem Paraná/Sharkão](https://www.bemparana.com.br/justica/justica-do-parana-condena-influenciador-digital-que-divulgou-golpe-de-esquema-de-piramide/); [SBT News/CPI](https://sbtnews.sbt.com.br/noticia/congresso/262364-cpi-das-piramides-financeiras-aprova-relatorio-final)
16. **Site bonito, sede física, atendimento impecável, logos de "parceiros"** sem vínculo comprovável — [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
17. **Pressão ou urgência** ("vagas limitadas", "última chance"). Vale ressaltar que só 4,5% das vítimas brasileiras disseram ter se sentido pressionadas — [FTC](https://consumer.ftc.gov/articles/multi-level-marketing-businesses-pyramid-schemes); [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)

*E. Sinais de estresse (se você já está dentro)*
18. **Atraso ou dificuldade para sacar, com novas regras, taxas ou prazos** justificados por "troca de sistema", "rede bitcoin", "volume atípico" ou "realocação de fundos" — [SEC](https://webarchive.library.unt.edu/web/20130217084604mp_/http://www.sec.gov/answers/ponzi.htm); [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf); [Tecnoblog/Atlas](https://tecnoblog.net/311165/atlas-quantum-arbitragem-bitcoin-saques-bloqueados/)
19. **Culpa em terceiros** (exchange, hacker, banco, "bloqueio judicial", regulador) — [InfoMoney/Braiscompany–Binance](https://www.infomoney.com.br/?p=2028161); [InfoMoney/Bitcoin Banco–hacker](https://www.infomoney.com.br/?p=1355525); [InfoMoney/Atlas processa CVM](https://www.infomoney.com.br/?p=1683301)
20. **Saldo convertido em token, moeda ou "pontos" próprios**, ou "migração" para nova plataforma — [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf); [Campo Grande News/Trust](https://www.campograndenews.com.br/cidades/capital/justica-ouve-o-cabeca-de-grupo-suspeito-de-enganar-1-3-milhao-em-piramide)
21. **Resposta a alerta da CVM com "auditoria"** apresentada pela própria empresa, ou com ataques ao regulador — [CVM/CECOP](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
22. **Pós-colapso: promessas de "retomada"**, "canal de transparência" e recuperação judicial com o rombo ainda desconhecido — [Suno/GAS](https://www.suno.com.br/noticias/?p=253989); [Suno/Bitcoin Banco RJ](https://www.suno.com.br/noticias/?p=45947)

### Inferences
- Pela conclusão da CVM de que os golpes reduziram os exageros, os itens mais discriminantes hoje são 8 (registro), 9 (contrato atípico), 4 (origem opaca do retorno) e 18–20 (liquidez). O item 1 (retorno absurdo) perde força isolado.
- Um teste rápido de três perguntas cobre a maior parte do checklist: (1) quem regula, e consigo achar no site da CVM/BCB? (2) de onde sai exatamente o dinheiro que me pagam? (3) consigo sacar tudo amanhã sem multa? Se a resposta a qualquer uma for vaga, não invista.

### Gaps
- Não consegui acessar as listas específicas de red flags da IOSCO, da FINRA (página 404), da ANBIMA nem do BCB sobre pirâmides. O checklist usa CVM, SEC, FTC e a pesquisa CVM. Recomendo que o redator não atribua itens a essas quatro instituições sem verificação.
- A página da CVM sobre pirâmides acessada traz só 4 sinais. Outras cartilhas da CVM em PDF ("Proteção contra fraudes") não foram lidas.

## 6. Diferença prática entre pirâmide, Ponzi, MMN legítimo e investimento de alto risco regulado

### Takeaway
A linha divisória é *de onde vem o dinheiro* e *quem fiscaliza*. Na pirâmide, o ganho vem da adesão de recrutados. No Ponzi, vem dos aportes de novos investidores, mesmo sem recrutar. No MMN legítimo, vem da venda de produto com demanda real a consumidor final. No investimento de alto risco regulado (day trade em corretora autorizada, cripto em PSAV autorizada pelo BCB), o resultado vem do mercado, pode ser negativo e isso é declarado, com custódia e supervisão. Alto risco regulado não é golpe, mas também não é garantia: 97% dos day traders persistentes perderam dinheiro.

### Cited Findings
- Pirâmide contra Ponzi: na pirâmide os ganhos dependem de recrutar. No Ponzi, os lucros também vêm de recursos novos, mas o investidor não precisa recrutar — [CVM/Portal do Investidor](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi)
- MMN legítimo: oferece "produtos que de fato são demandados pelo mercado", enquanto a pirâmide vende produtos sem valor relevante — [CVM/Portal do Investidor](https://www.gov.br/investidor/pt-br/investir/cuidados-ao-investir/evitando-problemas/principais-fraudes-e-esquemas-irregulares/piramides-financeiras-e-esquemas-ponzi). Critério da FTC: o MMN que não é pirâmide paga "com base nas suas vendas a clientes de varejo, sem ter de recrutar novos distribuidores". Mesmo no MMN legítimo, "a maioria … ganha pouco ou nada" e alguns perdem — [FTC](https://consumer.ftc.gov/articles/multi-level-marketing-businesses-pyramid-schemes)
- Caso-limite brasileiro: a TelexFree dizia vender pacotes de VoIP por MMN. A Justiça do Acre concluiu que era pirâmide, porque as taxas de adesão dos novos pagavam os antigos. O STJ ressaltou que distinguir pirâmide de MMN exige reexame de fatos e provas — [Conjur](https://www.conjur.com.br/?p=471803); [Migalhas](https://www.migalhas.com.br/quentes/181816/stj-mantem-suspensas-operacoes-da-telexfree)
- Cripto regulada: as Resoluções BCB 519, 520 e 521 (10/11/2025) criaram as sociedades prestadoras de serviços de ativos virtuais (SPSAVs), nas modalidades intermediária, custodiante e corretora, com regras de autorização e funcionamento em vigor desde 02/02/2026. O capital mínimo vai de R$ 10,8 milhões a R$ 37,2 milhões conforme a atividade — [Lefosse](https://lefosse.com/noticias/alerta/banco-central-regulamenta-o-uso-de-ativos-virtuais-e-o-funcionamento-das-prestadoras-de-servicos-de-ativos-virtuais/); [Poder360 (comunicado BCB, PDF)](https://static.poder360.com.br/2025/11/bc-regulamenta-ativos-virtuais-funcionamento-10nov2025.pdf)
- Alto risco regulado, com perda real: dos 19.646 indivíduos que começaram a operar day trade em minicontratos de Ibovespa entre 2013 e 2015, 97% dos que persistiram mais de 300 dias perderam dinheiro. Só 1,1% ganhou mais que um salário mínimo e só 0,5% mais que o salário inicial de um caixa de banco — [Chague, De-Losso & Giovannetti, "Day Trading for a Living?" (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101); [RePEc/FGV](https://econpapers.repec.org/RePEc:fgv:eesptd:525)
- A CVM conclui que "embora os investimentos possuam riscos, o maior risco é realizar investimentos não regulados" — [CVM/CECOP (2021)](https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/pesquisas/relatorio-pesquisa-fraudes-fin.pdf)
- Uso legítimo de IA ou robôs para investir exige o registro cabível na CVM, conforme a atividade automatizada (fonte secundária) — [Renova Invest](https://renovainvest.com.br/?p=13696)

**Quadro comparativo para leigos (síntese das fontes acima)**

| Critério | Pirâmide | Ponzi | MMN legítimo | Alto risco regulado (day trade, cripto em PSAV) |
|---|---|---|---|---|
| De onde vem o ganho | Taxas de adesão de recrutados | Aportes de novos investidores | Venda de produto a consumidor final | Resultado de mercado (pode ser negativo) |
| Precisa recrutar? | Sim, é o motor | Não obrigatório | Opcional; ganho não depende de recrutar | Não |
| Retorno prometido | Alto, fixo e rápido | Alto, fixo e "consistente" | Comissão variável sobre vendas | Nenhum; risco declarado |
| Quem fiscaliza | Ninguém (crime) | Ninguém (crime) | Direito do consumidor/comercial (não é investimento) | CVM/B3 (corretora) e BCB (PSAV desde 2026) |
| Saque e custódia | Restrito, com lock-up e multa | Restrito no estresse | N/A | Ativo em nome do cliente, em custodiante regulado |
| Exemplo BR | Kriptacoin, TelexFree | GAS, Braiscompany, Bitcoin Banco | (venda direta com produto de consumo real) | Minicontrato em corretora autorizada |

### Inferences
- Para o leigo, o teste prático tem quatro passos: (1) a instituição está autorizada (CVM para valores mobiliários; BCB para banco, corretora de câmbio e PSAV)? (2) o ativo fica em meu nome num custodiante independente? (3) existe promessa de retorno? (4) meu ganho depende de trazer gente? Investimento regulado de alto risco responde "sim, sim, não, não". Pirâmide e Ponzi respondem o contrário em pelo menos dois itens.
- O regime de PSAV em vigor desde 02/02/2026 dá ao investidor de cripto, pela primeira vez, um teste objetivo de registro no BCB. Plataforma que oferece "rendimento fixo em cripto" sem ser autorizada passa a ter um sinal de alerta inequívoco.
- O caso day trade mostra que "regulado" não significa "lucrativo". A diferença está na transparência do risco e na inexistência de promessa, não no retorno esperado.

### Gaps
- Não verifiquei se há período de transição ou regime de adequação para PSAVs já em operação antes de 02/02/2026, nem como o investidor consulta a lista de PSAVs autorizadas no site do BCB.
- Não li o Parecer de Orientação CVM 40 (criptoativos como valores mobiliários) nem a regulação de venda direta e MMN no Brasil (não há lei específica de MMN localizada nesta pesquisa).
