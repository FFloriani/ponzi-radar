# Linha do tempo das pirâmides e Ponzis com fachada cripto/forex no Brasil (2015 a out/2026): quanto duraram, como terminaram e se o bitcoin explica o colapso

> Notas de pesquisa de 07/10/2026. O foco é cronológico e operacional: eventos legais (stop order, operação, RJ, falência) aparecem só como marcos de data. Ponto de partida: as notas `casos_cripto_forex_2017_2022.md`, `casos_recentes_2023_2026.md` e `modus_operandi_sinais_alerta.md` (pasta "Pirâmides financeiras no Brasil"). Os fatos reaproveitados citam a fonte original. Datas novas do ciclo de vida vieram de buscas nesta rodada.
>
> **Convenções.**
> - **S** = início da captação. **E** = primeiro sinal de estresse visível para quem estava dentro. **P** = parada de pagamentos. **I** = intervenção (operação, bloqueio, prisão ou falência).
> - **Duração** = meses de S até o primeiro entre P e I ("colapso"). Faixas aparecem quando S ou P só são conhecidos pelo ano.
> - "Acusado"/"investigado" quando não há condenação; "condenado em 1ª instância" quando há sentença recorrível.
> - "(trecho de busca)" marca dado tirado do resumo do buscador, sem leitura da página. Trate como menos firme.
> - **Conversão de retornos:** diário → mensal em duas versões, simples (×30) e composta ((1+d)^30 − 1, 30 dias corridos). Quando faz diferença, informo também 21 dias úteis. Prazo → mensal: (multiplicador)^(1/n) − 1.
> - **BTC:** preço diário em USD da [Coin Metrics Community API](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d), de 01/12/2014 a 06/10/2026, baixado em 07/10/2026. As métricas são cálculo próprio:
>   - "var. 6m" = fechamento do mês do colapso contra o fechamento de 6 meses antes;
>   - "MDD janela" = maior queda pico→vale dentro da janela [M−6, M];
>   - "vs ATH" = fechamento do mês contra a máxima histórica até ali.

---

## 1. Régua de comparação: como o bitcoin se comportou em 2015–2026 e o que é "normal" numa janela de 6 meses

### Takeaway
O BTC teve três grandes topos com quedas de 53% a 84% depois deles: dez/2017, nov/2021 e out/2025. Mas quedas fortes em janelas de 6 meses são rotina. Em 61% dos meses entre 2016 e 2026 houve queda pico→vale de 30% ou mais nos 6 meses anteriores, e em 24% dos meses a queda foi de 50% ou mais. Por isso, achar um drawdown antes de um colapso não prova nada. O teste precisa comparar com essa taxa-base.

### Cited Findings
- **Máximas e mínimas anuais (USD; cálculo próprio)** — [Coin Metrics](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d):
  - 2017: máx. 19.641 (16/12)
  - 2018: mín. 3.185 (15/12), −83,8% do topo de 2017
  - 2019: máx. 12.863 (26/06)
  - 2020: mín. 4.959 (12/03)
  - 2021: máx. 67.542 (08/11)
  - 2022: mín. 15.758 (09/11, semana da quebra da FTX), −76,7% do topo
  - 2024: máx. 106.116 (17/12)
  - 2025: máx. 124.824 (06/10)
  - 2026: mín. 58.525 (30/06), −53,1% do topo
  - 06/10/2026: 85.523
- **Taxa-base (129 meses, jan/2016–set/2026; cálculo próprio)** — [Coin Metrics](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d):
  - MDD na janela de 6 meses de −30% ou pior em 61% dos meses; de −40% ou pior em 40%; de −50% ou pior em 24%; de −60% ou pior em 11%. Mediana: −32,1%.
  - Variação de 6 meses negativa em 33% dos meses; de −20% ou pior em 21%; de −40% ou pior em 9%.
  - Fechamento 50% ou mais abaixo do ATH em 34% dos meses (os "regimes de bear market": 2018–2020 e 2022–2023).
