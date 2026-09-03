# PLANO | o painel de gestão do negócio (Meshcraft 10X)

publico-para-ia: true

**Escrito em 03/09/2026**, a partir de: três documentos de arquitetura que o
mantenedor trouxe de uma IA externa (Arquitetura de Receita Meshcraft 10X v1,
v2 "Blueprint Econômico" e v3 "Revenue Operating System"), dois textos de apoio
sobre métricas de operação perpétua, cinco decisões do mantenedor em pergunta
estruturada (03/09/2026, listadas no §1) e a leitura da arquitetura em
`origin/main`. Molde: `docs/decisoes/PLANO-CELULA-GAMIFICACAO.md` (a escada) e
`docs/decisoes/PLANO-AREA-ADMIN.md` (as muralhas aplicadas).

Este documento NÃO é um painel: não guarda estado e não se atualiza sozinho.
Quem responde "isto foi feito?" é o livro (`painel/registros/`) e a fila
(`fila/`). O que este plano descreve como "andar zero", "cartão de métrica" e
"livro de fatos" só existe quando um PR o construir e um registro o provar.

Os três documentos de origem estão em inglês técnico e pensam numa empresa com
equipe comercial, dez produtos e um CRM contratado. Este plano traduz cada
ideia para a casa que existe: um mantenedor leigo, uma professora, robôs, um
curso, uma turma liberada por lista, e uma constituição que já decidiu como
fato se guarda e como estado se calcula. Onde a tradução mudou a ideia, o
motivo está escrito ao lado.

---

## Parte 0 | A visão, em resumo

O funil clássico pensa "anúncio, lead, lançamento, curso, fim", e cada mês
recomeça do zero. A arquitetura 10X pensa numa jornada inteira: a pessoa
descobre, experimenta, compra, aprende, monta portfólio, consegue o primeiro
resultado profissional, fica na comunidade, se especializa, é encontrada por um
estúdio, e traz outra pessoa. Cada ciclo deixa ativos (clientes, dados,
comunidade, casos, indicações), e o ciclo seguinte começa mais forte que o
anterior. O curso deixa de ser o negócio inteiro e vira a porta principal.

O que este plano constrói é o **instrumento de medição** dessa máquina. A
própria arquitetura v2 diz, no seu roteiro econômico, que a primeira etapa é
observabilidade ("sem isso, estamos dirigindo sem painel"), e a v3 põe as seis
primeiras fases do seu sistema exatamente nisso: identidade única, livro de
fatos, razão de receita, estado do cliente, coortes e painel executivo. Logo, o
painel de gestão não é um projeto paralelo à arquitetura. Ele é a Fase 1 dela.

As quatro leis que o painel obedece já são leis da casa, e nasceram do painel
do dono (`painel/LEIA-ME.md`):

1. **Acontecimento se acrescenta; estado se calcula.** Fato é evento
   (cadastrou, assistiu, comprou, cancelou), gravado uma vez e nunca editado.
   Métrica, marco, coorte e cor de saúde são vistas calculadas por cima.
2. **Verde exige prova conferida.** Um motor só fica verde com evidência e
   data de conferência. Sem prova, o painel diz "não comprovado".
3. **Nenhum fato mora em dois lugares.** Não existe lista mantida à mão ao
   lado de um cálculo. Se o painel não mostra algo, a mudança é na regra de
   cálculo, por PR, com teste-guarda.
4. **Número que não se pode confiar é pior que número nenhum.** Todo
   indicador carrega a sua confiança, e o painel diz em voz alta quando está
   cego. Este projeto já foi enganado por painel verde que mentia
   (`docs/decisoes/RETROSPECTIVA-FASE-D.md`, padrão 1).

---

## §1 As decisões do mantenedor que este plano executa

| Data | Decisão | Consequência neste plano |
|---|---|---|
| 22/08/2026 | **Pagamento por último.** Nada de checkout, pagamento ou venda até ele dizer que o site vai vender. | Toda camada de venda entra DESENHADA (motor, equação, cartões) e marcada "sem dados até o site vender". Nenhum PR de venda nasce deste plano. |
| 25/08/2026 | **Sempre completo, nunca a versão reduzida** (`DECISAO-filosofia-de-escopo.md`). | O destino é o sistema inteiro da v3. O caminho é a escada do §9, um degrau por PR. Fatiar não é reduzir. |
| 25/08/2026 | **Contadores em tempo real, por HTTP, não por evento** (`PLANO-AREA-ADMIN.md` §5). | Vale para os contadores do painel (quantos alunos agora). Coorte e LTV são história acumulada, outra natureza de dado, e por isso ganham o livro de fatos (§5). As duas coisas convivem: o contador diz "agora", o livro diz "desde quando". |
| 30/08/2026 | **A escola é 18+, sem menores.** Reconfirmado em 03/09/2026 diante da arquitetura v1, que assumia pai ou mãe como pagador. | Sai a jornada dupla aluno/pagador, saem "responsável", "idade" e "proteção de menores" das três arquiteturas. Se um dia ele abrir para menores, entra como fase nova, sem refazer o resto. |
| 03/09/2026 | **Os fatos do negócio moram numa célula nova, só para isso.** | Nasce a célula de medição (§5.2), consumidora dos eventos das outras células por contrato. A `admin` continua sendo a porta, não a memória. |
| 03/09/2026 | **A própria plataforma é o CRM.** Nenhuma ferramenta externa de CRM. | Identidade, leads, mensageria e o livro de fatos fazem o papel. Só o que nasce fora (gasto de anúncio) entra digitado, como medição com data. |
| 03/09/2026 | **A primeira Meta Crucialmente Importante é o NÚMERO DE ALUNOS na plataforma.** | O andar zero do painel nasce com esse número. O "de X para Y até quando" fica no §4.1, com o Y e a data como pendência dele. |
| 03/09/2026 | **Plano-mãe com a escada inteira.** | Este documento cobre o painel e sua base, e traz as dez fases da v3 dizendo o que já existe e o que falta. As fases de continuação ganham plano próprio, como a gamificação teve o dela. |

