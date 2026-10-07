# Linha do tempo (ciclo de vida) das pirâmides brasileiras sem fachada de cripto/forex, 1990 a out/2026

> Notas de pesquisa. Data: 07/10/2026. Escopo: Brasil, esquemas cuja fachada principal NÃO é cripto nem forex. Foco cronológico: quando começou, quanto prometeu, quando apareceram os primeiros alertas e sinais de estresse, quando parou de pagar, quando houve intervenção e o que o operador fez no fim. Eventos legais entram só como marcos de data.
> Ponto de partida: notas anteriores em `research_notes/Pirâmides financeiras no Brasil/casos_historicos_pre_cripto.md` e `casos_recentes_2023_2026.md`. As fontes originais delas estão citadas abaixo. O que veio só de resumo de busca (página não aberta ou não atribuível) está marcado "(snippet)".
> Linguagem: "acusado"/"investigado" quando não há condenação. "n/e" = não encontrado.
> Conversão de retorno: "simples" = retorno total dividido pelos meses; "composto" = (1 + retorno total)^(1/meses) − 1. Contas feitas em Python nesta sessão.
> Classificação do gatilho do fim: (a) intervenção do Estado antes da quebra; (b) corrida de saques/falta de dinheiro novo; (c) choque externo; (d) fuga/sumiço do operador; (e) exposição na mídia; (f) disputa interna.

---

## 1. Casos agropecuários e de "contrato de investimento coletivo" (1990–2006): Boi Gordo, Gallus, Embrapek, Ouro Branco, Avestruz Master

### Takeaway
Nos esquemas de boi e avestruz o produto era físico e a promessa era moderada (Boi Gordo: cerca de 2% ao mês composto; Avestruz Master: 7–10% ao mês). Eles duraram anos: Boi Gordo 5,5 a 13,5 anos, Avestruz Master cerca de 2 a 3 anos na fase de captação pública. O padrão do fim é o mesmo nos dois casos com dados. Primeiro um alerta do regulador corta ou ameaça o dinheiro novo; o operador então troca a forma do produto (CIC → ações na Boi Gordo; contrato → CPR na Avestruz). O colapso por falta de caixa vem 7 a 11 meses depois. Para Gallus, Embrapek e Ouro Branco quase não há dados de ciclo de vida.

### Cited Findings

