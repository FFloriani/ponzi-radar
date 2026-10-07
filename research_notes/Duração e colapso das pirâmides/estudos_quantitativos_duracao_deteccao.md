# Duração, longevidade, colapso e detecção de esquemas Ponzi e pirâmides: o que dizem os estudos quantitativos

> Notas de pesquisa, 07/10/2026. Complementa `research_notes/Pirâmides financeiras no Brasil/modus_operandi_sinais_alerta.md`, que já traz a média de ~4 anos de Deason et al., a equação de Artzrouni e o checklist qualitativo de sinais. Aqui o foco são os números: amostras, medianas, quartis, coeficientes, razões de risco (hazard ratios) e acurácia de modelos. Os PDFs de Deason et al., Moore et al., Vasek (tese), Bartoletti et al., Kell et al. (Forsage) e Liang et al. (PonziGuard) foram baixados e lidos no texto integral. Os demais estudos foram lidos só pelo resumo ou por reportagem, e isso vem marcado. "Cálculo próprio" indica conta feita por mim sobre os números da fonte.

## 1. Duração: quanto tempo esses esquemas costumam durar (estudos com amostras grandes)

### Takeaway
A duração depende muito do canal e de como o fim é medido. Ponzis "tradicionais" processados pela SEC (n=376, 1988–2012) duram **mediana de 3,1 anos** (média de 4,3; quartis de 1,8 e 5,0 anos). Os Ponzis online assumidos (HYIPs) têm **mediana de 28 dias**. Os de bitcoin anunciados em fórum duram **no máximo uma semana na metade dos casos**. Os "smart Ponzis" do Ethereum, em sua maioria, nem chegam a atrair usuários (~60% com vida ≈ 0 dia). Em todos os conjuntos a distribuição é muito assimétrica: a maioria morre cedo e uma minoria sobrevive por anos.

### Cited Findings

