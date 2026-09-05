publico-para-ia: true

# Constituição da Célula: cursos (a sala de aula da Meshcraft)
> **Jurisdição:** governa apenas `services/cursos/`. Herda `CONSTITUICAO.md`.
> **STATUS:** EM PAPEL (escrita em 04/09/2026 junto com
> `PLANO-CELULA-CURSOS.md`, aprovado pelo mantenedor no mesmo dia; é promovida
> a `constituicoes/AGENTS.cursos.md` na gênese, revista contra o código) · **Merge:** pela pista
> (`ci/mergear.py --pousar`), com CI verde

## Missão
Fazer o aluno entregar 33 vezes, do primeiro cubo ao primeiro colaborador
pago, e receber a cada entrega um laudo que diz o que fazer amanhã de manhã.
A célula guarda o conteúdo do curso (as encomendas com suas 16 peças, os
vídeos por link, as pausas, os instrumentos), o progresso de cada aluno (que
porta está aberta), o checkpoint (o envio, por link, na fila de 24 horas) e o
laudo (o instrumento, três forças, uma mudança, a decisão, a data, a pergunta).
**O checkpoint abre a porta; o calendário, nunca.** E os agentes de IA que
vivem aqui preparam e nunca publicam: a IA escreve, a pessoa assina.

