# PLANO | o painel de gestão do negócio (Meshcraft Scale OS)

publico-para-ia: true

**Reescrito em 03/09/2026 à noite**, e substitui por inteiro a versão da manhã
do mesmo dia. A versão da manhã nasceu de três arquiteturas de receita (v1, v2,
v3) e de cinco decisões do mantenedor; à noite ele trouxe quatro documentos
novos da mesma IA externa, o **Meshcraft Scale OS** (a tese, o manual
operacional, a arquitetura do painel e a especificação técnica), avisou que a
meta da manhã tinha sido escolhida sem estudar os documentos, e reformulou o
painel a partir deles. Os oito documentos estão inteiros em
`docs/consultorias/painel-de-gestao/`, e **o confronto de cada premissa deles
com as decisões da casa está em `CONFRONTO-scale-os.md`, na mesma pasta**: 34
premissas, cada uma com veredito. Este plano deriva do confronto, não dos
documentos direto (`armadilhas/299`).

**Em 04/09/2026 ele trouxe o NONO documento** (o quinto da leva Scale OS): o
*Growth Execution Engine v1.0*, o mesmo sistema escrito como playbook de
implementação para agentes de IA. Confronto em
`CONFRONTO-growth-execution-engine.md`: **91 das 100 seções repetem premissas
já julgadas e nenhum veredito mudou**; das oito peças novas, uma entrou nesta
escada como o degrau 19 (o grafo causal) e três viraram parágrafos nos degraus
11 e 13 e no §9. Se você chegou aqui vindo daquele documento, leia o confronto
ANTES de criar qualquer coisa: seguido ao pé da letra, ele manda construir uma
célula `scale_os`, rotas `/scale-os/` e um banco de tarefas, que duplicariam a
`metricas`, o `/admin/` e a `fila/`.

Este documento NÃO é um painel: não guarda estado e não se atualiza sozinho.
Quem responde "isto foi feito?" é o livro (`painel/registros/`) e a fila
(`fila/`). O que este plano descreve só existe quando um PR o construir e um
registro o provar.

Os documentos de origem pensam numa empresa com seis donos de área, vendedores,
um CRM contratado, checkout ativo e anúncios pagos. Este plano traduz cada
ideia para a casa que existe: um mantenedor leigo, uma professora, robôs, uma
turma que entra pela fila de liberação, a venda acontecendo fora do site e
congelada dentro dele, e uma constituição que já decidiu como fato se guarda e
como estado se calcula. Onde a tradução mudou a ideia, o motivo está no
confronto.

---

## Parte 0 | A visão, em resumo

Os documentos do Scale OS dizem uma coisa em quatro tamanhos: **a semana é a
unidade de execução, o ciclo de 12 semanas é a unidade de estratégia, e a
coorte (quem entrou no mesmo período) é a unidade de verdade econômica.** O
painel não é um relatório que diz "aconteceu isto"; é um sistema de decisão que
pergunta "então o que fazemos?", e cada tela termina num gesto.

Nesta casa isso se traduz assim:

- **Uma meta grande por ciclo**, no formato "de X para Y até quando", com a
  resposta em uma palavra: ganhando ou perdendo. Hoje: de 0 para 1000 pessoas
  que viraram alunas, somadas de 03/09 a 15/12/2026, com a barra do mês
  zerando todo dia 1.
- **Uma restrição por semana**: o único gargalo que, se melhorar, move a meta
  inteira. Calculada, e confirmada por ele.
- **Uma ou duas medidas de direção**: o que a casa consegue mover na semana e
  que antecipa a meta (pedidos de entrada, liberações em 48 horas).
- **Uma reunião de segunda-feira**, dentro do painel, que termina escrevendo
  registros no livro e tarefas na fila, pelos caminhos que já existem.
- **Um fechamento de ciclo a cada 12 semanas** que obrigatoriamente mata
  alguma coisa e fixa a meta seguinte.

As quatro leis que o painel obedece já são leis da casa (`painel/LEIA-ME.md`):
acontecimento se acrescenta e estado se calcula; verde exige prova conferida;
nenhum fato mora em dois lugares; número que não se pode confiar é pior que
número nenhum. Os documentos acrescentam quatro réguas de desenho, que este
plano adota como lei de toda tela (§2).

---

## §1 As decisões do mantenedor que este plano executa