Decisões anteriores que este plano respeita sem reabrir: reembolso tira o
acesso (31/08); a gestão mora em `/admin` (`DECISAO-a-gestao-da-caixa-mora-no-admin.md`);
o lançamento perpétuo tem área própria em `/admin/perpetuo/`
(`DECISAO-a-area-do-lancamento-perpetuo.md`); o mapa da jornada do aluno em
`/admin/escola/jornada/` já mostra oito paradas com "o que a pessoa vê"
(`DECISAO-o-mapa-da-jornada-do-aluno.md`); o portfólio do aluno tem plano
guardado, sem construção autorizada (`PLANO-PORTFOLIO-DO-ALUNO.md`).

---

## §2 A taxonomia: quatro tipos de número, e um cartão para cada um

Os três documentos de origem somam perto de cem indicadores e nenhum separa
**o que se olha** de **o que se move**. Essa é a distinção das 4 Disciplinas da
Execução (Covey, McChesney e Huling): medida de resultado é retrovisor,
medida de direção é volante. Um painel com cem retrovisores é grande e inútil.
O painel completo é o que tem POUCAS medidas de direção com dono, limiar e
ação, e todas as de resultado atrás delas, um clique abaixo.

Todo número do painel pertence a um destes quatro tipos, e o tipo vai escrito
no cartão:

| Tipo | O que é | Exemplo | Onde aparece |
|---|---|---|---|
| **Resultado** | Aconteceu; só se vê depois. | Alunos ativos, margem de contribuição, LTV em 90 dias, cancelamentos. | Andar 2 (saúde da máquina) e andar 3 (matemática). |
| **Direção** | Prevê o resultado E pode ser movida esta semana. | Pedidos de entrada por semana, alunos que fizeram o primeiro asset até o dia 7. | Andar 1 (a semana), com o compromisso ao lado. |
| **Par** | A métrica que segura a outra. Toda métrica que pode ser forçada tem uma. | Conversão sobe, reembolso tem que ficar parado. Alunos sobem, alunos ATIVOS em 30 dias tem que subir junto. | Sempre ao lado da métrica que protege, nunca sozinha. |
| **Confiança** | Quanto o número pode ser acreditado. | Cobertura de rastreio, frescor, divergência entre fontes. | Andar 4, e como selo em todo tile. |

**O cartão de métrica.** Nenhum tile existe sem cartão, e o gerador do painel
se recusa a desenhar um número sem ele (fail-closed, como o painel do dono se
recusa a aceitar um registro inválido). O cartão é um arquivo por métrica,
versionado no Git, com estes campos, na tradução direta da v2 §65 e v3 §93:

```
nome:            alunos-na-plataforma
tipo:            resultado | direcao | par | confianca
pergunta:        "Quantas pessoas são alunas hoje?"   (para leigo, sem sigla)
definicao:       matrículas em status de permissão (alunos.Matricula)
formula:         contagem, por site
fonte:           célula alunos, operação de leitura de contadores
autoridade:      alunos                (quem tem o DIREITO de declarar este número)
dono:            mantenedor
frequencia:      tempo real (HTTP) | diária | por ciclo
par:             alunos-ativos-30d
limiar_ambar:    ...                   (ou "a definir pela primeira medição")
limiar_vermelho: ...
versao:          1
desde:           2026-09-..            (data em que a versão passou a valer)
```

Regras que os testes-guarda impõem: cartão sem `par` só passa se `tipo` for
`confianca`; cartão sem `autoridade` reprova; mudar `formula` sem subir
`versao` reprova; e a `versao` fica gravada em cada foto de coorte, porque uma
fórmula que muda em silêncio torna o passado incomparável (v3 §23).

**Composto nunca no placar.** O "Placar de Saúde 87/100" da v3 §185, o Índice
de Qualidade de Receita (v2 §49) e a Pontuação de Alocação de Capital (v2 §46)
são úteis para comparar canais, mas um índice esconde qual componente se
mexeu. Regra: número composto só aparece com os componentes ao lado, e nunca
no andar zero. Guarda: teste que reprova cartão de tipo composto com
`andar: 0`.

---

## §3 Os cinco andares do painel

Não existe um painel gigante (v3 §72 concorda). Existem cinco andares, do que
cabe numa tela de celular até o que exige uma tarde. O mantenedor abre no
andar zero e desce só se quiser.

### Andar 0 | O placar

Uma tela, uma meta, um número, uma linha de alvo, e a resposta em uma palavra:
**estamos ganhando ou perdendo**. É o "placar convincente" da terceira
disciplina de Covey. Conteúdo: a Meta Crucialmente Importante da fase em curso
(§4.1), no formato "de X para Y até quando", com o valor de hoje, o alvo desta
semana e a distância. Nada mais. Sem sigla, sem índice, sem gráfico de dez
séries.

### Andar 1 | A direção da semana

As medidas de direção da meta (no máximo duas por resultado-chave), cada uma
com o compromisso da semana ao lado e o veredito da semana passada: cumprido
ou não. É a única parte do painel que **pede ação** do mantenedor, e é também
onde entram os alertas que passaram pelo filtro de cansaço (§7.3) e a caixa
"precisa de você", que já existe no painel do dono e é calculada (pedido sem
resposta).