Lei do assunto: `docs/decisoes/PLANO-CELULA-CURSOS.md` (a visão, as emendas da
casa aos nove documentos do projeto, o modelo, os eventos, as superfícies, os
agentes, os invariantes, a escada). Os nove documentos do curso (roadmap,
playbook, equipe de agentes) moram fora do repositório, de propósito
(`armadilhas/331`); quem constrói pede o caminho ao mantenedor e os lê antes.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/cursos/**`
- **SOMENTE LEITURA:** `contracts/identidade.openapi.yaml` (é por ele que se
  pergunta quem é a pessoa), `contracts/alunos.openapi.yaml` (é por ele que se
  sabe se ela está matriculada), `contracts/eventos/envio.*`, `laudo.*`,
  `aula.*`, `checkpoint.*`, `revisao.*`, `banca.*` (o que esta célula promete
  emitir) e `contracts/eventos/notificacao.devida.v1.json` (o sininho)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo. Em
  especial: `services/gamificacao/` (esta célula nunca calcula ponto),
  `services/pages/` (o portfólio não mora aqui), `services/quiz/` (o Crivo não
  é o quiz da encomenda), `services/checkout/` e `services/pagamentos/`
  (pagamento por último, diretiva de 22/08/2026)

## Comunicação
- **Expõe (telas):** `/cursos` (o mapa das portas), `/cursos/<numero>` (a
  aula: peças, vídeo com pausas, quiz, checkpoint), `/cursos/<numero>/laudo`
  (o laudo recebido, a data antes do texto), `/cursos/plantao` (a professora:
  a fila de revisão) e `/cursos/plantao/<envio>` (o formulário do laudo, com o
  botão "Rascunhar laudo"). Prefixo do gateway via `SCRIPT_NAME`; **o endereço
  é CAMINHO, nunca subdomínio**. A única rota que responde sem nada é
  `/healthz`. Telas são formulário normal com melhoria progressiva: nenhum
  caminho pode existir só com script
- **Expõe (contrato):** para o Admin, o editor (`listLessons`, `getLesson`,
  `putLesson`, `putInstrument`, `publishLesson`), os verificadores
  (`checkLesson`) e o placar da fila (`getReviewQueue`, contagens, nunca quem);
  para o Estúdio e a home, `getStudentProgress` (que portas abriram, sem nota).
  Nada disso responde pela borda pública sem Bearer, e `/interno` não resolve
  pela borda (`armadilhas/186`)
- **Consome:** `identidade` (`getSessionFull`, quem é o dono do cookie) e
  `alunos` (`getStudentStanding`, a matrícula ativa decide o acesso,
  fail-CLOSED). Na gênese `celulas.yml` diz `consome: []` (`armadilhas/224`);
  cada linha entra no PR do cliente que a lê
- **Auth:** Bearer dedicado por par, `TOKENS_ACEITOS_<PAR>`. Env ausente ⇒
  conjunto vazio ⇒ 401 para todo mundo. A lista `CURSOS_PROFESSORES` decide
  quem entra no plantão; vazia, ninguém entra
- **Emite:** `envio.recebido.v1`, `laudo.emitido.v1`, `aula.concluida.v1`,
  `checkpoint.devolvido.v1`, `revisao.prazo-estourado.v1`, `banca.decidida.v1`
  (Fase 5) e `notificacao.devida.v1` (assuntos `cursos.*`), pelo padrão outbox
  + relay Huey. **Só ids opacos viajam**: texto, link, e-mail e nome nunca
- **Banco:** `cursos_db` (role `cursos_user`, não enxerga nenhum outro
  database). Guarda o conteúdo do curso, o progresso, os registros de pausa,
  os envios, os laudos e os rascunhos da IA. `Pessoa` é espelho mínimo (id da
  plataforma, nome de exibição); a matrícula se pergunta à `alunos`

## Invariantes desta célula

- **[INV-P12] Esta célula NÃO assina sessão.** Sem `SessionMiddleware`, sem
  `django.contrib.sessions`, cookie de CSRF com nome próprio (`cursos_csrf`).
  Guarda: `tests/test_inv_cursos_nao_assina_sessao.py`, plantado na gênese e
  provado por mutação. A tentação aqui tem nome: a cerimônia do Boss é tela
  cheia, uma vez só, e "já viu?" pede memória; `request.session` deslogaria o
  site inteiro (`armadilhas/143`). O estado mora no MODELO.

- **Os sete do laudo [INV-CUR-L1..L7]**, os três da porta **[INV-CUR-P1..P3]**,
  os dois do conteúdo **[INV-CUR-C1..C2]** e os dois de segurança
  **[INV-CUR-S1..S2]**, escritos na lei §9 com o caminho do guarda de cada um.
  Nascem como teste no degrau que os implementa, entram no `INVARIANTES.md`
  no mesmo PR e nunca se flexibilizam. Os de laudo são **regra de API**: o
  `POST` devolve 422, e qualquer tela herda.

- **Reconhecer não é autorizar.** O `papel` que a `identidade` devolve é de
  exibição. Quem decide se alguém vê a aula (matrícula ativa) e se alguém
  entra no plantão (`CURSOS_PROFESSORES`) é esta célula, fail-CLOSED.

- **A IA nunca decide.** O `RascunhoDaIA` não tem campo de decisão, data nem
  resposta à pergunta de amanhã de manhã, e o teste sabota tentando gravá-los.
  O Assistente de laudo é degrau H para sempre.

- **24 horas é constante, com teste.** `prazo_em` não muda por API; o estouro
  se registra em `estourado_em` e aparece na tela. Não é parâmetro.

- **A escola é 18+.** Não há responsável, não há trava de idade, nenhum
  desenho novo assume criança no sistema.

- **Esta célula não sabe o que é ponto.** XP, medalha, Marco e título de nível
  são da `gamificacao`, por evento. Esta célula emite `aula.concluida.v1` e
  nunca lê o XP de ninguém.

- **Esta célula não constrói portfólio.** O Estúdio (`pages`) é a casa; daqui
  sai só `getStudentProgress`.

- **O conteúdo entra pela porta de máquina.** Nenhuma migração semeia texto de
  aula; a migração só semeia slug e nome canônico de instrumento.

## Critérios de morte (lei §11)
Se a construção começar a desenhar **um segundo lugar para o texto das
aulas**, **a IA persistindo decisão, data ou carimbo**, **o prazo de 24 horas
como parâmetro ou com botão de alongar**, **o estado "reprovado"**, **ranking
ou dois alunos lado a lado**, **aula atrás de XP ou pagamento dentro desta
célula**, **ponto calculado aqui**, **conteúdo por arquivo commitado**, ou
**chat livre fora do laudo**, **pare e reabra a decisão** com o mantenedor.

## O que esta célula ainda NÃO resolveu
Registrado para ninguém achar que foi esquecimento (lei §8):

1. **Onde moram os vídeos**: o mantenedor adiou a decisão para a fase da sala
   de aula (degrau 1.8), em 04/09/2026. O serviço, o custo e a restrição de
   quem assiste; a pausa real exige tocador controlável.
2. **O modelo e o custo do Assistente de laudo** (degrau 2.3), e a chave da
   Anthropic na VPS, que em 02/09/2026 ainda não existia.
3. **Quando abrir a E00** para os alunos que já estão na escola: decisão de
   produto, depende do conteúdo estar na tela.
4. **Quem revisa além da professora, e quando os pares começam** (Fase 4);
   **a composição das Bancas** sem pares formados (Fase 5).
5. **Os capítulos**: ainda só no chat do claude.ai (04/09/2026). Sem eles, a
   Fase 3 espera.