| Data | Decisão | Consequência neste plano |
|---|---|---|
| 22/08/2026 | **Pagamento por último.** Nada de checkout, pagamento ou venda até ele dizer que o site vai vender. | Toda camada de venda entra DESENHADA (cartão com `fonte: null` e `sem_fonte_porque`), nunca acesa. Nenhum PR de venda nasce deste plano. |
| 25/08/2026 | **Sempre completo, nunca a versão reduzida** (`DECISAO-filosofia-de-escopo.md`). | O destino é o sistema inteiro dos documentos. O caminho é a escada do §8, um degrau por PR. |
| 25/08/2026 | **Contadores em tempo real, por HTTP, exatos** (`DECISAO-celula-admin.md` §3). | O número "agora" vem ao vivo da célula dona, sem cache. O número "desde quando" (coorte, foto) vem da célula de medição, que é foto por natureza. |
| 30/08/2026 | **A escola é 18+, sem menores.** Reconfirmado em 03/09 de manhã (v1) e mantido à noite (Scale OS 1.2 §144 e §193 trazem "menor" de volta). | Sai o escopo de dado de menor, sai a objeção "pais". A pergunta não se repete: está registrada. |
| 03/09/2026 (manhã) | **Os fatos do negócio moram numa célula nova** (nome de trabalho `metricas`). | Uma célula, não quatro (o Scale OS 1.2 propõe `painel`, `revenue`, `analytics`, `automation`). `revenue` e `analytics` são a `metricas`; `automation` é a `mensageria`; `painel` é a `admin`. |
| 03/09/2026 (manhã) | **A própria plataforma é o CRM.** | Conciliação entre `pagamentos`, `alunos`, `identidade` e o livro de fatos; não há terceira ponta. |
| 03/09/2026 (noite) | **A Meta 1 é "quantas pessoas compraram neste mês"**, com a barra do mês zerando no dia 1 e a meta grande por cima: **de 0 para 500 pessoas somadas, de 03/09 a 15/12/2026**. A partida é 0 porque neste mês ainda não houve venda. Registro `20260903-036`. **Dobrada para 1000 em 04/09/2026**, com a meta repartida por uma curva de crescimento semanal (`DECISAO-o-calendario-do-ciclo.md`). | O placar foi reformulado (PR #936). A meta acumulada de alunos desceu ao andar 1. |
| 03/09/2026 (noite) | **A data que conta é a da liberação ou a da confirmação do pagamento**, nunca a que a pessoa digitou. | Rito de Contrato autorizado por ele: `virou_aluno_em` na lista de alunos (PR #933 contrato, #934 célula). Quem foi liberado antes de 03/09 (a turma da lista de WhatsApp, 02/09) não conta no ciclo. |
| 03/09/2026 (noite) | **Sem nota composta de 0 a 100 no topo** (ele marcou "sem preferência"; ficou a regra da casa). | Composto nunca no andar 0; se um dia entrar, só com os componentes ao lado. |
| 03/09/2026 (noite) | **Só ele lê o painel de gestão por enquanto** ("sem preferência"; ficou a recomendação). | `ADMIN_EMAILS` continua a única porta. Papel só-leitura para a professora é decisão futura dele, não deste plano. |
| 03/09/2026 (noite) | **As duas estrelas-guia dos documentos entram desenhadas, sem dados** ("sem preferência"; ficou a recomendação). | Cartões `alunos-com-resultado-profissional` e `margem-mensal` nascem com `sem_fonte_porque`, acima da Meta 1 na capa, e acendem quando a fonte nascer. |
| 05/09/2026 | **Ninguém pede entrada na escola: quem está na fila já comprou fora do site e espera confirmação.** As palavras dele: *"ninguém pede entrada na escola, todos entram apenas e unicamente pela matrícula mediante a compra do curso"* e *"os alunos dos quais estamos falando no painel das vendas são de vendas que foram efetuadas via checkout"*. Escolha dele em caixa de pergunta estruturada: consertar o nome e desenhar a medida certa. | As duas medidas de direção passam a se explicar como a **sala de espera** (as contas não mudam; o nome envelheceu). Ao lado nascem os dois cartões do caminho da venda, `visitas-na-pagina-de-venda-por-semana` e `compras-pelo-checkout-por-semana`, com `fonte: null` até o checkout abrir. O placar volta a apontar para a meta e nada some da tela. |

Decisões anteriores que este plano respeita sem reabrir: reembolso tira o
acesso (31/08; reembolsada não é compra); a gestão mora em `/admin`
(`DECISAO-a-gestao-da-caixa-mora-no-admin.md`); toda tela nova nasce fora do
prefixo `painel/` e entra em `painel/mapa-do-site.json`
(`DECISAO-a-area-do-lancamento-perpetuo.md` §1 e §5); o mapa da jornada em
`/admin/escola/jornada/` é a tela dos números de quem está na escola; o
portfólio tem plano guardado sem construção autorizada; tarefas e decisões
moram em arquivo, nunca em banco novo (veredito da central de orquestração,
29/08, com três pareceres externos); o motor de mensagens automáticas mora
dentro da `mensageria` (30/08).

---

## §2 As oito réguas de toda tela

As quatro primeiras já eram lei (`painel/LEIA-ME.md`). As quatro últimas vêm
dos documentos do Scale OS (1.1 §2, §125, §126, §132, §150, §151; 1.2 §237 a
§239, Parte LXXII) e viram regra desta casa a partir deste plano:

1. **Acontecimento se acrescenta; estado se calcula.** Fato é evento, gravado
   uma vez. Métrica, marco, coorte e cor são vistas calculadas.
2. **Verde exige prova conferida.** Sem `evidencia` e `verificado_em`, o painel
   diz "não comprovado".
3. **Nenhum fato mora em dois lugares.** Se o painel não mostra algo, muda a
   regra de cálculo, por PR, com teste-guarda. Nunca uma lista paralela.
4. **Número que não se pode confiar é pior que número nenhum.** "Não consigo
   contar" é resposta; zero inventado não é.
5. **Todo número do andar zero termina num gesto.** O cartão de um número de
   resultado no andar 0 tem o campo `acao` (o que fazer quando ele está
   abaixo do esperado), e o validador reprova sem ele (PR #936). A pergunta do
   Scale OS 1.1 §132: *se este número mudar, alguém faz algo diferente? Se
   não, ele sai da primeira tela.*
6. **Três cliques: número, diagnóstico, ação.** De todo número importante se
   chega, em um clique, a "de onde veio"; em dois, a "o que está mudando"; em
   três, a um gesto (abrir a fila, criar tarefa, registrar decisão).
7. **Fato nunca se mistura com hipótese.** Toda afirmação de robô ou de IA na
   tela traz a evidência, a confiança e as explicações alternativas, e diz em
   qual das duas caixas está. Registro tipo `nota` com `evidencia` é o molde.
8. **Tela vazia diz o que falta; dado velho diz que é velho.** "Sem dados até
   a célula de cursos nascer" em vez de zero; "medido há 3 dias" em vez de um
   número sem data. O campo `frescor_maximo` do cartão decide quando um número
   passa a ser velho.

---

## §3 A capa: os blocos, na ordem, e o teto

A capa do painel de gestão é `/admin/placar/` crescendo, não uma tela nova. Os
documentos propõem uma home de 11 blocos (Scale OS 1.1 §155); aqui são nove,
porque dois deles (aprovações; tarefas e robôs) já são telas da casa e entram
como atalho. **A capa tem teto de nove blocos e se recusa a crescer**, como a
capa do painel do dono: realidade nova entra como cartão, não como bloco.

| # | Bloco | O que mostra | De onde vem | Estado em 03/09/2026 |
|---|---|---|---|---|
| 1 | **A barra do mês e a meta grande** | quantas viraram alunas neste mês (meta do mês ao lado); de 0 para 1000 até 15/12, repartida pela curva de semanas; ganhando ou perdendo | `alunos` ao vivo, `virou_aluno_em` | **no ar** (PR #936) |
| 2 | **A restrição desta semana** | o único gargalo que, melhorado, move a meta; linha de base, valor de hoje, impacto estimado, confiança, e o gesto | calculado das taxas de passagem da jornada (§6.3); "suspeita" é cálculo, "confirmada" é registro dele | degrau 1 |
| 3 | **A direção da semana** | uma ou duas medidas de direção com a meta da semana, o valor de hoje e a sequência de semanas cumpridas; os compromissos da semana e o veredito da semana passada | `leads`, `alunos` (pedidos, liberações), o livro (compromissos como registros) | degrau 2 |
| 4 | **Precisa de você** | os pedidos sem resposta, com os quatro campos da decisão | o livro (já calculado em `/admin/painel/`) | **no ar**, entra como atalho |
| 5 | **O que mudou desde a semana passada** | só os números que se moveram além do ruído, com a direção pintada pelo cartão (`direcao`) | os cartões que têm fonte, contra a foto da semana anterior (a `metricas`) | degrau 6 |
| 6 | **O placar de doze** | os doze indicadores do Scale OS traduzidos (§4.3), cada um com fonte ou com "sem dados até X" | cartões | degrau 4 |
| 7 | **As estrelas-guia** | alunos com resultado profissional; margem mensal | desenhadas, sem fonte | degrau 4 |
| 8 | **O laboratório** | experimentos rodando, encerrados, vencedores, inconclusivos; a velocidade de aprendizado validado do ciclo | o livro (registros tipo `medicao` e as respostas) | degrau 12 |
| 9 | **Os robôs e a fila** | quem está com o quê agora, o que está bloqueado | `/admin/caixa/robos/` (já existe), entra como atalho | **no ar** |

Nada de nota composta no cabeçalho. O cabeçalho diz três coisas: a fase da
escola (achando, provando, escalando, compondo; calculada dos portões, §6.5),
a confiança dos dados desta tela (a fração dos blocos que chegaram com fonte),
e há quanto tempo cada bloco foi medido.

---

## §4 Os cartões: a taxonomia, os campos novos e o placar de doze

### §4.1 Os quatro tipos

Todo número pertence a um tipo, escrito no cartão (`painel/cartoes/`):
**resultado** (retrovisor: aconteceu), **direção** (volante: prevê o resultado
e pode ser movido esta semana), **par** (segura outra métrica que pode ser
forçada) e **confiança** (quanto se pode acreditar). É a distinção das 4
Disciplinas da Execução, que os documentos mantêm.

### §4.2 Os campos que entraram em 03/09 à noite (PR #936)

`acao` (obrigatório em resultado no andar 0), `direcao` (subir, descer, faixa),
`unidade`, `alvo_do_mes` (só na barra do mês). Faltam dois, que entram no
degrau 6: `frescor_maximo` (em dias; passa disso e o número é dito como velho)
e `dimensoes` (por onde o número se abre: site, turma, mês de entrada, canal).

### §4.3 O placar de doze, traduzido e honesto

Os documentos (Scale OS 1 §32; 2 Parte XVII; 3 §10) põem doze indicadores na
primeira tela. Nove dependem de venda ou anúncio (congelados) ou de células que
não existem. A régua de doze fica; cada cartão diz a verdade:

| # | Nos documentos | Aqui | Fonte hoje |
|---|---|---|---|
| 1 | Net New Buyers | pessoas que viraram alunas no mês | **tem** (`virou_aluno_em`) |
| 2 | Buyer Growth Rate | crescimento de um mês para o outro | **tem**, a partir do segundo mês |
| 3 | Buyer CAC | custo por pessoa que virou aluna | sem dados até haver gasto de anúncio digitado (medição do mantenedor) |
| 4 | Marginal CAC | custo do próximo aluno quando o gasto sobe | sem dados até três meses de gasto digitado |
| 5 | CAC Payback | dias até a compra pagar o custo de trazer a pessoa | sem dados até o site vender |
| 6 | Contribution Margin | margem de contribuição mensal | sem dados até o site vender (a estrela-guia econômica) |
| 7 | CM-LTV90/CAC | margem em 90 dias por real de aquisição | sem dados até o site vender |
| 8 | Core Conversion | pedidos de entrada que viraram aluno | **tem** (fila → liberação) |
| 9 | Activation D7 | primeira ação real em 7 dias | sem dados até a célula de cursos nascer; enquanto isso, "entrou pela primeira vez em 7 dias" quando a `metricas` receber o evento de entrada |
| 10 | Professional Outcome Rate | alunos com resultado profissional | sem dados até portfólio e cursos (a estrela-guia de valor) |
| 11 | Referral Revenue % | vindos por indicação | sem dados até existir indicação (nenhuma célula emite) |
| 12 | Validated Learnings / cycle | aprendizados validados no ciclo | **tem**, do livro: registros tipo `medicao` que respondem a experimentos |

Quatro acesos, oito desenhados. Não é fraqueza do painel: é a verdade, e cada
"sem dados" diz o que precisa existir.

---

## §5 A cadência: a semana, o mês, o ciclo, o ano

| Horizonte | O que acontece | Onde fica |
|---|---|---|
| **Diário** | ninguém se reúne; o painel mostra exceções (o sino, os incidentes, a caixa "precisa de você") | já existe |
| **Semanal, segunda-feira** | o **modo reunião**: a pauta guiada de oito passos dentro de `/admin/`, que termina escrevendo registros (compromissos com `vence_em_dias: 7`, decisões) e tarefas (`ci/fila.py criar`). Sem tabela nova: a reunião É os registros que ela produz | degrau 3 |
| **Mensal, dia 1** | a barra do mês fecha e vira a coorte daquele mês (foto D0); o placar mostra o mês fechado ao lado do que começa; as oito perguntas do pós-lançamento (v3 §159) viram um registro tipo `medicao` | degraus 0 e 10 |
| **A cada 12 semanas** | o **fechamento do ciclo**: a meta bateu ou não e por quê; as medidas de direção previram a meta ou não; o que a casa PARA de fazer (registro tipo `decisao`, obrigatório: o ciclo não fecha sem ele); a meta seguinte | degrau 13 |
| **Anual** | a revisão da tese (o que a escola é; o que morre; o que nasce) | fora deste plano; é conversa dele |

A pauta da segunda-feira, nos oito passos do Scale OS 1.1 §98 a §105,
traduzidos: as estrelas-guia (30 segundos); a meta e as medidas de direção
(ganhando?); os compromissos da semana passada (feito, parcial, não feito, cada
resposta é um registro que `responde_a`); os doze, só os desvios; a restrição
desta semana (a mesma, ou outra?); os experimentos (o que terminou, o que
ensinou); as decisões; os compromissos novos (um ou dois por pessoa, nunca
quinze). Quem participa: o mantenedor, a professora se ele quiser, e o robô da
sessão que preparou a leitura.

---

## §6 A base que o painel exige

### §6.1 Identidade única

Já existe: a pessoa da célula `identidade`, e todo evento das outras células
já carrega o id dela. Nenhum dado pessoal viaja em evento (`contracts/README.md`);
o envelope canônico da casa (`{event, version, event_id, occurred_at, data}`)
fica, e o `received_at` do Scale OS 1.2 §178 é do consumidor: a `metricas` o
grava ao receber. O `context` com IP e user agent não entra em evento.

### §6.2 O livro de fatos: a célula de medição

Decisão de 03/09 de manhã, mantida à noite. A `metricas` é consumidora, nunca
dona: recebe os eventos que as outras células publicam por contrato e os guarda
imutáveis (`ocorrido_em`, `recebido_em`, célula emissora, versão do esquema, id
externo para recusar duplicata). Fail-closed em fato financeiro: evento
inválido vai para a fila de eventos mortos, visível no painel com as três ações
do Scale OS 1.2 §183 (inspecionar, tentar de novo, descartar com motivo), e
vira registro de incidente. Um evento nunca se corrige; corrige-se
acrescentando. Medição digitada é evento também, com autoridade `mantenedor` e
a data. Ela responde por API própria (contrato congelado pelo Rito): fotos de
coorte, marcos por pessoa, contadores históricos, cobertura de rastreio,
conciliação, e as fotos semanais de que o bloco "o que mudou" precisa.

A gênese segue o rito de célula nova (`celulas.yml` declara `consome` só do que
liga, `armadilhas/224`; segunda instância de API proibida, `armadilhas/041`;
endpoint nasce exposto atrás do gateway e exige o guarda de 401 no mesmo PR; o
mapa `painel/ia/04` ganha a linha).

### §6.3 A restrição desta semana

A peça nova mais valiosa dos documentos (Scale OS 1 §8 a §10 e §33; 2 Parte
VII; 3 §26 a §30; 4 Parte X). Um cartão `restricao-da-semana` com: nome da
etapa, linha de base, valor de hoje, alvo, impacto estimado na meta, confiança,
evidência, e o gesto (os cinco passos da Teoria das Restrições: identificar,
explorar, subordinar, elevar, repetir).

O cálculo, sobre a jornada que existe hoje: as taxas de passagem entre
**cadastrou → pediu entrada → foi liberada → entrou pela primeira vez →
escreveu no fórum**, medidas nos últimos 7 e 28 dias, e a etapa cuja melhora
até a mediana histórica produziria o maior número de pessoas na meta. Isso é a
"suspeita", calculada. "Confirmada" só por registro tipo `decisao` do
mantenedor (Scale OS 1.2 §51: a IA propõe, o humano promove). Enquanto a
`metricas` não existe, as duas primeiras passagens vêm de `leads` e `alunos`
ao vivo, e as duas últimas dizem "sem dados até a medição receber o evento".

### §6.4 Marcos, não estados; coortes e fotos; scores por regra

Mantido da versão da manhã, porque nada nos documentos novos o contradiz: marco
é conquista com data (uma pessoa tem vários); dimensão é vista calculada sobre
os marcos; estado principal só existe para a fila de próxima ação e é regra
versionada; marco automático e marco assinado são coisas diferentes e o painel
diz qual é qual. Coorte é "quem virou aluna no mês tal" (a barra do mês
fechada é a coorte D0), depois por turma e por canal; fotos em D0, D7, D30,
D90, D180 e D365, cada uma com a versão de cada cartão; foto tirada não se
refaz. Score começa por regra explícita com versão, e cada mudança de regra é
evento.

### §6.5 A fase da escola e os portões

Os documentos põem a empresa em quatro fases (achar, provar, escalar, compor;
Scale OS 2 §4) e exigem portões antes de escalar (demanda, conversão,
economia, entrega, resultado, retenção, repetição, escala; 2 §60). Aqui a fase
é CALCULADA dos portões, nunca digitada: cada portão é um registro com
`evidencia` e `verificado_em`; nenhum provado é "achando"; até quatro é
"provando"; todos é "escalando". Sem venda a escola está em "achando", e o
cabeçalho diz isso.

### §6.6 A confiança (o andar que os documentos quase não têm)

Cobertura de rastreio (de cada evento do mapa de fatos, chegou nos últimos 7
dias?), frescor (`frescor_maximo` do cartão), conciliação diária como sonda
(`pagamentos` × `alunos` × `identidade` × livro de fatos; divergência é número
na tela e registro de incidente), confiança por indicador, linhagem (clicar no
número mostra o caminho até o evento), e a fila de eventos mortos à vista. As
regras de qualidade de dados (compra sem pessoa, matrícula sem pagamento, id
duplicado, data impossível) são ARQUIVOS, uma por regra, como os cartões.

### §6.7 As três latências da gestão

O único indicador dos documentos (Scale OS 1.1 §166 a §169) que já tem fonte
completa no dia em que este plano é escrito, e por isso entra cedo: **sinal →
decisão** (registro `pendencia` até a `resposta`), **decisão → execução**
(registro `decisao` até a tarefa reivindicada na fila) e **experimento →
aprendizado** (registro `medicao` encerrado até a `armadilha` ou a decisão
que ele gerou). Três cartões de tipo `confianca`, calculados do livro e da
fila. Medem a gestão, não a escola, e continuam funcionando quando todo o
resto estiver cego.

---

## §7 O que os documentos pedem e a casa já tem

O mapa completo (20 peças) está em `CONFRONTO-scale-os.md` §3. Em uma linha
cada: o motor de tarefas com travas, lotes e grupo de conflito é `fila/` +
`ci/fila.py` + `ci/reservar.py` + `celulas.yml`; o quadro dos robôs é
`/admin/caixa/robos/`; a exceção que chega decidível é o registro `pendencia`
com os quatro campos; a caixa de aprovações é "precisa de você"; a memória de
decisão com data de revisão é o registro `decisao` + `responde_a` +
`vence_em_dias`; os aprendizados validados são `armadilhas/` com sino; o
registro de métricas é `painel/cartoes/`; a auditoria é a da `admin` com
trigger; incidentes, contratos de evento com idempotência, mudança com plano de
volta, tudo no ar. **A lei anti-duplicação manda mapear, não reconstruir.**
Nenhum banco novo para tarefas, decisões ou aprovações: decidido em 29/08 com
três pareceres externos, e nada mudou.

---

## §8 A escada de entrega

Um degrau por PR (orçamento de 15 arquivos, Ritos de Contrato, evidência
vermelho → verde). A ordem mudou em relação à manhã: os documentos mandam
começar pelos contratos e não pela home bonita (Scale OS 1.2 §265), mas também
mandam que a primeira tela seja a que decide (1.1 §159: placar, meta, restrição,
tarefas, qualidade de dados). A escada abaixo faz as duas coisas: **o que já
tem fonte ao vivo sobe primeiro para a capa; a célula de medição nasce em
paralelo, e o que depende dela vem depois.** Itens ❄ estão congelados pela
decisão de 22/08 e entram desenhados.

| Degrau | O que nasce | O que já existe | Depende de |
|---|---|---|---|
| **0. O placar** | A barra do mês e a meta do ciclo, contadas por `virou_aluno_em`; os cartões com `acao`, `direcao`, `alvo_do_mes`. | **FEITO**: PRs #924 (manhã), #933 e #934 (o rito), #936 (a reforma). | nada |
| **1. A restrição desta semana** | O cartão `restricao-da-semana` e o bloco 2 da capa; as taxas cadastro → pedido → liberação medidas ao vivo de `leads` e `alunos`; "suspeita" calculada, "confirmada" por registro. | a jornada, as duas células | 0 |
| **2. A direção da semana** | Os dois cartões de direção da **sala de espera** (`pedidos-de-entrada-por-semana`, `liberacoes-em-48h`) com a meta da semana e a sequência; o compromisso como registro com `vence_em_dias: 7`; o veredito da semana passada calculado; o bloco 3 da capa. Desde 05/09/2026 eles medem a venda feita FORA do site (quem chega já comprou e espera confirmação), e ao lado deles ficam os dois cartões do caminho da venda, desenhados e sem número enquanto o checkout estiver congelado. | o livro, `leads`, `alunos` | 0 |
| **3. O modo reunião** | A pauta de segunda em `/admin/reuniao/`, oito passos, que termina escrevendo registros e tarefas pelos caminhos que existem; o atalho na capa. | o livro, a fila | 1, 2 |
| **4. O placar de doze e as estrelas-guia** | Os doze cartões do §4.3 e os dois das estrelas, cada um com fonte ou com `sem_fonte_porque`; os blocos 6 e 7 da capa; o teto de nove blocos como teste-guarda. | os cartões | 0 |
| **5. As três latências** | Três cartões de tipo `confianca` calculados do livro e da fila (§6.7); a regra de cálculo em `painel/logica.js` com teste. | o livro, a fila | 4 |
| **6. O que mudou** | Os campos `frescor_maximo` e `dimensoes` no cartão; a foto semanal dos cartões com fonte (no livro, tipo `medicao`, gravada pelo modo reunião até a `metricas` existir); o bloco 5 da capa. | 3, 4 | 3, 4 |
| **7. A célula de medição** | Gênese da `metricas` (§6.2): recebe `identidade.pessoa-cadastrada`, `quiz.completado`, `forum.*`; guarda imutável; fila de eventos mortos; API de leitura com guarda de 401; linha em `painel/ia/04`. | contratos de evento, rito de gênese | 0 (em paralelo com 1 a 6) |
| **8. Os fatos que faltam** | Contratos de evento de `alunos` (pediu entrada, liberada, ativa, suspensa, encerrada, reembolsada) e de `leads`; a `metricas` os recebe. E **"como você conheceu a escola?"** no pedido de entrada, opcional (Rito de Contrato na `alunos`): a única atribuição que não depende de anúncio, semente das coortes por canal. | as células, a outbox de `alunos` | 7 |
| **9. Marcos e dimensões** | Marcos automáticos calculados na `metricas`; marco assinado como registro; a dimensão "aprendizado" ligada ao mapa da jornada; a restrição passa a ler na `metricas` as passagens do **caminho da venda** (chegou na página de venda → comprou → foi confirmada → entrou pela primeira vez), e não mais só as da sala de espera, que é o que a `alunos` sabe responder hoje. | `/admin/escola/jornada/` | 8 |
| **10. Coortes e fotos** | A barra do mês fechada vira coorte D0; fotos D7 a D365; coorte por turma e por canal; a tabela na capa (um clique abaixo do bloco 1). | 9 | 9 |
| **11. A confiança** | Cobertura, frescor, conciliação diária como sonda, confiança por indicador, linhagem, regras de qualidade como arquivos, a fila de eventos mortos à vista (§6.6). **E o alerta como objeto** (quinto documento §54 e §55): `severidade`, `confianca`, `impacto_no_negocio` e `resolvido_em`, com a regra de que nem todo desvio vira alerta, para a caixa dele não morrer de fadiga. | sondas do sistema imunológico, sino | 7 |
| **12. O laboratório** | Experimento como registro tipo `medicao` (problema, hipótese, métrica primária, guardas, prazo); resultado como registro que `responde_a`; a tela com rodando, encerrados, vencedores, inconclusivos; a velocidade de aprendizado validado (o 12º do placar de doze); o bloco 8 da capa. Teste A/B com variante por pessoa fica desenhado até haver contagem de visitas (decisão dele em aberto desde 25/08). | o livro | 4 |
| **13. O fechamento do ciclo** | A tela do fechamento das 12 semanas: a meta e o porquê; as medidas de direção previram?; **o que paramos de fazer** (registro `decisao` obrigatório: sem ele o ciclo não fecha); a meta seguinte gravada no cartão e no livro; a fase da escola recalculada dos portões (§6.5). **O guarda deste degrau é o teste do laço inteiro** (quinto documento §81): um cenário automatizado que percorre ciclo ativo, meta, medidas de direção, medição, restrição detectada, experimento, semana aberta, tarefa gerada, tarefa executada, semana encerrada, aprendizado registrado e placar atualizado. Os pedaços já são testados; o laço, não. | 3, 10 | 3, 10 |
| **14. A matemática** ❄ | A razão de receita (taxa, imposto, reembolso, custo variável) e as equações por camada; os oito cartões do placar de doze que dependem de venda acendem. Desenhado agora, aceso só quando o site vender. | contratos de pagamento | 7, e a ordem dele |
| **15. A fila de próxima ação** | Regra por dimensão, versionada; roteador automação, humano ou robô; tarefas no balcão; "sucesso do aluno antes de venda" como guarda; tetos de contato como parâmetro com dono. | `mensageria/apps/jornadas`, `fila/` | 9, 3 |
| **16. O robô analista** | UM robô, por último (Scale OS 1.2 §218), que escreve registros tipo `nota` com o contrato de saída dos documentos (afirmação, evidência, confiança, alternativas, próximo passo) e vira `pendencia` quando pede decisão; o brief da segunda-feira; o "o que estou deixando passar?" do fechamento de ciclo. Pela mesma chave que o fórum vai usar. | o livro, a chave da Anthropic (pendência dele) | 5, 11, 12 |
| **17. Rede de talentos e B2B, à mão** | Contagens digitadas (alunos selecionados, estúdios parceiros, encaixes) como medição; o laço de talentos sai do cinza. | nada | 13 |
| **18. Integrações de fora** | Gasto de anúncio e alcance por API em vez de digitado; WhatsApp pela API oficial. | nada | credenciais e plano pago: **passo do mantenedor** |
| **19. O grafo causal** | A tarefa da fila passa a declarar QUE NÚMERO ela move (ou a declarar-se `manutencao`, o `whirlwind` do documento); o painel ganha o caminho de volta, de um número para as tarefas que trabalham nele. O guarda do degrau é o teste do §97 do quinto documento: de uma tarefa se chega ao número, e do número se volta às tarefas. | `fila/`, `ci/fila.py`, `painel/cartoes/`, `painel/logica.js` | 0 (não depende de célula nova nem de venda) |

Os degraus 1, 2, 4 e 5 nascem sem célula nova e sem venda: tudo o que eles
precisam já responde ao vivo hoje. É por eles que a capa deixa de ser um
número só e vira uma cabine na primeira semana.

---

## §9 O que NÃO se constrói ainda

- **Nenhum tile de venda, checkout, ticket médio, CAC, payback ou margem
  aceso** até a ordem do mantenedor. Desenhado, sim; aceso, não.
- **Nenhuma jornada dupla** aluno/pagador. Escola 18+.
- **Nenhum CRM externo**, nenhuma cópia de tabela de pessoa para a `metricas`.
- **Nenhuma nota composta** no andar zero, nem no cabeçalho.
- **Nenhum banco novo** para tarefas, decisões, aprovações ou aprendizados.
- **Nenhuma tabela de papéis de acesso** (onze papéis do Scale OS 1.2 §141):
  `ADMIN_EMAILS` é a porta, e robô não tem crachá de sessão.
- **Nenhum aprendizado de máquina, previsão ou simulador** antes de doze meses
  de coorte. Descritivo, depois diagnóstico. Regras explícitas antes de modelo.
- **Nenhum marketplace automatizado**: talentos começam à mão.
- **Nenhum alvo inventado** para métrica em descoberta: a primeira medição vira
  a base, e a base vira o alvo do ciclo seguinte.
- **Nenhum "reembolso zero" como meta.** Reembolso baixo é medida de saúde.
- **Nenhum envio de lista de alunos para plataforma de anúncio** sem decisão
  dele e consentimento registrado.
- **Nenhum interruptor por porcentagem de público** (feature flag com rollout):
  tela nova entra por PR, atrás da porta, para um leitor.
- **Nenhum nível de autonomia novo para robô.** Os níveis do quinto documento
  (§87) já são a prática desta casa, e vale escrevê-los uma vez: o robô
  analista do degrau 16 recomenda (nível 1); caminho CODEOWNERS exige mandato
  do despacho (nível 2); um despacho da fila executa o reversível dentro de
  limites (nível 3); e o nível 5 não existe por construção, porque quem
  mergeia é a pista, não o agente.

---

## §10 O que espera pelo mantenedor

Cada item vira registro de `pendencia` no PR do degrau que o exige, e a caixa
"precisa de você" o cobra. Nenhum é bloqueio dos degraus 1 a 6.

1. **A meta do mês fixada à mão**, quando quiser (`alvo_do_mes` no cartão
   `compras-no-mes`); até lá a tela deriva da linha reta (setembro: 131;
   outubro: 151).
2. **O nome definitivo da célula de medição** (nome de trabalho `metricas`).
   Degrau 7.
3. **A restrição confirmada**, toda semana, por registro. Degrau 1.
4. **"Como você conheceu a escola?"** no pedido de entrada é Rito de Contrato:
   sessão com ele presente. Degrau 8.
5. **A chave da Anthropic** (já pendente para o fórum). Degrau 16.
6. **A API oficial do WhatsApp** e as credenciais de anúncio. Degrau 18.
7. **A ordem de vender**, que descongela o degrau 14. Sem prazo, por decisão dele.
8. **A professora como leitora do painel** (com os mesmos poderes, ou só
   lendo): decisão futura, fora deste plano.

---

## §11 Quem faz valer (os mecanismos)

Garantia escrita em prosa apodrece (`RETROSPECTIVA-FASE-D.md`, padrão 2).

| Regra | Mecanismo |
|---|---|
| Número sem cartão não aparece | `services/admin/apps/core/placar.py::validar`; `tests/test_placar.py` com o caso que DEVE reprovar |
| Resultado no andar 0 sem `acao` | idem (PR #936) |
| Composto nunca no andar 0 | idem |
| Conta pela data certa, no fuso certo, sem zero inventado | `tests/test_placar.py` (fuso, partida, reembolsada, sem data, sem campo) |
| Fórmula mudou sem versão | teste sobre os cartões; a versão viaja na foto de coorte |
| A capa não passa de nove blocos | teste-guarda no degrau 4 |
| Restrição "confirmada" só por registro dele | regra de cálculo com teste, degrau 1 |
| O ciclo não fecha sem "o que paramos de fazer" | regra de cálculo com teste, degrau 13 |
| Evento não se edita; fato financeiro inválido vai para a fila de mortos | a `metricas`, degraus 7 e 11 |
| Conciliação diária | sonda; sonda vermelha abre incidente |
| Venda antes de sucesso do aluno é recusada | teste-guarda na fila de próxima ação, degrau 15 |
| Compromisso vencido aparece | `vence_em_dias`, já existente |
| Célula nova aparece no mapa para IA | `ci/tests/test_painel_ia_atualizado.py` |
| A LEITURA deste plano | sem mecanismo (`ci/leis-sem-mecanismo.txt`); quem constrói um degrau cita este plano no registro |

---

## §12 Glossário, para quem não é do ramo

- **Meta Crucialmente Importante (MCI):** a única meta grande de um ciclo, no
  formato "de X para Y até quando". Hoje: de 0 para 1000 pessoas até 15/12.
- **Medida de resultado e medida de direção:** a primeira se vê depois
  (retrovisor: quem comprou); a segunda prevê a primeira e pode ser movida
  esta semana (volante: pedidos de entrada, liberações rápidas).
- **Restrição (gargalo):** a etapa da jornada que, se melhorar, move a meta
  inteira. Uma por vez: melhorar o resto é encher um cano furado.
- **Coorte:** quem virou aluna no mesmo mês (ou pela mesma turma, ou pelo mesmo
  canal). Acompanhar a coorte é perguntar "o que aconteceu com quem entrou em
  setembro".
- **Ciclo:** 12 semanas com uma meta só. No fim, o que bateu, o que ensinou, o
  que se para de fazer, e a meta seguinte.
- **Estrela-guia:** o número de longo prazo acima de toda meta: alunos com
  resultado profissional; margem mensal. Hoje sem fonte.
- **Marco:** uma conquista com data. Uma pessoa acumula marcos.
- **Portão:** uma pergunta que precisa de prova antes de a escola crescer.
- **Fail-closed:** quando algo está estranho, o sistema para e avisa, em vez de
  seguir e adivinhar.
- **Latência da gestão:** quanto tempo passa entre um sinal e a decisão, entre a
  decisão e o começo do trabalho, e entre o fim de um experimento e o
  aprendizado incorporado.