### Andar 2 | A saúde da máquina

Os onze motores da arquitetura (audiência, valor grátis, entrada paga, core,
resultado do aluno, comunidade, especialização, acelerador, rede de talentos,
B2B, indicação), cada um com uma cor e um modo:

| Cor | Significa | Regra |
|---|---|---|
| Verde | economia dentro dos parâmetros | só com os sete portões do §7.1 com prova registrada |
| Âmbar | deterioração | alguma métrica de resultado cruzou o limiar âmbar do cartão |
| Vermelho | quebrado, não escalar | cruzou o limiar vermelho, ou um portão perdeu a prova |
| Azul | em experimento, ainda sem dado suficiente | modo descoberta ou validação |
| Cinza | não iniciado | nenhum evento do motor jamais chegou ao livro |

Abaixo dos motores, os cinco blocos do painel executivo da v2 §44
(crescimento, receita, resultado do aluno, retenção, volante), cada um com três
ou quatro números de resultado e seus pares. E, abaixo deles, **a máquina**: o
funil por marcos (§5.4), com a taxa de passagem entre cada marco, o tempo
médio entre marcos, e ao lado de cada marco a fila de próxima ação (quem está
parado ali e o que fazer). Este é o ponto em que o painel deixa de ser
relatório e vira cabine: ele produz a lista de com quem falar hoje, e essa
lista é trabalho que os robôs já sabem pegar no balcão (`fila/`).

No dia em que este plano nasce, o retrato honesto do andar 2 é: audiência e
valor grátis em azul, core em azul (a turma entra por liberação, sem venda),
resultado do aluno em azul, comunidade em azul (fórum no ar), e os outros seis
em cinza. Onze motores desenhados, quatro acesos. Isso não é fraqueza do
painel: é a verdade, e a v2 §51 diz que o ecossistema não precisa amadurecer
inteiro ao mesmo tempo.

### Andar 3 | A matemática de cada camada

Para cada produto ou motor, a equação escrita na tela, com os números de hoje
encaixados:

```
entradas  ×  taxa de passagem  ×  ticket  −  custo variável  =  margem de contribuição
                                             tempo até recuperar o custo de aquisição: N dias
```

A linha fica vermelha quando a conta não fecha. É a "matemática unitária que
precisa fechar em cada camada" da v1, virando mecanismo em vez de frase. As
fórmulas vêm da v2 (margem de contribuição §2, razão de recuperação da
aquisição §6, teto de custo de aquisição §22, tempo de recuperação §23,
margem por hora de entrega §7) e cada uma tem cartão.

**As taxas não vieram nas arquiteturas**, e este plano não as inventa. A v2 traz
fórmulas e preços hipotéticos, mas nenhuma hipótese numérica de passagem entre
marcos. Motor em modo descoberta nasce com a equação escrita e o alvo marcado
"a definir pela primeira medição"; o primeiro ciclo completo grava a base, e a
base vira o alvo do ciclo seguinte. Alvo inventado hoje viraria o número que o
painel persegue amanhã.

Aqui mora também o **gargalo**: a v3 §165 pede que o sistema aponte qual
restrição limita mais o crescimento agora (tráfego, qualidade de lead,
checkout, ativação, entrega, retenção), e a regra da teoria das restrições:
atacar a restrição dominante antes de aumentar o fluxo. O andar 3 termina com
uma linha só: "o gargalo desta semana é X, porque Y". É o que a v3 §185 chama
de "próximas alavancas".

### Andar 4 | A confiança

O andar que os três documentos de origem quase não têm, e que este projeto
aprendeu a exigir do jeito caro. Mostra:

- **Cobertura de rastreio:** de cada evento do mapa de fatos (§6), quantos
  chegaram nos últimos 7 dias, e quais nunca chegaram.
- **Frescor:** para cada tile, quando o número foi calculado, e para cada
  medição digitada à mão, quando e por quem.
- **Conciliação entre fontes** (v3 §90): o que a célula de pagamentos diz que
  vendeu contra o que a de alunos diz que matriculou contra o que o livro de
  fatos registrou. Divergência é número na tela, não segredo. A conciliação
  roda como sonda diária, e sonda vermelha vira registro de incidente no livro.
- **Confiança por indicador** (v3 §92): um percentual ao lado do número, que
  cai quando a cobertura cai. O painel não mostra "conversão 4,2%" com
  precisão de casa decimal quando um terço dos eventos não chegou.
- **Linhagem** (v3 §145): clicar num número mostra de onde ele veio, até o
  evento.

---

## §4 As 4 Disciplinas da Execução e os OKRs, encaixados

Os dois sistemas brigam quando se sobrepõem. Aqui eles se encaixam por camada:

| Camada | Instrumento | Quantidade | Cadência |
|---|---|---|---|
| A meta | Meta Crucialmente Importante (4DX, disciplina 1) = o Objetivo do OKR do trimestre | uma por vez, no máximo duas | trimestral |
| A prova | Resultados-Chave do OKR = medidas de resultado | no máximo três por meta | trimestral, lido toda semana |
| A aposta | Medidas de direção (4DX, disciplina 2) | no máximo duas por resultado-chave | semanal |
| O placar | Andar 0 (4DX, disciplina 3) | um | sempre aberto |
| A responsabilidade | Cadência de responsabilidade (4DX, disciplina 4) | uma reunião | semanal |

### §4.1 A primeira Meta Crucialmente Importante: o número de alunos

Decisão do mantenedor em 03/09/2026. No formato de Covey:

> **De X para Y alunos na plataforma até DD/MM/AAAA.**