- **Referências externas de duração:**
  - Ponzis processados pela SEC (376 casos, 1988–2012) duraram em média cerca de 4 anos — [Deason, Rajgopal & Waymire (SSRN, 2015)](https://papers.ssrn.com/abstract=2586490)
  - Golpes cripto rastreados pela Chainalysis ficaram ativos em média 271 dias quando começaram em 2020 e 42 dias quando começaram em 2024 (até o meio de 2024). A tendência é de campanhas menores e descartáveis, como o pig butchering — [Cyberscoop, 29/08/2024, sobre o "2024 Crypto Crime Mid-Year Update"](https://cyberscoop.com/online-scamming-cycles-shorter-more-effective-chainalysis/)
  - Ponzis em contratos inteligentes no Ethereum: cerca de 60% tiveram vida "próxima de 0 dias", porque não atraíram usuários. A vida é medida do primeiro ao último fluxo do contrato — [Bartoletti et al., "Dissecting Ponzi schemes on Ethereum" (arXiv 1703.03779)](https://arxiv.org/pdf/1703.03779)
  - Choque de mercado como gatilho fora do Brasil: segundo um escritório de advocacia americano, mais de 150 Ponzis colapsaram nos EUA em 2009, contra cerca de 40 em 2008. O caso Madoff estourou com pedidos de saque de cerca de US$ 7 bi na crise — [Investor Lawyers (blog; trecho de busca, página não abriu)](https://www.investorlawyers.com/blog/number-of-ponzi-scam-collapses/); [International Banker](https://internationalbanker.com/history-of-financial-crises/bernie-madoffs-ponzi-scheme-2008/)
- Não achei estudo brasileiro que meça a duração média de pirâmides. A busca só trouxe textos educativos — [busca registrada; ex.: Eu Quero Investir](https://euqueroinvestir.com/educacao-financeira/opiniao-o-brasileiro-e-as-piramides-financeiras)

### Inferences
- Como 1 em cada 4 meses tem queda de 50% ou mais na janela de 6 meses, só um excesso claro sobre esses 24% (ou sobre os 34% de meses em bear market) sustentaria a tese "colapsos seguem o ciclo do BTC". É esse o teste da seção 7.
- A queda de 2026 (de 124,8 mil para 58,5 mil) é a primeira grande queda com o regime de PSAVs do BCB já em vigor. Os casos de 2026 levantados (Mirage, Criptoabate) são falsas plataformas encerradas por intervenção, não pirâmides que quebraram com o mercado (seção 4).

### Gaps
- Não usei série em reais (BTC/BRL). O drawdown em reais difere do em dólares em anos de câmbio volátil, como 2020 e 2024.
- O dado de 2009 (EUA) é de blog de escritório, só pelo trecho de busca. Não achei a fonte primária, provavelmente Marquet International.

---

## 2. Fichas de ciclo de vida: primeira onda (captação 2015–2018, colapsos 2017–2020)

### Takeaway
Na primeira onda, a maioria dos esquemas morreu de falta de caixa, antes ou sem intervenção estatal: Minerworld, Trade Coin Club, GBB, Unick, 18k e BWA. Kriptacoin e InDeal foram fechadas por operações policiais quando ainda captavam. Na Atlas, foi o stop order da CVM que disparou a corrida de saques. Os colapsos se concentram em dois momentos: o topo do BTC no fim de 2017 (Minerworld, TCC) e o meio de 2019, quando o BTC subia mais de 100% em 6 meses (Unick, Atlas, FX, VIK, 18k).

### Cited Findings

#### Kriptacoin / Wall Street Corporate (Brasília/DF, Weverton Viana Marinho)
- **Início e fachada:** jan/2017; moeda virtual própria e fictícia (token próprio) — [MPDFT, 21/09/2017](https://www.mpdft.mp.br/portal/index.php/comunicacao-menu/sala-de-imprensa/noticias/noticias-2017/9478-operacao-patrick-moeda-digital-kriptacoin-e-alvo-de-investigacao-do-mpdft-e-da-pcdf); [ConJur](https://www.conjur.com.br/?p=443147)
- **Retorno:** "1% de lucro ao dia" e "R$ 1 milhão em até seis meses" (MPDFT 2017). Conversão: 30% a.m. simples; 34,8% a.m. composto em 30 dias; 23,2% em 21 dias úteis.
- **Estrutura:**
  - Bônus de 10% por indicação (trecho de busca: [Metrópoles](https://www.metropoles.com/distrito-federal/seguranca-df/vitimas-do-df-relatam-prejuizos-de-ate-r-200-mil-com-kriptacoin); [Tecnoblog](https://tecnoblog.net/224216/kriptacoin-falsa-moeda-digital/)) e "ganhos maiores por indicação" — [MPDFT 2018](https://www.mpdft.mp.br/portal/index.php/comunicacao-menu/sala-de-imprensa/noticias/noticias-2018/10000-operacao-patrik-13-sao-condenados-no-esquema-da-kriptacoin)
  - Recrutamento obrigatório, níveis, carência e reinvestimento: não encontrado.
- **Pico:** cerca de 40 mil vítimas e cerca de R$ 250 mi (MPDFT 2017). Mês do pico: não encontrado.
- **1º alerta público:** nenhum anterior à operação encontrado (sem stop order da CVM nem matéria crítica prévia).
- **Estresse:** primeiro saque diário de até R$ 600, depois só semanal, depois suspenso. Os operadores alegaram "ataques cibernéticos" — [MoneyTimes, 21/09/2017](https://www.moneytimes.com.br/operacao-que-combate-piramide-com-uso-da-kriptacoin-prende-11-pessoas/). Mês de cada etapa: não informado; todas antes de 21/09/2017.
- **Parada e intervenção:**
  - Os saques já estavam suspensos antes da operação, segundo o promotor citado pela MoneyTimes.
  - Operação Patrik em 21/09/2017, com 11 de 13 prisões e 18 buscas no DF e em GO (MPDFT 2017).
  - Denúncia em 28/09/2017 — [Correio Braziliense](https://www.correiobraziliense.com.br/app/noticia/cidades/2017/09/28/interna_cidadesdf,629904/mpdft-denuncia-16-no-esquema-de-fraude-da-moeda-virtual-kriptacoin.shtml)
- **Duração:** 8 meses (jan→set/2017). Estresse → colapso: não calculável.
- **Gatilho:** (a) intervenção do Estado, com saques já racionados.
- **BTC (set/2017):** fechamento de 4.335; var. 6m +300,7%; MDD da janela −35,8% (11/06→16/07/2017); −11,9% do ATH. Dentro de setembro caiu −34% do topo de 01/09 — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** culpou "hacker" e foi preso na operação, sem fuga prévia. Condenado em 1ª instância em 24/04/2018 (MPDFT 2018).

#### Minerworld (Campo Grande/MS, Cícero Saad Cruz; depois Jonhnes Carvalho)
- **Início e fachada:** eventos de divulgação desde set/2016; "mineração de bitcoin" — [Wikipédia](https://pt.wikipedia.org/wiki/Minerworld); "nos últimos dois anos" em jan/2018 — [Correio do Estado, 15/01/2018](https://www.correiodoestado.com.br/cidades/campo-grande/suspeita-de-piramide-empresa-de-bitcoins-atrasa-pagamentos/319493/)
- **Retorno:** dobrar em 12 meses (Correio do Estado) ou "100% em 12 meses" (Wikipédia). Conversão: 5,95% a.m. composto; 8,3% simples.
- **Estrutura:**
  - Planos de US$ 30 a 1.000 (Wikipédia).
  - Pagava em reais até dez/2017; depois só em BTC, pela plataforma da empresa e com taxa (Correio do Estado, 15/01/2018).
  - Indicação, níveis e carência: não verificados.
- **Pico:** 70 mil afiliados em jan/2018 (Correio do Estado). Mais de 120 mil segundo a empresa e mais de 50 mil lesados segundo a acusação — [InfoMoney](https://www.infomoney.com.br/mercados/justica-brasileira-bloqueia-r-300-milhoes-de-envolvidos-em-esquema-de-piramide-com-criptomoedas/)
- **1º alerta público:**
  - Denúncia da CNV do Paraguai em mai/2017 (Wikipédia).
  - Primeira matéria crítica achada em 15/01/2018 (Correio do Estado), quando o estresse já tinha começado.
- **Estresse:**
  - out/2017: atrasos de até 40 dias (Wikipédia).
  - 29/10/2017: a empresa diz ter "descoberto" um hack na conta da Poloniex, com cerca de US$ 5 mi — [Correio do Estado, 04/12/2018](https://www.correiodoestado.com.br/cidades/investigada-por-esquema-milionario-minerworld-alega-nao-ter-saldo-a/342358/)
  - nov/2017: token próprio MCash e troca de CEO (InfoMoney).
  - dez/2017: saque só em BTC e com taxa; a empresa culpa "plataformas de trader" no exterior (Correio do Estado, 15/01/2018).
  - Data não confirmada: proposta de pagar em 24 meses em BTC, ou antecipado em MCash ([BehindMLM](https://behindmlm.com/companies/minerworld-under-criminal-investigation-in-brazil), trecho de busca).
- **Parada e intervenção:**
  - Parou de pagar em out–dez/2017: "desde outubro" segundo o BehindMLM, dez/2017 segundo o Correio do Estado.
  - Operação Lucro Fácil (Gaeco/MPMS) em 17/04/2018 e bloqueio de R$ 300 mi em mai/2018 (InfoMoney).
  - Máquinas desligadas em jan/2019 (Wikipédia).
- **Duração:** 13–15 meses até P; 19 até I. Estresse → P: 0–2 meses; estresse → I: 6.
- **Gatilho:** (b) falta de dinheiro novo. O calote veio seis meses antes da operação.
- **BTC:**
  - Em out–dez/2017 o BTC batia recorde: var. 6m de +365% (out) e +468% (dez).
  - Em abr/2018, mês da operação, o MDD da janela era −66,3%.
  - Fonte: [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** culpou hack e exchange e ofereceu MCash e parcelamento. Em dez/2018 alegou não ter saldo para depósito judicial (Correio do Estado, 04/12/2018). Não fugiu.

#### Trade Coin Club (Douver Torres Braga; rede com forte base brasileira)
- **Início e fachada:** dez/2016; "software" de trading de bitcoin com "milhões de microtransações" — [IRS-CI/DOJ](https://www.irs.gov/compliance/criminal-investigation/brazilian-extradited-from-switzerland-to-the-united-states-to-face-indictment-charging-involvement-in-290m-plus-cryptocurrency-fraud-scheme); [SEC 2022-201](https://www.sec.gov/news/press-release/2022-201)
- **Retorno:** mínimo de 0,35% ao dia (SEC), ou 11,1% a.m. composto, coerente com os "11% ao mês" — [InfoMoney](https://www.infomoney.com.br/onde-investir/golpe-de-r-7-bi-com-robo-milagroso-da-atlas-quantum-e-alvo-da-cpi-das-piramides/)
- **Estrutura:** MLM com rede mundial de promotores; depósitos e saques em BTC (IRS/SEC). Obrigatoriedade de recrutar e níveis: não encontrado.
- **Pico:** 126 mil membros alegados; mais de 82 mil BTC, cerca de US$ 290–295 mi (IRS). Pico provável em 2017 (inferência).
- **1º alerta público:** nenhum alerta brasileiro achado. Nos EUA, ação civil da SEC em nov/2022 — [SEC LR-25571](https://www.sec.gov/litigation/litreleases/lr-25571)
- **Estresse:**
  - Fim de 2017: dificuldade de saque e token de saída "TCoin" ([BehindMLM](https://behindmlm.com/companies/tccs-douver-braga-arrested-in-switzerland-extradited-to-us), trecho de busca).
  - jan/2018: encerra operações nos EUA e cancela contas (IRS).
- **Parada e intervenção:**
  - Parou entre o início de 2018 e mai/2018 (IRS).
  - Indictment em out/2022, sigiloso. Prisão na Suíça em fev/2025 e audiência em Seattle em 21/02/2025 (IRS).
  - Operação Fantasos (PF) em 30/04/2025 — [Diário do Comércio](https://diariodocomercio.com.br/financas/pf-operacao-fbi-contra-fraude-internacional-criptomoedas/)
- **Duração:** 13–17 meses. Estresse → P: cerca de 2–5 meses. P → I no Brasil: cerca de 7 anos.
- **Gatilho:** (b) falta de dinheiro novo, com (d) saída planejada pelo operador (TCoin, cancelamento de contas).
- **BTC:** jan/2018 com MDD −49,3% do ATH de 16/12/2017; mai/2018 com var. 6m −25,2% e MDD −66,3% — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d). O estresse começou no topo; a parada ocorreu já na queda.
- **Operador no fim:** recebeu pelo menos US$ 50 mi entre dez/2016 e jul/2019 (IRS), ou seja, o dinheiro seguiu chegando depois do colapso. Lançou o TCoin.

#### InDeal Consultoria (Novo Hamburgo/RS)
- **Início e fachada:** out/2017 segundo a CVM, com dados da Receita — [relatório de PAS da CVM, dez/2023](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2023/20231211_PAS_CVM_19957_001124_2021_74_relatorio_diretor_joao_accioly.pdf). ago/2017 segundo o [TRF4](https://www.trf4.jus.br/trf4/controlador.php?acao=noticia_visualizar&id_noticia=27879) (**divergência**). Fachada: gestão de compra e venda de criptoativos; só comprou BTC em fev/2019 (TRF4).
- **Retorno:** "ganho de capital de 15% no prazo de um mês" (contrato, PAS CVM), ou 15% a.m.
- **Estrutura:**
  - Consultores, WhatsApp e reuniões; contrato de ciclo mensal (PAS CVM).
  - Bônus e níveis: não encontrados.
- **Pico:** pelo menos R$ 1,069 bi entre out/2017 e 21/05/2019 (PAS CVM). Clientes: 38.157 segundo o TRF4; 23.277 lesados segundo o [ABC+](https://www.abcmais.com/policia/caso-indeal-saiba-quantos-milhoes-serao-devolvidos-aos-232-mil-clientes-lesados-pela-empresa-de-novo-hamburgo/). Ainda captava em mai/2019.
- **1º alerta público:**
  - Reportagem do Grupo Sinos cerca de 3 meses antes da operação (~fev/2019) — [ABC+](https://www.abcmais.com/policia/caso-indeal-15-reus-sao-condenados-a-penas-que-somam-mais-de-200-anos-de-prisao-veja-o-que-decidiu-a-justica-federal/)
  - Processo na CVM em 2018, sem stop order público (PAS CVM).
- **Estresse:** só interno. Segundo o relatório da PF transcrito pela CVM, em 08/05/2019 um sócio dizia faltar R$ 5 mi "a ser captado para honrar com os pagamentos" (PAS CVM). Atraso público: não encontrado.
- **Parada e intervenção:** pagava, ao que tudo indica, até a Operação Egypto (PF), em 21/05/2019 (PAS CVM) — [TecMundo](https://www.tecmundo.com.br/seguranca/141543-pf-investiga-piramide-criptomoedas-levantou-r-700-milhoes.htm)
- **Duração:** 19 meses (out/2017) ou 21 (ago/2017). Estresse interno → I: 13 dias.
- **Gatilho:** (a) intervenção do Estado, com o caixa já dependente de dinheiro novo.
- **BTC (mai/2019):** var. 6m +115,3%. O MDD da janela, −51,0%, vem do crash de nov–dez/2018. Fechamento −56,4% do ATH — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** sócios presos na operação; depois veio a falência — [Lex](https://www.lex.com.br/nota-de-decretacao-de-falencia-da-empresa-indeal/) (data não obtida).

#### Grupo Bitcoin Banco (Curitiba/PR, Cláudio José de Oliveira; NegocieCoins, TemBTC)
- **Início e fachada:** início não confirmado. Fachada de exchanges próprias e "arbitragem" entre elas; a NegocieCoins reportou volume de US$ 900 mi em abr/2019 — [InfoMoney](https://www.infomoney.com.br/onde-investir/rei-do-bitcoin-tem-bens-bloqueados-e-escancara-crise-do-grupo-bitcoin-banco/)
- **Retorno:** aplicações de 3% em 90 dias e 6% em 180 dias, cerca de 1% a.m. Isso veio de trecho de busca, de fonte provável [Finsiders](https://finsidersbrasil.com.br/?p=110416). Pode ser a oferta posterior ao bloqueio. O % da arbitragem original não foi encontrado.
- **Estrutura:** depois do bloqueio ofereceu o token próprio Br2Ex, com saque de até R$ 30 mil (InfoMoney). Indicação: não encontrada.
- **Pico:** 1º semestre de 2019. Dívida de R$ 2,1 bi segundo consultoria — [Suno](https://www.suno.com.br/noticias/?p=51620); R$ 1,5 bi segundo a PF.
- **1º alerta público:** o próprio anúncio de "fraude" pelo GBB, em mai/2019. Imprensa crítica em 12/08/2019, com cerca de 200 ações — [Canaltech](https://canaltech.com.br/criptomoedas/clientes-processam-empresa-paranaense-de-bitcoins-por-sumico-de-dinheiro-146475/). Stop order da CVM: não encontrado.
- **Estresse:**
  - Início de 2019: saques começam a ser barrados ([Decrypt](https://decrypt.co/75275/brazilian-king-bitcoin-busted-alleged-300-million-fraud), trecho de busca).
  - mai/2019: alega cerca de R$ 50 mi em "saques indevidos", suspende retiradas e congela contas (InfoMoney). Outras matérias falam em ataque hacker — [InfoMoney](https://www.infomoney.com.br/?p=1355525)
- **Parada e intervenção:**
  - Parou em mai/2019.
  - Recuperação judicial pedida em nov/2019 e aceita no fim do mês — [Finsiders](https://finsidersbrasil.com.br/noticias-sobre-fintechs/bitcoin-banco-a-historia-da-falsa-empresa-que-foi-da-ostentacao-a-falencia/)
  - Operação Daemon (PF) em 05/07/2021 e falência em 07/07/2021 — [Livecoins](https://livecoins.com.br/bitcoin-banco-tem-falencia-decretada-pela-justica/)
- **Duração:** não calculável (início desconhecido). Estresse → P: 0–4 meses. P → I: 26 meses.
- **Gatilho:** (b) falta de dinheiro, com culpa em "hacker" ou "saques indevidos". A parada foi decidida pela própria empresa, sem ação estatal antes.
- **BTC:**
  - O estresse do início de 2019 coincide com o fundo do bear market: jan/2019 com var. 6m −55,9% e −82,6% do ATH.
  - Em mai/2019 o BTC já subia: var. 6m +115,3%.
  - Fonte: [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** RJ usada como blindagem, segundo a juíza da falência. Ofereceu acordos e o token Br2Ex. Houve relatos de passagem comprada para a Suíça em 21/08/2019 (InfoMoney). Foi preso em 2021.

#### FX Trading Corporation (Philip Han, "Global Master"; endereço em Nova Iguaçu/RJ)
- **Início e fachada:** início não encontrado. Forex com marketing multinível — [Monitor Mercantil, 20/05/2019](https://monitormercantil.com.br/cvm-suspende-atuacao-por-irregularidade-da-fx-trading-corporation/)
- **Retorno:** até 2,5% ao dia, ou "100% em 3 meses / 400% em 12 meses" — [Livecoins](https://livecoins.com.br/fx-trading-investigada-golpe-bilhao-com-bitcoin/); [Cointimes](https://cointimes.com.br/fx-trading-corp-outra-piramide/). Conversão: 2,5% ao dia dá 75% a.m. simples e 109,8% composto; 100% em 3 meses dá 26,0% a.m.; ×5 em 12 meses dá 14,4% a.m.
- **Estrutura:** multinível com bônus de 10%, cortado para 8%; "teto de ganho" rebaixado; saque diário que virou mensal — [Suno, 28/06/2019](https://www.suno.com.br/noticias/fx-trading-anuncia-encerramento-de-suas-atividades/)
- **Pico:** suspeita de cerca de R$ 1 bi (Livecoins). Clientes e mês do pico: não encontrados.
- **1º alerta público:** Ato Declaratório CVM 17.142, noticiado em 20/05/2019, com multa de R$ 1.000 por dia (Monitor Mercantil).
- **Estresse:** saque diário vira mensal "nos últimos meses" antes de jun/2019. Desculpa: "as exchanges terceirizadas não suportam o volume", somada a "exigências regulatórias" (Suno, 28/06/2019).
- **Parada e intervenção:** a maioria das reclamações antes de jun/2019 já relatava "impossibilidade de sacar". Philip Han anunciou o encerramento do multinível para 07/07/2019 (Suno). Operação policial: não encontrada.
- **Duração:** não calculável. Stop order → encerramento: cerca de 1,5 mês.
- **Gatilho:** (a) stop order da CVM sobre um esquema já em (b).
- **BTC:** mai–jul/2019 com var. 6m de +115% a +195% — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** culpou exchanges e regulação e anunciou o encerramento.

#### Atlas Quantum (São Paulo/SP, Rodrigo Marques dos Santos)
- **Início e fachada:** robô de arbitragem de BTC ("Quantum").
  - **Divergência sobre o início:** mai/2018 segundo a [InfoMoney](https://www.infomoney.com.br/onde-investir/golpe-de-r-7-bi-com-robo-milagroso-da-atlas-quantum-e-alvo-da-cpi-das-piramides/); 2017 segundo a [CNN Brasil](https://www.cnnbrasil.com.br/economia/macroeconomia/investigada-por-fraude-empresa-bloqueia-mais-de-r-4-bi-em-bitcoins-de-clientes/), que cita investigação da CVM nesse ano.
  - O vazamento de 25/08/2018, com 264.189 cadastros, torna 2017 mais plausível — [Tecnoblog](https://tecnoblog.net/257328/vazamento-dados-atlas-quantum-fintech-bitcoin/)
- **Retorno:** "3–7% a month (~60% a year)" — [Decrypt, 12/10/2019](https://decrypt.co/10269/is-brazils-most-ambitious-crypto-company-on-the-ropes). 60% ao ano equivale a 4,0% a.m. composto.
- **Estrutura:** vendido como investimento passivo, sem exigência de recrutar documentada. Saldos em BTC; a partir de 2020 o token próprio BTCQ, sem paridade — [InfoMoney, 19/08/2021](https://www.infomoney.com.br/?p=1683301)
- **Pico:** meados de 2019 (inferência). A Grant Thornton atestou 15.226,1 BTC mais 34,8 mi em "crypto dollars" em ago/2019 (InfoMoney). Clientes: de 22 mil a 264 mil, conforme a fonte.
- **1º alerta público:** Deliberação CVM 826, de 13/08/2019 — [Livecoins](https://livecoins.com.br/cvm-proibe-atlas-quantum-investimento-em-bitcoin/)
- **Estresse:**
  - ago/2019: saques travados; a empresa alega "volume atípico" nas exchanges — [Tecnoblog](https://tecnoblog.net/311165/atlas-quantum-arbitragem-bitcoin-saques-bloqueados/)
  - Fim de set/2019: só metade dos 15 mil pedidos de saque foi paga; HitBTC e Gate.io negam ter contas da Atlas (Decrypt).
  - 20–30/01/2020: "migração de plataforma", com o sistema fora do ar cerca de 10 dias e os saldos convertidos em "Saldo Migrado" — [Suno, 30/01/2020](https://www.suno.com.br/noticias/atlas-quantum-sistema-fora-do-ar-10-dias/)
  - 2020: token BTCQ.
- **Parada e intervenção:** parada ampla em ago–set/2019 e total em jan/2020. Nenhuma operação policial nem falência. Multa da CVM em 22/05/2024 — [Livecoins](https://livecoins.com.br/cvm-multa-atlas-quantum-e-rodrigo-marques-em-r-55-milhoes/)
- **Duração:** 15–31 meses (início em mai/2018 ou em 2017). Estresse → P: 0–1 mês.
- **Gatilho:** (a) stop order que disparou (b) uma corrida de saques. A própria Atlas atribui a "onda de saques" ao stop order (InfoMoney 2021).
- **BTC (ago/2019):** var. 6m +153,2%; MDD da janela −26,6% (26/06→27/07/2019) — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** em 11/08/2021 processou a CVM pedindo R$ 3,167 bi (InfoMoney 2021). Vive no exterior (México e Espanha), sem mandado de prisão.

#### Unick Forex (São Leopoldo/RS, Leidimar Lopes)
- **Início e fachada:** início até 17/11/2017, data da primeira denúncia à CVM ("site capitando recursos prometendo lucro com forex"). Produtos: forex, "lotes de participação" e apostas, depois "material educativo" com MLM — [PAS CVM 19957.000238/2019-82, 08/12/2020](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2020/20201208_PAS_CVM_SEI_19957_000238_2019_82_relatorio_presidente_marcelo_barbosa.pdf-1636b454537947559d2cae64f17de17f)
- **Retorno:** "100% sobre o valor investido, em um prazo de apenas seis meses", segundo a PF — [Suno, 17/10/2019](https://www.suno.com.br/noticias/unick-forex-pf-operacao-rs/). Equivale a 12,25% a.m. composto. A CVM fala em "até 3% ao dia".
- **Estrutura:** bônus e prêmios por indicação, que variavam com o número de indicados e o valor (PAS CVM). Obrigatoriedade e níveis: não encontrados.
- **Pico:** até R$ 40 mi captados por dia (PF/Suno); 1 a 1,5 milhão de clientes. Até jun/2019 a nota no Reclame Aqui ainda era "ótimo" — [Suno, 03/09/2019](https://www.suno.com.br/noticias/reclamacoes-unick-forex-triplicam-dois-meses/)
- **1º alerta público:** stop order por Ato Declaratório CVM 16.169, de 19/03/2018 e publicado em 21/03/2018, com multa de R$ 1.000 por dia (PAS CVM). Ignorado. Novo alerta em 25/04/2019 — [MoneyTimes](https://moneytimes.com.br/cvm-reforca-alerta-e-abre-processo-contra-atuacao-irregular-da-unick/). (Corrige a nota anterior, que punha o stop order em 2019.)
- **Estresse:**
  - 22/06/2019: primeiro relato de saque pedido e não pago — [Suno, 01/08/2019](https://www.suno.com.br/noticias/unick-forex-150-reclamacoes-24h-problemas-saque/)
  - 29–30/07/2019: mais de 150 reclamações em 24 horas no Reclame Aqui (Suno, 01/08/2019).
  - ago/2019: "manutenção" de 10 dias que congelou pagamentos, bônus e cadastros, com lista de CPFs bloqueados — [Guia do Investidor, 19/08/2019](https://guiadoinvestidor.com.br/noticias/unick-forex-possui-5-mil-reclamacoes-registradas/)
  - 16/08/2019: saque passa a mensal, só para quem não tinha sacado o principal. Reclamações sobem de 3.651 para 9.929 (Suno, 03/09/2019).
  - 03/10/2019: só devolveria por acordo extrajudicial, "sem prazo"; nota assinada em Belize — [Suno, 03/10/2019](https://www.suno.com.br/noticias/unick-forex-contrata-escritorio-negociar-clientes/)
- **Parada e intervenção:** parada de fato em ago/2019 e formal em 03/10/2019. Operação Lamanai (PF) em 17/10/2019 (Suno).
- **Duração:** pelo menos 21 meses até P (nov/2017→ago/2019) e 23 até I. Estresse → P: cerca de 2 meses; estresse → I: cerca de 4. Stop order → P: cerca de 17 meses.
- **Gatilho:** (b) corrida de saques e falta de dinheiro novo.
- **BTC:**
  - O 1º estresse (22/06/2019) coincide com o topo local de 26/06/2019 (12.863).
  - Em ago/2019 a var. 6m era +153,2% e o MDD da janela −26,6%. Em out/2019, var. 6m +73,8% e MDD −42,1%.
  - Fonte: [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:**
  - Sede declarada em Belize e acordos extrajudiciais.
  - Ex-líderes migraram para a Moguro Club, outro esquema com promessa de rentabilidade em bitcoin — [Suno, 28/10/2019](https://www.suno.com.br/noticias/antigos-lideres-unick-forex-envolvidos-em-nova-piramide/)
  - Em ago/2021, Leidimar estava "em lugar incerto e não sabido" — [Livecoins](https://livecoins.com.br/leidimar-lopes-desaparecido-sp-unick-forex/)

#### 18kRonaldinho (18k Watch Corporation; Marcelo Lara Marcelino, Raphael Horácio Nunes de Oliveira e outros)
- **Início e fachada:** em 2019 a marca de relógios abriu um canal de trading e cripto "com remuneração multinível" — [Suno](https://www.suno.com.br/noticias/ronaldinho-pagar-r-300-mi-piramide/amp/)
- **Retorno (divergência):** 2% ao dia, cerca de 400% ao ano (Suno); até 0,99% ao dia ([BehindMLM](https://behindmlm.com/companies/18k-ronaldinho-ponzi-collapses-investors-sue), trecho de busca). Conversão: 2% ao dia dá 60% a.m. simples e 81,1% composto; 0,99% ao dia dá 34,4% composto; ×5 ao ano dá 14,4% a.m.
- **Estrutura:** bônus de 7% sobre o pacote por indicação; o plano mais alto dava "80 relógios e jantar com Ronaldinho" (Suno).
- **Pico:** não encontrado. Ação coletiva de cerca de 150 vítimas pedindo R$ 300 mi — [Livecoins](https://livecoins.com.br/ronaldinho-gaucho-vira-reu-em-acao-coletiva-contra-18k/)
- **1º alerta público:** ação do Ibedec, com Ronaldinho réu na ação cível em fev/2020 (Livecoins).
- **Estresse e parada:** bloqueio de dinheiro dos clientes "desde 2019" (Ibedec, via Suno). Mês exato: não confirmado. A nota anterior falava em out/2019, sem fonte específica.
- **Intervenção:** nenhuma estatal localizada; só a ação cível e a CPI (31/08/2023).
- **Duração:** menos de 12 meses (2019→2019).
- **Gatilho:** (b), por inferência.
- **BTC (out/2019, se confirmado):** var. 6m +73,8%; MDD da janela −42,1% — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** não encontrado.

#### BWA Brasil (SP, Paulo Roberto Ramos Bilibio)
- **Início e fachada:** fundada em 2017, com exposição a BTC — [CryptoSlate](https://cryptoslate.com/brazilian-judge-allows-nft-subpoenas-to-bitcoin-wallets-in-high-profile-fraud-case/)
- **Retorno (divergência):** 10% a.m. segundo o [Livecoins](https://livecoins.com.br/justica-aceita-pedido-de-recuperacao-judicial-da-bwa-brasil-suspeita-de-golpe-com-bitcoin/); 5% fixos a.m. segundo o CryptoSlate.
- **Estrutura:** cresceu por indicação de amigos — [Olhar Digital, 18/07/2020](https://olhardigital.com.br/2020/07/18/seguranca/suspeita-de-piramide-empresa-de-bitcoins-some-com-r-300-milhoes-de-clientes/). Mais de 50% dos negócios passavam pelo Bitcoin Banco — [Suno](https://www.suno.com.br/noticias/plataforma-criptomoedas-bwa-recuperacao-judicial/amp/)
- **Pico:** cerca de 2.000 clientes (Suno); 1.897 credores e R$ 295,4 mi — [CoinTelegraph Brasil](https://br.cointelegraph.com/news/bwa-brasil-asks-for-judicial-recovery-with-debt-of-r-295-million-with-clients)
- **1º alerta público:** imprensa e RJ em jul/2020 (Olhar Digital).
- **Parada:** fim de 2019 segundo a Suno; início de 2020 segundo o CryptoSlate.
- **Intervenção:**
  - RJ deferida em 08/07/2020 (Suno).
  - O administrador opinou pela falência — [Suno](https://www.suno.com.br/noticias/?p=72565)
  - Falência "menos de um ano depois" (CryptoSlate). O mês abr/2021 veio só de trecho de busca.
- **Duração:** cerca de 24–36 meses.
- **Gatilho:** (b), provavelmente por contágio do GBB (inferência a partir da dependência de mais de 50%).
- **BTC (dez/2019):** var. 6m −33,9%; MDD da janela −48,6% (26/06→17/12/2019) — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** pediu RJ. Bilibio é acusado de usar o dinheiro retido para comprar BTC. Em 2025 o juízo autorizou notificar carteiras por NFT (CryptoSlate).

#### Casos menores com datas úteis
- **VIK Traders (DF/nacional):**
  - Robôs de trading com até 3% ao dia (142,7% a.m. composto) e bônus por convidar pessoas.
  - Saques bloqueados em ago/2019. Desculpas: "atualização do sistema", "fraudes realizadas por líderes brasileiros", o ex-CEO e "desvalorização" das criptomoedas.
  - Depois prometeu retomar pagamentos "por ordem de chegada" com teto de US$ 100.
  - Fonte: [Metrópoles, 09/12/2019](https://www.metropoles.com/distrito-federal/df-investidores-expoem-piramide-financeira-em-empresa-de-bitcoin)
  - BTC em ago/2019: var. 6m +153% (cálculo próprio).
- **Alcateia Investimentos (SC):**
  - Aporte em set/2017; pequenos saques no começo.
  - No fim do contrato, em jan/2018, apareceu "limite de saque diário excedido, tente novamente no próximo dia útil".
  - A empresa alegou problemas operacionais e simulou venda a outra empresa (Máximus).
  - Fonte: [Exame, 13/09/2019](https://exame.com/invest/minhas-financas/piramides-de-bitcoin-perda-pode-acabar-com-economias-saiba-evitar/)
- **Fora do escopo:**
  - D9 Clube de Empreendedores (fachada de apostas esportivas) — [InfoMoney](https://www.infomoney.com.br/?p=417020)
  - MMM Brasil ("ajuda mútua"). O braço bitcoin que colapsou em 2016 é documentado para a MMM Global e a da África do Sul, não para a brasileira — [IOL, 13/04/2016](https://iol.co.za/news/south-africa/western-cape/2016-04-13-ponzi-mmm-still-strong-after-bitcoin-collapse/)

### Inferences
- Nenhum esquema desta onda quebrou por causa do crash de 2018 de forma clara. A Minerworld e o TCC entraram em estresse em out–dez/2017, no auge do BTC. A Minerworld chegou a converter o pagamento para BTC justamente quando o BTC estava mais caro.
- O cluster de meados de 2019 (Unick, Atlas, FX, VIK, 18k) ocorreu com o BTC subindo mais de 100% em 6 meses. Ele coincide com ações de órgãos: alertas e stop orders da CVM (Unick em abr/2019, FX em mai/2019, Atlas em ago/2019) e a Operação Egypto. A explicação mais plausível é que a coorte captada em 2017–2018 chegou ao fim dos contratos ao mesmo tempo, somada à pressão regulatória. O preço não explica.
- Hipótese a testar, com poucos pontos: nos esquemas com passivo em BTC (TCC, Atlas, depois Trust), uma alta forte do BTC aumenta em reais o valor que os clientes podem sacar. Se o operador desviou ou trocou os BTC por reais, a alta piora a solvência. TCC (fim de 2017) e Atlas (ago/2019) entraram em estresse logo depois de altas de mais de 150%.

### Gaps
- Início do GBB e da FX Trading; mês exato do bloqueio da 18k; data do pedido de RJ da BWA; URL da falência da BWA.
- Mês das restrições de saque na Kriptacoin; data em que a InDeal parou de pagar (se é que parou antes da operação).
- Data exata da conversão para BTCQ com desconto de 99,9% na Atlas.

---

## 3. Fichas de ciclo de vida: segunda onda (captação 2015–2021, colapsos 2021–2023)

### Takeaway
A segunda onda inclui o esquema mais longo da amostra: a GAS, com cerca de 70 meses, que pagou em dia durante a queda de 53% do BTC em 2021 e só parou três semanas depois da Operação Kryptos. Outros três esquemas grandes (Rental Coins, Trust, MSK) pararam de pagar no mesmo mês, nov–dez/2021, cerca de 10 a 12 meses antes de qualquer intervenção. Foi logo depois do topo histórico do BTC (08/11/2021), meses depois da Kryptos e na semana da aprovação do PL 2.303/15 na Câmara. A Braiscompany quebrou em dez/2022, no fundo do inverno cripto e logo depois da FTX, e é o caso que mais se aproxima de "choque de mercado".

### Cited Findings

#### GAS Consultoria Bitcoin (Cabo Frio/RJ, Glaidson Acácio dos Santos e Mirelis Diaz Zerpa)
- **Início e fachada:** movimentação de 03/11/2015 a 20/05/2021 segundo o RIF citado na denúncia. O contrato mudou de nome: "contrato de investimento" (2017), "prestação de serviços para investimento em bitcoins" (2018), "terceirização de trader de criptoativo" (2019–2021) — [relatório da CVM, PAS 19957.002835/2022-47](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2023/20230829_pas_cvm_19957_002835_2022_47_presidente_cvm_joao_pedro_nascimento_relatorio.pdf)
- **Retorno:** "percentual bruto de 10% sobre o valor investido" pago "todo dia 14 do mês subsequente", por 12 meses, com o capital devolvido no fim e nota promissória (relatório da CVM). Ou seja, 10% a.m.
- **Estrutura:**
  - Consultores e "associados" comissionados; um operador captou "centenas de clientes" — [relatório final da CPI das Pirâmides, p. 99](https://www2.camara.leg.br/atividade-legislativa/comissoes/comissoes-temporarias/parlamentar-de-inquerito/57a-legislatura/piramides-financeiras/outros-documentos/relatorio-cpi)
  - Capital travado até o fim do contrato.
  - Recrutar não era obrigatório (cliente comum só aplicava).
- **Pico:**
  - R$ 38,2 bi movimentados (CPI p. 32).
  - 127.628 clientes no cadastro de credores, declarando R$ 9,9 bi — [Folha PE](https://www.folhape.com.br/noticias/relatorio-da-cvm-conclui-que-operacoes-de-empresa-do-farao-dos/255996/)
  - Ainda havia depósitos em jun/2021 — [Metrópoles](https://www.metropoles.com/brasil/pf-investiga-se-empresa-de-criptomoedas-recebeu-r-17-milhao-do-trafico)
- **1º alerta público:** nenhum. A CVM recebeu denúncias em 2019. Em 12/08/2019 o caso foi para a área de ofertas, que viu "fortes indícios de (...) esquema Ponzi" mas não emitiu stop order. A CVM só agiu depois do ofício do MPF de 27/10/2021 (relatório da CVM).
- **Estresse antes da intervenção:**
  - A Foxbit encerrou a conta de Glaidson em fev/2018, por compliance (relatório da CVM).
  - A denúncia cita conversas sobre uma operadora com "problemas para pagar seus investidores", sem data clara (CPI p. 33).
  - Atraso visível para clientes antes de ago/2021: não encontrado.
- **Parada e intervenção:**
  - Operação Kryptos em 25/08/2021.
  - Pagou normalmente até 15/09/2021, quando os consultores foram avisados de que o "bloqueio judicial de R$ 38 bilhões" impedia os repasses — [Suno, 17/09/2021](https://www.suno.com.br/noticias/?p=185262). O administrador judicial usa 16/09/2021 (trecho de busca).
  - RJ pedida em mai/2022 — [Folha PE](https://www.folhape.com.br/economia/justica-antecipa-falencia-da-gas-empresa-do-farao-dos-bitcoins/258681/)
  - "Justiça antecipa falência" noticiado em 17/02/2023 — [Economic News](https://economicnewsbrasil.com.br/2023/02/17/justica-antecipa-falencia-de-empresa-do-farao-dos-bitcoins/)
  - Falência decretada em mai/2025: 16/05 segundo o [Portal Tela](https://www.portaltela.com/noticias/economia/2025/05/16/justica-do-rio-declara-falencia-da-gas-consultoria-com-divida-de-r-38-bilhoes/); 21/05 segundo o [administrador judicial](https://zveiter.com.br/gas). A relação entre a "antecipação" de 2023 e a decretação de 2025 não ficou clara.
- **Duração:** 69 meses até I (nov/2015→ago/2021) e 70 até P. Estresse → colapso: 0, porque não houve estresse visível antes da intervenção.
- **Gatilho:** (a) intervenção do Estado. O bloqueio judicial cortou os repasses.
- **BTC:**
  - Ago/2021: var. 6m +4,1%; MDD da janela −53,1% (13/04→20/07/2021); BTC a 49.002 em 25/08/2021.
  - A GAS pagou durante toda essa queda de 53%.
  - Fonte: [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:**
  - Pediu RJ.
  - O discurso aos clientes era de que receberiam quando Glaidson fosse solto (trecho de busca).
  - Em set/2026 disse ter fortuna para ressarcir 77 mil investidores — [Economic News, 07/09/2026](https://economicnewsbrasil.com.br/2026/09/07/fortuna-farao-dos-bitcoins-credores/)
  - Mirelis fugiu para os EUA (CPI p. 32).
  - A organização teria criado uma exchange para evitar bloqueios depois da 1ª operação — [Tecnoblog](https://tecnoblog.net/noticias/pf-faz-nova-operacao-sobre-farao-dos-bitcoins-e-prende-dona-de-corretora/) (trecho de busca).

#### Rental Coins / Grupo InterAG (Curitiba/PR, Francisley Valdevino da Silva)
- **Início e fachada:** 2019 segundo a CPI (p. 99) e a [Suno, 10/08/2022](https://www.suno.com.br/noticias/?p=283548); "desde 2016" segundo a PF, via [InfoMoney, 26/10/2022](https://www.infomoney.com.br/?p=1966026) (**divergência**). Contrato de "cessão temporária de uso de protocolos digitais", isto é, aluguel de cripto (CPI).
- **Retorno:** 13,5% a.m. (Suno) ou 20% a.m. (PF, via InfoMoney).
- **Estrutura:** recrutamento, bônus, lock-up e moeda de pagamento não encontrados.
- **Pico:** pelo menos 9 mil clientes afetados (Suno). Cerca de 15 mil vítimas e mais de R$ 4 bi movimentados — [InfoMoney](https://www.infomoney.com.br/?p=2629485)
- **1º alerta público:** não encontrado nenhum antes de 2022, nem stop order da CVM.
- **Estresse:** atrasos a partir de out/2021 (trecho de busca); parada "desde dezembro" de 2021 (Suno). Em 2022 Francisley pediu gratuidade de justiça alegando pobreza, apesar de ter mais de 130 empresas (Suno).
- **Parada e intervenção:**
  - Parou em dez/2021.
  - Falência pedida por um credor de R$ 66 mil e decretada em 25/10/2022 (InfoMoney).
  - Operação Poyais (PF com autoridades dos EUA) em out/2022 — [InfoMoney](https://www.infomoney.com.br/mercados/pf-mira-sheik-das-criptomoedas-em-nova-operacao-esquema-movimentou-r-4-bi-no-brasil-e-no-exterior/)
- **Duração:** 24–35 meses (início em 2019); até cerca de 70 se o início foi em 2016. Estresse → P: cerca de 2 meses. P → I: cerca de 10 meses.
- **Gatilho:** (b) falta de dinheiro novo.
- **BTC (dez/2021):** var. 6m +32,2%; −31,4% do ATH de 08/11/2021 (67.542). Em out/2021, mês do 1º atraso, o BTC estava 7% abaixo do ATH — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:** silêncio na CPI e ataques aos "acusadores de Curitiba" (CPI p. 100). Preso em 2022, solto em jun/2023 e preso de novo em ago/2024 (InfoMoney).

#### Trust Investing (Patrick Abrahão, "Number One", e outros)
- **Início e fachada:** 2019, segundo a PF (CPI p. 145). Patrick diz ter entrado quando a empresa tinha 3 meses e 3.800 pessoas (CPI p. 150). Trading e arbitragem de cripto, sede declarada na Estônia ([Blocktrends](https://blocktrends.com.br/?p=80810), trecho de busca).
- **Retorno:** 0,1% a 5% ao dia, até 500% ao ano — [Campo Grande News](https://www.campograndenews.com.br/brasil/cidades/number-one-pastor-e-mais-4-sao-condenados-em-esquema-bilionario-de-piramide). Conversão: de 3,0% a 332% a.m. composto (de 3% a 150% simples); ×6 ao ano dá 16,1% a.m.
- **Estrutura:**
  - MLM com "team leaders"; Patrick era o maior captador (CPI p. 157).
  - Entrada e saída em cripto.
  - Duas criptomoedas próprias, entre elas a TrusterCoin, "para alongar a pirâmide", que perderam todo o valor (CPI p. 145).
- **Pico:** 1,3 milhão de pessoas em 80 países e prejuízo de cerca de R$ 4,1 bi (PF, na CPI) — [Campo Grande News](https://www.campograndenews.com.br/cidades/capital/justica-ouve-o-cabeca-de-grupo-suspeito-de-enganar-1-3-milhao-em-piramide)
- **1º alerta público:** nenhum brasileiro encontrado antes de 2022.
- **Estresse:**
  - 2021: restrições a saques em USDT entre o anúncio e o lançamento do TrusterCoin.
  - nov/2021: limite de 35 mil USDT por semana (BehindMLM, trecho de busca).
  - Fim de 2021: site em "manutenção para instalar blockchain" (Blocktrends).
  - "Hack" de US$ 800 mi com "auditoria" de 90 dias e pagamentos suspensos; a sentença considerou o ataque forjado (Campo Grande News).
- **Parada e intervenção:** parou em nov–dez/2021. Operação La Casa de Papel (PF) em 19/10/2022 — [Livecoins](https://livecoins.com.br/trust-investing-chega-ao-fim-e-marido-da-cantora-perlla-e-preso-no-rio/)
- **Duração:** cerca de 24–35 meses. Estresse → P: até cerca de 6 meses (datas imprecisas). P → I: cerca de 10–11 meses.
- **Gatilho:** (b) corrida de saques e falta de dinheiro novo.
- **BTC (nov–dez/2021):** topo histórico em 08/11/2021 e −31,4% até o fim de dezembro; var. 6m positiva (+53,0% em nov; +32,2% em dez) — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:**
  - Narrativa de hacker e auditoria.
  - Novos produtos: Trust Diamond, Wine, Travel, Solar e Recycle (CPI p. 146).
  - Patrick abriu a Actyon Crypto "para a continuação da pirâmide" (CPI p. 157).

#### MSK Investimentos (Santana de Parnaíba/SP)
- **Início e fachada:** 2016; até 5% a.m. fixos com cripto (CPI p. 157).
- **Pico:** de 3,5 mil a 4 mil clientes e cerca de R$ 700 mi. Mais de US$ 1 bi captado, segundo o indiciamento (CPI p. 158–159).
- **Estresse e parada:** parou em dez/2021, culpando a aprovação do PL 2.303/15 na Câmara — [Tecnoblog, 22/12/2021](https://tecnoblog.net/noticias/2021/12/22/firma-de-criptomoedas-acusada-de-golpe-de-r-700-mi-e-alvo-do-procon-sp/) (trecho de busca). A Câmara aprovou o PL em 08/12/2021 — [Bloomberg Línea, 10/12/2021](https://www.bloomberglinea.com.br/2021/12/10/regulamentacao-do-mercado-cripto-avanca-no-congresso/) (trecho de busca).
- **Depois da parada:**
  - Acordo com o Procon-SP em jan/2022, descumprido.
  - Mais de 500 pessoas acusando golpe em fev/2022 — [Bloomberg Línea, 21/02/2022](https://www.bloomberglinea.com.br/2022/02/21/piramide-cripto-mais-de-500-acusam-golpe-que-vira-caso-de-policia-em-sp/)
  - RJ em abr/2022.
  - Indiciamento pela Polícia Civil de SP em 28/12/2022, que tratou a RJ como "artifício para ganhar tempo". O Mercado Bitcoin já tinha encerrado as contas da MSK por fraude (CPI p. 158–159).
- **Duração:** cerca de 60–71 meses. P → indiciamento: 12 meses.
- **Gatilho:** (b), com desculpa regulatória.
- **BTC (dez/2021):** igual ao da Rental e da Trust (+32,2% em 6m; −31,4% do ATH).

#### Braiscompany (Campina Grande/PB, Antônio Inácio da Silva Neto e Fabrícia Farias Campos)
- **Início e fachada:** fundada em mai/2018, com "aluguel de criptomoedas" — [InfoMoney, 11/01/2023](https://www.infomoney.com.br/?p=2028161). Os dois vinham do D9 Clube (CPI p. 248).
- **Retorno:** até 9% a.m. (InfoMoney). A faixa de 3–10% a.m. aparece em relatos de clientes — [Jornal da Paraíba](https://jornaldaparaiba.com.br/_/163550)
- **Estrutura:**
  - Contrato de 12 meses e multa de 30% na rescisão antecipada (InfoMoney).
  - Consultores obrigados a investir 30% do salário, segundo ex-funcionário (relato não verificado) — [O Antagonista](https://oantagonista.com.br/economia/antagonista-docs-exclusivo-o-escandalo-braiscompany/)
  - Obrigatoriedade de recrutar para o cliente: não encontrada.
- **Pico:** R$ 600 mi de 10 mil clientes segundo o próprio Antônio Neto (InfoMoney, jan/2023); cerca de 20 mil clientes e R$ 1,11 bi desviados segundo a PF — [ParaibaOnline](https://paraibaonline.com.br/policial/2026/05/05/fundador-da-braiscompany-reaparece-em-live-e-nega-acusacoes/). Recebeu cerca de 7.203 BTC em cinco anos — [Jornal da Paraíba](https://jornaldaparaiba.com.br/economia/entenda-polemica-com-empresa-de-criptoativos-braiscompany)
- **1º alerta público:**
  - Processo na CVM em jul/2020, não público; o MP-Procon arquivou um procedimento em 2020 (InfoMoney).
  - Exposição pública pelo ator Lucas Veloso no fim de dez/2022 (Jornal da Paraíba).
- **Estresse:**
  - Segundo a empresa, a Binance limitava transferências acima de 3–5 BTC "desde novembro" de 2022.
  - Pagamentos de 30/12/2022 não caíram.
  - Live de 09/01/2023: "só 1% dos clientes" sem receber (InfoMoney).
  - Nota de 17/01/2023 (Jornal da Paraíba).
  - Live de 07/02/2023: "novo aplicativo", e a Binance limitando a 10% do necessário a cada 10 dias (trecho de busca).
  - Em mar/2023 culpou a queda do bitcoin (Jornal da Paraíba).
- **Parada e intervenção:**
  - Atraso em 30/12/2022 e parada em jan/2023.
  - Operação Halving (PF) em 16/02/2023 — [A União](https://auniao.pb.gov.br/noticias/caderno_paraiba/braiscompany-e-alvo-de-acao-da-pf)
  - Preventiva e Interpol em 24/02/2023 (Jornal da Paraíba).
- **Duração:** 55 meses até P (mai/2018→dez/2022) e 57 até I. Estresse → P: cerca de 1–2 meses; estresse → I: cerca de 3.
- **Gatilho:** (b) falta de dinheiro novo e corrida, com (c) choque de mercado como pano de fundo (FTX, restrições da Binance, BTC −75% do ATH).
- **BTC (dez/2022):** var. 6m −14,5%; MDD da janela −49,7% (06/06→09/11/2022); −75,5% do ATH — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)
- **Operador no fim:**
  - O casal fugiu por terra para a Argentina depois de 16/02/2023 — [Itatiaia](https://www.itatiaia.com.br/mundo/braiscompany-casal-de-brasileiro-foragido-por-esquema-de-piramides-e-preso-na-argentina/)
  - Presos em 29/02/2024 — [Poder Paraíba](https://poderparaiba.com.br/dono-da-braiscompany-antonio-neto-vai-cumprir-pena-em-prisao-domiciliar-na-argentina/)
  - Em mai/2026, live dizendo que o retorno era "variável" (ParaibaOnline).

#### Fiji Solutions (Campina Grande/PB): a "nova Braiscompany"
- **Início e fachada:** fim de 2021; aluguel de cripto — [InfoMoney, 16/03/2023](https://www.infomoney.com.br/?p=2083064)
- **Retorno:** 4% a 12% a.m. (trecho de busca).
- **Pico:** cerca de R$ 420 mi em risco (InfoMoney, mar/2023) a R$ 600 mi movimentados (PF) — [InfoMoney](https://www.infomoney.com.br/onde-investir/pf-faz-operacao-contra-nova-braiscompany-suspeita-de-golpe-de-r-600-milhoes-em-cripto/)
- **Estresse e parada:** saques congelados em fev/2023; a empresa culpou um bloqueio na KuCoin ("que eu prove que eu sou eu mesmo") (InfoMoney, 16/03/2023).
- **1º alerta público:** recomendação do MP-Procon com prazo de 72 h, em 16/03/2023 (InfoMoney).
- **Intervenção:**
  - Ação civil do MPPB em 04/04/2023, com R$ 399 mi bloqueados pelo TJPB.
  - Operação Ilha da Fantasia (PF) em 15/06/2023 (InfoMoney).
- **Duração:** cerca de 14–16 meses. Estresse → P: 0. P → I (PF): cerca de 4 meses.
- **Gatilho:** (b), com culpa na exchange. A parada caiu no mesmo mês da Operação Halving contra a Braiscompany, na mesma cidade. Isso sugere fuga de dinheiro novo por contágio de confiança (inferência).
- **BTC (fev/2023):** var. 6m +15,6%; MDD da janela −35,5% (FTX) — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)

#### RCX Group (Caio Almeida Lima, foragido; Ricardo Stradiotto; Paulo Segarra desde 2020)
- **Início e fachada:** 2018; "contrato de locação" de bitcoin (CPI p. 115–118).
- **Retorno:** até 8,5% a.m. segundo o requerimento da CPI; 2–5% a.m. segundo Segarra.
- **Estrutura:** sem comissão por indicação, segundo Segarra (CPI).
- **Pico:** cerca de 1.100 clientes, 480 ativos no fim (CPI).
- **Estresse e parada:**
  - Problemas de pagamento a partir de 2022.
  - 1.165 reclamações no Reclame Aqui, com data "04/2022", provavelmente erro por 04/2023.
  - Segarra diz que a empresa parou em "4 de 2023", culpando a queda de 70% do mercado, e prometeu "migração" para um fundo "RCX Tech" que nunca aconteceu (CPI p. 117).
- **Intervenção:** não encontrada.
- **Duração:** cerca de 37–63 meses.
- **Gatilho:** (b), com (c) alegado pelo sócio.
- **BTC:** 2022 inteiro em bear market (−76,7% do topo até 09/11/2022). Em abr/2023, var. 6m +43,3% — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)

#### Grow Up Club (Campos dos Goytacazes/RJ, Gleidson Gonçalves Costa)
- **Início e fachada:** informal desde 2017, formalizada em 2019; forex, cripto, cursos e a suposta mineradora "Trading Farm" (CPI p. 255–261).
- **Retorno:**
  - Plano PLUS: até 10% a.m.
  - Plano GOLD: 1,25% por semana por 3 anos, cerca de 5,5% a.m. composto (cálculo: 1,0125^4,345 − 1).
  - "Consórcio": +25% depois de 12 parcelas (CPI).
  - Havia cláusula de fidelidade.
- **Pico:** 300 a 320 clientes, segundo o próprio Gleidson (CPI).
- **Estresse e parada:** a Trading Farm parou de pagar em 2022; uma vítima não recebeu no início de 2023 (CPI).
- **Intervenção:** pelo menos 20 inquéritos na Delegacia de Defraudações do RJ (CPI), sem operação identificada.
- **Gatilho:** (b) e (d). Uma vítima ouvida pela CPI diz que "Gleidson sumiu com meu dinheiro" (CPI p. 264–265).

#### OWS (One World Services / OWS Brasil, Campinas/SP)
- Não era pirâmide aberta ao público. Era uma mesa de cripto e market making que, segundo a CPI, serviu de canal de remessa ao exterior da GAS (R$ 851 mi) e da MSK (R$ 294 mi): remeteu US$ 535 mi entre 05/06/2019 e 06/10/2021.
- A PF fez busca no banco em 22/09/2022 e a conta foi encerrada em 13/10/2022 (CPI p. 395–403).
- Fica fora das estatísticas de duração.

### Inferences
- A GAS mostra que um Ponzi de 10% a.m. pode durar quase seis anos e atravessar uma queda de 53% do BTC sem atrasar. Isso indica que a fachada "bitcoin" não ligava o fluxo de caixa ao preço do BTC: o que sustentava era a captação local por afinidade.
- O cluster de dez/2021 (Rental, Trust, MSK) tem três explicações concorrentes que não consigo separar com os dados:
  1. o topo do BTC em 08/11/2021, seguido de queda de 31% em dezembro, que pode ter esfriado a entrada de dinheiro novo;
  2. o efeito Kryptos (ago/2021) sobre a confiança no setor;
  3. o PL 2.303/15, aprovado na Câmara em 08/12/2021 e usado como desculpa pela MSK.
- A Braiscompany é o caso em que o mercado aparece mais claramente. A própria empresa culpou a Binance e depois a queda do BTC, e o colapso se deu com o BTC 75% abaixo do topo, logo após a FTX. Mesmo aí, a CVM já tinha processo aberto desde 2020 e a exposição pública do fim de dez/2022 coincidiu com os atrasos.
- O contágio local aparece duas vezes: Fiji depois da Braiscompany, em Campina Grande, no mesmo mês; BWA depois do GBB, que concentrava mais de 50% dos seus negócios.

### Gaps
- Mês de início da Trust e da Rental (as fontes divergem entre 2016 e 2019 na Rental); dia exato da Operação Poyais.
- Data exata do pedido de RJ e da "antecipação de falência" da GAS (fev/2023) contra a decretação de mai/2025.
- Atrasos da Trust "desde maio": o ano não foi identificado.
- Grow Up e RCX: intervenção estatal não encontrada.

---

## 4. Fichas de ciclo de vida: 2023 a out/2026

### Takeaway
Depois de 2023, as pirâmides de "aluguel de cripto" com sede física (Deadcoin, Luxus) seguem o roteiro antigo: param de pagar, culpam a exchange e a intervenção vem meses depois. A Ouranós é a exceção, interrompida pela PF sem calote documentado. As falsas plataformas de 2024–2026 (TDASX, Aglobal Trade, Mirage RS) são outra espécie. Não dependem de dinheiro novo para pagar antigos e não "colapsam": liberam saques pequenos, bloqueiam os grandes cobrando "taxas" e somem ou mudam de país quando a investigação aparece. A duração relevante nelas é o ciclo por vítima, de semanas a meses.

### Cited Findings

#### Operação Ouranós (PF/SC, 28/11/2023)
- **Empresa:** não divulgada. As fontes falam numa DTVM e em mais de 50 empresas. A gestora Titanium Asset (Curitiba) aparece como investigada — [Livecoins](https://livecoins.com.br/operacao-ouranos-megaoperacao-da-pf-derruba-piramide-criptomoedas/); [Blocktrends](https://blocktrends.com.br/titanium-asset-e-investigada-por-envolvimento-com-piramide-financeira/)
- **Início e fachada:** captação desde 2020 ou antes, porque a investigação começou em 2020 — [CNN Brasil](https://www.cnnbrasil.com.br/nacional/megaoperacao-contra-piramide-financeira-bloqueia-r-400-milhoes-de-alvos-da-pf/). Contratos de investimento coletivo de "arbitragem de criptomoedas".
- **Retorno:** "remunerações fixas e variáveis"; percentual não divulgado (Livecoins).
- **Pico:** mais de R$ 1 bi de cerca de 7 mil investidores em 17 estados (CNN).
- **Estresse:** a PF descreve "blindagem patrimonial", sem data (Livecoins). Atraso de saque antes da operação: não encontrado.
- **Intervenção:** 28/11/2023, com 28 buscas, 11 cautelares e bloqueio de cerca de R$ 400 mi (473 imóveis, 10 embarcações, 1 aeronave), sem prisões — [SBT News](https://sbtnews.sbt.com.br/noticia/sbt-news/267021-aviao-473-imoveis-10-barcos-e-40-veiculos-pf-bloqueia-r-400-milhoes-em-bens-de-grupo-criminoso)
- **Duração:** pelo menos 35 meses até I.
- **Gatilho:** (a) intervenção do Estado.
- **BTC (nov/2023):** var. 6m +38,6%; MDD da janela −20,0% — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)

#### Operação Deadcoin (PF/SC, 07/11/2024, oeste de SC)
- **Empresa:** não divulgada nas fontes abertas (MPF, Livecoins, ND+, Agência Brasil).
- **Fachada e retorno:** corretora simulada com "locação de criptoativos" e "até 30% ao mês". As rentabilidades diárias eram "lançadas manualmente" no app — [MPF/SC, 07/07/2026](https://www.mpf.mp.br/o-mpf/unidades/pr-sc/noticias/mpf-recorre-para-condenar-reus-e-ampliar-reparacao-de-danos-por-piramide-financeira-com-criptoativos-no-oeste-de-sc)
- **Estrutura:**
  - Capital travado por 3 a 6 meses, com multa de até 25% no resgate antecipado — [ND+](https://ndmais.com.br/seguranca/piramide-financeira-com-criptomoedas-mpf-pode-pedir-r-91-milhoes-em-reparacao/)
  - No começo pagava parte do lucro, para criar confiança — [Agência Brasil](https://agenciabrasil.ebc.com.br/geral/noticia/2024-11/pf-investiga-golpes-envolvendo-investimentos-em-criptomoedas)
- **Pico:** cerca de 10 mil clientes e quase R$ 200 mi (MPF), ou R$ 250 mi de prejuízo (PF em 2024, via [Livecoins](https://livecoins.com.br/policia-federal-apreende-carteiras-de-criptomoedas-em-operacao-deadcoin/)).
- **Estresse e parada:** "com o aumento dos valores depositados", as vítimas perderam rendimentos e acesso ao capital "sem justificativa plausível" (Agência Brasil). Sem data; antes de nov/2024, porque a operação nasceu de denúncias de saques bloqueados.
- **Intervenção:** 07/11/2024, com 28 buscas em 9 cidades de SC e RS e 2 preventivas (Livecoins).
- **Gatilho:** (b), seguido de (a).
- **BTC (nov/2024):** var. 6m +43,2%; fechamento −2,5% do ATH — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)

#### Operação Luxus (PF, 12/06/2025, Ponta Grossa/PR)
- **Empresa:** nome não divulgado; o patrimônio dos sócios cresceu sobretudo a partir de 2024 — [PF](https://www.gov.br/pf/pt-br/assuntos/noticias/2025/06/pf-deflagra-operacao-para-investigar-crimes-financeiros-com-criptomoedas-em-ponta-grossa-pr); [Metrópoles](https://www.metropoles.com/colunas/mirelle-pinheiro/grupo-deixa-400-investidores-de-criptomoedas-com-prejuizo-de-r-50-mi)
- **Estresse e parada:** no início de 2025 o sócio alegou "problemas operacionais com uma exchange" e suspendeu rendimentos e devoluções (PF).
- **Pico:** mais de 400 lesados e mais de R$ 50 mi (PF).
- **Intervenção:** 12/06/2025, com 12 buscas e preventiva do sócio principal (PF).
- **Duração:** não calculável. P → I: cerca de 5 meses.
- **Gatilho:** (b), com culpa na exchange.
- **BTC (jan–mar/2025):** de −3,6% a −22,3% do ATH; var. 6m de +30% a +58% — [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)

#### Operação Criptoabate (PC-RS, 13/08/2026): falsa plataforma "TDASX"
- **Início:** até ago/2024. A vítima principal, de 70 anos, depositou R$ 37 mi entre ago/2024 e jan/2025. A TDASX tinha 246 reclamações no Reclame Aqui, 225 delas em 2024 — [Livecoins](https://livecoins.com.br/policia-civil-deflagra-operacao-criptoabate-contra-esquema-de-falsa-plataforma-de-investimento-em-criptomoedas/); [GuarulhosWeb](https://guarulhosweb.com.br/operacao-criptoabate-investiga-golpe-de-r-37-milhoes-contra-idosa-de-70-anos/)
- **Mecânica:** grupos que simulavam "comunidades de estudo". Liberava os primeiros saques e depois exigia "taxas, impostos ou valores necessários para a liberação" (Livecoins).
- **Fim da plataforma:** "teria sido fechada logo após o início das investigações" (Livecoins). A data não foi informada.
- **Intervenção:** 13/08/2026, com 10 preventivas em RS, SC e SP. R$ 30 bi em transações suspeitas é número de movimentação, não de prejuízo — [ABC+](https://www.abcmais.com/brasil/rio-grande-do-sul/golpe-de-falsa-plataforma-de-investimentos-causa-prejuizo-de-r-37-milhoes-a-uma-unica-vitima-e-revela-r-30-bilhoes-em-transacoes-suspeitas/)
- **Ciclo da vítima principal:** cerca de 6 meses de aportes.
- **Gatilho:** (d) sumiço do operador (plataforma fora do ar), muito antes da operação.

#### Operação Mirage: dois casos distintos com o mesmo nome
- **Mirage RS (PC-RS, 13/01/2026):**
  - Anúncios levavam a grupos de WhatsApp com falso "professor americano". Havia ganhos reais no início e depois migração para plataforma falsa com saldo inflado.
  - Uma vítima perdeu R$ 4.378.000 em mai/2025, em menos de um mês.
  - 5 preventivas; carteiras bloqueadas em 17 exchanges; ligação com o Camboja.
  - Fonte: [PC-RS](https://www.pc.rs.gov.br/operacao-mirage-mira-organizacao-criminosa-especializada-em-golpes-de-falsos-investimentos)
  - Gatilho: (a).
- **Mirage PE (PC-PE), falsa plataforma "Aglobal Trade":**
  - Operava pelo menos desde 2024, quando a investigação começou com uma vítima de mais de R$ 1,5 mi.
  - Liberava saques pequenos (R$ 10 mil e R$ 17 mil). Nos grandes, "erros na plataforma" ou novos depósitos para "recuperar" o dinheiro.
  - 13 presos em flagrante em 15/07/2026, num call center com meta de US$ 800 mil por mês. Havia reservas e orientações para mudar a operação para o México.
  - Fontes: [Diario de Pernambuco, 21/07/2026](https://www.diariodepernambuco.com.br/vida-urbana/2026/07/11719257-criminosos-utilizavam-site-de-investimentos-para-aplicar-golpes-milionarios-diz-policia-civil.html); [Diario de Pernambuco 2](https://www.diariodepernambuco.com.br/vida-urbana/2026/07/11719298-metas-em-dolar-e-plano-para-o-mexico-revelam-bastidores-de-grupo-preso-no-recife-por-golpe.html); [CBN Recife](https://www.cbnrecife.com/2026/07/21/operacao-mirage-grupo-aplicava-golpes-milionarios-em-sites-de-investimentos/)
  - Gatilho: (a).
- **BTC nas intervenções de 2026:**
  - Jan/2026: −36,9% do ATH de 06/10/2025.
  - Jul/2026: var. 6m −20,1% e MDD da janela −39,7%.
  - Ago/2026: var. 6m +17,3%, fechamento −37,1% do ATH.
  - Fonte: [Coin Metrics, cálculo próprio](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d)

### Inferences
- As falsas plataformas não têm "momento de colapso" ligado a caixa. Cada vítima tem seu ciclo: saque pequeno liberado, aportes crescentes e bloqueio com cobrança de taxa. Por isso, a queda do BTC de 2026 (−53%) não aparece como gatilho: o saldo exibido é fictício. Isso bate com a Chainalysis, que mostra golpes cada vez mais curtos e descartáveis (seção 1).
- Deadcoin e Luxus repetem a sequência clássica de 2019 e 2021: dinheiro novo acaba, culpa na exchange, intervenção meses depois. E isso ocorreu com o BTC perto do recorde.

### Gaps
- Nome da empresa-alvo da Ouranós e da Deadcoin; início da captação de ambas; data da parada da Deadcoin.
- Data em que a TDASX saiu do ar e data de início da investigação.
- Liberty Up (DF), Dumb Money, JJ Invest e Rompot: sem datas de ciclo de vida nesta rodada.

---

## 5. Quanto tempo duraram, e quanto tempo passou entre o primeiro estresse e o colapso?

### Takeaway
Nos 17 esquemas clássicos com início e fim datáveis, a duração mediana foi de cerca de 30 meses (2,5 anos), com quartis de cerca de 15 e 56 meses. Os extremos são a Kriptacoin, com 8 meses e 1% ao dia, e a GAS, com cerca de 70 meses e 10% a.m. Do primeiro sinal de estresse visível à parada de pagamentos a mediana foi de cerca de 1,5 mês, e do estresse à intervenção, de cerca de 4,5 meses. Quem esperou "para ver" depois do primeiro atraso quase nunca teve janela útil de saída.

### Cited Findings
- **Duração S → colapso**, em meses (fontes nas fichas das seções 2–4):
  - Kriptacoin: 8
  - 18k: menos de 12
  - Minerworld: 13–15
  - Fiji: 14–16
  - TCC: 13–17
  - Atlas: 15–31
  - InDeal: 19–21
  - Unick: 21 ou mais
  - BWA: cerca de 24–36
  - Rental Coins: 24–35 (ou até cerca de 70 se o início foi em 2016)
  - Trust: cerca de 24–35
  - Ouranós: pelo menos 35 até I
  - RCX: cerca de 37–63
  - Grow Up: cerca de 37–74
  - Braiscompany: 55
  - MSK: cerca de 60–71
  - GAS: 69–70
  - Sem início datável: GBB, FX Trading, Deadcoin, Luxus.
- **Estatística (cálculo próprio, com o ponto médio de cada faixa):** n = 17; mediana de cerca de 30 meses; 1º quartil de cerca de 15; 3º quartil de cerca de 56. Para comparar: média de cerca de 48 meses nos Ponzis da SEC — [Deason et al. (SSRN, 2015)](https://papers.ssrn.com/abstract=2586490)
- **1º estresse → parada de pagamentos (meses):** Fiji 0; Luxus 0; Atlas 0–1; Minerworld 0–2; Braiscompany 1–2; GBB 0–4; Unick cerca de 2; Rental cerca de 2; TCC cerca de 2–5. Mediana de cerca de 1,5 mês (cálculo próprio).
- **1º estresse → intervenção (meses):** InDeal 0,5 (estresse interno); Braiscompany cerca de 3; Unick cerca de 4; Fiji cerca de 4 (PF; 2 até o bloqueio cível); Luxus cerca de 5; Minerworld cerca de 6; Trust cerca de 10–11; Rental cerca de 12. Mediana de cerca de 4,5 meses (cálculo próprio).
- **Parada → intervenção (meses):** Braiscompany cerca de 1,5; Unick cerca de 2; Fiji cerca de 4; Minerworld cerca de 4–6; Luxus cerca de 5; BWA cerca de 7 (até a RJ); Rental cerca de 10; Trust cerca de 10–11; MSK cerca de 12 (até o indiciamento); GBB 26 (até a Daemon); TCC cerca de 7 anos (até a Fantasos). Atlas e 18k nunca tiveram operação.
- **Alerta público → colapso:**
  - Unick: stop order de mar/2018 ignorado por cerca de 17 meses — [PAS CVM](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2020/20201208_PAS_CVM_SEI_19957_000238_2019_82_relatorio_presidente_marcelo_barbosa.pdf-1636b454537947559d2cae64f17de17f)
  - Atlas: 0 meses, porque o stop order disparou a corrida — [InfoMoney](https://www.infomoney.com.br/?p=1683301)
  - FX: cerca de 1,5 mês — [Suno](https://www.suno.com.br/noticias/fx-trading-anuncia-encerramento-de-suas-atividades/)
  - GAS: a CVM tinha denúncias desde 2019, sem alerta público — [relatório CVM](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2023/20230829_pas_cvm_19957_002835_2022_47_presidente_cvm_joao_pedro_nascimento_relatorio.pdf)
  - Braiscompany: processo na CVM em jul/2020, não público; exposição pública no mesmo mês do 1º atraso — [InfoMoney](https://www.infomoney.com.br/?p=2028161)

### Inferences
- Promessa diária e duração curta andam juntas: Kriptacoin (1% ao dia, 8 meses) e 18k (2% ao dia, menos de 12 meses). Promessas de 2–10% ao mês com captação por afinidade e consultores duraram 4–6 anos: GAS, MSK, Braiscompany, RCX. A relação não é limpa, porque a GAS prometia 10% a.m. e foi a mais longa. O volume e a velocidade de entrada de dinheiro novo parecem pesar mais que a taxa prometida.
- A mediana de cerca de 30 meses fica abaixo dos cerca de 48 meses dos Ponzis da SEC. Uma explicação possível é que a fachada cripto promete taxas mais altas e atrai coortes que querem sacar mais cedo. É inferência, sem teste.
- A janela de 1,5 mês entre o 1º estresse e a parada é o dado mais útil para o investidor: o primeiro atraso, limite de saque ou "manutenção" é o sinal de saída, não o começo de uma fase longa.

### Gaps
- Início exato de vários casos (Trust, Rental, GBB, FX, Deadcoin, Luxus). Os pontos médios das faixas afetam a mediana em alguns meses.
- A amostra privilegia casos grandes e noticiados. Esquemas pequenos que quebram rápido tendem a ficar fora da imprensa (viés de sobrevivência).

---

## 6. Como e por que terminaram? Classificação do gatilho principal

### Takeaway
Nos 23 esquemas clássicos classificados, o gatilho principal foi (b), corrida de saques ou falta de dinheiro novo, em cerca de 15. Em 6 foi (a), intervenção do Estado antes da quebra: Kriptacoin, InDeal, GAS, Atlas (stop order que disparou a corrida), FX (stop order sobre um esquema já em estresse) e Ouranós. Em 1 foi (d), fuga do operador (TDASX); o TCC e a Grow Up também têm componente de fuga. Não achei nenhum caso em que (c) choque de mercado, (e) mídia ou (f) disputa interna tenha sido o gatilho principal. A queda do BTC aparece como fator secundário na Braiscompany e, segundo o próprio sócio, na RCX. A mídia funciona como acelerador: InDeal (3 meses antes), Braiscompany (junto com os atrasos), Minerworld (depois do estresse).

### Cited Findings
- **(a) Intervenção do Estado antes da quebra:**
  - Kriptacoin (21/09/2017, com saques já racionados) — [MoneyTimes](https://www.moneytimes.com.br/operacao-que-combate-piramide-com-uso-da-kriptacoin-prende-11-pessoas/)
  - InDeal (21/05/2019, faltando R$ 5 mi de captação) — [PAS CVM](https://www.gov.br/cvm/pt-br/assuntos/noticias/anexos/2023/20231211_PAS_CVM_19957_001124_2021_74_relatorio_diretor_joao_accioly.pdf)
  - GAS (Kryptos em 25/08/2021; parada em 15/09/2021) — [Suno](https://www.suno.com.br/noticias/?p=185262)
  - Atlas (CVM 826, 13/08/2019) — [InfoMoney](https://www.infomoney.com.br/?p=1683301)
  - FX Trading (Ato Declaratório 17.142, mai/2019) — [Monitor Mercantil](https://monitormercantil.com.br/cvm-suspende-atuacao-por-irregularidade-da-fx-trading-corporation/)
  - Ouranós (28/11/2023) — [SBT News](https://sbtnews.sbt.com.br/noticia/sbt-news/267021-aviao-473-imoveis-10-barcos-e-40-veiculos-pf-bloqueia-r-400-milhoes-em-bens-de-grupo-criminoso)
  - Também as falsas plataformas Mirage RS e Mirage PE/Aglobal — [PC-RS](https://www.pc.rs.gov.br/operacao-mirage-mira-organizacao-criminosa-especializada-em-golpes-de-falsos-investimentos); [Diario de PE](https://www.diariodepernambuco.com.br/vida-urbana/2026/07/11719298-metas-em-dolar-e-plano-para-o-mexico-revelam-bastidores-de-grupo-preso-no-recife-por-golpe.html)
- **(b) Corrida de saques ou falta de dinheiro novo:**
  - Minerworld — [Correio do Estado](https://www.correiodoestado.com.br/cidades/campo-grande/suspeita-de-piramide-empresa-de-bitcoins-atrasa-pagamentos/319493/)
  - TCC — [IRS](https://www.irs.gov/compliance/criminal-investigation/brazilian-extradited-from-switzerland-to-the-united-states-to-face-indictment-charging-involvement-in-290m-plus-cryptocurrency-fraud-scheme)
  - GBB — [InfoMoney](https://www.infomoney.com.br/onde-investir/rei-do-bitcoin-tem-bens-bloqueados-e-escancara-crise-do-grupo-bitcoin-banco/)
  - Unick — [Suno](https://www.suno.com.br/noticias/reclamacoes-unick-forex-triplicam-dois-meses/)
  - 18k — [Suno](https://www.suno.com.br/noticias/ronaldinho-pagar-r-300-mi-piramide/amp/)
  - BWA — [Suno](https://www.suno.com.br/noticias/plataforma-criptomoedas-bwa-recuperacao-judicial/amp/)
  - Rental — [Suno](https://www.suno.com.br/noticias/?p=283548)
  - Trust — [Campo Grande News](https://www.campograndenews.com.br/brasil/cidades/number-one-pastor-e-mais-4-sao-condenados-em-esquema-bilionario-de-piramide)
  - MSK — [CPI](https://www2.camara.leg.br/atividade-legislativa/comissoes/comissoes-temporarias/parlamentar-de-inquerito/57a-legislatura/piramides-financeiras/outros-documentos/relatorio-cpi)
  - Braiscompany — [InfoMoney](https://www.infomoney.com.br/?p=2028161)
  - Fiji — [InfoMoney](https://www.infomoney.com.br/?p=2083064)
  - RCX — [CPI p. 117](https://www2.camara.leg.br/atividade-legislativa/comissoes/comissoes-temporarias/parlamentar-de-inquerito/57a-legislatura/piramides-financeiras/outros-documentos/relatorio-cpi)
  - Grow Up — CPI, mesmo link.
  - Deadcoin — [Agência Brasil](https://agenciabrasil.ebc.com.br/geral/noticia/2024-11/pf-investiga-golpes-envolvendo-investimentos-em-criptomoedas)
  - Luxus — [PF](https://www.gov.br/pf/pt-br/assuntos/noticias/2025/06/pf-deflagra-operacao-para-investigar-crimes-financeiros-com-criptomoedas-em-ponta-grossa-pr)
  - Também os menores VIK Traders e Alcateia — [Metrópoles](https://www.metropoles.com/distrito-federal/df-investidores-expoem-piramide-financeira-em-empresa-de-bitcoin); [Exame](https://exame.com/invest/minhas-financas/piramides-de-bitcoin-perda-pode-acabar-com-economias-saiba-evitar/)
- **(d) Fuga ou sumiço:**
  - TDASX fora do ar logo após o início das investigações — [Livecoins](https://livecoins.com.br/policia-civil-deflagra-operacao-criptoabate-contra-esquema-de-falsa-plataforma-de-investimento-em-criptomoedas/)
  - Componente secundário no TCC (TCoin e contas canceladas) e na Grow Up ("sumiu com meu dinheiro", CPI p. 264–265).
- **Desculpas registradas na hora do estresse:**
  - Hacker ou ataque: Kriptacoin, Minerworld (Poloniex), GBB, Trust (US$ 800 mi, considerado forjado).
  - Exchange: Atlas ("volume atípico"), FX ("exchanges não suportam o volume"), Braiscompany (Binance), Fiji (KuCoin), Luxus.
  - "Manutenção" ou "migração": Unick (10 dias), Atlas (jan/2020), Trust ("instalar blockchain"), VIK ("atualização do sistema"), Braiscompany ("novo aplicativo").
  - Regulação: MSK (PL 2.303/15), FX ("exigências regulatórias"), GAS ("bloqueio judicial"), Atlas (processou a CVM).
  - Queda do mercado: VIK ("desvalorização" em ago/2019, com o BTC +153% em 6 meses), Braiscompany (mar/2023), RCX ("queda de 70%").
  - Fontes nas fichas.

### Inferences
- A falta de dinheiro novo é o modo normal de morte. A intervenção estatal só chega primeiro quando a investigação começou cedo: InDeal, GAS e Ouranós foram investigadas por anos.
- "Culpa no mercado" é desculpa e não deve ser tomada como causa. A VIK alegou "desvalorização das criptomoedas" quando o BTC tinha subido 153% em 6 meses.
- O stop order da CVM teve efeitos opostos. Na Atlas precipitou a corrida em dias. Na Unick foi ignorado por 17 meses, enquanto a captação crescia. Um alerta sem bloqueio de contas não interrompe, por si, um esquema com base fiel.

### Gaps
- A classificação é minha, a partir das fontes. Em vários casos (Deadcoin, Kriptacoin, FX) (a) e (b) coexistem, e a escolha do "principal" é discutível.

---

## 7. Os colapsos coincidem com quedas do bitcoin ou com ações de órgãos?

### Takeaway
Não há evidência de que o ciclo do BTC explique os colapsos.
- Nos cerca de 20 esquemas clássicos com mês de colapso datável, a proporção de colapsos com queda de 50% ou mais do BTC na janela de 6 meses (cerca de 20–25%) é igual à taxa-base de qualquer mês (24%). Com variação de 6 meses de −20% ou pior, ficam cerca de 15–20%, contra 21% de base.
- Há leve excesso de colapsos em meses de bear market (cerca de 40–45%, contra 34%). Ele vem quase todo do cluster de 2019, quando o BTC estava abaixo do topo de 2017 mas subia forte.
- Muitos colapsos ocorreram no topo ou em alta: Minerworld e TCC no fim de 2017; Unick, Atlas, FX e VIK no meio de 2019; Rental, Trust e MSK logo após o ATH de nov/2021; Deadcoin e Luxus perto do ATH de 2024–2025.
- O choque de mercado aparece como agravante em Braiscompany (FTX, Binance) e RCX.
- A coincidência mais forte é com ações de órgãos e choques de confiança setoriais: o cluster de 2019 com a onda de stop orders e operações da CVM e da PF; o de dez/2021 com a Kryptos e o PL 2.303.

### Cited Findings
- **Mês de colapso e BTC** (var. 6m / MDD na janela / fechamento contra ATH), cálculo próprio com a [Coin Metrics](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d):
  - Kriptacoin, set/2017: +300,7% / −35,8% / −11,9%
  - Minerworld, out–dez/2017: +365% a +468% / −35,8% / 0 a −29,1%
  - TCC, jan–mai/2018: +251% a −25,2% / −49,3% a −66,3% / −48,8% a −61,9%
  - InDeal e GBB, mai/2019: +115,3% / −51,0% / −56,4%
  - Atlas, Unick e VIK, ago/2019: +153,2% / −26,6% / −51,1%
  - 18k, out/2019 (se confirmado): +73,8% / −42,1% / −53,4%
  - BWA, dez/2019: −33,9% / −48,6% / −63,5%
  - GAS, ago/2021 (I) e set/2021 (P): +4,1% e −25,5% / −53,1% / −25,6% e −31,0%
  - Rental, Trust e MSK, dez/2021: +32,2% / −31,4% / −31,4%
  - Braiscompany, dez/2022: −14,5% / −49,7% / −75,5%
  - Fiji, fev/2023: +15,6% / −35,5% / −65,7%
  - RCX, abr/2023 (ou 2022): +43,3% / −26,0% / −56,5%
  - Ouranós, nov/2023: +38,6% / −20,0% / −44,2%
  - Deadcoin, nov/2024: +43,2% / −24,4% / −2,5%
  - Luxus, jan–fev/2025: +58,1% e +42,9% / −21,0% / −3,6% e −20,6%
- **Contagem (cálculo próprio, cerca de 20 casos):**
  - MDD de −50% ou pior: TCC (mai/2018), InDeal, GBB, GAS e talvez FX (se o colapso for em mai/2019); cerca de 4–5 de 20 (20–25%), contra 24% de base. Nos três casos de mai/2019, o MDD vem do crash de nov–dez/2018, e o BTC já subia +115% em 6 meses.
  - Var. 6m de −20% ou pior: TCC (mai/2018), BWA, GAS (P em set/2021); cerca de 3 de 20 (15%), contra 21% de base.
  - Fechamento 50% ou mais abaixo do ATH: TCC, InDeal, GBB, Atlas, Unick, 18k, BWA, Braiscompany, Fiji, RCX; cerca de 8–10 de 20 (40–45%), contra 34% de base.
  - Taxas-base na seção 1.
- **Ações de órgãos coincidentes:**
  - **2019:** CVM com 371 investigações do mercado marginal em 2019, o triplo de 2018 — [CNN Brasil, 05/08/2020](https://www.cnnbrasil.com.br/economia/macroeconomia/com-criptomoedas-como-disfarce-golpes-financeiros-disparam-na-pandemia/)
  - Unick: novo alerta em 25/04/2019 — [MoneyTimes](https://moneytimes.com.br/cvm-reforca-alerta-e-abre-processo-contra-atuacao-irregular-da-unick/)
  - FX: stop order em mai/2019 — [Monitor Mercantil](https://monitormercantil.com.br/cvm-suspende-atuacao-por-irregularidade-da-fx-trading-corporation/)
  - Atlas: stop order em ago/2019 — [Livecoins](https://livecoins.com.br/cvm-proibe-atlas-quantum-investimento-em-bitcoin/)
  - Operações Egypto (mai/2019) e Lamanai (out/2019) — [TecMundo](https://www.tecmundo.com.br/seguranca/141543-pf-investiga-piramide-criptomoedas-levantou-r-700-milhoes.htm); [Suno](https://www.suno.com.br/noticias/unick-forex-pf-operacao-rs/)
  - **2021:** Kryptos em 25/08/2021, a maior operação do período — [Suno](https://www.suno.com.br/noticias/?p=185262). PL 2.303/15 aprovado na Câmara em 08/12/2021 e usado como desculpa pela MSK — [Bloomberg Línea](https://www.bloomberglinea.com.br/2021/12/10/regulamentacao-do-mercado-cripto-avanca-no-congresso/) (trecho de busca); [Tecnoblog](https://tecnoblog.net/noticias/2021/12/22/firma-de-criptomoedas-acusada-de-golpe-de-r-700-mi-e-alvo-do-procon-sp/) (trecho de busca)
  - **2023:** Operação Halving (16/02/2023) e parada da Fiji no mesmo mês — [InfoMoney](https://www.infomoney.com.br/?p=2083064)
- **Casos que contrariam a tese de mercado:**
  - A GAS pagou durante uma queda de 53% (abr–jul/2021) — [Suno](https://www.suno.com.br/noticias/?p=185262) e Coin Metrics.
  - A Minerworld entrou em estresse com o BTC a +365% em 6 meses — [Wikipédia](https://pt.wikipedia.org/wiki/Minerworld) e Coin Metrics.

### Inferences
- Para a pergunta "o crash do BTC derruba pirâmides brasileiras?", a resposta empírica desta amostra é "raramente, e como agravante". O fluxo de caixa desses esquemas vem de dinheiro novo captado por afinidade, não do preço do ativo de fachada. O preço do BTC age mais pelo lado da narrativa e da captação: em alta, facilita vender a fachada; em baixa, dá desculpa.
- Mecanismo alternativo, com poucos pontos e a testar: alta forte do BTC pode estressar esquemas com passivo denominado em BTC (TCC no fim de 2017; Atlas em ago/2019, depois de +150%; Trust no ATH de nov/2021). Os clientes veem o saldo valer mais em reais e pedem saque.
- Choques de confiança setoriais funcionam como gatilho comum para vários esquemas ao mesmo tempo: grande operação policial, alerta da CVM em série, projeto de lei, quebra de vizinho. Exemplos: o meio de 2019; dez/2021; Campina Grande em fev/2023. Para um estudo maior, a variável a coletar é "data da maior ação estatal ou colapso vizinho nos 3 meses anteriores", não só o preço do BTC.

### Gaps
- Amostra pequena (cerca de 20), datas mensais imprecisas e sem teste estatístico formal. A comparação com a taxa-base é descritiva.
- Não medi a captação (entrada de dinheiro novo) mês a mês de nenhum esquema. Esse seria o dado decisivo, e só aparece em autos (RIF, laudos), não na imprensa.
- Faltou série de BTC em reais e de busca no Google ("bitcoin") como proxy de interesse do varejo.

---

## 8. Como os operadores agiram no fim?

### Takeaway
O repertório de fim de vida se repete: narrativa técnica (hacker, exchange, manutenção, migração), conversão do saldo em token próprio ou "saldo migrado", acordos e RJ para ganhar tempo, fuga para o exterior e, em vários casos, abertura de novo esquema pelos mesmos líderes.

### Cited Findings
- **Token próprio ou saldo convertido:**
  - Minerworld: MCash, nov/2017 — [InfoMoney](https://www.infomoney.com.br/mercados/justica-brasileira-bloqueia-r-300-milhoes-de-envolvidos-em-esquema-de-piramide-com-criptomoedas/)
  - TCC: TCoin, fim de 2017 — [BehindMLM](https://behindmlm.com/companies/tccs-douver-braga-arrested-in-switzerland-extradited-to-us) (trecho de busca)
  - GBB: Br2Ex — [InfoMoney](https://www.infomoney.com.br/onde-investir/rei-do-bitcoin-tem-bens-bloqueados-e-escancara-crise-do-grupo-bitcoin-banco/)
  - Atlas: "Saldo Migrado" e BTCQ em 2020 — [Suno](https://www.suno.com.br/noticias/atlas-quantum-sistema-fora-do-ar-10-dias/); [InfoMoney](https://www.infomoney.com.br/?p=1683301)
  - Trust: TrusterCoin e mais um token — [CPI p. 145](https://www2.camara.leg.br/atividade-legislativa/comissoes/comissoes-temporarias/parlamentar-de-inquerito/57a-legislatura/piramides-financeiras/outros-documentos/relatorio-cpi)
- **Acordos, parcelamento e retomada parcial:**
  - Minerworld: 24 meses em BTC (trecho de busca).
  - Unick: só acordo extrajudicial, "sem prazo" — [Suno](https://www.suno.com.br/noticias/unick-forex-contrata-escritorio-negociar-clientes/)
  - GBB: site de acordos — [MoneyTimes](https://www.moneytimes.com.br/bitcoin-banco-lanca-site-para-de-acordos-entre-clientes-e-corretoras-negociecoins-e-tembtc/)
  - VIK: pagamentos "por ordem de chegada" até US$ 100 — [Metrópoles](https://www.metropoles.com/distrito-federal/df-investidores-expoem-piramide-financeira-em-empresa-de-bitcoin)
  - MSK: acordo com o Procon-SP descumprido (CPI).
  - RCX: "migração" para fundo que não existiu (CPI p. 117).
- **Recuperação judicial:**
  - GBB, nov/2019 — [Finsiders](https://finsidersbrasil.com.br/noticias-sobre-fintechs/bitcoin-banco-a-historia-da-falsa-empresa-que-foi-da-ostentacao-a-falencia/)
  - BWA, jul/2020 — [Suno](https://www.suno.com.br/noticias/plataforma-criptomoedas-bwa-recuperacao-judicial/amp/)
  - MSK, abr/2022, chamada pela polícia de "artifício para ganhar tempo" (CPI p. 158–159).
  - GAS, mai/2022 — [Folha PE](https://www.folhape.com.br/economia/justica-antecipa-falencia-da-gas-empresa-do-farao-dos-bitcoins/258681/)
- **Fuga ou exterior:**
  - Braiscompany para a Argentina, depois de 16/02/2023 — [Itatiaia](https://www.itatiaia.com.br/mundo/braiscompany-casal-de-brasileiro-foragido-por-esquema-de-piramides-e-preso-na-argentina/)
  - Mirelis (GAS) para os EUA (CPI p. 32).
  - Leidimar (Unick): nota de Belize e depois "lugar incerto" — [Livecoins](https://livecoins.com.br/leidimar-lopes-desaparecido-sp-unick-forex/)
  - Rodrigo Marques (Atlas) no México e na Espanha — [InfoMoney](https://www.infomoney.com.br/onde-investir/golpe-de-r-7-bi-com-robo-milagroso-da-atlas-quantum-e-alvo-da-cpi-das-piramides/)
  - Douver Braga (TCC): Flórida até 2021, depois Suíça — [IRS](https://www.irs.gov/compliance/criminal-investigation/brazilian-extradited-from-switzerland-to-the-united-states-to-face-indictment-charging-involvement-in-290m-plus-cryptocurrency-fraud-scheme)
  - Caio Almeida Lima (RCX), foragido (CPI).
  - Aglobal Trade: plano para o México — [Diario de PE](https://www.diariodepernambuco.com.br/vida-urbana/2026/07/11719298-metas-em-dolar-e-plano-para-o-mexico-revelam-bastidores-de-grupo-preso-no-recife-por-golpe.html)
- **Novo esquema pelos mesmos líderes:**
  - Ex-líderes da Unick na Moguro Club, out/2019 — [Suno](https://www.suno.com.br/noticias/antigos-lideres-unick-forex-envolvidos-em-nova-piramide/)
  - Patrick Abrahão (Trust) e a Actyon Crypto (CPI p. 157).
  - Os fundadores da Braiscompany vinham do D9 (CPI p. 248).
  - Os sócios da Titanium (investigada na Ouranós) teriam tentado lançar a "LeaxCoin" com Cláudio Oliveira, do GBB — [Blocktrends](https://blocktrends.com.br/titanium-asset-e-investigada-por-envolvimento-com-piramide-financeira/)
- **Ataque ao regulador ou "perseguição":**
  - Atlas processou a CVM pedindo R$ 3,167 bi em 11/08/2021 — [InfoMoney](https://www.infomoney.com.br/?p=1683301)
  - Francisley atacou os "acusadores" (CPI p. 100).
  - Glaidson diz ter fortuna para pagar 77 mil, em set/2026 — [Economic News](https://economicnewsbrasil.com.br/2026/09/07/fortuna-farao-dos-bitcoins-credores/)

### Inferences
- Token próprio e "migração" servem para trocar saldo sacável por saldo ilíquido e ganhar meses. Atlas, Minerworld e Trust fizeram isso logo no início do estresse. Para quem está dentro, o anúncio de token ou migração equivale à parada de pagamentos.
- A reciclagem de líderes (D9 → Braiscompany; Unick → Moguro; GBB → LeaxCoin; Trust → Actyon) sugere que a carreira do operador dura mais que cada esquema. Para estudar duração, a unidade de análise pode ser a rede de líderes, não a empresa.

### Gaps
- Não achei o destino de vários operadores (sócios da 18k, Minerworld depois de 2019, Philip Han da FX).

---

## 9. Tabela-resumo

### Takeaway
Uma linha por caso, com dados das fichas. "n/d" = não encontrado. Recrutamento: nenhum caso tem recrutamento obrigatório documentado. Quase todos pagavam bônus por indicação opcional ou usavam consultores comissionados, ou seja, são Ponzis com camada de MLM, não pirâmides puras de recrutamento. BTC = var. 6m / MDD na janela no mês do colapso, cálculo próprio com a [Coin Metrics](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d).

### Cited Findings

| Caso | Início | Fim (P = parou de pagar; I = intervenção) | Duração (meses) | Retorno %/mês (conversão) | Recrutamento obrigatório | 1º estresse → colapso (meses) | Gatilho principal | BTC nos 6 meses anteriores (var. / MDD) |
|---|---|---|---|---|---|---|---|---|
| Kriptacoin (DF) | jan/2017 | P antes de I; I 21/09/2017 | 8 | 1%/dia = 30% simples; 34,8% composto | n/d (bônus de 10%) | n/d | (a), com saques já suspensos | +301% / −36% |
| Minerworld (MS) | set/2016 | P out–dez/2017; I 17/04/2018 | 13–15 | 100% em 12m = 5,95% | n/d | 0–2 (até P); 6 (até I) | (b) | +365% a +468% / −36% |
| Trade Coin Club | dez/2016 | P jan–mai/2018; I (BR) 30/04/2025 | 13–17 | 0,35%/dia = 11,1% | n/d (MLM) | ~2–5 | (b) + (d) | +251% a −25% / −49% a −66% |
| InDeal (RS) | out/2017 (CVM) ou ago/2017 | I 21/05/2019 (pagava até lá) | 19–21 | 15% | n (consultores) | 0,5 (estresse interno) | (a) | +115% / −51% |
| GBB (PR) | n/d | P mai/2019; RJ nov/2019; I 05/07/2021 | n/d | ~1% (3%/90d; 6%/180d, pós-bloqueio?) | n/d | 0–4 | (b) | +115% / −51% (estresse no fundo de jan/2019: −56% em 6m) |
| FX Trading | n/d | stop order 20/05/2019; encerramento 07/07/2019 | n/d | 2,5%/dia = 109,8% composto; 100% em 3m = 26% | n/d (MLM, bônus 10→8%) | ~1–3 | (a) sobre (b) | +115% a +195% / −51% (mai) a −23% (jun) |
| Atlas Quantum (SP) | 2017 (ou mai/2018) | P ago–set/2019 (total jan/2020); sem I policial | 15–31 | 3–7% (~4%) | n | 0–1 | (a) → (b) | +153% / −27% |
| Unick Forex (RS) | até nov/2017 | P ago/2019; I 17/10/2019 | 21+ | ×2 em 6m = 12,25% | n/d (bônus) | ~2 (até P); ~4 (até I) | (b) | +153% / −27% |
| 18kRonaldinho | 2019 | P 2019 (out?); sem I | <12 | 2%/dia = 81,1% composto (ou 0,99%/dia = 34,4%) | n/d (bônus de 7%) | n/d | (b) (inferência) | +74% / −42% (out/2019) |
| BWA Brasil (SP) | 2017 | P fim/2019–início/2020; RJ 08/07/2020 | ~24–36 | 5–10% | n/d | n/d | (b), contágio do GBB | −34% / −49% |
| GAS (RJ) | nov/2015 | I 25/08/2021; P 15–16/09/2021 | 69–70 | 10% | n (consultores) | 0 (sem estresse antes de I) | (a) | +4% / −53% |
| Rental Coins (PR) | 2019 (ou 2016) | P dez/2021; I out/2022 | 24–35 | 13,5–20% | n/d | ~2 | (b) | +32% / −31% |
| Trust Investing | 2019 | P nov–dez/2021; I 19/10/2022 | ~24–35 | 0,1–5%/dia = 3–332%; 500% a.a. = 16,1% | n/d (MLM) | ≤6 (impreciso) | (b) | +32% a +53% / −31% a −49% |
| MSK (SP) | 2016 | P dez/2021; RJ abr/2022; indiciamento 28/12/2022 | ~60–71 | até 5% | n/d | n/d | (b), desculpa regulatória | +32% / −31% |
| Braiscompany (PB) | mai/2018 | P 30/12/2022–jan/2023; I 16/02/2023 | 55 | até 9% (3–10%) | n/d | ~1–2 | (b), com (c) de fundo | −15% / −50% (−75,5% do ATH) |
| RCX Group | 2018 | P 2022 ou abr/2023; I n/d | ~37–63 | 2–8,5% | n (sem comissão, segundo sócio) | n/d | (b) + (c) alegado | 2022: bear (−77% do topo); abr/2023: +43% / −26% |
| Grow Up (RJ) | 2017/2019 | P 2022–início/2023; I n/d | ~37–74 | até 10% (GOLD ~5,5%) | n/d | n/d | (b) + (d) | jan–fev/2023: −1% a +16% / −36% |
| Fiji Solutions (PB) | fim/2021 | P fev/2023; I 15/06/2023 | 14–16 | 4–12% | n/d | 0 | (b), contágio da Braiscompany | +16% / −36% |
| Ouranós (SC/PR) | ≤2020 | I 28/11/2023 | ≥35 | fixo + variável (n/d) | n (CIC via DTVM) | sem estresse achado | (a) | +39% / −20% |
| Deadcoin (SC) | n/d | P antes de I; I 07/11/2024 | n/d | até 30% | n/d | n/d | (b) → (a) | +43% / −24% |
| Luxus (PR) | n/d (cresce em 2024) | P início/2025; I 12/06/2025 | n/d | n/d | n/d | 0 | (b) | +43% a +58% / −21% |
| TDASX (Criptoabate) | ≤ago/2024 | plataforma fora do ar (data n/d); I 13/08/2026 | ciclo da vítima: ~6 | n/d (falsa plataforma) | não se aplica | não se aplica | (d) | n/a (saldo fictício) |
| Aglobal Trade (Mirage PE) | ≤2024 | I 15/07/2026 | ≥19 | n/d (falsa plataforma) | não se aplica | não se aplica | (a) | −20% / −40% (jul/2026) |
| Mirage RS | n/d | I 13/01/2026 | ciclo da vítima: <1 | n/d (falsa plataforma) | não se aplica | não se aplica | (a) | −32% / −37% (jan/2026) |

Fontes por linha: fichas das seções 2, 3 e 4. Conversões e BTC: cálculo próprio.

### Inferences
- Na tabela, o "gatilho" quase nunca acompanha a coluna do BTC. Há colapsos por (b) com o BTC a +150% (Unick, Atlas) e a −15% (Braiscompany), e intervenções (a) com o BTC em alta (Ouranós, InDeal) e em queda (GAS).
- A coluna "1º estresse → colapso" concentra-se em 0–2 meses, o que reforça o uso do primeiro atraso como sinal de saída.

### Gaps
- Campos "n/d" ainda abertos: início (GBB, FX, Deadcoin, Luxus), retorno (Ouranós, Luxus), mês da parada (18k, BWA) e nome das empresas da Ouranós e da Deadcoin.
- Sobre as correções feitas às notas anteriores, que o redator deve preferir:
  - Unick: stop order em mar/2018, não em 2019.
  - InDeal: início em out/2017 segundo a CVM, além de ago/2017.
  - Braiscompany: fundada em mai/2018.
  - Rental, Trust e MSK: pararam de pagar em dez/2021.
  - GAS: RJ pedida em mai/2022.
  - Atlas: retorno de 3–7% a.m.
  - 18k: "out/2019" não confirmado.
