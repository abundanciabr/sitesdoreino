# Constituição da Célula: metricas (o livro de fatos da plataforma)

> **Jurisdição:** governa apenas `services/metricas/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 04/09/2026, PR de gênese, degrau 7.1 do plano
> do painel de gestão) · **Merge:** pela pista (`ci/mergear.py --pousar`), com
> CI verde

## Missão

Guardar a HISTÓRIA dos fatos da escola para que o painel do mantenedor possa
dizer o que mudou, e não só o que é. Hoje toda tela de gestão conta ao vivo,
perguntando às células a cada abertura: isso responde "quantas alunas há
agora", nunca "quantas havia na semana passada". Um número sem passado não
sustenta meta, coorte, marco nem experimento.

Esta célula recebe os eventos que as outras publicam, guarda-os **imutáveis**,
e responde por API de leitura. Ela é **consumidora, nunca dona**: não decide
nada sobre pessoa, matrícula, ponto ou mensagem. O dono de cada fato continua
sendo a célula que o emitiu.

Lei do assunto: `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §6.2 (o livro de
fatos), §6.4 (marcos, coortes, dimensões), §6.6 (a confiança) e a escada do
§8, degrau 7. A régua de cada número mora nos cartões (`painel/cartoes/`), e
não aqui: esta célula guarda o fato, o cartão diz o que ele significa.

## Fronteiras

- **PERMITIDO ESCREVER:** `services/metricas/**`
- **SOMENTE LEITURA:** `contracts/eventos/*.json` (o que ela recebe) e, quando
  existir, `contracts/metricas.openapi.yaml` (o que ela promete responder)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo.
  Em especial, **é proibido consultar API de outra célula para "completar" um
  fato**: o que o evento não trouxer, esta célula não sabe, e dizer "não sei"
  é resposta legítima. Preencher buraco perguntando ao vivo transformaria o
  livro de fatos num espelho do presente, que é exatamente o que ele não é

## Comunicação

- **Expõe (telas):** nenhuma, hoje e sempre. Quem mostra número é a `admin`,
  que já tem porta, crachá e uma leitora só (o mantenedor). A única rota da
  gênese é `/healthz`, de máquina
- **Expõe (máquina, desde o degrau 7.4):** a API de leitura `/api/metricas/`,
  com quatro operações: contadores históricos por dia (`countFacts`), cobertura
  de rastreio e frescor (`listCoverage`) e a fila de eventos mortos, em lista e
  uma a uma (`listDeadLetters`, `getDeadLetter`). **Os marcos NÃO se leem por
  aqui**: a tabela existe desde o degrau 9 do plano e é escrita pela recepção,
  mas a operação de leitura é porta nova, e porta nova é Rito de Contrato com o
  mantenedor presente (`RITOS.md` §3). Enquanto o Rito não acontece, quem
  precisa dos marcos os lê no banco da célula. Fotos de coorte e conciliação
  seguem sem tabela: uma operação que hoje respondesse lista vazia pareceria
  resposta. Nada responde
  sem Bearer, e o token é o único guarda que conta: hoje esta célula não tem
  rota no Traefik, mas topologia é configuração de infra e muda sem passar por
  aqui (`armadilhas/186`). O teste de 401 cobre TODAS as operações, medidas do
  schema vivo
- **A recepção NÃO é porta HTTP**, e essa é a correção de rumo do degrau 7.3: o
  transporte de evento nesta casa é Redis Streams, e uma segunda forma de
  entrar seria uma segunda forma de o mesmo fato chegar. Quem escuta é
  `consume_eventos`, no molde [RECEITA:R4 v1] das outras cinco consumidoras
- **Consome:** ninguém, por desenho. `celulas.yml` diz `consome: []` e vai
  continuar dizendo mesmo com a célula completa, porque `consome` mede leitura
  de API alheia e esta célula lê EVENTOS. Quem a consome é a `admin`, e é o
  mapa dela que ganha `metricas` no PR do cliente (`armadilhas/224`)
- **Auth:** Bearer dedicado por par, `TOKENS_ACEITOS_<PAR>`. Env ausente ⇒
  conjunto vazio ⇒ 401 para todo mundo (fail-closed sem derrubar o boot)
- **Emite:** nada. Um livro de fatos que emite fato vira fonte de si mesmo, e
  o laço fecharia sem ninguém ver. A exceção prevista é o registro de
  INCIDENTE quando um evento chega inválido, e isso vai para o livro de
  ocorrências (`painel/registros/`), pelo caminho de sempre, não por evento