- **X** é medido, não digitado: a contagem de matrículas em status de
  permissão na célula `alunos` (a lista de PERMISSÃO de `Matricula`, que decide
  quem "é aluno"; `DECISAO-fila-de-liberacao.md`). É o mesmo número que o
  mapa da jornada já mostra em `/admin/escola/jornada/`.
- **Y e a data** são dele, e entram no livro como registro de decisão. Até lá
  o andar zero mostra X e a frase "alvo: aguardando o mantenedor", que é
  honesto e cobra a decisão pela caixa "precisa de você".
- **O par obrigatório:** alunos ATIVOS em 30 dias. Sem o par, a meta se
  cumpre liberando contas que nunca entram. O placar mostra os dois, lado a
  lado, e "ganhando" exige que os dois subam.

Medidas de direção candidatas (a escolha final é do primeiro ciclo, porque
medida de direção que não move o resultado se troca):

1. **Pedidos de entrada por semana** (pessoas que pediram para entrar pela
   fila de liberação). É a torneira do número.
2. **Liberações feitas em até 48 horas** do pedido. É a parte que depende só
   da casa, e é onde um robô ou o mantenedor age.
3. **Alunos que fizeram a primeira ação real em 7 dias** (primeira aula ou
   primeiro asset, conforme a célula de cursos existir). É o que protege o par.

Resultados-chave sugeridos para o trimestre, a confirmar com ele: alunos na
plataforma (a meta), alunos ativos em 30 dias (o par), e tempo médio do pedido
até a liberação (a fricção).

### §4.2 A cadência de responsabilidade

Toda segunda-feira, uma reunião curta com pauta fixa: as dez perguntas da v2
§62 (aquisição, conversão, caixa, margem, aprendizado, resultado, retenção,
ascensão, indicação, mercado), lidas do painel, não de memória. Cada resposta
que exige ação vira **compromisso**: um registro no livro, tipo `nota`, com
`vence_em_dias: 7`. Na semana seguinte, o painel calcula sozinho: compromisso
com registro de resposta é "cumprido"; compromisso vencido sem resposta é "não
cumprido", e aparece no andar 1. Nada é mantido à mão. Quem participa: o
mantenedor, a professora, e o robô da sessão que preparou a leitura. Em lote,
é a sessão-maestro quem consolida (`RUNBOOK-LOTES.md`).

O ciclo mensal do lançamento (v2 §7 e v3 §158) tem o seu próprio fechamento:
um lançamento não termina no fechamento do carrinho, termina quando a coorte
dele tem foto de 30 dias no livro. O pós-lançamento (v3 §159, as oito
perguntas) é um registro de tipo `medicao`, e os deltas do ciclo (v3 §160)
saem calculados de duas fotos de coorte, nunca digitados.

---

## §5 A base que o painel exige

### §5.1 Identidade única

A v3 §8 pede um "id global do cliente" porque uma pessoa aparece com cinco
identidades (Instagram, telefone, e-mail do checkout, id do curso, id do CRM).
Nesta casa esse id já existe: é a pessoa da célula `identidade`
(`DECISAO-celula-de-identidade.md`), e todo evento das outras células já
carrega o id dela. As identidades secundárias (telefone, usuário do Roblox,
perfil do Instagram) são dado de pessoa e ficam na `identidade`, por contrato,
nunca copiadas para a célula de medição. O que a medição guarda é o id e o que
aconteceu com ele.

Visitante anônimo (antes do cadastro) é a única identidade que não existe
hoje. O plano da área admin já decidiu que contagem de visita é despacho
próprio, com pergunta de privacidade embutida (`PLANO-AREA-ADMIN.md` §4.6b).
Este plano não promete visitas. O funil do andar 2 começa em "cadastrou".

### §5.2 O livro de fatos do negócio: a célula de medição

Decisão do mantenedor em 03/09/2026: célula nova, só para isso. Nome de
trabalho: **`metricas`** (a gênese pode renomear, como a gamificação renomeou;
`economia` está tomado pela gamificação). O que ela é:

- **Consumidora, nunca dona.** Ela não lê o banco de ninguém (lei da casa,
  `PLANO-AREA-ADMIN.md` §5) e não cria fato nenhum sobre pessoa. Ela recebe
  os eventos que as outras células já publicam por contrato
  (`contracts/eventos/*.json`) e os guarda **imutáveis**, com `ocorrido_em`,
  `recebido_em`, célula emissora, versão do esquema e id externo para recusar
  duplicata (v3 §136).
- **Fail-closed em fato financeiro** (v3 §144): evento de pagamento inválido
  não é "adivinhado"; vai para a fila de exceção e vira registro de incidente.
  Melhor "não processado" que "processado errado".
- **Um evento nunca se corrige; corrige-se acrescentando** (v3 §6):
  `reembolso.concluido`, `atribuicao.corrigida`, `identidade.unida`.
- **Medição digitada é evento também**, com autoridade `mantenedor` e a data
  de quando foi digitada: gasto de anúncio, alcance, horas de atendimento. O
  cartão da métrica diz que a fonte é manual, e o andar 4 mostra o frescor.
- **Ela tem uma caixa de saída própria** para o que ela calcula e as outras
  precisam saber (marco conquistado, coorte fechada), pelo mesmo mecanismo de
  outbox que `alunos` já usa.

O que ela responde por API (contrato próprio, congelado pelo Rito): fotos de
coorte, marcos por pessoa, contadores históricos, cobertura de rastreio,
conciliação. A `admin` consome isso por HTTP em tempo real, como consome as
outras (a decisão de 25/08 continua valendo para o ato de mostrar). A
diferença é só de onde o número vem: o contador "agora" vem da célula dona
(`alunos` diz quantos alunos); o número "desde quando" vem da `metricas`.