**1.1 Fazendas Reunidas Boi Gordo (SP/MT)**
- **Início / fachada:** empresa fundada em 1988 por Paulo Roberto de Andrade. Vendia contratos de "parceria"/CIC de engorda de gado — [Pública, 19/06/2018](https://apublica.org/2018/06/investigacao-indica-que-dinheiro-dos-credores-da-boi-gordo-virou-terra-em-matopiba/). Segundo a Notícias Agrícolas, o esquema "começou em 1996" — [Notícias Agrícolas, 20/11/2017](https://www.noticiasagricolas.com.br/noticia/202795). A divulgação de massa ("Quem tem cabeça investe em gado") passava nos intervalos da novela "O Rei do Gado" — [Folha Vitória/Estadão (curl)](https://www.folhavitoria.com.br/economia/justica-bloqueia-bens-de-donos-da-fazendas-reunidas-boi-gordo/). Entre 1999 e 2001, a empresa emitiu cerca de R$ 100 milhões em CICs sem autorização da CVM — [Capital Aberto, ~out/2003](https://capitalaberto.com.br/edicoes/agora-eles-vem-vestidos-de-governanca/)
- **Retorno prometido (as fontes divergem):**
  - "42% no prazo de 18 meses" — [Isto É Dinheiro, 09/11/2001](https://istoedinheiro.com.br/dez-licoes-para-o-tempo-de-vacas-magras). Conversão: 1,42^(1/18) − 1 = **1,97% ao mês composto** (2,33% simples).
  - "40% de lucro em um ano e meio", quando a pecuária rendia cerca de 9% ao ano — [Pública](https://apublica.org/2018/06/investigacao-indica-que-dinheiro-dos-credores-da-boi-gordo-virou-terra-em-matopiba/). Conversão: **1,89% ao mês composto**.
  - "42% em 30 meses" garantidos, mais um adicional conforme a arroba — [Isto É Dinheiro, 26/07/2000](https://istoedinheiro.com.br/arriscado-mas-nem-tanto). Conversão: **1,18% ao mês composto**.
  - Divergentes: "cerca de 4,25% ao mês" — [AgFeed (sem data visível)](https://agfeed.com.br/?p=46521); "3,5% a 5% ao mês" — (snippet de busca sem fonte identificável). Esses números não batem com os 40–42% em 18 meses das fontes de época.
- **Estrutura:** venda direta de contratos com publicidade em TV e celebridades. Não encontrei exigência de recrutamento, bônus por indicação nem taxa de adesão. Havia carência implícita: prazo de 18 a 30 meses até a "venda do boi gordo" — [Folha Vitória/Estadão](https://www.folhavitoria.com.br/economia/justica-bloqueia-bens-de-donos-da-fazendas-reunidas-boi-gordo/); [Isto É Dinheiro, 2000](https://istoedinheiro.com.br/arriscado-mas-nem-tanto). Não achei dado sobre incentivo a reinvestimento.
- **Pico:**
  - Em jul/2000, "menos de 21 mil pessoas" tinham contratos de boi no mercado inteiro — [Isto É Dinheiro, 2000](https://istoedinheiro.com.br/arriscado-mas-nem-tanto)
  - Na concordata, mais de 20 mil investidores e rombo de R$ 1,2 bilhão — [Isto É Dinheiro, 2001](https://istoedinheiro.com.br/dez-licoes-para-o-tempo-de-vacas-magras)
  - 28 mil investidores e R$ 1,234 bilhão em créditos de CICs — [Capital Aberto](https://capitalaberto.com.br/edicoes/agora-eles-vem-vestidos-de-governanca/)
  - Mais tarde: 30–33 mil credores — [Pública](https://apublica.org/2018/06/investigacao-indica-que-dinheiro-dos-credores-da-boi-gordo-virou-terra-em-matopiba/); [Sedep](https://www.sedep.com.br/?p=26876)
  - O pico fica entre 2000 e 2001.
- **Primeiro alerta público:**
  - Setorial: quebra da Gallus no início de 1998 e MP 1.637 de jan/1998 — [Isto É Dinheiro, 2000](https://istoedinheiro.com.br/arriscado-mas-nem-tanto)
  - Específico: a CVM recebeu denúncia anônima de um suposto funcionário em **14/02/2001** e aprovou em **27/03/2001** a **Deliberação CVM 376/01**, alertando o público sobre os CICs da Boi Gordo — (snippet de busca sobre material da CVM/USP; data confirmada indiretamente por [Isto É Dinheiro, 2001](https://istoedinheiro.com.br/dez-licoes-para-o-tempo-de-vacas-magras): "Em março, a CVM proibiu uma nova emissão de contrato da Boi Gordo"). A Capital Aberto diz que a CVM "baixou em março de 2001 uma deliberação suspendendo as operações" — [Capital Aberto](https://capitalaberto.com.br/edicoes/agora-eles-vem-vestidos-de-governanca/)
- **Sinais de estresse visíveis para quem estava dentro:**
  - 23/05/2001: pedido de registro de companhia aberta e de quatro séries de CICs, duas para regularizar emissões ilegais.
  - **26/06/2001**: pedido para emitir 3,1 bilhões de ações e **trocá-las pelos CICs**, "com a finalidade de reduzir o passivo com os investidores". Na prática, uma troca de "moeda"/plano.
  - 20/08/2001: a CVM aprovou os registros, "exatos 57 dias antes" da concordata.
  - Fonte dos três itens: [Capital Aberto](https://capitalaberto.com.br/edicoes/agora-eles-vem-vestidos-de-governanca/)
  - O controlador mudou-se para Comodoro (MT) dois meses antes do pedido de concordata, feito lá. Advogados de credores contestaram a escolha do foro como manobra — (snippet de busca; [Pública](https://apublica.org/2018/06/investigacao-indica-que-dinheiro-dos-credores-da-boi-gordo-virou-terra-em-matopiba/))
  - Não encontrei registro de atraso de pagamento antes da concordata.
- **Parada de pagamentos / intervenção:** concordata preventiva em **15/10/2001**. A empresa rescindiu unilateralmente todos os CICs e propôs pagar 40% até 15/10/2002 e o saldo depois — [Sedep](https://www.sedep.com.br/artigos/a-concordata-da-boi-gordo-e-as-duvidas-de-investidores/). Falência em abr/2004, "sem honrar nenhum pagamento aos credores no período da concordata" — [Pública](https://apublica.org/2018/06/investigacao-indica-que-dinheiro-dos-credores-da-boi-gordo-virou-terra-em-matopiba/). Uma síntese de busca cita 02/02/2004 como data da falência, sem fonte identificável; **não usar**.
- **Operador no fim:** pediu concordata em foro escolhido por ele. Em 2003 vendeu o controle ao Grupo Golin, depois responsabilizado por desvios de ativos — [Folha Vitória/Estadão](https://www.folhavitoria.com.br/economia/justica-bloqueia-bens-de-donos-da-fazendas-reunidas-boi-gordo/); [Pública](https://apublica.org/2018/06/investigacao-indica-que-dinheiro-dos-credores-da-boi-gordo-virou-terra-em-matopiba/)

**1.2 Gallus Agropecuária**
- Quebrou no início de 1998, com rombo de R$ 35 milhões — [Isto É Dinheiro, 26/07/2000](https://istoedinheiro.com.br/arriscado-mas-nem-tanto); [Isto É Dinheiro, 2001](https://istoedinheiro.com.br/dez-licoes-para-o-tempo-de-vacas-magras)
- Segundo a Forbes: dono Gelson Camargo dos Santos; promessa de cerca de 12,8% em quatro meses (3,06% ao mês composto); cerca de 300 investidores — [Forbes Agro, dez/2024](https://forbes.com.br/forbesagro/2024/12/4-grandes-golpes-no-agro-que-prejudicaram-produtores-e-investidores/). A mesma matéria fala em "US$ 1 bilhão" e em dívida de R$ 12 milhões, números incompatíveis entre si. **Não confiável.**
- Início da captação, sinais de estresse e gatilho: n/e.

**1.3 Embrapek**
- A Deliberação CVM 277, de **28/08/1998**, suspendeu a venda de CICs da Embrapek porque o pedido de registro foi feito fora do prazo da Instrução 270/98. Multa diária de R$ 5.000 — [CVM, Deliberação 277](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/deliberacoes/anexos/0200/deli277.pdf)
- Início, pico, parada de pagamentos e desfecho: n/e (buscas sem resultado).

**1.4 Fazendas Integradas Ouro Branco S/A**
- Tinha registro na CVM como emissora de CIC, mas não conseguiu registrar as ofertas públicas. Deixou de enviar demonstrações financeiras à CVM desde dez/1998 e teve a falência decretada. A CVM cancelou o registro em 15/02/2006 — [CVM, Processo RJ 2005/9462, Reg. Col. 4979/2005](https://conteudo.cvm.gov.br/export/sites/cvm/decisoes/anexos/0003/4979-0.pdf)
- Perdeu o direito de atuar por omitir dados financeiros. Falência em ago/1999 — [Isto É Dinheiro, 2000](https://istoedinheiro.com.br/arriscado-mas-nem-tanto)
- Na mesma decisão de 2006, a CVM cancelou o registro de outras cinco emissoras de CIC que pararam de prestar contas: Arroba's (desde 2002), Bawman (dez/1999), Suinvest (mar/2001), Bovinus (dez/2000) e Rural Agroinvest (dez/1999) — [CVM 4979/2005](https://conteudo.cvm.gov.br/export/sites/cvm/decisoes/anexos/0003/4979-0.pdf). Não há dados de ciclo de vida delas.

**1.5 Avestruz Master (Goiânia-GO)**
- **Início / fachada:** fundada em 1998 em Goiânia por Jerson Maciel da Silva e filhos. Começou com "hotelaria" de aves de terceiros e virou, "em cerca de cinco anos", o maior criatório das Américas — [Gazeta do Povo, 03/12/2025](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/)
- Outra fonte data a pirâmide em 2003–2005 — [Rota Jurídica](https://www.rotajuridica.com.br/?p=71774)
- Pelos dados da CVM, a captação por contratos de compra e venda/parceria foi de fev a jul/2004 (cerca de R$ 12 milhões). As CPRs com recompra vieram a partir de jul/2004 — [CVM, PAS 23/04](https://conteudo.cvm.gov.br/export/sites/cvm/sancionadores/sancionador/anexos/2006/20060928_PAS_2304.pdf)
- **Retorno prometido:**
  - Taxas implícitas de 7% a 9,14% ao mês, "em torno de 10% ao mês" — [CVM PAS 23/04](https://conteudo.cvm.gov.br/export/sites/cvm/sancionadores/sancionador/anexos/2006/20060928_PAS_2304.pdf)
  - Recompra com valorização de "até 10% ao mês" — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/)
  - 11% ao mês — [Forbes Agro](https://forbes.com.br/forbesagro/2024/12/4-grandes-golpes-no-agro-que-prejudicaram-produtores-e-investidores/)
  - Campanha "Projeto 33": 33 parcelas mensais, com promessa de capital dobrado ao fim de 33 meses — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/). Conversão (TIR de 33 aportes mensais que viram 66 parcelas no mês 33): **≈ 3,78% ao mês**.
- **Estrutura:** recompra garantida pelo abatedouro do próprio grupo (Struthio Gold). CPRs de 3, 6 ou 9 meses (carência/lock-up curto). "Filiais" que eram sociedades separadas, anúncios em jornal e TV — [CVM PAS 23/04](https://conteudo.cvm.gov.br/export/sites/cvm/sancionadores/sancionador/anexos/2006/20060928_PAS_2304.pdf). Em 2004, R$ 4 milhões em publicidade contra R$ 100 mil em ração (laudo da PF) — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/). Não encontrei exigência de recrutamento, bônus por indicação em níveis nem taxa de adesão.
- **Pico:** 172.298 CPRs com mais de 600 mil aves vendidas a 45,1 mil investidores. Segundo o MPF, o plantel real era de 38 mil aves e 17 mil ovos. Dívida de cerca de R$ 1 bilhão — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/). A captação via CPR chegou a R$ 86 milhões em mar/2005 — [CVM PAS 23/04](https://conteudo.cvm.gov.br/export/sites/cvm/sancionadores/sancionador/anexos/2006/20060928_PAS_2304.pdf). Pico provável: 2004–2005.
- **Primeiros alertas públicos:**
  - Fim de 2003: o Procon-GO recebeu denúncias, achou 4.371 aves numa fazenda onde a empresa declarava 5,8 mil e preparou o fechamento. Uma decisão judicial tirou do Procon a atribuição. Depois veio um TAC com o MPF, e a empresa continuou operando — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/)
  - 27/02/2004: o Banco Central comunicou a CVM — [CVM PAS 23/04](https://conteudo.cvm.gov.br/export/sites/cvm/sancionadores/sancionador/anexos/2006/20060928_PAS_2304.pdf)
  - 2004: primeira matéria crítica, do semanário "O Sucesso" (Goiânia) — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/)
  - Inspeção da CVM em ago/2004 e stop order (Deliberação CVM 473) em **01/12/2004** — [CVM PAS 23/04](https://conteudo.cvm.gov.br/export/sites/cvm/sancionadores/sancionador/anexos/2006/20060928_PAS_2304.pdf)
- **Sinais de estresse:**
  - Troca de forma jurídica (contrato → CPR, jul/2004) para escapar da CVM, mantendo as mesmas promessas — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/); [CVM PAS 23/04](https://conteudo.cvm.gov.br/export/sites/cvm/sancionadores/sancionador/anexos/2006/20060928_PAS_2304.pdf)
  - "Lucro fictício": só em dez/2004, R$ 6,9 milhões retirados pelos sócios — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/)
  - Atrasos e lucros que deixaram de ser depositados em 2005 — [Click Petróleo e Gás (fonte fraca)](https://en.clickpetroleoegas.com.br/o-golpe-que-devorou-o-bolso-dos-brasileiros-40-mil-pessoas-perderam-r-1-bilhao-de-investimentos-na-maior-fraude-financeira-do-brasil-fcmo87/). Não achei a data do primeiro atraso.
- **Parada de pagamentos:** **04/11/2005**. Cheques de investidores voltaram sem fundos e a sede na Av. T-10 amanheceu fechada — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/)
- **Intervenção:** Maciel se entregou em 10/11/2005 e o MPF sequestrou bens — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/). Pedido de recuperação judicial em 13/12/2005; falência em 28/07/2006 — [Migalhas, 28/07/2006](https://www.migalhas.com.br/quentes/28072/caso-avestruz-master--tj-go-decretada-falencia-do-grupo-e-prisao-de-jerson-maciel)
- **Operador no fim:** Maciel, duas filhas e um genro partiram "em comboio rumo ao Paraguai", deixando o filho para responder. Maciel voltou e se entregou seis dias depois. A empresa tentou recuperação judicial; o plano foi aprovado em assembleia de cerca de 7 mil credores no Estádio Serra Dourada (abr/2006). O MPF exigiu o afastamento da família e veio a falência — [Gazeta do Povo](https://www.gazetadopovo.com.br/agronegocio/avestruz-master-historia/)

### Inferences
- **Duração:**
  - Boi Gordo: cerca de 66 meses contando da fase de massa (1996 → 15/10/2001), ou cerca de 165 meses desde a fundação (1988).
  - Avestruz Master: cerca de 21 meses contando da captação documentada pela CVM (fev/2004 → 04/11/2005), cerca de 34 meses desde 2003, ou cerca de 90 meses desde a fundação (1998).
- **Do primeiro estresse ao colapso:**
  - Boi Gordo: cerca de 7 meses do alerta da CVM (mar/2001) e cerca de 4 meses da proposta de troca de CICs por ações (jun/2001).
  - Avestruz Master: cerca de 11 meses da stop order da CVM (dez/2004) e cerca de 23 meses das denúncias ao Procon (fim de 2003).
- **Gatilho principal:**
  - Boi Gordo: (b) falta de dinheiro novo, catalisada por (a), já que o alerta da CVM fechou a porta de entrada.
  - Avestruz Master: (b) falta de caixa (cheques devolvidos), com (a) e (d) como fatores secundários.
  - Em nenhum dos dois o Estado interveio antes da quebra. Os alertas oficiais existiram, mas o esquema seguiu vendendo até faltar caixa.
- Com retorno baixo (cerca de 2% ao mês) e ativo físico, a Boi Gordo sobreviveu mais de cinco anos. Com 7–10% ao mês, a Avestruz Master durou cerca de 2 a 3 anos na fase pública.

### Gaps
- Início exato (mês/ano) da captação pública da Boi Gordo e data do primeiro atraso de pagamento, se houve antes de out/2001.
- Gallus, Embrapek e Ouro Branco: início, pico, primeiro alerta e gatilho não encontrados. O acervo da Folha e do Estadão não foi acessível nesta sessão.
- Avestruz Master: data do primeiro atraso de recompra em 2005 (só fonte fraca).
- O texto integral da Deliberação CVM 376/2001 não foi aberto. A data 27/03/2001 vem de snippet coerente com fontes de época.

---

## 2. Onda multinível digital e de "anúncios" (2012–2017): TelexFree/Ympactus, BBom, Priples, Multiclick, D9 Clube

### Takeaway
Os esquemas de 2012–2017 prometiam retornos altíssimos: cerca de 30% ao mês na TelexFree, cerca de 62% na Priples e 33% no D9. Cresceram muito rápido, de centenas de milhares a 1 milhão de pessoas em meses. Duraram pouco: 4 a 15 meses. TelexFree, BBom e Priples foram travadas por **intervenção do Estado antes de qualquer sinal público de estresse**: o bloqueio judicial de jun–ago/2013 congelou pagamentos e adesões ao mesmo tempo. O D9 terminou por **fuga do operador** (Dubai, mai/2017), seis meses após o lançamento. Nos EUA, onde não houve bloqueio precoce, a TelexFree durou cerca de 26 meses e colapsou cerca de 6 semanas depois de mudar o plano de compensação.

### Cited Findings

**2.1 TelexFree / Ympactus Comercial (Brasil)**
- **Início / fachada:** VoIP mais "postagem de anúncios". No Brasil, começou a operar em **mar/2012** — (snippet de busca sobre [Correio do Estado](https://correiodoestado.com.br/cidades/justica-bloqueia-pagamentos-da-telexfree-e-barra-participantes/185702/)). A Wikipedia diz que a operação brasileira (Ympactus) começou em 2011 — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree). A TelexFree Inc. foi registrada em 02/02/2012 — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree) — e o domínio telexfree.com em 30/01/2012 — [BehindMLM, 2012 (curl)](https://behindmlm.com/?p=8746)
- **Retorno prometido e conversão:**
  - AdCentral: pagar US$ 299 por ano (US$ 269 por posição adicional, até 5) e publicar 1 anúncio por dia dava **US$ 20 por semana** (US$ 1.040 por ano) — [BehindMLM, 2012](https://behindmlm.com/?p=8746). Outra versão fala em US$ 289 por posição — [BehindMLM, 03/03/2014](https://behindmlm.com/companies/telexfree/telexfree-compensation-plan-v2-0-review).
  - Conversão: US$ 86,67 por mês sobre US$ 299 = **29,0% ao mês simples** (30,0% sobre US$ 289). TIR de 52 pagamentos semanais de US$ 20 contra US$ 299 à vista ≈ 6,4% por semana ≈ **31% ao mês**.
  - AdCentral Family: US$ 1.375 dava US$ 100 por semana, ou 31,5% ao mês simples (TIR ≈ 34% ao mês).
  - O Correio do Estado (via snippet) cita "lucro anual de US$ 12.974" para o Family, número divergente que deve incluir bônus.
- **Estrutura:**
  - Bônus de US$ 20 por recrutado AdCentral e de US$ 100 por recrutado Family.
  - Binário: US$ 0,40 por semana por membro da rede e US$ 20 por ciclo pareado, com teto de 22 ciclos (US$ 440) por dia.
  - Matriz 5x5 sobre VoIP e bonus pool.
  - Taxa anual (renovação).
  - O ROI semanal dependia de postar anúncios, não de recrutar. A conta só fechava com mais de 3 novos membros por posição por ano.
  - Fonte de todos os itens: [BehindMLM, 2012](https://behindmlm.com/?p=8746)
  - A A Gazeta descreve o ganho como condicionado ao recrutamento — [A Gazeta, 2023](https://www.agazeta.com.br/es/economia/telexfree-o-que-aconteceu-com-chefoes-10-anos-apos-queda-da-piramide-0823)
- **Pico:** 1.049.619 "divulgadores ativos" no Brasil, segundo a própria empresa em ago/2013 — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree). Cerca de 70 mil só no Acre — [Conjur, set/2015](https://www.conjur.com.br/?p=471803). Cerca de 800 mil "investimentos", totalizando cerca de US$ 900 milhões em 2012–2013, no mundo — [Ponzitracker, 15/04/2014](https://www.ponzitracker.com/home/2014/4/15/massachusetts-regulators-allege-telexfree-is-1-billion-ponzi.html). Pico brasileiro: meados de 2013, logo antes do bloqueio.
- **Primeiros alertas públicos:**
  - Investigação aberta por autoridades brasileiras em jan/2013 — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree)
  - Memorando 118/GABIN/SEAE/MF, de **05/03/2013**, apontando esquema Ponzi — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree). Em março a Seae pediu à PF e ao MPF que investigassem, e ao menos sete MPs abriram procedimentos — [Correio do Estado (curl)](https://correiodoestado.com.br/cidades/mpe-investiga-empresas-por-golpe-da-piramide/182575/)
  - Massachusetts pediu demonstrativos em 04/04/2013 — [Ponzitracker](https://www.ponzitracker.com/home/2014/4/15/massachusetts-regulators-allege-telexfree-is-1-billion-ponzi.html)
  - Nota pública da Seae em 14/06/2013 — (snippet de busca)
- **Sinais de estresse antes do bloqueio (Brasil):** não encontrei atraso, limite de saque nem troca de plano antes de jun/2013.
- **Parada de pagamentos = intervenção:** liminar da 2ª Vara Cível de Rio Branco (ACP do MP-AC) suspendeu pagamentos e novas adesões em todo o país, com multa de R$ 500 mil — (snippet sobre [Correio do Estado](https://correiodoestado.com.br/cidades/justica-bloqueia-pagamentos-da-telexfree-e-barra-participantes/185702/)). As datas divergem:
  - **18/06/2013** — [A Gazeta](https://www.agazeta.com.br/es/economia/telexfree-o-que-aconteceu-com-chefoes-10-anos-apos-queda-da-piramide-0823); manifestantes falam em "decisão de 18 de junho" (snippet)
  - 19/06/2013 — (snippet de busca)
  - 13/06/2013 — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree)
- **Operador no fim:**
  - Negou ser pirâmide e recorreu: 13 recursos frustrados até set/2013 — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree)
  - A Ympactus pediu recuperação judicial — [Conjur, 20/09/2013](https://www.conjur.com.br/2013-set-20/empresa-controla-telexfree-entra-pedido-recuperacao-judicial//?print=1)
  - Divulgadores protestaram em Brasília — [Jornal de Brasília](https://jornaldebrasilia.com.br/brasilia/protesto-de-divulgadores-da-telexfree-fecha-vias-de-acesso-ao-aeroporto/)
  - Em jan/2014 a empresa se dizia "preparada" para "adequação", queria "reatar o contrato entre Ympactus e TelexFREE Internacional" e patrocinava o Botafogo — [Exame, 15/01/2014](https://exame.com/negocios/noticias/telexfree-admite-que-pode-adaptar-modelo-de-negocio-no-pais)
- **Ramo dos EUA (contraste útil):**
  - Plano novo divulgado em português no fim de fev/2014 e em inglês por volta de 03/03/2014. Ele trocou o "invista US$ 289 e receba US$ 20 por semana" por exigências de vender 10 pacotes VoIP, manter 5 clientes e recrutar 2 afiliados qualificados para continuar recebendo — [BehindMLM, 03/03/2014](https://behindmlm.com/companies/telexfree/telexfree-compensation-plan-v2-0-review)
  - Pedido de falência (Chapter 11) em **13/04/2014**; congelamento de ativos pela SEC e por Massachusetts em 15–16/04/2014 — [Wikipedia](https://en.wikipedia.org/wiki/Telexfree)

**2.2 BBom / Embrasystem (rastreadores veiculares)**
- **Início:** "lançado em fevereiro" de 2013 — [Rota Jurídica, 09/11/2013](https://www.rotajuridica.com.br/?p=3158)
- **Retorno:** sem percentual fixo. A remuneração vinha de bônus sobre adesões.
- **Estrutura:**
  - Cadastro de R$ 60 mais plano bronze (R$ 600), prata (R$ 1.800) ou ouro (R$ 3.000).
  - **Obrigação de recrutar.**
  - Mensalidade de R$ 80 por 36 meses (o "comodato" do rastreador).
  - Bônus calculado sobre novas adesões.
  - Fonte: (snippet da ACP do MPF/GO via [Rota Jurídica](https://www.rotajuridica.com.br/?p=36814)); [Rota Jurídica, sentença](https://www.rotajuridica.com.br/?p=57262)
  - Os bônus de "venda direta" (10% sobre assinaturas de indicados) e "início rápido" foram citados na liberação parcial pelo TRF1 — [Rota Jurídica (snippet)](https://www.rotajuridica.com.br/?p=2923)
- **Pico:** cerca de 300 mil pessoas — [Rota Jurídica, 2013](https://www.rotajuridica.com.br/?p=3158). R$ 300 milhões bloqueados — [Bahia Notícias (snippet)](https://www.bahianoticias.com.br/justica/noticia/46581-justica-bloqueia-contas-da-bbom-por-suspeita-de-piramide-financeira). "Quase R$ 500 milhões" movimentados — [Rota Jurídica, 2014](https://www.rotajuridica.com.br/?p=15407). A perícia considerou impossível a entrega do 1 milhão de rastreadores alegado — (snippet de busca sobre [Rota Jurídica](https://www.rotajuridica.com.br/?p=43579))
- **Primeiro alerta:** a Seae/MF chegou a investigar, mas uma liminar a impediu (relatório "em vias de conclusão") — [Rota Jurídica, 09/11/2013](https://www.rotajuridica.com.br/?p=3158). A ACP do MPF/GO é o primeiro marco datado. Não achei matéria de imprensa anterior ao bloqueio.
- **Sinais de estresse:** n/e antes do bloqueio.
- **Parada de pagamentos = intervenção:** contas e atividades bloqueadas em **09/07/2013** pela juíza Luciana Gheller — [Rota Jurídica](https://www.rotajuridica.com.br/?p=3158). Outras datas citadas: 10/07/2013 — [Sedep](https://www.sedep.com.br/?p=54638); bens indisponíveis em 11/07 (snippet).
- **Operador no fim:**
  - Em 04/11/2013 o TRF cassou temporariamente o bloqueio, e houve retomada parcial — [Rota Jurídica](https://www.rotajuridica.com.br/?p=3158)
  - Acordo de devolução assinado em out/2015 e não homologado: a empresa trocou cinco vezes de representante e de advogados — [Rota Jurídica, 2016](https://www.rotajuridica.com.br/?p=36814)
  - Sentença em 18/12/2017: dissolução, R$ 100 milhões de dano moral coletivo e reembolso a quem aderiu antes de 05/08/2013 — [Rota Jurídica](https://www.rotajuridica.com.br/?p=57262)

**2.3 Priples (Pernambuco)**
- **Início:** abril de 2013 — [Exame, 16/08/2013](https://exame.com/negocios/depois-da-telexfree-priples-tambem-e-barrada-pela-justica/)
- **Retorno:** R$ 20 por dia para cada recarga de R$ 1.000 (R$ 620 por mês) — [Exame](https://exame.com/negocios/depois-da-telexfree-priples-tambem-e-barrada-pela-justica/). Conversão: **62% ao mês simples** (2% ao dia). O prazo do contrato não foi informado.
- **Estrutura:** pagamento via créditos de anúncios publicados ou revendidos à empresa. 95% da receita vinha de adesões — [Exame](https://exame.com/negocios/depois-da-telexfree-priples-tambem-e-barrada-pela-justica/). Detalhes de bônus por indicação: n/e.
- **Pico:** cerca de 200 mil associados e R$ 107 milhões movimentados desde abr/2013, com cerca de R$ 70 milhões bloqueados — [Exame](https://exame.com/negocios/depois-da-telexfree-priples-tambem-e-barrada-pela-justica/)
- **Parada de pagamentos = intervenção:** a Justiça de PE, atendendo a representação da Polícia Civil, proibiu pagamentos e novos cadastros. Os dois sócios foram presos num "sábado" anterior à matéria de 16/08/2013 (provavelmente 10/08/2013; a data não é dada) — [Exame](https://exame.com/negocios/depois-da-telexfree-priples-tambem-e-barrada-pela-justica/)
- Primeiro alerta e sinais de estresse: n/e.

**2.4 Multiclick Brasil**
- Em 2013, a 25ª Promotoria do MPE-MS abriu procedimento contra Ympactus e Multiclick, que pagavam por "propaganda boca a boca" na internet e por recrutamento — [Correio do Estado (curl)](https://correiodoestado.com.br/cidades/mpe-investiga-empresas-por-golpe-da-piramide/182575/)
- Representação ao MPF-SP. A 2ª CCR negou o declínio para o MP estadual — [MPF, Voto 1046/2014](https://www.mpf.mp.br/atuacao/ccr2/publicacoes/boletins/documentos/boletins-2014/boletim-53/Voto_1046_2014.pdf)
- Associados da "Multiclique" protestaram junto com os da TelexFree e da BBom — [InfoMoney (snippet)](https://www.infomoney.com.br/?p=184542)
- Início, retorno, pico, parada de pagamentos e gatilho: n/e.

**2.5 D9 Clube de Empreendedores (Itabuna-BA; apostas esportivas)**
- **Início:** "no final do ano passado", ou seja, fim de 2016 — [MPRS, 14/08/2017](https://www.mprs.mp.br/noticias/criminal/44885/); "launched last year" — [BehindMLM, 2017 (curl)](https://behindmlm.com/?p=35887). Fachada: "ganhe dinheiro assistindo futebol" e cursos de "trading esportivo", com acesso de 52 semanas à BetFair. A BetFair negou qualquer parceria — [BehindMLM](https://behindmlm.com/?p=35887); [MPRS, 11/09/2017](https://www.mprs.mp.br/noticias/criminal/45123/). Usava bitcoin como meio de pagamento, por isso é um caso de transição.
- **Retorno (as fontes divergem):**
  - 33% ao mês — [Bahia Notícias, 07/07/2018](https://www.bahianoticias.com.br/justica/noticia/59111-tj-ba-decreta-prisao-preventiva-de-danilo-d9-por-pratica-de-piramide-financeira); [InfoMoney, 2018](https://www.infomoney.com.br/?p=417020)
  - "Até 300% do valor investido no prazo de um ano", ou **9,6% a 12,3% ao mês composto**, conforme 300% signifique 3x ou 4x — [MPRS, 11/09/2017](https://www.mprs.mp.br/noticias/criminal/45123/)
  - "Ganhos imediatos entre 30% e 150%" — [MPRS, 14/08/2017](https://www.mprs.mp.br/noticias/criminal/44885/)
- **Estrutura:** ROI mais comissões de recrutamento em pirâmide — [BehindMLM](https://behindmlm.com/?p=35887). Disfarce de multinível — [MPRS](https://www.mprs.mp.br/noticias/criminal/45123/). Um comentário no BehindMLM menciona restrição a reinvestimento (fonte fraca).
- **Pico:** cerca de R$ 200 milhões no Brasil — [Bahia Notícias](https://www.bahianoticias.com.br/justica/noticia/59111-tj-ba-decreta-prisao-preventiva-de-danilo-d9-por-pratica-de-piramide-financeira). O BehindMLM fala em US$ 642 milhões, inclusive com vítimas no exterior (Paraguai, Ruanda, Quênia) — [BehindMLM](https://behindmlm.com/companies/d9-clube-owner-arrested-in-dubai-to-be-extradited-to-brazil). Os números são incompatíveis.
- **Primeiro alerta público:** comunicado da Comissão Nacional de Valores do Paraguai em 10/05/2017 (ano inferido pelo contexto das matérias), seguido de investigação da promotoria paraguaia — [BehindMLM](https://behindmlm.com/?p=35887). No Brasil, a "Operação Giza" correu por seis meses até ago/2017 — [BehindMLM](https://behindmlm.com/companies/d9-clube-owner-arrested-in-dubai-to-be-extradited-to-brazil).
- **Sinais de estresse:** investidores ficavam com "saldo virtual em bitcoins que eles não conseguem sacar" — [MPRS, 14/08/2017](https://www.mprs.mp.br/noticias/criminal/44885/)
- **Parada de pagamentos / fuga:** Danilo Santana deixou o Brasil em **mai/2017** e "zerou as contas das empresas" — [Bahia Notícias](https://www.bahianoticias.com.br/justica/noticia/59111-tj-ba-decreta-prisao-preventiva-de-danilo-d9-por-pratica-de-piramide-financeira)
- **Intervenção:** buscas no RS em 11/08/2017 — [MPRS, 14/08/2017](https://www.mprs.mp.br/noticias/criminal/44885/). Denúncia do MPRS contra 23 pessoas em 11/09/2017 — [MPRS](https://www.mprs.mp.br/noticias/criminal/45123/). Preso em Dubai em fev/2018 — [Bahia Notícias](https://www.bahianoticias.com.br/justica/noticia/59111-tj-ba-decreta-prisao-preventiva-de-danilo-d9-por-pratica-de-piramide-financeira)
- **Operador no fim:** de Dubai, continuou promovendo o esquema por vídeos e áudios — [Bahia Notícias](https://www.bahianoticias.com.br/justica/noticia/59111-tj-ba-decreta-prisao-preventiva-de-danilo-d9-por-pratica-de-piramide-financeira). Em abr/2021 seguia em Dubai como "trader" — [A Gazeta, 20/04/2021](https://www.agazeta.com.br/entretenimento/famosos/bruno-da-dupla-com-marrone-publica-foto-ao-lado-de-foragido-da-justica-0421)

### Inferences
- **Durações:**
  - TelexFree Brasil: cerca de 15 meses (mar/2012 → jun/2013)
  - BBom: cerca de 5 meses (fev → 09/07/2013)
  - Priples: cerca de 4 meses (abr → ago/2013)
  - D9: cerca de 6 meses até a fuga (fim 2016 → mai/2017) e cerca de 9 meses até a operação
  - TelexFree EUA: cerca de 26 meses (fev/2012 → abr/2014)
- **Gatilho:**
  - (a) para TelexFree Brasil, BBom e Priples. Os três foram cortados no auge, sem sinais públicos de estresse. Do primeiro alerta oficial ao bloqueio passaram cerca de 3 meses na TelexFree (Seae em mar/2013 → jun/2013).
  - (d) para o D9.
  - Nos EUA, (b) desencadeada pela mudança de plano, com cerca de 1,5 mês entre o novo plano e o pedido de falência.
- A onda de jun–ago/2013 sugere efeito de contágio regulatório: depois da TelexFree, BBom e Priples caíram em 3 a 8 semanas.
- O estresse "visível de dentro" nesse grupo aparece só onde não houve bloqueio precoce: troca de plano nos EUA e saldo não sacável no D9.

### Gaps
- TelexFree Brasil: mês exato do início (2011 ou mar/2012) e data exata da liminar (13, 18 ou 19/06/2013).
- Priples: data exata da liminar e da prisão; detalhes de bônus por indicação.
- Multiclick: ciclo de vida inteiro não encontrado.
- D9: data em que os saques pararam (antes de mai/2017?).
- g1/Fantástico (ago/2017) sobre D9 e "Tips Clube": domínio bloqueado nesta sessão.

---

## 3. Casos de 2022–2026 sem cripto: Extrema Confiança (PI/MA), Queops/consignado (RJ), Sanakay (SP), Golpe da Fé (RJ) e outros

### Takeaway
Os casos recentes sem cripto são locais e de **afinidade**: comunidade cigana (Sanakay), igreja (Golpe da Fé), rede de militares, aposentados e servidores (Queops), círculo regional de um "trader" (Extrema Confiança). Prometem cerca de 10% ao mês (até 100% na Sanakay, segundo uma fonte) e **duram mais** que as pirâmides digitais de 2013: cerca de 2,5 a 3,5 anos, e até cerca de 9 anos no caso do consignado. O fim típico é (b) parar de pagar "com justificativas" ou (d) sumiço do operador. A intervenção vem depois: em geral **3 a 17 meses após a parada**, primeiro com bloqueio ou buscas e depois com prisões. A Operação Luxus (PR) citada na pauta tem fachada **cripto** e fica fora do escopo; mesmo assim, registro abaixo a linha do tempo.

### Cited Findings

**3.1 Operação Extrema Confiança: "Xtreme"/Xtreme Trade (Teresina-PI e Timon-MA)**
- **Início / fachada:** empresa registrada na Junta Comercial do PI ("XTREME TRADE"), que dizia operar na B3 com o capital dos clientes. Movimentou R$ 440 milhões "ao longo de aproximadamente dois anos e meio de atuação" — [O Imparcial, 23/06/2026](https://oimparcial.com.br/timon/cidades/2026/06/acao-interestadual-mira-grupo-suspeito-de-movimentar-r-440-milhoes-em-golpes/). Mês/ano exato do início: n/e. Pela conta, algo entre fim de 2022 e 2023.
- **Retorno:** "até 10% mensais" — [Metrópoles, 18/09/2025](https://www.metropoles.com/colunas/mirelle-pinheiro/mp-mira-trader-golpista-investigado-por-causar-prejuizo-milionario)
- **Estrutura** (recrutamento, bônus, carência): n/e.
- **Pico:** mais de 300 vítimas no PI e no MA; prejuízo estimado de cerca de R$ 100 milhões — [Metrópoles](https://www.metropoles.com/colunas/mirelle-pinheiro/saiba-quem-e-o-trader-que-deu-golpe-milionario-em-300-pessoas); R$ 440 milhões movimentados — [O Imparcial](https://oimparcial.com.br/timon/cidades/2026/06/acao-interestadual-mira-grupo-suspeito-de-movimentar-r-440-milhoes-em-golpes/)
- **Parada de pagamentos:** "em 2025" a empresa parou de pagar e o representante, Francisco das Chagas Chaves da Silva ("Chico"), **desapareceu** — [Metrópoles, 18/09/2025](https://www.metropoles.com/colunas/mirelle-pinheiro/mp-mira-trader-golpista-investigado-por-causar-prejuizo-milionario). Mês: n/e.
- **Intervenção:**
  - 1ª fase em **18/09/2025** (Gaeco/MPPI com as PCs e PMs do PI e do MA): 7 buscas, 5 em Teresina e 2 em Timon — [Metrópoles](https://www.metropoles.com/colunas/mirelle-pinheiro/mp-mira-trader-golpista-investigado-por-causar-prejuizo-milionario)
  - Nova ação em **22/06/2026**, com 2 presos (40 anos em Timon; 28 anos em São Luís) — [O Imparcial](https://oimparcial.com.br/timon/cidades/2026/06/acao-interestadual-mira-grupo-suspeito-de-movimentar-r-440-milhoes-em-golpes/)
  - Uma manchete diz que, preso, o suspeito alega "não ter dinheiro para vítimas" — [noticias-do-brasil.news (título; página não carregou)](https://noticias-do-brasil.news/politica/corrupcao/chico-trader-preso-suspeito-alega-no-ter-dinheiro.html)
- **Divergência:** a nota anterior datava o caso em "jun/2024" a partir de um snippet do Lupa1. As fontes abertas agora mostram as operações em set/2025 e jun/2026. A data de 2024 parece errada.

**3.2 "Pirâmide do consignado": Operação Queops (PC-RJ e MPRJ)**
- **Início:** "desde 2015" — [Agência Brasil, 31/10/2024](https://agenciabrasil.ebc.com.br/geral/noticia/2024-10/esquema-de-piramide-que-movimentou-r-1-bi-e-alvo-de-operacao-no-rio)
- **Mecanismo:** (1) a vítima tomava um consignado no banco indicado, ficava com 10% e transferia o resto a uma empresa do grupo, que prometia quitar o empréstimo e não quitava; (2) "compra da dívida" para reduzir parcelas, com "promessa de ganho de 10% sobre o saldo devedor", contratando novo empréstimo em nome da vítima. Público: militares, aposentados, pensionistas e servidores. 15 empresas criadas para o golpe. Ameaças às vítimas para que não denunciassem — [Agência Brasil](https://agenciabrasil.ebc.com.br/geral/noticia/2024-10/esquema-de-piramide-que-movimentou-r-1-bi-e-alvo-de-operacao-no-rio); [InfoMoney](https://www.infomoney.com.br/?p=2653813)
- **Retorno:** 10% do valor do empréstimo, pago uma única vez, sem capital próprio da vítima. **Não é convertível em % ao mês.**
- **Pico:** cerca de R$ 1 bilhão movimentado e "centenas" de vítimas; 39 denunciados pelo Gaeco/MPRJ; 12 buscas contra 4 integrantes — [Agência Brasil](https://agenciabrasil.ebc.com.br/geral/noticia/2024-10/esquema-de-piramide-que-movimentou-r-1-bi-e-alvo-de-operacao-no-rio)
- **Intervenção:** **31/10/2024** — [Agência Brasil](https://agenciabrasil.ebc.com.br/geral/noticia/2024-10/esquema-de-piramide-que-movimentou-r-1-bi-e-alvo-de-operacao-no-rio)
- Primeiro alerta, sinais de estresse e parada de pagamentos: n/e.

**3.3 Operação Sanakay (MPSP; "investimento em ouro"; comunidade cigana)**
- **Início:** "a partir de janeiro de 2023" — [BNews SP, 27/05/2026](https://www.bnewssaopaulo.com.br/noticias/policia/justica-determina-bloqueio-de-r-162-milhoes-de-piramide-financeira-contra-ciganos.html)
- **Fachada:** cotas de compra de ouro com revenda internacional; a matéria de maio também cita moedas estrangeiras e automóveis. As vítimas eram da comunidade cigana no Brasil e no exterior, e o grupo tinha "permissão interna" para vender cotas aos próprios membros — [BNews SP](https://www.bnewssaopaulo.com.br/noticias/policia/justica-determina-bloqueio-de-r-162-milhoes-de-piramide-financeira-contra-ciganos.html); (snippet de busca)
- **Retorno:** "até 100% ao mês" — [BNews SP, 27/05/2026](https://www.bnewssaopaulo.com.br/noticias/policia/justica-determina-bloqueio-de-r-162-milhoes-de-piramide-financeira-contra-ciganos.html); "altos rendimentos" — [NC News, 29/09/2026](https://ncnews.com.br/?p=54547)
- **Estrutura:** parte do dinheiro "permaneceu aplicada para criar uma aparência de rentabilidade" — [Banda B, 30/09/2026](https://www.bandab.com.br/nacional/operacao-policial-apreende-helicoptero-e-busca-recuperar-r-500-milhoes-de-golpe-de-piramide/). Recrutamento e bônus: n/e.
- **Pico:** cerca de 2 mil vítimas. Movimentação de R$ 700 milhões segundo a matéria de maio — [BNews SP](https://www.bnewssaopaulo.com.br/noticias/policia/justica-determina-bloqueio-de-r-162-milhoes-de-piramide-financeira-contra-ciganos.html) — e de cerca de R$ 500 milhões segundo as de setembro — [Banda B](https://www.bandab.com.br/nacional/operacao-policial-apreende-helicoptero-e-busca-recuperar-r-500-milhoes-de-golpe-de-piramide/). 137 pessoas físicas e 32 jurídicas investigadas — (snippet).
- **Colapso:** a matéria de 27/05/2026 já fala em "colapso da pirâmide". As vítimas perceberam a fraude e passaram a cobrar ressarcimento — [BNews SP](https://www.bnewssaopaulo.com.br/noticias/policia/justica-determina-bloqueio-de-r-162-milhoes-de-piramide-financeira-contra-ciganos.html); [NC News](https://ncnews.com.br/?p=54547). A data exata da parada de pagamentos não foi encontrada; o colapso ocorreu **até mai/2026**.
- **Intervenção:**
  - Bloqueio de R$ 162 milhões noticiado em 27/05/2026 — [BNews SP](https://www.bnewssaopaulo.com.br/noticias/policia/justica-determina-bloqueio-de-r-162-milhoes-de-piramide-financeira-contra-ciganos.html). A NC News fala em "decisão judicial de agosto" — [NC News](https://ncnews.com.br/?p=54547). Divergência: maio ou agosto, ou duas decisões.
  - Operação em **29/09/2026**: 13 buscas e apreensão de um helicóptero R66 de mais de R$ 10 milhões — [Banda B](https://www.bandab.com.br/nacional/operacao-policial-apreende-helicoptero-e-busca-recuperar-r-500-milhoes-de-golpe-de-piramide/)

**3.4 "Golpe da Fé" / "Banco do Pastor": GAL Invest Bank (Niterói-RJ)**
- **Início / fachada:** "banco digital" GAL Invest Bank (Grupo América Latina), apresentado aos fiéis pelo pastor Roberto Vieira Soares (Igreja Apostólica Vida e Adoração) — [Diário do Rio, ago/2026](https://diariodorio.com/pastor-de-niteroi-e-alvo-de-operacao-contra-esquema-milionario-que-prometia-lucro-de-10-ao-mes). R$ 8 milhões movimentados **entre 2022 e 2025** — [Diário do Rio](https://diariodorio.com/pastor-de-niteroi-e-alvo-de-operacao-contra-esquema-milionario-que-prometia-lucro-de-10-ao-mes). Início provável: 2022.
- **Retorno:** "até 10% ao mês" — [Diário do Rio](https://diariodorio.com/pastor-de-niteroi-e-alvo-de-operacao-contra-esquema-milionario-que-prometia-lucro-de-10-ao-mes); [Correio da Manhã, ago/2026](https://www.correiodamanha.com.br/rio-de-janeiro/2026/08/311815-pastor-e-alvo-de-operacao-por-suspeita-de-usar-igreja-para-captar-dinheiro-e-aplicar-golpe-milionario-no-rio.html)
- **Pico:** prejuízo de R$ 1,11 milhão, mais de R$ 5,4 milhões movimentados via instituição de pagamento e ao menos 7 boletins de ocorrência — [Correio da Manhã](https://www.correiodamanha.com.br/rio-de-janeiro/2026/08/311815-pastor-e-alvo-de-operacao-por-suspeita-de-usar-igreja-para-captar-dinheiro-e-aplicar-golpe-milionario-no-rio.html)
- **Sinais de estresse:** os investidores receberam no início, depois "diferentes justificativas eram apresentadas às vítimas até que as restituições fossem completamente interrompidas" — [Correio da Manhã](https://www.correiodamanha.com.br/rio-de-janeiro/2026/08/311815-pastor-e-alvo-de-operacao-por-suspeita-de-usar-igreja-para-captar-dinheiro-e-aplicar-golpe-milionario-no-rio.html). Conteúdo e datas das justificativas: n/e.
- **Intervenção:** **18/08/2026**: 38–39 mandados de busca contra 12 alvos no RJ e em SP; bloqueio de R$ 8 milhões — [Diário do Rio](https://diariodorio.com/pastor-de-niteroi-e-alvo-de-operacao-contra-esquema-milionario-que-prometia-lucro-de-10-ao-mes); [Agência Brasil/Radioagência](https://agenciabrasil.ebc.com.br/radioagencia-nacional/geral/audio/2026-08/operacao-mira-falso-banco-digital-ligado-igreja-evangelica-do-rj)

**3.5 Operação Luxus (PF, Ponta Grossa-PR): FORA DO ESCOPO (fachada cripto), só para registro**
- Fachada: empresa de criptomoedas — [PF, jun/2025](https://www.gov.br/pf/pt-br/assuntos/noticias/2025/06/pf-deflagra-operacao-para-investigar-crimes-financeiros-com-criptomoedas-em-ponta-grossa-pr)
- Linha do tempo: forte aumento patrimonial dos sócios a partir de 2024. No **início de 2025** o sócio alegou "problema com a exchange" (culpa em terceiros), e desde então os clientes deixaram de receber rendimentos e depósitos. Operação em jun/2025, com cerca de 400 investidores e R$ 50 milhões — [Seu Crédito Digital (snippet)](https://seucreditodigital.com.br/policia-federal-golpe-50-criptomoedas/); [PF](https://www.gov.br/pf/pt-br/assuntos/noticias/2025/06/pf-deflagra-operacao-para-investigar-crimes-financeiros-com-criptomoedas-em-ponta-grossa-pr)

**3.6 Outros casos recentes sem cripto (dados de ciclo parciais)**
- **Operação Ponzi (MPSP, PF e PC, 11/11/2024), interior de SP:** fachada de correspondente de crédito, juros de até 6% ao mês, mais de R$ 100 milhões, vítimas "na casa dos milhares", 2 presos — [MPSP](https://www.mpsp.mp.br/w/opera%C3%A7%C3%A3o-ponzi-prende-dois-por-ind%C3%ADcios-de-envolvimento-com-pir%C3%A2mide-financeira) (citada na nota anterior; a página deu 403 nesta sessão). Início e parada de pagamentos: n/e.
- **Operação Dumb Money (PF, 07/08/2025):** "operações no mercado financeiro", R$ 21 milhões, "dezenas" de investidores. O principal investigado **fugiu no fim de 2023**, cerca de 20 meses antes da operação — [CNN Brasil](https://www.cnnbrasil.com.br/nacional/brasil/piramide-financeira-pf-faz-operacao-contra-fraude-de-r-21-milhoes/)
- **PC-RJ (17/04/2026):** organização ativa desde 2020, com 19 empresas de fachada sem registro na CVM, mais de R$ 7 milhões e 11 prisões preventivas — [Diário do Rio](https://diariodorio.com/policia-civil-faz-operacao-contra-piramide-financeira-que-causou-prejuizo-de-r-7-milhoes-no-rio). Cerca de 6 anos até a operação.
- **Operação Mercadores do Templo (MPMG), caso de fronteira com apelo religioso:** "Embaixador Investimentos/Embaixador Bank", com 8,33% ao mês para pessoa física e 10% para jurídica (100–120% ao ano simples). O líder se apresentava como "homem de Deus". Operação em mai/2022; denúncia de 27 pessoas em 23/08/2023; 98 vítimas. Houve apreensão de R$ 2,6 milhões em cripto, mas a fachada era "banco/investimentos" — [MPMG](https://www.mpmg.mp.br/portal/menu/comunicacao/noticias/alvos-da-operacao-mercadores-do-templo-sao-denunciados-por-organizacao-criminosa-estelionato-e-outros-crimes-ligados-a-piramide-financeira.shtml). Início: n/e.

### Inferences
- **Durações:**
  - Extrema Confiança: cerca de 30 meses (cerca de 2,5 anos até a parada em 2025)
  - Golpe da Fé: cerca de 36 meses (2022 → 2025)
  - Sanakay: até cerca de 40 meses (jan/2023 → colapso até mai/2026)
  - Queops: cerca de 115 meses (2015 → operação em out/2024; não se sabe se ainda pagava)
  - PC-RJ 2026: cerca de 70 meses
- **Defasagem entre parada e intervenção:**
  - Extrema Confiança: parou em 2025, buscas em set/2025, prisões cerca de 9 meses depois
  - Golpe da Fé: parou em 2025, operação em ago/2026
  - Sanakay: colapso até mai/2026, operação 4 meses depois
  - Dumb Money: cerca de 20 meses da fuga à operação
  - Ao contrário de 2013, o Estado chega **depois** da quebra.
- **Gatilho principal:**
  - (b) para Sanakay e Golpe da Fé
  - (d) para Extrema Confiança e Dumb Money
  - (a) para Queops (operação com o esquema possivelmente ainda ativo; não confirmado)
- A afinidade (etnia, igreja, rede funcional) parece compensar promessas altas (10% a 100% ao mês) e alongar a vida do esquema. A base é pequena (300 a 2.000 pessoas), mas com tíquete alto (R$ 100 milhões de prejuízo para cerca de 300 pessoas na Extrema Confiança).
- O roteiro de estresse observado se repete: atrasos com "diferentes justificativas" (Golpe da Fé), culpa em terceiro (Luxus: "problema com a exchange") e sumiço do operador (Extrema Confiança, Dumb Money).

### Gaps
- Mês exato de parada de pagamentos em todos os casos de 2025–2026; datas e conteúdo das "justificativas" do Golpe da Fé.
- Extrema Confiança: mês de início, estrutura (indicação/bônus) e data da prisão do operador.
- Queops: se havia pagamento periódico (o que caracterizaria Ponzi) e quando as vítimas pararam de receber. Não confirmei se a condenação "consignado de R$ 156 milhões rende 24 anos" ([Painel Político](https://painelpolitico.com/golpe-do-consignado-piramide-de-r-156-milhoes-rende-24-anos-de-prisao)) é deste ou de outro caso.
- Sanakay: data da decisão de bloqueio (mai ou ago/2026) e mecanismo de recrutamento dentro da comunidade.
- Operação Ponzi (SP): início e cronologia (página do MPSP inacessível nesta sessão).

---

## 4. Vida útil do "golpe da tarefa" e das plataformas falsas de WhatsApp

### Takeaway
Não encontrei nenhum dado publicado (Redbelt, polícias ou imprensa) sobre **quanto tempo** dura um grupo do golpe da tarefa ou uma plataforma falsa. O que há é contagem de grupos ativos (Redbelt: 73 em set/2024 e 128 em dez/2025, +75%) e a mecânica, que já nasce com fim programado: pagamento inicial pequeno, escada de depósitos, bloqueio do saque com cobrança de "taxa" e sumiço. São esquemas descartáveis. A "vida" relevante é a da **organização**, que dura anos (Dark Wallet: 2 anos; RJ: desde 2020) trocando de grupo e de plataforma. Esses golpes não são pirâmides clássicas: quase nunca pagam rendimento real com dinheiro de novos entrantes, só simulam saldo.

### Cited Findings
- **Redbelt Security:** 128 grupos ativos do golpe da tarefa no Brasil, contra 73 monitorados em set/2024 (+75% em menos de um ano), com base em "inteligência cibernética na deep web" — [CNN Brasil, 02/12/2025](https://www.cnnbrasil.com.br/nacional/brasil/levantamento-aponta-boom-do-golpe-da-tarefa-no-brasil/); [Canaltech](https://canaltech.com.br/seguranca/golpe-da-tarefa-dispara-75-e-vira-principal-ameaca-no-brasil-conheca/). Nenhuma das duas matérias informa a duração dos grupos.
- **Ciclo da vítima:** primeiro pagamento de R$ 5 a R$ 20 "para gerar confiança"; depois, depósitos progressivos para "desbloquear tarefas mais lucrativas"; mais recentemente, apps falsos que roubam credenciais e SMS. Canais: WhatsApp e Telegram. É uma adaptação do Sha Zhu Pan asiático com Pix — [CNN Brasil](https://www.cnnbrasil.com.br/nacional/brasil/levantamento-aponta-boom-do-golpe-da-tarefa-no-brasil/)
- **Plataformas falsas:**
  - "Aglobal Trade" (Recife, jul/2026): sem CNPJ; liberava saques pequenos e bloqueava os grandes; meta mensal de US$ 800 mil; 13 presos em flagrante no call center — [Diario de Pernambuco, 21/07/2026](https://www.diariodepernambuco.com.br/vida-urbana/2026/07/11719257-criminosos-utilizavam-site-de-investimentos-para-aplicar-golpes-milionarios-diz-policia-civil.html)
  - **Operação Dark Wallet** (PC-PE, 2ª fase em 23/07/2026): grupo que movimentou **R$ 188 milhões em 2 anos** com sites falsos; "o aplicativo funciona como se fosse um game"; pequenos valores devolvidos no início; três núcleos (engenharia social, operacional, financeiro); uma vítima de GO perdeu mais de R$ 640 mil — [Diario de Pernambuco, jul/2026](https://www.diariodepernambuco.com.br/vida-urbana/2026/07/11719411-quadrilha-usava-falsas-plataformas-de-investimento-para-aplicar-golpes-e-movimentou-rs-188-milhoes-diz-policia.html)
  - Operação Mirage (PC-RS, 13/01/2026): grupos de WhatsApp de "investimentos"; uma vítima perdeu mais de R$ 4,3 milhões — [TecMundo](https://www.tecmundo.com.br/seguranca/409822-policia-desmantela-quadrilha-de-investimentos-falsos-via-whatsapp-no-brasil.htm)
  - Criptoabate (PC-RS, 13/08/2026): plataforma "TDASX"; perda de R$ 37 milhões de uma vítima — [ABC+](https://www.abcmais.com/brasil/rio-grande-do-sul/golpe-de-falsa-plataforma-de-investimentos-causa-prejuizo-de-r-37-milhoes-a-uma-unica-vitima-e-revela-r-30-bilhoes-em-transacoes-suspeitas/). Fachada cripto, só como referência.
- **Roteiro de fim** ("Truman Show Scam"): pequenos resgates reais no início e depois **bloqueio do saque com cobrança de "taxas regulatórias/tributárias"** — [InvestNews, 16/06/2026](https://investnews.com.br/investimentos/golpe-de-falso-investimento-usa-ia/)

### Inferences
- Para comparação com as pirâmides, o golpe da tarefa e a plataforma falsa ficam numa categoria à parte. Cada "instância" (grupo ou site) é descartável e termina por desenho com (d) sumiço do operador, após a cobrança de taxa de saque. A organização persiste por anos. A Dark Wallet operou cerca de 24 meses, faixa parecida com a das pirâmides de afinidade.
- O crescimento de 73 para 128 grupos ativos entre set/2024 e dez/2025 mede o estoque em dois pontos no tempo. Sem dado de entrada e saída, não dá para estimar a vida média.

### Gaps
- Vida média de um grupo do golpe da tarefa ou de um domínio de plataforma falsa: **não encontrada** em fonte brasileira (Redbelt, polícias, SaferNet). O relatório original da Redbelt não foi localizado.
- Número de "etapas" típicas da escada de depósitos e tempo médio até a perda total: n/e.
- Uma síntese de busca mencionava plataforma "retirada do ar após cobrar caução de 5%". A fonte não foi identificada; **não usar**.

---

## 5. Padrões de duração e colapso (tabela-resumo)

### Takeaway
Três regimes aparecem:
- **Agro/CIC (1990–2006):** retorno moderado (cerca de 2% a 10% ao mês) e vida longa (cerca de 2 a 13 anos). O colapso por falta de caixa vem 7 a 11 meses depois de um alerta do regulador, sem intervenção prévia.
- **Multinível digital (2012–2017):** retorno extremo (30% a 62% ao mês) e vida curta (4 a 15 meses). Ou o Estado corta no auge, antes de qualquer estresse visível, ou o operador foge (D9).
- **Afinidade local sem cripto (2022–2026):** cerca de 10% ao mês (até 100%) e vida de cerca de 2,5 a 3,5 anos. O fim vem por parada de pagamentos com justificativas ou por sumiço do operador; o Estado chega meses depois.

Quanto maior a promessa, menor a vida, exceto quando a base é fechada (afinidade).

### Cited Findings
- Todas as datas e números da tabela vêm das seções 1 a 4, com as fontes citadas lá.

### Inferences

**TABELA-RESUMO** (n/e = não encontrado; ~ = aproximado; meses arredondados)

| Caso | Início | Fim (parada de pagamentos ou intervenção) | Duração (meses) | Retorno % ao mês | Recrutamento obrigatório (s/n) | 1º estresse → colapso (meses) | Gatilho principal |
|---|---|---|---|---|---|---|---|
| Boi Gordo | 1988 (empresa); 1996 (massa) | 15/10/2001 (concordata, rescisão dos CICs) | ~66 (desde 1996); ~165 (desde 1988) | 1,9–2,0 composto (40–42% em 18 meses); 1,2 se em 30 meses; 3,5–5 em fontes isoladas | n | ~7 (alerta CVM mar/2001); ~4 (troca CIC→ações jun/2001) | (b) falta de dinheiro novo, após (a) alerta da CVM |
| Gallus | n/e | início/1998 (quebra) | n/e | ~3,1 (12,8% em 4 meses; Forbes, pouco confiável) | n/e | n/e | n/e |
| Embrapek | n/e | 28/08/1998 (CVM suspende oferta); desfecho n/e | n/e | n/e | n/e | n/e | (a) na oferta; desfecho n/e |
| Ouro Branco | n/e | ago/1999 (falência) | n/e | n/e | n/e | ~8 (sem demonstrações à CVM desde dez/1998) | n/e ((a)/(b) prováveis) |
| Avestruz Master | 1998 (empresa); fev/2004 (captação documentada) | 04/11/2005 (cheques sem fundo); RJ 13/12/2005; falência 28/07/2006 | ~21 (desde fev/2004); ~34 (desde 2003); ~90 (desde 1998) | 7–10 (CVM); ~3,8 (Projeto 33) | n | ~11 (stop order CVM dez/2004); ~23 (denúncias Procon fim/2003) | (b) falta de caixa (com (d) fuga breve e (a)) |
| TelexFree/Ympactus (BR) | mar/2012 (ou 2011) | 18/06/2013 (bloqueio; datas divergentes: 13 e 19/06) | ~15 | ~29–30 simples (US$ 20 por semana sobre US$ 289–299); TIR ~31 | n para o ROI base (bônus de recrutamento à parte) | n/a (sem estresse antes do bloqueio); EUA: ~1,5 | (a) |
| BBom/Embrasystem | fev/2013 | 09/07/2013 (bloqueio) | ~5 | sem % fixo (bônus sobre adesões) | s | n/a | (a) |
| Priples | abr/2013 | ~10–12/08/2013 (liminar e prisão) | ~4 | ~62 simples (R$ 20 por dia por R$ 1.000) | n/e | n/a | (a) |
| Multiclick | n/e | n/e | n/e | n/e | n/e (pagava por recrutamento) | n/e | n/e |
| D9 Clube | fim/2016 | mai/2017 (fuga e contas zeradas); operação 11/08/2017 | ~6 (até a fuga); ~9 (até a operação) | 33 (BA) ou 9,6–12,3 (300% ao ano, MPRS) | n/e (havia comissões de recrutamento) | ~0–3 (saldo não sacável → fuga/operação) | (d) |
| Extrema Confiança (Xtreme) | ~fim/2022–2023 (inferido) | 2025 (parou de pagar e sumiu); buscas 18/09/2025; prisões 22/06/2026 | ~30 | até 10 | n/e | n/e | (d), com (b) |
| Queops (consignado, RJ) | 2015 | 31/10/2024 (operação) | ~115 | n/a (10% do empréstimo, pago uma vez) | n/e (rede de captadores) | n/e | (a) (não confirmado se ainda pagava) |
| Sanakay (ouro, SP) | jan/2023 | colapso até mai/2026; bloqueio mai ou ago/2026; operação 29/09/2026 | até ~40 | até 100 (uma fonte); "altos rendimentos" | n/e (afinidade, comunidade cigana) | n/e | (b) |
| Golpe da Fé (GAL Invest) | 2022 | 2025 (pagamentos interrompidos); operação 18/08/2026 | ~36 | até 10 | n/e (afinidade, igreja) | n/e (houve "diferentes justificativas" antes) | (b) |
| Dumb Money (PF) | n/e | fim/2023 (fuga); operação 07/08/2025 | n/e | n/e ("altos retornos") | n/e | n/e | (d) |
| Mercadores do Templo (MG) | n/e | operação mai/2022 | n/e | 8,33 (PF) / 10 (PJ) | n/e | n/e | (a)? n/e |
| Luxus (PR), **excluído: cripto** | n/e | início/2025 ("problema com a exchange"); operação jun/2025 | n/e | n/e | n/e | ~5 (alegação → operação) | (b) |
| Golpe da tarefa / plataformas falsas (instância) | — | — | n/e (organizações: ~24 meses, Dark Wallet) | n/a (escada de depósitos; saldo simulado) | n | n/e | (d) por desenho |

**Padrões**
- **Retorno x duração** (casos com início e fim datados):
  - ~2% ao mês: Boi Gordo, 66+ meses
  - 7–10%: Avestruz Master, ~21–34 meses; Extrema Confiança, ~30; Golpe da Fé, ~36
  - ~30%: TelexFree, 15 meses (cortada pelo Estado)
  - 33%: D9, ~6
  - ~62%: Priples, ~4 (cortada pelo Estado)
  - A Sanakay (até 100% ao mês, cerca de 40 meses) é a exceção. É um caso de afinidade fechada, e o número de 100% vem de uma única fonte.
- **Gatilho por era:**
  - (a) domina em 2013, na onda TelexFree, BBom e Priples, com cortes no auge.
  - (b) domina nos casos agro e nos de afinidade recentes.
  - (d) aparece no D9 (2017) e nos casos de 2023–2025 (Extrema Confiança, Dumb Money).
  - Não encontrei caso sem cripto cujo fim tenha sido causado principalmente por (c) choque externo, (e) mídia ou (f) disputa interna. A mídia aparece como alerta (O Sucesso, 2004, na Avestruz; matérias de 2013), não como gatilho.
- **Sinais de estresse que antecederam o colapso:**
  - troca da forma do produto ou do plano (Avestruz: contrato → CPR, jul/2004; Boi Gordo: CIC → ações, jun/2001; TelexFree EUA: novo plano, mar/2014)
  - mudança de sede ou de foro (Boi Gordo → Comodoro-MT, ago/2001)
  - saldo virtual não sacável (D9)
  - justificativas sucessivas para atrasos (Golpe da Fé)
  - culpa em terceiro (Luxus: "exchange")
  - cheques sem fundo (Avestruz)
- **Defasagem do estresse ao colapso, onde mensurável:** ~1,5 mês (TelexFree EUA), ~4–7 meses (Boi Gordo) e ~11 meses (Avestruz, desde a stop order).
- **Comportamento do operador no fim:**
  - reestruturação formal: concordata (Boi Gordo); recuperação judicial (Avestruz Master, Ympactus)
  - promessa de "retomada" ou "adequação" (TelexFree em jan/2014; BBom após o TRF1 em nov/2013)
  - fuga: Avestruz ao Paraguai, com retorno em 6 dias; D9 a Dubai; Xtreme com sumiço; Dumb Money
  - continuidade no exterior: D9 seguiu captando de Dubai; TelexFree seguiu nos EUA até 2014

### Gaps
- Os meses de início e de parada de pagamentos são imprecisos (só o ano) em vários casos (Extrema Confiança, Golpe da Fé, Sanakay, Gallus, Ouro Branco). As durações da tabela são aproximadas e não servem para estatística fina.
- Amostra pequena e enviesada para casos que viraram operação ou notícia. Esquemas que quebraram sem intervenção nem cobertura não aparecem.
- Não encontrei dados do Reclame Aqui (picos de reclamação) para nenhum caso. O site não foi consultado com sucesso nesta sessão.