- **Banco:** `metricas_db` (role `metricas_user`, que não enxerga nenhum outro
  database). Guarda eventos crus, a fila de eventos mortos, marcos derivados e
  fotos. **Só ids opacos viajam e só ids opacos ficam:** nome, e-mail e texto
  de mensagem não entram aqui. Para contar não é preciso saber quem é

## Invariantes desta célula

- **[INV-P12] Esta célula NÃO assina sessão.** Sem `SessionMiddleware`, sem
  `django.contrib.sessions`, sem `SESSION_ENGINE`, sem `django.contrib.auth`,
  cookie de CSRF com nome próprio (`metricas_csrf`). Guarda:
  `tests/test_inv_metricas_nao_assina_sessao.py`, plantado na gênese e provado
  por mutação. A tentação aqui tem forma própria: esta célula guarda fatos
  sobre pessoas, e "de quem é este evento?" aparece em toda linha. A resposta
  vem do CORPO do evento, pelo contrato, nunca de quem fez a chamada

- **O fuso é a unidade da medição, não a exibição.** `TIME_ZONE` é
  `America/Sao_Paulo` e o armazenamento é UTC. Tudo o que esta célula responde
  é contagem por DIA, e um instante perto da virada muda de mês com o fuso
  errado, sem erro em lugar nenhum (`armadilhas/099`). A `admin` já conta
  assim (`placar.py::dia_em_sao_paulo`) e as duas contas têm de concordar.
  Guarda: `tests/test_fuso_horario.py`, provado por mutação

- **Um evento nunca se corrige; corrige-se acrescentando.** Fato gravado é
  imutável: sem `UPDATE`, sem `DELETE`. Correção é evento novo que aponta para
  o anterior. Guarda: nasce com a tabela, no degrau 7.2, e entra no
  `INVARIANTES.md` no mesmo PR

- **Duplicata se recusa pelo id externo, não pelo conteúdo.** Todo evento traz
  id próprio; receber o mesmo duas vezes grava uma vez. Entrega repetida é o
  normal de qualquer fila, e contar duas vezes é como uma métrica mente sem
  parecer errada

- **Fail-closed em fato inválido.** Evento que não casa com o contrato vai
  para a fila de eventos mortos e vira incidente no livro, com as três ações
  do painel (inspecionar, tentar de novo, descartar com motivo). **Nunca é
  aceito pela metade**: meio fato guardado é pior do que fato nenhum, porque o
  número resultante parece medido

- **"Não sei" é resposta.** Onde falta cobertura, a API diz que falta, e a
  `admin` mostra "sem dados" em vez de zero. Zero é uma afirmação sobre o
  mundo; ausência de dado não é

## Escada (o que nasce quando)

| Degrau | O que nasce |
|---|---|
| **7.1 FEITO** | A gênese: esqueleto, `/healthz`, os três guardas, o lugar da célula nos mapas da casa |
| **7.2 FEITO** | O evento imutável e a fila de eventos mortos (tabela, migração, a trava dupla: ORM e banco) |
| **7.3 FEITO** | A recepção, e ela NÃO virou porta HTTP: é o consumidor de Redis Streams, com recusa de duplicata pelo id externo e fila de mortos |
| **7.4 FEITO** | A API de leitura (`/api/metricas/`), Bearer de par, teste de 401 em todas as operações medidas do schema vivo |
| 7.5 | O compose (`infra/`), em PR próprio (`armadilhas/134`), com o env e o banco na VPS antes (`armadilhas/088`) |
| 7.6 | O contrato congelado pelo `RITOS.md` §3 (PR só de `contracts/`, etiqueta `contrato`, o mantenedor presente) e a `admin` como cliente, com o token do par |
| **9 (do plano) FEITO pela metade** | Os MARCOS: a tabela `Marco`, a derivação automática dentro da recepção e a passada `manage.py derivar_marcos` sobre o livro já guardado. A porta de leitura NÃO nasceu junto, e é essa a metade que falta: ela é Rito de Contrato, e o mandato não foi dado |

Até o 7.5, o `deploy-celula` desta célula fica vermelho em todo merge que a
toca, e **isso é esperado**: o compose da VPS ainda não a conhece
(`armadilhas/088`).