A gênese segue o rito de célula nova: `celulas.yml` declara `consome` só do
que a gênese de fato liga (`armadilhas/224`), a segunda instância de API é
proibida (`armadilhas/041`), o endpoint nasce exposto atrás do gateway e exige
o guarda de 401 sem token no mesmo PR, e o mapa `painel/ia/04` ganha a linha
da célula (teste `test_painel_ia_atualizado.py`).

### §5.3 A razão de receita

A v3 §40 pede pedido, pagamento, reembolso, estorno, taxa, imposto, comissão e
custo variável. Pedido e pagamento já têm dono (`checkout` e `pagamentos`) e
contratos de evento (`pedido.criado`, `pagamento.aprovado`,
`pagamento.recusado`, `pix.expirado`). O que falta são os DESCONTOS da
margem (taxa do meio de pagamento, imposto, reembolso concluído, custo
variável de entrega), que hoje não existem em evento nenhum.

**Tudo isto está congelado** pela decisão de 22/08. O plano deixa a razão
desenhada: a margem de contribuição por pedido é calculada na `metricas` a
partir dos eventos de pagamento mais uma tabela de parâmetros com dono (taxa
do meio, alíquota), versionada como os cartões. Quando o site for vender, a
escada do §9 tem o degrau pronto, e o andar 3 acende.

### §5.4 Marcos, não estados

A v1 propõe 14 estados, a v2 23, a v3 23 mais cinco dimensões. Os três
concordam num ponto e se contradizem noutro: concordam que estado é derivado
de evento e nunca editado à mão (v3 §14), e se contradizem entre "um estado
principal" (v3 §13) e "uma pessoa tem vários ao mesmo tempo" (v3 §16). Uma
pessoa pode ser membro da comunidade e aluna travada na mesma semana. Se o
painel guardar um estado só, ele mente.

O desenho deste plano:

- **Marco** é uma conquista gravada por um evento: cadastrou, respondeu o
  quiz, pediu entrada, foi liberada, entrou pela primeira vez, concluiu a
  primeira aula, enviou o primeiro asset, concluiu o portfólio, portfólio
  aprovado, primeiro resultado profissional, entrou na comunidade, indicou
  alguém. Uma pessoa tem VÁRIOS marcos, cada um com data.
- **Dimensão** é uma vista calculada sobre os marcos: comercial, aprendizado,
  comunidade, carreira, risco (v3 §16). Cada dimensão tem uma regra de cálculo
  com versão.
- **Estado principal** existe só para a fila de próxima ação, e é uma regra
  versionada por cima das dimensões, não um campo gravado.
- **Marco automático e marco assinado são coisas diferentes, e o painel diz
  qual é qual.** "Comprou", "assistiu 90%", "visitou o checkout três vezes"
  são automáticos. "Lead qualificado", "aluno competente", "portfólio
  aprovado", "talento validado" dependem de julgamento humano e entram como
  registro assinado (quem, quando, com que evidência), pelo mesmo molde do
  `PLANO-PORTFOLIO-DO-ALUNO.md` (a escola confere). Um número que mistura os
  dois sem avisar é um número que ninguém sabe o que significa.

O mapa da jornada de `/admin/escola/jornada/` (oito paradas) é a primeira
vista de dimensão que já existe, e continua sendo a tela dela. Este plano não
o substitui: ele o alimenta com história.

### §5.5 Coortes e fotos

Nunca analisar só a média global (v2 §18). Uma coorte é "quem entrou no mês
tal", e depois "por canal", "por criativo", "por oferta de entrada", "por
turma". A `metricas` tira **fotos** de cada coorte em D0, D7, D30, D90, D180 e
D365 (v3 §49), cada foto com receita, margem, reembolso, marcos alcançados,
comunidade, indicação, e a versão de cada cartão usada. Foto tirada não se
refaz; se a fórmula mudou, a foto seguinte carrega a versão nova e o painel
mostra as duas.

É isto que responde a pergunta que o gerenciador de anúncios nunca responde:
qual aquisição produz os MELHORES clientes, não as vendas mais baratas (v2
§41). E é por isso que o livro de fatos precisa começar ANTES de vender:
cadastro, quiz, liberação, entrada, fórum e mensagens já acontecem hoje, e
cada dia sem gravá-los é uma coorte que nunca terá D0.

### §5.6 Os scores começam por regra, e a regra tem versão

Intenção, aprendizado, risco, oportunidade e resultado (v3 §17 a §22). Nenhum
peso é fixado para sempre: começa por regras simples e explícitas, e cada
mudança de regra é evento (`regra.alterada`, com a versão nova). Sem isso,
quando o mantenedor quiser descobrir daqui a seis meses o que prediz compra,
não saberá qual regra pontuou cada pessoa (v3 §23). Score é dimensão calculada
(§5.4), não campo gravado.

---

## §6 O mapa dos fatos: quem emite o quê, e o que ainda não existe

Este é o pedido de obra. Cada evento da v3 §7 mapeado para a célula que o
emite, se o contrato existe em `contracts/eventos/`, e se a célula já emite.
A tabela é a foto de 03/09/2026 pela leitura de `origin/main`; a gênese da
`metricas` a confere de novo.