**Ponzis processados pela SEC (EUA): Deason, Rajgopal e Waymire (SSRN, 2015)**
- Amostra: 376 Ponzis processados pela SEC entre 1988 e 2012, de 1.425 processos lidos. A duração vai da data de início alegada até o primeiro processo da SEC, que pede liminar e encerra o esquema. Duração (n=367): **média de 4,3 anos, Q1 de 1,8, mediana de 3,1 e Q3 de 5,0 anos**. O texto também arredonda a média para "about 4.25 years" — [Deason, Rajgopal & Waymire, rascunho de mai/2015 (PDF)](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf); [SSRN 2586490](https://papers.ssrn.com/abstract=2586490)
- Tamanho: valor captado com média de US$ 208 mi, Q1 de US$ 5,1 mi, **mediana de US$ 14,7 mi** e Q3 de US$ 39,0 mi. Investidores (n=353): média de 3.127 e **mediana de 150**. Aporte por investidor: média de US$ 431,2 mil e mediana de US$ 87,7 mil. Valor desviado pelo fraudador (n=291): média de US$ 13,4 mi, mediana de US$ 2,3 mi, ou 22,8% (média) e 13,2% (mediana) do captado. *Inconsistência interna:* a introdução diz que o fraudador leva "about 29%" e o texto da seção 3 dá mediana de US$ 1,0 mi, mas a Tabela 2 traz 22,8% e US$ 2,3 mi (US$ 1,0 mi é o Q1) — [Deason et al. (PDF), Tabela 2](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)
- Retorno prometido (anual): o mínimo prometido tem média de 111% e **mediana de 12%**; o máximo tem média de 437% e **mediana de 25%** (24,5%). Nos Ponzis "offline" americanos, a promessa típica é modesta e a média é puxada por poucos casos extremos — [Deason et al. (PDF)](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)
- Perfil: 57% dos fraudadores agem sozinhos, 14% são mulheres, 17% têm condenação anterior por fraude financeira, idade mediana de 45 anos no início. 46% dos esquemas têm vínculo de afinidade ou miram idosos — [Deason et al. (PDF)](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)

**Base de casos descobertos nos EUA (Ponzitracker, 2008–2018)**
- Cerca de 811 Ponzis descobertos em 11 anos, com perdas acima de US$ 58 bi. **Tamanho médio de US$ 71,8 mi e mediano de US$ 8 mi.** Pelo menos 715 condenados, com pena média de 130 meses e mediana de 97 — [Ponzitracker, "Ten Years After Madoff…" (23/04/2019)](https://www.ponzitracker.com/home/tag/fraud)

**HYIPs (Ponzis online assumidos): Moore, Han e Clayton (Financial Cryptography 2012)**
- Dados: 9 sites agregadores ("monitores": myhyip, maxhyip, iehyip, hyipranks, hyipmonitor, hyipinvestment, hyip.com, hothyips, everyhyip), visitados diariamente de 17/11/2010 a 21/08/2011. São 1.576 HYIPs distintos (595 em mais de um agregador). 187 (12%) ainda funcionavam no fim e foram tratados como censurados à direita. Lifetime = primeira aparição no agregador até a saída, sempre porque o HYIP parou de pagar — [Moore, Han & Clayton (PDF)](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- Kaplan-Meier: **mediana de 28 dias**; **1 em 4 passa de 3 meses**; **1 em 10 passa de 10 meses** — [Moore, Han & Clayton (PDF)](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- As promessas vão de "440% em 10 minutos" a "1–2% ao dia". **Metade dos HYIPs oferece mais de 10% ao dia** — [Moore, Han & Clayton (PDF)](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- Volume estimado do ecossistema: pelo menos US$ 6 milhões/mês (estimativa por buscas no Google: 441 mil buscas mensais por termos de HYIP) — [Moore, Han & Clayton (PDF)](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)

**Ponzis em bitcoin: Vasek e Moore (FC 2015 e Bitcoin Workshop/FC 2018; tese de Vasek, 2017)**
- FC 2015: análise de 42 golpes de bitcoin com endereço rastreável (Ponzis, mineração, carteiras e exchanges falsas). Pelo menos **US$ 11 mi de ~13 mil vítimas**; os "Bridge HYIPs" respondem por 60% da receita — [Vasek, tese (PDF), cap. 4](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)
- Bridge HYIPs (HYIPs tradicionais que passaram a aceitar BTC; 9 casos, set/2013–set/2014): **mediana de 125 dias**. HYIPs só de bitcoin (23 casos, jan/2013–set/2014): **mediana de 37 dias** — [Vasek, tese (PDF), Tabela 4.2](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)
- FC 2018: 11.424 tópicos de 3 subfóruns do Bitcointalk (jun/2011–nov/2016), com **1.780 golpes** de 1.956 golpistas em 2.625 posts e 11.990 usuários respondendo. **Cerca de 1/4 não durou um dia e metade durou até uma semana.** O mais longo passou de 3 anos. Muitos dos que duraram um dia foram derrubados por moderadores — [Vasek, tese (PDF), cap. 5](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf); [UCL Discovery (registro do artigo de 2018)](https://discovery.ucl.ac.uk/id/eprint/10154819/)

**"Smart Ponzis" no Ethereum: Bartoletti, Carta, Cimoli e Saia (FGCS, 2020; arXiv v6, 2019)**
- Dataset: 138 Ponzis com código-fonte verificado, ampliados para **184** por similaridade de bytecode, até 2017. **~60% têm vida próxima de 0 dia**: foram publicados (às vezes anunciados), mas não atraíram ninguém. A vida média (primeira à última transação, medida "grosseira") é de **393 dias**, inflada por transações esparsas depois do pico. Padrão típico: pico intenso de atividade e depois quase nada. Pico de criação em abril/2016, com 91 novos esquemas; depois, ~3 por mês — [Bartoletti et al., arXiv 1703.03779v6 (PDF)](https://export.arxiv.org/pdf/1703.03779v6)
- Impacto: os 184 contratos receberam **US$ 630.662 de 2.378 usuários distintos**. 1.232 (51%) receberam algum pagamento, o que não quer dizer lucro. 151 dos 184 são "chain-shaped" (fila de pagamento) — [Bartoletti et al. (PDF), Tabela 2](https://export.arxiv.org/pdf/1703.03779v6)
- Varredura posterior com detector dinâmico (PonziGuard; ~14 milhões de blocos, até jan/2022): **805 contratos Ponzi**, 615.483 transações e 281.700 ETH recebidos entre jan/2015 e jul/2023 (~US$ 500 mi ao câmbio de 2024). **Vida média de ~7,1 meses**, a maioria abaixo de 3 meses. Pico em fev/2018, com 117.953 ETH (~US$ 108 mi na época) — [Liang et al., "PonziGuard", arXiv 2406.00921 (PDF)](https://export.arxiv.org/pdf/2406.00921)
- Forsage (pirâmide em smart contract, 2020–2021): 721 mil ETH (US$ 226 mi) passaram pelo contrato até jan/2021. Os contratos oficiais juntaram mais de US$ 267 mi no primeiro ano, com recorde de US$ 3,7 mi num só dia (01/08/2020) — [Kell et al., "Forsage: Anatomy of a Smart-Contract Pyramid Scheme" (arXiv 2105.04380)](https://export.arxiv.org/pdf/2105.04380)

**Plataformas P2P chinesas (2007–2020)**
- O mercado começou a crescer em 2013, chegou ao pico de **CNY 2,8 trilhões** transacionados em 2017 e conectou mais de 4 milhões de credores e tomadores. Em 27/11/2020 a CBIRC anunciou que o número de plataformas tinha **caído a zero**. Em 2016 quase todas já operavam como "shadow banks", com garantia de principal — [Huang, HKUST IEMS Thought Leadership Brief nº 61 (2022)](https://iems.ust.hk/assets/publications/thought-leadership-briefs/2022/hkustiems-huang-why-did-the-peer-to-peer-lending-market-fail-in-china-tlb61.pdf)
- Estudos de sobrevivência com milhares de plataformas existem. Um deles usa riscos competitivos (falência contra fuga com o dinheiro) e conclui que participação de venture capital reduz o hazard de falência, mas quase não afeta o de fuga. Plataformas grandes, com empresa listada como grande acionista e com melhor divulgação de informação, tiveram menos falência e menos fuga (resumo de busca; texto completo não lido) — [IWH Halle, "VC Participation and Failure of Startups: Evidence from P2P Lending Platforms in China"](https://www.iwh-halle.de/en/publications/detail/vc-participation-and-failure-of-startups-evidence-from-p2p-lending-platforms-in-china)

**Casos históricos de escala nacional**
- Albânia (1996–1997): passivos nominais de quase **metade do PIB** no pico (US$ 1,2 bi de valor de face em nov/1996). Cerca de **dois terços da população** de 3,5 milhões investiram. Xhafferi e Populli atraíram quase 2 milhões de depositantes "em poucos meses". O colapso começou em 19/11/1996 (default da Sude) e as falências formais vieram em jan/1997 — [Jarvis, "The Rise and Fall of Albania's Pyramid Schemes", IMF F&D (mar/2000)](https://www.imf.org/external/pubs/ft/fandd/2000/03/jarvis.htm)
- Colômbia (DMG e DRFE): mais de meio milhão de clientes e recursos equivalentes a **1,2% do PIB anual**. Fechadas pelo governo em nov/2008 — [Hofstetter, Mejía, Rosas & Urrutia, J. Banking & Finance 96 (2018)](https://ideas.repec.org/a/eee/jbfina/v96y2018icp18-33.html)

**Brasil: durações extraídas das notas de casos (não é estudo com amostra)**
- GAS Consultoria: 10% a.m., atividade de 2015 a 2021 (~6 anos), interrompida pela prisão do líder — [Gulf News/AP](https://gulfnews.com/world/americas/bitcoin-pyramid-schemes-wreak-havoc-on-brazils-new-egypt-1.1642866971653); [Liras da Liberdade (MPF: R$ 38,2 bi entre 2015 e 2021)](https://www.lirasdaliberdade.com.br/mpf-pede-condenacao-do-farao-dos-bitcoins-por-quatro-crimes/)
- Rental Coins (Sheik dos Bitcoins): 13,5% a 20% a.m., de 2018 a out/2022 (~4 anos, até a Operação Poyais) — [InfoMoney (2022)](https://www.infomoney.com.br/mercados/pf-mira-sheik-das-criptomoedas-em-nova-operacao-esquema-movimentou-r-4-bi-no-brasil-e-no-exterior/)
- InDeal: 15% a.m., de ago/2017 a mai/2019 (~21 meses, até a Operação Egypto) — [TRF4](https://www.trf4.jus.br/trf4/controlador.php?acao=noticia_visualizar&id_noticia=27879); [ABC+](https://www.abcmais.com/policia/caso-indeal-saiba-quantos-milhoes-serao-devolvidos-aos-232-mil-clientes-lesados-pela-empresa-de-novo-hamburgo/)
- Kriptacoin: 1% ao dia, cerca de 6 meses em 2017 (até a Operação Patrik) — [Metrópoles](https://www.metropoles.com/distrito-federal/na-mira/pcdf-mira-irmaos-que-criaram-moeda-virtual-e-enganaram-40-mil-pessoas)
- BBom (pirâmide de adesão): ~300 mil associados em 6 meses, até o bloqueio judicial de 10/07/2013 — [Bahia Notícias](https://www.bahianoticias.com.br/justica/noticia/46581-justica-bloqueia-contas-da-bbom-por-suspeita-de-piramide-financeira)
- Boi Gordo: promessa de "até 42% em 18 meses" ou "42% em 30 meses" (≈1,2–2,0% a.m., cálculo próprio), com contratos desde 1996 e empresa ativa até 2004 (~8 anos) — [Pública (2018)](https://apublica.org/2018/06/investigacao-indica-que-dinheiro-dos-credores-da-boi-gordo-virou-terra-em-matopiba/); [Isto É Dinheiro (2000)](https://istoedinheiro.com.br/arriscado-mas-nem-tanto)

### Inferences
- **Não existe "uma" duração típica.** Há pelo menos três regimes: (a) Ponzi pessoal ou de afinidade, com promessa "plausível" (mediana de 12–25% a.a.), que dura anos (mediana de 3,1 anos na SEC); (b) Ponzi online assumido, com promessa absurda (metade acima de 10% ao dia), que dura dias a semanas (mediana de 28 dias nos HYIPs, ≤7 dias no Bitcointalk); (c) Ponzi de massa com fachada (GAS, ~6 anos; Rental Coins, ~4 anos), que mistura promessa alta com prova social intensa e pode durar anos até uma intervenção ou um choque. A Albânia mostra que, em escala nacional, a fase final de captação explosiva dura poucos meses.
- **Viés de seleção.** A amostra da SEC só inclui casos grandes e duradouros o bastante para serem processados, e o fim é a data do processo, não a do colapso econômico. Nos estudos online, o "fim" é a saída do agregador ou o último post. As medianas não são comparáveis entre si.
- A mini-série brasileira (n=6, sem rigor estatístico) é coerente com Moore et al.: Boi Gordo (~1–2% a.m.) durou ~8 anos; GAS (10% a.m.), ~6 anos; Rental Coins (13,5–20% a.m.), ~4; InDeal (15% a.m.), ~21 meses; Kriptacoin (~1% ao dia), ~6 meses. Mas quase todos acabaram por operação policial, não por colapso espontâneo. A duração brasileira mede em boa parte a velocidade da repressão.
- O Ponzitracker dá mediana de US$ 8 mi e Deason de US$ 14,7 mi. O Ponzi típico descoberto é pequeno; Madoff, Stanford e GAS são exceções que puxam a média.

### Gaps
- Não achei estudo brasileiro com amostra de pirâmides e datas de início e fim (análise de sobrevivência). Os dados de CVM, PF e MP não estão organizados assim em fonte pública.
- Não li o texto integral dos estudos de sobrevivência das P2P chinesas. Um resumo de busca cita um painel de 6.190 plataformas (jun/2007–jun/2017), mas não identifiquei com segurança qual artigo é. Ficam sem número exato: mediana de sobrevivência e hazard ratios.
- Não acessei "The Ponzi Book" (Phelps & Rhodes) nem a base de Kathy Bazoian Phelps.

## 2. Fatores de longevidade e gatilhos de colapso (taxa prometida, tamanho, indicação, fachada, afinidade, macro, reguladores, mídia, exit scams)

### Takeaway
Os fatores com evidência quantitativa são estes. **Taxa prometida mais baixa e prazo mínimo de aplicação mais longo** estão associados a vida mais longa (HYIPs). **Afinidade e foco em idosos** alongam a vida; **marketing por mídia de massa** e **fraudador com condenação anterior** encurtam (SEC). **Pagar comissão a recrutadores** não alonga a vida, mas aumenta muito o valor captado. **Mercado em queda** coincide com mais colapsos: 2009 teve 118 Ponzis descobertos nos EUA contra 40 em 2008, e a correlação trimestral com o S&P 500 é de −0,28. Em cripto, a receita de golpes cai junto com o preço do bitcoin. Não achei estudo causal sobre o efeito de alertas de reguladores ou de cobertura de mídia na velocidade do colapso.

### Cited Findings

**Taxa prometida e prazo (HYIPs)**
- HYIPs com taxa menos generosa ("menos de alguns % ao dia") têm mais chance de sobreviver por mais tempo. Acima de 10% ao dia (metade da amostra), a vida é "mais consistentemente curta". Os autores concluem que "oferecer taxas mais altas não atrai investimento suficiente para compensar o custo de servir os compromissos existentes". HYIPs com **prazo mínimo de aplicação maior** são mais estáveis, mas há grande variação mesmo entre os de taxa modesta — [Moore, Han & Clayton (PDF), seção 4.2 e Fig. 3](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- A análise é descritiva (box plots por decil de taxa e por prazo). O artigo não estima um modelo multivariado de sobrevivência com a taxa como covariável — [Moore, Han & Clayton (PDF)](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)

**Afinidade, idosos, mídia, recrutadores e histórico do fraudador (SEC, regressão OLS de ln(duração), n=349, R² ajustado de 0,133)**
- Coeficientes sobre ln(duração), com conversão para efeito percentual (cálculo próprio, exp(β)−1):
  - afinidade (soma de 4 indicadores: religião, família/amigos, etnia, relação profissional): **+0,184** (p<0,05), ≈ +20% de duração por tipo de vínculo;
  - idosos como alvo: **+0,297** (p<0,05), ≈ +35%;
  - **mídia de massa** (jornal, internet, rádio) para vender o esquema: **−0,505** (p<0,01), ≈ −40%;
  - fraudador com condenação anterior: **−0,318** (p<0,01), ≈ −27%;
  - comissão ou taxa de indicação a recrutadores: −0,119, não significativo;
  - esquema encerrado após 1999: +0,270 (p<0,10);
  - fonte: [Deason et al. (PDF), Tabela 5, Painel B](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)
- Recrutadores pagos são a variável mais importante para o **tamanho**: coeficiente de **+0,475** (p<0,05) em ln(US$ captado), ≈ +61% de captação (cálculo próprio). O mesmo indicador reduz a fatia do fraudador (−0,078, p<0,10). Os modelos de tamanho explicam pouco (R² ajustado de 0,015) — [Deason et al. (PDF)](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)
- Correlações simples com ln(duração): mídia de massa −0,28; condenação anterior −0,18; afinidade +0,14; idosos +0,13; ln(US$ captado) +0,33. Esquemas mais longos captam mais — [Deason et al. (PDF), Tabela 5, Painel A](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)
- Ponzis da SEC são mais frequentes em estados americanos onde as pessoas confiam mais em estranhos e onde há menos alternativas locais de investimento — [Deason et al. (PDF)](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)

**Comportamento no fórum (Bitcointalk, modelo de Cox, n=1.780, R²=0,218)**
- Hazard ratios (>1 = morre mais rápido):
  - cada comentário diário a mais de vítimas: **1,029** (+2,9% de hazard, p≪0,0001);
  - cada comentário diário a mais do golpista: **1,022** (p=0,034);
  - presença de "shill" (conta que só posta naquele tópico): **0,429**, ou **−57% de hazard**;
  - conta do golpista criada no mesmo dia do anúncio: **1,453** (+45%);
  - fonte: [Vasek, tese (PDF), Tabela 5.2](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)
- 39% dos golpes vieram de contas criadas no mesmo dia. **Mediana de 4 dias para essas contas contra 26 dias** para contas com pelo menos um dia de histórico (p<0,01). Quando o golpista escreve pelo menos metade dos posts, o golpe dura em média ~3 semanas, contra ~1 semana no geral (p<0,01) — [Vasek, tese (PDF), cap. 5](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)

**Crise macro de 2008–2009 (EUA)**
- Na amostra da SEC, os quatro trimestres com 10 ou mais Ponzis estão todos em 2008–2009, e o máximo é o 4º tri de 2009 (n=20). **A correlação entre o número de Ponzis processados no trimestre e o retorno do S&P 500 no mesmo trimestre é de −0,284.** Os autores dão duas explicações: no mercado ruim, o fraudador tende a pular um pagamento, o que dispara saques e reduz entradas; e os orçamentos de fiscalização sobem depois do estouro de bolhas — [Deason et al. (PDF), seção 2](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)
- Ponzis descobertos por ano nos EUA: 2008: 40 · **2009: 118** · 2010: 80 · 2011: 99 · 2012: 103 · 2013: 65 · 2014: 66 · 2015: 73 · 2016: 65 · 2017: 60 · 2018: 42 — [Ponzitracker (2019)](https://www.ponzitracker.com/home/tag/fraud)
- *Contagem divergente para 2009:* a AP fala em "mais de 150 Ponzis colapsaram em 2009, contra cerca de 40 em 2008", com mais de US$ 16,5 bi perdidos em 2009 sem contar Madoff — [Lawrence Journal-World/AP, "Ponzi collapses quadrupled in '09"](https://www2.ljworld.com/news/2009/dec/29/ponzi-collapses-quadrupled-09/); [PlanAdviser, "2009 was the Year of the Ponzi"](https://www.planadviser.com/ap-2009-was-the-year-of-the-ponzi/)
- Colômbia: antes do fechamento das pirâmides DMG e DRFE (nov/2008), os depósitos bancários caíram mais nos municípios mais expostos. Os participantes tinham mais crédito e melhor rating antes do fechamento e pioraram depois — [Hofstetter et al., JBF (2018)](https://ideas.repec.org/a/eee/jbfina/v96y2018icp18-33.html)

**Bear markets cripto (2018, 2022)**
- Em 2019, golpes cripto receberam US$ 4,3 bi (mais que o triplo de 2018), e **92% foram Ponzis**. Só o PlusToken trouxe pelo menos US$ 2 bi de mais de 3 milhões de pessoas — [MIT Technology Review, sobre a Chainalysis (30/01/2020)](https://www.technologyreview.com/2020/01/30/275964/cryptocurrency-ponzi-scams-chainalysis/)
- Em 2022 (até julho), a receita de golpes cripto ficou em US$ 1,6 bi, 65% abaixo do mesmo período de 2021. Segundo a Chainalysis, desde jan/2022 ela "caiu mais ou menos em linha com o preço do bitcoin" — [Decrypt (ago/2022)](https://decrypt.co/107613/crypto-crime-falls-15-along-with-bear-market-chainalysis)
- No Ethereum, a criação de Ponzis teve pico em 2016–2019, recuo no período da COVID e um pico menor em 2021. O maior fluxo de entrada foi em fev/2018, logo depois do topo de preços de dez/2017 — [Liang et al., PonziGuard (PDF)](https://export.arxiv.org/pdf/2406.00921)

**China P2P: corrida e fuga**
- Mecanismo descrito: com garantia de principal e reservas pequenas, "quando faltavam novos investidores ou havia desaceleração econômica", poucos defaults esgotavam a reserva, criavam pânico e disparavam uma **corrida** de saques — [Huang, HKUST IEMS (2022)](https://iems.ust.hk/assets/publications/thought-leadership-briefs/2022/hkustiems-huang-why-did-the-peer-to-peer-lending-market-fail-in-china-tlb61.pdf)
- Das **6.292 quebras registradas, 1.219 (19,37%) foram fuga dos donos** e 397 (6,31%) foram investigadas por fraude, como Ponzi ou informação falsa sobre tomadores. As demais foram por causas "normais" (liquidez, falta de investidores, prejuízo). Há 30 colapsos com mais de CNY 1 bi em aberto, com concentração em jun–jul/2018. Exemplos: Ezubao (dez/2015, CNY 38 bi, 895 mil credores), Fanya (abr/2015, CNY 33,8 bi, 135 mil), Tuandai (mar/2019, CNY 14,5 bi, 222 mil) — [Huang, HKUST IEMS (2022), Fig. 3 e Tabela 2](https://iems.ust.hk/assets/publications/thought-leadership-briefs/2022/hkustiems-huang-why-did-the-peer-to-peer-lending-market-fail-in-china-tlb61.pdf)

**Exit scams (fuga planejada)**
- Smart Ponzis: parte dos 805 contratos acabou porque não atraiu investidores novos. Outra parte acabou porque o dono acionou a função *self-destruct* e fugiu com os fundos — [Liang et al., PonziGuard (PDF)](https://export.arxiv.org/pdf/2406.00921)
- Rug pulls em DEX (Ethereum e BSC): ~60% dos tokens vivem menos de 1 dia. 81,2% dos tokens de 1 dia na PancakeSwap têm o padrão de rug pull. Foram 272.349 rug pulls potenciais na BSC e 21.742 no Ethereum, com ~US$ 240 mi para os organizadores — [Cernera et al., "Token Spammers, Rug Pulls, and Sniper Bots" (USENIX Security 2023)](https://www.usenix.net/system/files/usenixsecurity23-cernera.pdf); [arXiv 2206.08202](https://arxiv.org/abs/2206.08202v2)

### Inferences
- **Taxa prometida:** a evidência direta (HYIPs) aponta que promessa maior leva a vida menor. Na SEC, a promessa mediana (12–25% a.a.) é baixa, e os esquemas duram anos. O mecanismo é o da equação de Artzrouni: o passivo cresce à taxa prometida, e a taxa de entrada precisa superá-la. Em termos práticos, cada ponto de taxa prometida "compra" crescimento rápido ao custo de vida curta.
- **Afinidade contra mídia de massa:** confiança construída cara a cara (igreja, família, idosos) alonga a vida porque reduz os saques e o questionamento. Marketing amplo atrai investidores menos leais e mais atenção de regulador. É o oposto do que um observador leigo intuiria ("quem anuncia na TV deve ser legítimo").
- **Recrutadores pagos** são o motor de **tamanho**, não de longevidade. Isso conversa com as pirâmides brasileiras de bônus por indicação: crescem rápido e grandes, e não necessariamente duram mais.
- **Macro:** o choque de mercado age pelos dois lados do fluxo de caixa: menos entrada (investidores sem caixa) e mais saída (resgates para cobrir perdas). Em cripto, o canal dominante parece ser a entrada: com o preço caindo, o apetite pelo "retorno em cripto" some.
- **Exit scam é um desfecho frequente, não exceção:** na China, ~1 em 5 quebras de P2P foi fuga. Em smart contracts, o dono pode destruir o contrato. Para quem observa de fora, o fim pode ser decisão do operador, sem nenhum sinal de esgotamento de caixa.

### Gaps
- **Efeito de alertas de reguladores e de cobertura de mídia sobre a velocidade do colapso:** não achei estudo de evento ou de sobrevivência que meça isso. Há só indícios: no Bitcointalk, ~1/4 dos golpes morreu em menos de um dia, muitos derrubados por moderadores ([Vasek, tese](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)). Na China, a onda de colapsos de 2018–2019 coincide com o aperto regulatório ([HKUST IEMS](https://iems.ust.hk/assets/publications/thought-leadership-briefs/2022/hkustiems-huang-why-did-the-peer-to-peer-lending-market-fail-in-china-tlb61.pdf)). Os casos brasileiros (Atlas parou de pagar logo após o stop order; a Unick ignorou o seu) estão nas notas de modus operandi, sem medida sistemática.
- Não achei uma série da Chainalysis só de Ponzis para 2020–2025, com receita anual por tipo. Os números de 2021 e 2022 que encontrei são de "golpes" em geral. Um resumo de busca atribui à Chainalysis a queda de US$ 10,9 bi (2021) para US$ 5,9 bi (2022) e a cifra de mais de US$ 1,1 bi do Finiko (2021), mas não confirmei na fonte primária.
- Não verifiquei a fala atribuída ao presidente da CBIRC (Guo Shuqing) de que produtos com mais de 8% a.a. seriam "enormemente perigosos". Apareceu só em resumo de busca.
- Tamanho contra duração na SEC: só há a correlação simples (+0,33 entre ln(captado) e ln(duração)). Não há modelo que separe causa de efeito.

## 3. Distribuição de ganhos e perdas: quem sai no lucro e o papel do momento de entrada

### Takeaway
Em todos os Ponzis com dados completos, **a minoria sai no lucro**. Nos smart Ponzis de Bartoletti, em média ~70% dos participantes não recuperam o aportado (faixa de 44% a 88%). No Forsage, **mais de 88% tiveram perda líquida**. No TelexFree, ~93 mil "net winners" para até 1,9 milhão de participantes (≈5%). No Madoff, ~2 mil net winners. O ganho se concentra no dono, nos primeiros participantes e em poucos grandes investidores. O lado da entrada também é concentrado: ~20% das vítimas respondem por ~90% do dinheiro em alguns HYIPs.

### Cited Findings

**Smart Ponzis (Ethereum)**
- Em 23 contratos analisados, a fatia de usuários **sem ganho** (razão recebido/investido ≤ 1) é em média **~70%**. Os piores: Doubler 88% (81 de 92), ShinySquirrels 87%, GreedPit 85%, Rubixi 83%, Etheramid1 82%, Doubler2 79% (165 de 210), DynamicPyramid 76% (133 de 174), EthereumPyramid 68% (221 de 326). Os menos piores: ZeroPonzi 59% (sem taxa do dono), DianaEthereum 51%, Myscheme 44% — [Bartoletti et al. (PDF), Fig. A.34](https://export.arxiv.org/pdf/1703.03779v6)
- Doubler2, que promete dobrar: dos 210 usuários, 142 nunca receberam nada (67,6%), 23 recuperaram só parte (razão entre 0 e 1), 44 ficaram entre 1 e 2 e **1 recebeu 486x** (investiu 1 ETH e recebeu 486). Os ganhos excepcionais costumam ser do dono, via taxas — [Bartoletti et al. (PDF), seção 6](https://export.arxiv.org/pdf/1703.03779v6)
- **Gini dos pagamentos acima de 80%** na coleção — [Bartoletti et al. (PDF), seções 8–9](https://export.arxiv.org/pdf/1703.03779v6)

**Forsage**
- "A vasta maioria dos jogadores perdeu dinheiro, com **perdas líquidas para mais de 88%**." O dono do contrato recebeu mais de 5.000 ETH (US$ 1,2 mi). Os autores dizem ser a primeira quantificação precisa de ganhos e perdas em uma grande pirâmide. Quem comprou mais "níveis" foi, em média, mais lucrativo — [Kell et al., Forsage (arXiv 2105.04380)](https://export.arxiv.org/pdf/2105.04380)

**HYIPs em bitcoin (fluxo de caixa)**
- Bridge HYIPs: entraram US$ 6.456.593 e voltaram aos "investidores" no máximo US$ 3.464.476, o que deixa ~US$ 3 mi (≈46%, cálculo próprio) para os operadores. Há 9.410 grupos de endereços, teto do número de vítimas. HYIPs só de bitcoin: entraram US$ 842.909, voltaram US$ 802.655 e o golpista ficou com só US$ 40.254. Os autores avisam que parte dos "pagamentos às vítimas" deve ir para endereços do próprio golpista — [Vasek, tese (PDF), Tabela 4.2](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)
- Concentração da entrada: no Leancy, **~20% das vítimas contribuíram com 90%** dos pagamentos. Os 80% menores respondem por ~5% da receita nos HYIPs só de bitcoin e ~15% nos Bridge HYIPs — [Vasek, tese (PDF), seção 4.6.2](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)

**Madoff**
- O trustee Irving Picard considerava ~**2.000** ex-clientes "net winners" (sacaram mais do que aportaram) e moveu ~1.000 ações de clawback contra eles — [NBC News (2010)](https://www.nbcnews.com/id/wbna38417075)
- Os net losers com crédito aprovado receberam de volta, em média, **70%** do aportado (AP, 2021) — [ABC News 4/AP](https://abcnews4.com/news/nation-world/even-after-madoffs-death-work-to-unwind-epic-fraud-goes-on)

**TelexFree (EUA e Brasil)**
- Segundo o trustee Stephen Darr, o TelexFree teve até **1,9 milhão de participantes** e ~US$ 3 bi de atividade. Ele processou ~**93 mil net winners** (≈15 mil nos EUA e ≈78 mil no exterior). Isso dá ≈4,9% dos participantes como ganhadores líquidos (cálculo próprio) — [Patrick Pretty](https://patrickpretty.com/?p=26562); [Ponzitracker (2016)](https://ponzitracker.com/home/2016/1/24/telexfree-trustee-files-clawback-suit-against-78000-foreign.html); [Patrick Pretty (classe dos EUA)](https://patrickpretty.com/?p=27791)
- *Contagem alternativa:* manchete do BehindMLM fala em "63 mil investidores do TelexFree lesaram 831 mil vítimas" (página bloqueada ao acesso; só o título foi visto) — [BehindMLM](https://behindmlm.com/companies/telexfree/63000-telexfree-investors-ripped-off-831000-victims)
- A falência americana aprovou distribuição de US$ 150 milhões às vítimas — [Boston Globe (09/07/2020)](https://www.bostonglobe.com/2020/07/09/business/telexfree-bankruptcy-judge-approves-150-million-pyramid-scheme-victims)

### Inferences
- **A regra empírica é de 5% a 30% de ganhadores líquidos.** TelexFree (~5%) e Forsage (<12%) ficam na ponta baixa; os smart Ponzis simples (~30% em média; 41% no ZeroPonzi, sem taxa) na alta. Quanto mais taxa e "camadas" o operador extrai, menor a fração de ganhadores.
- **O momento de entrada decide quase tudo.** Nos contratos de fila (chain-shaped, 151 de 184), só quem entrou cedo o bastante para ser pago antes da parada recebe. Quem comprou mais níveis no Forsage (estrutura que remunera por recrutamento) e quem é dono (taxas) tende a ganhar. O peso da hora de entrada nesses casos não foi medido nas fontes. O ganhador típico é o operador, o recrutador de topo ou o participante precoce que saiu.
- Ser "net winner" não encerra o risco. No Madoff e no TelexFree, os ganhadores foram alvo de clawback, e as notas brasileiras mostram a sentença do TelexFree descontando o lucro recebido. Para a vítima potencial, até o cenário de sair no lucro tem risco jurídico (ver as notas de marco legal).
- A concentração da entrada (20% das vítimas = 90% do dinheiro) explica por que os operadores investem em "baleias" e em afinidade com pessoas de patrimônio, como os idosos nos dados da SEC.

### Gaps
- Não achei o número total de contas do Madoff, para calcular a fração exata de net winners, nem a distribuição por data de entrada.
- MMM (Rússia, 1994; MMM Global, 2015–2016): não achei estudo quantitativo da distribuição de ganhos.
- Não há, que eu tenha encontrado, curva publicada de "probabilidade de lucro × mês de entrada" para um Ponzi real. Bartoletti e Kell têm os dados on-chain para isso, mas só publicam agregados (Doubler2 por usuário; Forsage por nível comprado).

## 4. Modelos teóricos: o que preveem sobre o momento do colapso

### Takeaway
Os modelos concordam em um ponto: **o colapso acontece quando o fluxo líquido de caixa (entradas − saques e juros) cruza zero**, e crescer mais rápido antecipa esse ponto. Artzrouni dá as condições analíticas de solvência a partir de quatro parâmetros. Os modelos epidemiológicos em redes mostram que difusão mais rápida leva a pico mais alto e colapso mais cedo, e propõem o zero do fluxo de fundos como indicador antecedente. Bhattacharya explica por que esquemas gigantes podem continuar mesmo com participantes que sabem do fim: a expectativa de socorro.

### Cited Findings
- **Artzrouni (2009):** equação diferencial linear de 1ª ordem com quatro parâmetros (taxa prometida, taxa nominal realizada, ritmo de novos depósitos e taxa de saques). Dá condições de solvência ou colapso e foi ajustada aos dados do esquema de Charles Ponzi (1920). *Mathematical Social Sciences* 58(2):190–201 — [IDEAS/RePEc](https://ideas.repec.org/a/eee/matsoc/v58y2009i2p190-201.html); [MPRA](https://mpra.ub.uni-muenchen.de/14420/)
- **Bhattacharya (2003):** numa economia finita, nenhum agente racional entraria na última rodada, o que dificulta desenhar Ponzis "certos de explodir". Mas, se os agentes esperam um **socorro parcial** quando um Ponzi gigante quebra (uma redistribuição de não participantes para participantes), entrar pode ser racional mesmo sabendo que é a última rodada. O promotor maximizador de lucro desenha esquemas gigantes para explorar o "grande demais para quebrar". *Journal of Financial Intermediation* 12(1):2–24 — [IDEAS/RePEc](https://ideas.repec.org/a/eee/jfinin/v12y2003i1p2-24.html)
- **Zhu, Fu, Zhang & Chen (2017), modelo PID (potencial investidor–investidor–desinvestidor) em redes:** grau médio maior e distribuição de grau em lei de potência **reduzem o limiar crítico de difusão e aceleram o espalhamento**. "Quanto mais rápido o esquema se difunde, mais alto o pico e **mais cedo o colapso**." Difusão rápida alivia temporariamente o peso dos juros, mas antecipa o fim. O **cruzamento por zero da função de fluxo de fundos** serve como índice para prever instabilidade e colapso. Simulações em redes artificiais e no Facebook. *Physica A* 479:128–136 — [IDEAS/RePEc](https://ideas.repec.org/a/eee/phsmap/v479y2017icp128-136.html)
- Extensão PIDI (com reinvestimento, Physica A 490, 2018): a taxa de espalhamento se relaciona ao surto epidêmico e a taxa de reinvestimento aos estados finais (resumo de busca) — [IDEAS/RePEc](https://ideas.repec.org/a/eee/phsmap/v490y2018icp632-642.html)
- Empiria que conversa com os modelos: no Ethereum, o fluxo de entrada de Ether e o número de transações dos Ponzis andam juntos (correlação positiva). Os contratos mostram pico de entrada e saída seguido de estagnação — [Liang et al., PonziGuard (PDF)](https://export.arxiv.org/pdf/2406.00921); [Bartoletti et al. (PDF), seção 7](https://export.arxiv.org/pdf/1703.03779v6)

### Inferences
- **Previsão operacional dos modelos:** o tempo até o colapso cai com (i) a diferença entre a taxa prometida e a realizada, (ii) a taxa de saques e (iii) a velocidade de crescimento, porque a saturação chega antes. Taxa prometida de 10% a.m. contra ~1% a.m. de retorno real (CDI de out/2026) exige que a captação líquida cresça ~9% a.m. só para empatar. Isso mostra por que esquemas desse tipo vivem de meses a poucos anos.
- O "zero-crossing" do fluxo líquido é teoricamente o melhor indicador antecedente, mas **não é observável de fora** num esquema off-chain. Na prática, o observador externo usa proxies: atraso de saque, novas regras, troca por token próprio (ver seção 6).
- Bhattacharya ajuda a entender a resiliência de esquemas de massa (Albânia, GAS, PlusToken). Quando o número de participantes é politicamente relevante, a expectativa de socorro ou de "retomada" reduz os saques e alonga a vida.

### Gaps
- Não li o texto integral de Artzrouni nem de Bhattacharya. Não tenho as fórmulas fechadas de tempo de colapso nem os valores ajustados ao caso Ponzi de 1920.
- Não achei validação empírica dos modelos PID/PIDI com dados de um esquema real (só simulação).

## 5. Detecção e escore de risco: que modelos e indicadores classificam uma oferta como provável Ponzi

### Takeaway
Não achei nenhum **escore de "probabilidade de ser Ponzi" publicado e validado por regulador** (SEC, FINRA ou CVM). As listas oficiais são checklists sem pesos. Os escores quantitativos validados vêm da academia, em três famílias. (1) **Gestores regulados:** as divulgações do Form ADV (violações passadas, conflitos de interesse, monitoramento) preveem fraude; evitar os 5% de maior risco previsto evita 29% dos casos e mais de 40% das perdas. As "performance flags" de retorno (retornos suaves demais, poucos meses negativos, descontinuidade em zero) disparam mais em fundos acusados de Ponzi. (2) **Smart contracts:** classificadores por código e por comportamento chegam a 89–97% de precisão, mas a frequência de opcodes sozinha é fraca. (3) **Web e fóruns:** sinais de reputação (conta nova, shills, avaliação de agregador) separam bem esquemas de vida curta e longa.

### Cited Findings

**Fraude de gestores (EUA)**
- **Dimmock e Gerken (JFE, 2012):** Form ADV de todos os consultores de investimento entre ago/2001 e jul/2006, com fraudes contra clientes identificadas até jul/2010. Divulgações sobre **violações regulatórias e legais passadas, conflitos de interesse e monitoramento** têm poder preditivo significativo. **Evitar os 5% de firmas com maior risco previsto ex ante evita 29% dos casos de fraude e mais de 40% das perdas em dólar.** Não há evidência de que o investidor seja compensado pelo risco com desempenho melhor ou taxas menores — [Alpha Architect (resumo do artigo)](https://alphaarchitect.com/2012/07/6480/); [Gerken, versão de conferência (PDF)](https://www.ou.edu/dam/price/Finance/Oklahoma_conference/2011/William%20Gerken%20-%20Finding%20Bernie%20Madoff%20Detecting%20Fraud%20by%20Investment%20Managers.pdf)
- **Bollen e Pool (RFS, 2012):** propõem "performance flags" baseadas em padrões suspeitos de retorno. Fundos acusados de **apropriação indébita, sobreavaliação, declaração falsa ou Ponzi** disparam as flags com mais frequência que os outros. Amostra: 8.770 fundos, sendo 195 "problemáticos" (alvo de ação da SEC ou de investidores) e 8.575 não problemáticos. Flags: (1) descontinuidade na distribuição dos retornos em zero; (2) baixa correlação com fatores de estilo; (3) retornos artificialmente suaves (autocorrelação); (4) tratamento diferente de perdas e ganhos; (5) má qualidade dos dados (retornos repetidos, poucos negativos) — [IDEAS/RePEc (RFS 25(9):2673–2702)](https://ideas.repec.org/a/oup/rfinst/v25y2012i9p2673-2702.html); [Vanderbilt News (2011)](https://news.vanderbilt.edu/2011/04/15/how-to-catch-a-hedge-fund-cheater); [Vanderbilt News (2012)](https://news.vanderbilt.edu/2012/02/28/do-not-ignore-signs-of-hedge-fund-fraud/)
- Na amostra da SEC, 17% dos fraudadores tinham condenação anterior por fraude financeira, e isso encurta a vida do esquema (−0,318 em ln(duração)). O histórico do responsável é um sinal observável de fora — [Deason et al. (PDF)](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)

**Smart contracts (Ethereum)**
- **Chen et al. (WWW 2018):** primeiro classificador (XGBoost) com features de conta (transações) e de opcodes do contrato. Detecta Ponzis "no momento da criação" e estimou mais de 400 Ponzis rodando no Ethereum — [Webis/ACM anthology (resumo)](https://ir.webis.de/anthology/2018.wwwconf_conference-2018.138); [Papers with Code](https://cs.paperswithcode.com/paper/detecting-ponzi-schemes-on-ethereum-towards)
- Comparação no mesmo dataset ground truth, por validação K-fold (precisão / recall / F1):
  - OpML (opcodes, Chen et al.): 89,0% / 77,8% / 83,0%;
  - TxML (transações): 69,6% / 63,4% / 66,4%;
  - SADPonzi (execução simbólica): 88,1% / 64,5% / 74,5%;
  - MulCas: 95,1% / 67,4% / 78,9%;
  - SourceP (código-fonte): 91,6% / 93,3% / 92,4%;
  - **PonziGuard** (grafo de comportamento em tempo de execução + rede neural de grafos): **96,9% / 98,2% / 97,5%**;
  - fonte: [Liang et al., PonziGuard (PDF), Tabela 3](https://export.arxiv.org/pdf/2406.00921)
- A frequência de opcodes é feature fraca: a divergência KL entre Ponzis e não Ponzis fica entre só 0,011 e 0,018, praticamente a mesma que entre Ponzis diferentes (0,012–0,016). O comportamento de fluxo de dinheiro (quem paga quem, sob que condição) discrimina melhor. Modelos por transação não detectam Ponzis "0-day", ainda sem transações — [Liang et al., PonziGuard (PDF)](https://export.arxiv.org/pdf/2406.00921)
- Os Ponzis do Ethereum são clones: a distância de Levenshtein normalizada média entre os bytecodes é de 0,54, contra 0,79 entre contratos quaisquer. Similaridade de código com Ponzi conhecido é uma feature forte — [Bartoletti et al. (PDF)](https://export.arxiv.org/pdf/1703.03779v6)
- Revisão de métodos de ML (RF, NN, KNN) para Ponzi no Ethereum: o random forest teve melhor desempenho, com acurácia de 0,94 (resumo de busca; artigo não lido) — [Detection of Ponzi scheme on Ethereum using machine learning algorithms (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10611762/)
- Resumo de busca, não verificado: um modelo por transação detectaria mais de 89% dos novos Ponzis com precisão de ~80%, e mais de 80% das features importantes viriam de volume de transações, atividade de investimento e pagamento e saldo (metade delas séries temporais). O mesmo resumo fala em "F1 de pelo menos 90%", o que é incompatível com precisão de 80% e recall de 89% (F1 ≈ 84%, cálculo próprio). Não confirmei que esses números são deste artigo — [arXiv 2308.16391, "Improving the Accuracy of Transaction-Based Ponzi Detection on Ethereum"](https://arxiv.org/pdf/2308.16391)

**Web e fóruns (HYIPs e Bitcointalk)**
- Os agregadores de HYIP funcionam como "escore" informal. Uma semana antes do colapso, a **nota média dos agregadores era de 22%** e **92% dos HYIPs tinham nota ≤ 50%**. A **nota média dos usuários era de 60%**, e 57% tinham nota ≥ 80%. No hyipranks.com: usuários com 96% e agregador com 35%. Quem já investiu tem incentivo para inflar a nota e atrair dinheiro novo. Os agregadores, que esperam o colapso, são mais precisos. Não há indício de conluio entre agregadores — [Moore, Han & Clayton (PDF), seção 4.3](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- Meios de pagamento como marcador: Liberty Reserve era aceita por 83% dos HYIPs e Perfect Money por 70%. 72% dos backlinks da Perfect Money vinham de sites de HYIP — [Moore, Han & Clayton (PDF), seção 5](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- No Bitcointalk, conta criada no mesmo dia (hazard +45%) e presença de shills (hazard −57%) são preditores fortes de vida curta ou longa (seção 2) — [Vasek, tese (PDF)](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)

**P2P (China)**
- Classificador de falência de plataformas P2P chinesas com seleção de variáveis (filter e wrapper): **AUC ≈ 0,96 e F1 ≈ 0,88** — [Yeh, Chiu & Huang, "Predicting Failure of P2P Lending Platforms through Machine Learning: The Case in China" (Finance Research Letters 59, 2024; arXiv 2311.14577)](https://arxiv.org/abs/2311.14577v1)

### Inferences
- **Indicadores com mais poder preditivo, pela evidência acumulada (síntese própria):**
  1. **Histórico do responsável** (violações e condenações anteriores): Dimmock-Gerken e Deason.
  2. **Forma da série de retornos** (suave demais, sem meses negativos, retornos repetidos): Bollen-Pool, o padrão Madoff.
  3. **Origem do pagamento**, isto é, se o dinheiro dos novos paga os antigos (o critério dos classificadores on-chain e de comportamento): PonziGuard e Bartoletti.
  4. **Clonagem** de código ou site de esquema conhecido: Bartoletti.
  5. **Reputação e idade da identidade** do promotor (conta ou CNPJ recém-criado): Vasek.
  6. **Taxa prometida** (acima de alguns % ao dia, vida curta quase certa): Moore.
- **Nota da multidão é contraindicador.** Avaliações positivas de participantes (grupos de WhatsApp, depoimentos, YouTube) refletem o incentivo de quem já está dentro (Moore et al.). Isso conversa com o achado da CVM de que 38,8% das vítimas citaram amigos e familiares que já investiam.
- Para o Brasil, um escore fora do mundo cripto teria de usar dados que o investidor consegue checar: registro na CVM ou no BCB, histórico de processos do responsável, idade e capital social do CNPJ, retorno prometido contra o CDI, tipo de contrato e bônus por indicação. Os pesos não estão validados empiricamente. A literatura sustenta a direção de cada item, não um peso numérico.

### Gaps
- **Não achei escore publicado de "probabilidade de ser Ponzi"** por SEC, FINRA, CVM ou IOSCO, nem lista ponderada. As listas são binárias (SEC: 7 red flags; CVM: 4 sinais; ver notas de modus operandi). Não consegui acessar listas da FINRA nesta pesquisa nem na anterior.
- Não confirmei os números originais de precisão e recall de Chen et al. (WWW 2018). Os 89,0% / 77,8% são da reprodução feita pelo PonziGuard em outro dataset.
- Não verifiquei na fonte primária o número "51% dos fundos problemáticos com 'retornos aleatórios' contra 23% dos não problemáticos" atribuído a Bollen e Pool num resumo de busca. Não confirmei a fração de fundos Ponzi que disparam cada flag.
- Não achei estudo de detecção de HYIPs só pelas características do site (classificador com features de HTML ou texto) com acurácia publicada. O trabalho de Neisius e Clayton (eCrime 2014) sobre kits de HYIP não foi lido.

## 6. Indicadores de proximidade do colapso: o que antecede o fim, e com quanta antecedência

### Takeaway
A evidência quantitativa sobre sinais antecedentes é escassa, e quase toda de esquemas online, onde há dados diários. Os achados mais sólidos: (1) os **pagamentos param ("flat-line") alguns dias antes** de o agregador declarar o HYIP morto; (2) **aumento de reclamações e posts de vítimas** eleva o risco diário de fim (+2,9% por comentário diário); (3) nos smart Ponzis, a **entrada atinge pico e cai**, e o colapso segue a estagnação; (4) em esquemas de massa, **escalada da taxa prometida** precede o colapso em meses (Albânia: de 4–5% a.m. para mais de 30% a.m. em menos de um ano); (5) **choques macro** coincidem com ondas de colapso. Não achei estudo que meça o tempo de antecedência de sinais como mudança de regra de saque ou troca por token próprio.

### Cited Findings
- **Pagamentos param antes do anúncio:** os agregadores registram o ROI dos próprios investimentos, que "achata" (para de mudar) alguns dias antes de o agregador parar de acompanhar o HYIP. Nos HYIPs de vida muito curta (menos de uma semana), medir pela parada do ROI dá vida bem menor que medir pela saída da lista — [Moore, Han & Clayton (PDF), seção 3.2 e Fig. 2](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- **Notas 7 dias antes do colapso:** 92% dos HYIPs já tinham nota de agregador ≤ 50%, mas só 38% tinham nota de usuário ≤ 50% — [Moore, Han & Clayton (PDF), seção 4.3](https://www.cl.cam.ac.uk/~rnc1/hyips.pdf)
- **Reclamações sobem antes do fim:** cada comentário diário a mais de vítimas eleva o hazard em 2,9%, e cada um do golpista em 2,2%. A interpretação dos autores é que vítimas e golpistas postam mais quando há problemas. A mediana do primeiro comentário de vítima é ~5 dias depois do anúncio — [Vasek, tese (PDF), seção 5.2](https://tylermoore.ens.utulsa.edu/thesis/vasek.pdf)
- **Escalada da taxa prometida (Albânia):** em jan/1996 as taxas subiram de 4–5% a.m. para 6% a.m., e na incerteza eleitoral para 8% a.m. No fim de 1996, a Sude oferecia 12–19% a.m., a Populli mais de 30% a.m. e a Xhafferi prometia triplicar o dinheiro em 3 meses. A Sude respondeu com "dobrar o principal em 2 meses". O default da Sude veio em 19/11/1996, seguido de falências em jan/1997, ~2.000 mortos, queda de ~7% do produto e inflação acima de 40% em 1997 — [Jarvis, IMF F&D (2000)](https://www.imf.org/external/pubs/ft/fandd/2000/03/jarvis.htm)
- **Pico e estagnação do fluxo (smart Ponzis):** contratos com alto volume de transações num intervalo curto, depois transações isoladas e inatividade. No Etheramid, 1 mês de atividade, com 5 dias intensos. Há correlação entre entrada e saída ao longo do tempo — [Bartoletti et al. (PDF), seção 7](https://export.arxiv.org/pdf/1703.03779v6)
- **Zero do fluxo líquido como indicador teórico:** o cruzamento por zero da função de fluxo de fundos (entrada − saída) indica o colapso iminente nos modelos de difusão — [Zhu et al., Physica A (2017)](https://ideas.repec.org/a/eee/phsmap/v479y2017icp128-136.html)
- **Choque macro:** trimestres de S&P 500 negativo concentram processos de Ponzis (correlação de −0,284). O fraudador tende a pular um pagamento em tempos ruins, o que dispara saques e reduz entradas — [Deason et al. (PDF)](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/12962/ponzi%20draft%20may%2013%202015.pdf)
- **Esgotamento de reserva e corrida (P2P):** poucos defaults esgotam a reserva de garantia, e a perda de confiança leva à corrida de saques — [Huang, HKUST IEMS (2022)](https://iems.ust.hk/assets/publications/thought-leadership-briefs/2022/hkustiems-huang-why-did-the-peer-to-peer-lending-market-fail-in-china-tlb61.pdf)
- **Saída dos bancos antes do fechamento (Colômbia):** depósitos bancários caíram mais nos municípios expostos antes de nov/2008. É um sinal agregado de migração de poupança para as pirâmides na fase de aceleração — [Hofstetter et al., JBF (2018)](https://ideas.repec.org/a/eee/jbfina/v96y2018icp18-33.html)

### Inferences
- **Ordem provável dos sinais para quem observa de fora (síntese própria, sem tempos medidos):**
  1. aceleração da captação e escalada de taxa ou bônus para atrair dinheiro novo (meses antes, como na Albânia);
  2. aumento de reclamações públicas e de "tranquilizadores" (shills, depoimentos);
  3. atraso ou "flat-line" dos pagamentos, com novas regras de saque, taxas, lock-up ou troca por token próprio (dias a semanas antes, como nos HYIPs; os casos brasileiros estão nas notas de modus operandi);
  4. parada total.
- A **escalada da taxa prometida** é o sinal antecedente com melhor fundamento teórico e histórico. Pela equação de Artzrouni, subir a taxa para atrair entradas aumenta o passivo futuro e antecipa o zero do fluxo líquido. Um esquema que eleva a promessa ou cria bônus extra está, provavelmente, com entrada líquida em queda.
- Para o investidor já dentro, o sinal mais acionável é o **primeiro atraso de saque**. Nos HYIPs, a distância entre a parada dos pagamentos e o colapso declarado é de dias. Na maioria dos casos, a janela de saída se fecha muito antes de o esquema admitir problema.
- Avaliações de quem está dentro não antecipam nada: a nota dos usuários segue alta até a semana do colapso.

### Gaps
- **Nenhum estudo encontrado mede com quanta antecedência** mudança de regra de saque, troca para token próprio, aumento de bônus ou queda na taxa de novos depósitos precedem o colapso, com amostra. A evidência sobre esses sinais é qualitativa (pesquisa CVM/CECOP 2021 e casos brasileiros nas notas de modus operandi).
- Não achei os números dos resgates pedidos ao Madoff no fim de 2008 em fonte verificada, que seriam o exemplo clássico de corrida de saques como gatilho.
- Não achei estudo com dados on-chain que meça a queda de usuários novos por semana antes do fim de um grande Ponzi, como Forsage ou PlusToken. O artigo do Forsage mostra pico em jun–ago/2020 seguido de queda, mas eu não extraí números de antecedência.