| Fato | Célula dona | Contrato de evento | Situação |
|---|---|---|---|
| Pessoa cadastrou | identidade | `identidade.pessoa-cadastrada.v1` | existe e emite |
| Respondeu o quiz | quiz | `quiz.completado.v1` | existe e emite |
| Lead criado | leads | nenhum | célula tem API; contrato de evento a congelar |
| Pediu entrada, foi liberada, matrícula ativa/suspensa/encerrada | alunos | nenhum em `contracts/eventos/` | célula tem caixa de saída (`OutboxEvent`); contrato a congelar |
| Pedido criado | checkout | `pedido.criado.v1` | existe; **congelado** (22/08) |
| Pagamento aprovado / recusado / PIX expirado | pagamentos | `pagamento.aprovado.v1`, `pagamento.recusado.v1`, `pix.expirado.v1` | existem; **congelados** |
| Reembolso concluído, estorno, taxa, imposto | pagamentos | nenhum | a nascer com a razão de receita (§5.3); **congelado** |
| Primeira aula, aula concluída, projeto enviado | célula de cursos | nenhum | **a célula não existe**; plano pedido em 03/09 (`project_celula_de_cursos`) |
| Portfólio iniciado / concluído / aprovado | portfólio (dentro de alunos ou célula própria) | nenhum | plano guardado, construção não autorizada (`PLANO-PORTFOLIO-DO-ALUNO.md`) |
| Marco de competência, XP, conquista | gamificacao | contrato OpenAPI existe; evento a conferir | célula no ar; economia desligada |
| Tópico criado, resposta aceita | forum | `forum.topico-criado.v1`, `forum.resposta-aceita.v1` (e mais dois) | existem e emitem |
| Mensagem enviada / entregue / respondida | mensageria, notificacoes | `notificacao.devida.v1` | a entrega e a resposta precisam de evento próprio |
| Sugestão criada, votada | sugestoes | `sugestao.*` (cinco) | existem e emitem |
| Indicação criada, lead indicado, compra indicada | ninguém | nenhum | **não existe em lugar nenhum** |
| Gasto de anúncio, alcance, seguidores | fora do site | medição digitada | entra à mão, com data e autoridade `mantenedor` |
| Horas humanas de atendimento e de entrega | fora do site | medição digitada | idem; alimenta a margem por hora (§3, andar 3) |

O andar 4 nasce mostrando esta tabela viva: para cada linha, "chegou nos
últimos 7 dias: sim/não". "Ainda não medimos" aparece como fato, não como
buraco.

---

## §7 O que a v3 pede e a casa já tem (a lei anti-duplicação aplicada)

A v3 descreve um sistema operacional inteiro (190 itens). Boa parte dele já
existe aqui com outro nome, construída entre 26/08 e 02/09. A lei
anti-duplicação manda mapear, não reconstruir. Só se cria o que não existe.

| A v3 pede | Nesta casa é | O que falta |
|---|---|---|
| Motor de tarefas, Kanban, "pronto só com dependências resolvidas" (§55 a §59) | `fila/` + balcão `ci/fila.py` + aba "Os robôs" em `/admin/caixa/robos/` | nada; a fila de próxima ação (§3, andar 2) CRIA tarefas no balcão, não noutro quadro |
| Trava de robô, expiração (§60) | `ci/reservar.py` (referência atômica no servidor, expira em 3h) | nada |
| Lotes, paralelismo, grupo de conflito (§61, §62) | `RUNBOOK-LOTES.md`, `PLANO-MESTRE-ROBOS-SEM-COLISAO.md` | nada |
| Revisão por exceção com evidência (§63) | registro tipo `pendencia` com `precisa_do_dono` e os quatro campos da decisão | nada |
| Definição de pronto verificável (§65) | `evidencia` + `verificado_em` no livro; `concluir` da fila recusa sem prova | nada |
| Trilha de auditoria (§39) | o livro (`painel/registros/`) + o Git + `admin.auditoria` | nada |
| Memória de decisão (§162) | registros tipo `decisao` e os `DECISAO-*.md` | nada |
| Modelo de permissão de robôs (§35 a §38) | `CONSTITUICAO.md`, hooks de `.claude/settings.json`, muralhas, CODEOWNERS | nada |
| Registro de mudança com plano de volta (§132, §133) | PR + `ci/portao_de_deploy.py` + rollback medido em 76s (Fase D) | nada |
| Cartão de experimento (§50 a §54) | **não existe** como tipo | registro tipo `medicao` com campos de experimento; o resultado é registro que `responde_a`; o painel calcula "abertos", "vencidos", "decididos" |
| Alerta com nível e cansaço (§70, §71) | sino do sistema imunológico + registro `incidente` | a regra de cansaço (magnitude × duração × confiança) no cartão da métrica; alerta sem cartão não dispara |
| Insight da IA (§66 a §68) | **não existe** como tipo | registro tipo `nota` com `evidencia`, confiança e recomendação; vira `pendencia` se pedir decisão |
| Registro de métrica, camada semântica (§93 a §95) | **não existe** | os cartões do §2 |
| Conciliação diária (§90, §91) | sondas existem para outras coisas | sonda nova, na `metricas` |
| Livro de fatos, identidade, coortes (§5, §8, §48) | **não existe** | a célula `metricas` (§5.2) |
| Próxima melhor ação (§27 a §33) | mensageria + sequências de mensagens (degraus 2 a 5 no ar) | a regra que escolhe a ação por dimensão, versionada; o roteador que decide "automação, humano ou robô" |
| "Humano aprova" (§98, §155) | a caixa "precisa de você" | nada; a IA recomenda abrindo pendência |

### §7.1 Os sete portões de escala

A v2 §33 pede sete portões antes de um motor escalar: demanda, conversão,
economia, entrega, resultado, retenção, escala. Aqui cada portão é um registro
com `evidencia` e `verificado_em`, e o motor só fica verde no andar 2 com os
sete registrados. Portão sem prova é o motor em azul. ROAS nunca é
autorização de escala (v2 §34).

### §7.2 Os três modos

Descoberta, validação, escala (v2 §50). O modo é calculado dos portões: nenhum
portão provado é descoberta; até quatro é validação; os sete é escala. O
painel mostra o modo ao lado da cor. Um motor pode estar em escala enquanto
outro está em descoberta, e isso é normal.

### §7.3 O cansaço de alerta

A v3 §71 está certa: painel que alerta tudo vira sirene permanente e o dono
para de olhar. Um alerta só nasce quando o cartão da métrica define magnitude
(quanto caiu), duração (por quanto tempo), confiança (cobertura mínima) e
impacto (em que andar aparece). Sem os quatro, o desvio aparece no andar 2 e
não sobe ao andar 1.

---

## §8 A regra de contato e o lugar do humano

A v3 §10 manda perguntar cinco coisas antes de qualquer mensagem: qual estado,
qual objetivo, qual barreira, qual próxima ação, automação ou humano. E a v3
§29 dá a regra de conflito: **sucesso do aluno precede monetização**. Aluno
parado em 15% do curso não recebe oferta de especialização; recebe ajuda.
Essa regra entra como teste-guarda da fila de próxima ação: uma ação de
categoria "venda" para uma pessoa com dimensão de aprendizado "travada" é
recusada pelo cálculo.

Quem atende, nesta casa, é o mantenedor, a professora e os robôs. Não há
setter, closer nem SDR (v2 §37, v3 §33). Logo a métrica que decide onde a
atenção humana entra é **margem de contribuição por hora de atenção humana**
(v2 §7 aplicou só ao acelerador; aqui vale para todo motor com gente no meio),
e o cartão de cada canal de atendimento mede leads recebidos, conversas,
resultado e horas. O robô cuida da escala; a pessoa cuida dos pontos de alta
ambiguidade e confiança (v1 §11).

Dois limites que a v3 §128 e §126 pedem e que a mensageria já respeita em
parte: teto de mensagens por 24h e por 7 dias por pessoa, e tempo mínimo entre
dois contatos comerciais. Os dois viram parâmetros com dono, não regra
enterrada em código (v3 §130).

---

## §9 A escada de entrega

Um degrau por PR (orçamento de 15 arquivos, Ritos de Contrato, evidência
vermelho → verde), e **uma Meta Crucialmente Importante por degrau**: enquanto
o degrau N não tem registro verde, o degrau N+1 não começa. As dez fases da v3
§180 estão aqui na ordem, com o que já existe e o que falta. Os itens marcados
❄ estão congelados pela decisão de 22/08 e entram desenhados.

| Degrau | O que nasce | O que já existe | PRs (estimativa) | Depende de |
|---|---|---|---|---|
| **0. O placar** | Andar 0 em `/admin/placar/` (fora do prefixo `painel/`, que é do livro) com a Meta 1 (§4.1): X medido de `alunos` por HTTP, alvo e data lidos do livro, par "ativos em 30 dias". Os primeiros cartões de métrica e o teste que recusa tile sem cartão. | a porta admin, o consumo de `alunos`, o mapa da jornada | 2 | nada |
| **1. A célula de medição** | Gênese da `metricas` (§5.2): recebe `identidade.pessoa-cadastrada`, `quiz.completado`, `forum.*`; guarda imutável; API de leitura com guarda de 401; linha em `painel/ia/04`. | contratos de evento, outbox de `alunos`, rito de gênese | 3 (gênese, consumo, API) + 1 sessão de Rito de Contrato | 0 |
| **2. Os fatos que faltam** | Contratos de evento de `leads` e `alunos` (pediu entrada, liberada, ativa, suspensa, encerrada); a `metricas` passa a recebê-los. | as células e a caixa de saída | 2 por provedora (contrato e serviço não viajam no mesmo PR) | 1 |
| **3. Marcos e dimensões** | Marcos automáticos calculados; marco assinado como registro; a dimensão "aprendizado" ligada ao mapa da jornada. | `/admin/escola/jornada/` | 2 | 2 |
| **4. Coortes e fotos** | Coorte por mês de entrada e por turma; fotos D0 a D365; tabela de coorte no andar 2. | nada | 2 | 3 |
| **5. Confiança** | Andar 4: cobertura, frescor, conciliação diária (sonda), confiança por indicador, linhagem. | sondas do sistema imunológico, sino | 3 | 4 |
| **6. A direção da semana** | Andar 1: medidas de direção, compromisso como registro com vencimento, veredito calculado; pauta fixa de segunda. | o livro, a caixa "precisa de você" | 2 | 0 |
| **7. A saúde da máquina** | Andar 2: os onze motores com cor e modo calculados dos portões; os cinco blocos; o funil por marcos com taxas. | nada | 3 | 4, 5 |
| **8. A matemática** ❄ | Andar 3 com as equações; razão de receita (§5.3); parâmetros com dono. Desenhado agora, aceso só quando o site vender. | contratos de pagamento | 3 + 1 sessão de Rito | 7, e a ordem do mantenedor |
| **9. A fila de próxima ação** | Regra por dimensão, versionada; roteador automação/humano/robô; tarefas no balcão; regra "sucesso antes de venda" como guarda; tetos de contato como parâmetro. | mensageria, sequências, `fila/` | 3 | 3, 6 |
| **10. O robô analista e os experimentos** | Insight como registro com evidência e confiança; experimento como registro com resultado que responde; anomalia por cartão; o gargalo da semana. | o livro, o sino | 3 | 5, 7 |
| **11. Rede de talentos e B2B, à mão** | Contagens manuais (alunos selecionados, estúdios parceiros, encaixes feitos) como medição digitada; o motor sai do cinza. | nada | 1 | 7 |
| **12. Integrações de fora** | Gasto de anúncio e alcance por API em vez de digitado; WhatsApp pela API oficial. | nada | a definir | credenciais e plano pago: **passo do mantenedor** |

O degrau 0 pode nascer amanhã, sem célula nova e sem venda: o número de alunos
já existe na célula `alunos` e a admin já o consome. É o menor PR que entrega
a decisão dele de 03/09 e o coloca na tela.

---

## §10 O que NÃO se constrói ainda

- **Nenhum tile de venda, checkout, ticket médio, order bump ou upsell** até a
  ordem do mantenedor. Desenhado, sim; aceso, não.
- **Nenhuma jornada dupla** aluno/pagador. Escola 18+.
- **Nenhum CRM externo**, nenhuma cópia de tabela de pessoa para a `metricas`.
- **Nenhum índice composto** no andar zero, e nenhum sem os componentes ao lado.
- **Nenhum aprendizado de máquina, previsão ou otimização adaptativa** (v3
  §182, §183): primeiro descritivo, depois diagnóstico. Regras explícitas e
  dados confiáveis antes de qualquer modelo.
- **Nenhum marketplace automatizado**: a rede de talentos começa à mão (v1
  §10, "serviço, depois fluxo, depois plataforma").
- **Nenhum alvo inventado**: motor em descoberta tem base, não meta.
- **Nenhuma lista mantida à mão** em nenhum andar. Se falta algo, muda a regra
  de cálculo.
- **Nenhum "reembolso zero" como meta.** O direito de arrependimento de 7 dias
  é lei; reembolso baixo é medida de saúde, reembolso zero como meta convida a
  esconder o botão.
- **Nenhum envio de lista de alunos para plataforma de anúncio** (público
  semelhante) sem decisão dele e consentimento registrado.

---

## §11 O que espera pelo mantenedor

Cada item abaixo vira registro de `pendencia` no livro no PR do degrau que
o exige, e é a caixa "precisa de você" que o cobra. Nenhum é bloqueio do
degrau 0.

1. **O Y e a data da Meta 1** ("de X para Y alunos até quando"). Degrau 0 nasce
   sem eles e os cobra.
2. **O nome definitivo da célula de medição** (nome de trabalho `metricas`).
   Degrau 1.
3. **Os resultados-chave do trimestre** (sugestão no §4.1). Degrau 6.
4. **A API oficial do WhatsApp** (serviço pago, cadastro em nome da empresa) e
   as credenciais de anúncio (Meta, Google). Degrau 12.
5. **A ordem de vender**, que descongela o degrau 8. Sem prazo, por decisão dele.

---

## §12 Quem faz valer (os mecanismos)

Garantia escrita em prosa apodrece (`RETROSPECTIVA-FASE-D.md`, padrão 2).
Cada regra deste plano tem, ou terá no PR que a construir, um mecanismo:

| Regra | Mecanismo |
|---|---|
| Tile sem cartão não existe | gerador do painel recusa; teste-guarda com o caso que DEVE reprovar |
| Composto nunca no andar 0 | teste sobre os cartões |
| Fórmula mudou sem versão | teste sobre os cartões; a versão viaja na foto de coorte |
| Motor verde só com sete portões provados | regra de cálculo em `painel/logica.js` (ou na `metricas`), com teste |
| Evento não se edita | a `metricas` não tem endpoint de escrita além de "acrescentar"; teste que prova a recusa |
| Fato financeiro inválido não se adivinha | fila de exceção + registro de incidente; teste com evento malformado |
| Conciliação diária | sonda; sonda vermelha abre incidente no livro |
| Venda antes de sucesso é recusada | teste-guarda na regra da fila de próxima ação |
| Compromisso vencido aparece | regra de cálculo do livro (`vence_em_dias`), já existente |
| Célula nova aparece no mapa para IA | `ci/tests/test_painel_ia_atualizado.py`, já existente |
| A LEITURA deste plano | não tem mecanismo, como a leitura das armadilhas (dívida reconhecida em `ci/leis-sem-mecanismo.txt`); quem constrói um degrau cita este plano no registro |

---

## §13 Glossário, para quem não é do ramo

- **Coorte:** o grupo de pessoas que entrou no mesmo período (ou pelo mesmo
  canal). Acompanhar a coorte é perguntar "o que aconteceu com quem entrou em
  setembro", em vez de olhar a média de todo mundo.
- **LTV (valor no tempo de vida):** quanto uma pessoa gera para a escola ao
  longo do relacionamento. LTV90 é o quanto gerou em 90 dias.
- **CAC (custo de aquisição):** quanto custou trazer uma pessoa, contando tudo
  (anúncio, criativo, ferramenta, hora de atendimento).
- **Tempo de recuperação (payback):** quantos dias até o que a pessoa pagou
  cobrir o que custou trazê-la. Pode ter LTV ótimo e quebrar o caixa no
  caminho.
- **Margem de contribuição:** o que sobra da receita depois dos custos que
  variam com cada venda (taxa, imposto, reembolso, entrega). Não é lucro; é o
  que contribui para pagar o resto.
- **Medida de resultado e medida de direção:** a primeira você vê depois que
  aconteceu (retrovisor); a segunda prevê a primeira e pode ser movida esta
  semana (volante).
- **Marco:** uma conquista com data (fez a primeira aula, enviou o primeiro
  asset). Uma pessoa acumula marcos; ninguém "está" num marco só.
- **Portão de escala:** uma pergunta que precisa de prova antes de um motor
  crescer (existe demanda? converte? dá margem? conseguimos entregar? o aluno
  tem resultado? fica? funciona com mais gente?).
- **Fail-closed:** quando algo está estranho, o sistema para e avisa, em vez
  de seguir e adivinhar.
