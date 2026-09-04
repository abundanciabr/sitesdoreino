# Constituição da Célula: encomendas (a Fila do Primeiro Dólar)
> **Jurisdição:** governa apenas `services/encomendas/`. Herda `CONSTITUICAO.md`.
> **STATUS:** APROVADA EM PAPEL (03/09/2026); **a célula ainda não existe em
> `services/`**, nasce na gênese (TAR-109) depois de o mantenedor aprovar a
> lei · **Merge:** pela pista (`ci/mergear.py --pousar`), com CI verde

## Missão
Atravessar, uma vez por aluno, o ponto mais difícil da carreira de um
modelador: ninguém contrata quem nunca entregou, e ninguém entrega sem ser
contratado. A célula guarda a fila, faz a oferta certa à pessoa certa, segura
a encomenda até um humano olhar a entrega, e devolve ao aluno o portfólio e o
botão de pedido direto. **A plataforma escolhe o aluno, não o cliente.**

Lei do assunto: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` (o que vale,
as emendas da casa ao plano, os invariantes, os parâmetros, a escada). O
produto inteiro (cardápio, jornadas, livro de regras, algoritmo, textos de
tela, cenários de aceite): `docs/decisoes/PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md`.
O contrato v1 em papel, até congelar: `docs/decisoes/CONTRATO-encomendas-v1-rascunho.md`.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/encomendas/**`
- **SOMENTE LEITURA:** `contracts/identidade.openapi.yaml` (é por ele que se
  pergunta quem é a pessoa), `contracts/alunos.openapi.yaml` (é por ele que
  se sabe se ela é aluna), `contracts/eventos/encomenda.*`, `oferta.*`,
  `entrega.*`, `aluno.*`, `portfolio.*`, `pedido-direto.*` (o que esta célula
  promete emitir) e `contracts/eventos/notificacao.devida.v1.json` (o sininho)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de
  pagamento. **`services/checkout/` e `services/pagamentos/` estão fora de
  mandato inclusive para leitura até a Fase 3**, que só abre quando o
  mantenedor disser que o site vai vender (diretiva de 22/08/2026, lei §3.4).
  A Fase 3, quando abrir, é PR próprio na `pagamentos`, nunca daqui

## Comunicação
- **Expõe (telas):** `/encomendas` (o aluno: na fila · oportunidade · em
  andamento), `/encomendas/pedir` (o cliente: três cartões, briefing
  blindado, confirmar, pagar), `/encomendas/acompanhar/<id>` (o rastreio de
  uma linha), `/encomendas/plantao` (o professor). Prefixo do gateway via
  `SCRIPT_NAME`; **o endereço é CAMINHO, nunca subdomínio** (é o que mantém
  o login único de pé). A única rota que responde sem nada é `/healthz`.
  Telas são formulário normal com melhoria progressiva: nenhum caminho desta
  célula pode existir só com script (regra do fórum, herdada)
- **Expõe (contrato, Parte A do anexo):** os parâmetros (`getParameters`,
  `setParameter`, para a tela do Admin), o estado da fila de uma pessoa
  (`getQueueStanding`, para a home e o Estúdio), as peças aprovadas e
  autorizadas de uma pessoa (`getApprovedPieces`, para o Estúdio) e duas
  portas internas: `confirmPayment` (da `pagamentos`, Fase 3) e
  `reportAudit` (do worker de auditoria, Fase 5). Nada disso responde pela
  borda pública sem Bearer, e `/interno` não resolve pela borda
  (`armadilhas/186`)
- **Consome:** `identidade` — `GET /interno/sessao/completa` (`getSessionFull`),
  server-side, com timeout explícito, para saber quem é o dono do cookie;
  `alunos` — `GET /alunos/{email}/situacao` (`getStudentStanding`). Na
  gênese `celulas.yml` diz `consome: []`, com o comentário que explica a
  lista vazia (`armadilhas/224`); cada linha entra no PR do cliente que a lê
- **Auth:** Bearer dedicado por par, `TOKENS_ACEITOS_<PAR>`. Env ausente ⇒
  conjunto vazio ⇒ 401 para todo mundo (fail-closed sem derrubar o boot)
- **Emite:** os 20 eventos da lei §3.9 e `notificacao.devida.v1` (assuntos
  `encomendas.*`, Rito aditivo na Fase 4), pelo padrão outbox + relay Huey.
  **Só ids opacos viajam**: briefing, texto, e-mail e nome nunca
- **Banco:** `encomendas_db` (role `encomendas_user` — não enxerga nenhum
  outro database). Guarda perfis profissionais, fila, ofertas, encomendas
  (com histórico de status e autor), entregas, revisões, correções,
  mediações e a tabela de parâmetros com histórico. **Nada de dado alheio
  copiado sem necessidade**: `Pessoa` é espelho mínimo (id da plataforma,
  nome de exibição); a matrícula se pergunta à `alunos`

## Invariantes desta célula

- **[INV-P12] Esta célula NÃO assina sessão.** Sem `SessionMiddleware`, sem
  `django.contrib.sessions`, sem `SESSION_ENGINE`, cookie de CSRF com nome
  próprio (`encomendas_csrf`). A célula repassa o cookie e pergunta quem é.
  Guarda: `tests/test_inv_encomendas_nao_assina_sessao.py`, plantado na
  gênese e **provado por mutação**. Aqui a tentação tem nome: a **cerimônia
  do primeiro dólar** é tela cheia, uma vez só, e "já viu?" pede memória; o
  caminho curto é `request.session[...]`, que deslogaria o site inteiro sem
  erro em lugar nenhum (`armadilhas/143`). O estado mora no MODELO.

- **Os dez de justiça [INV-ENC-J1..J10]**, os cinco de dinheiro
  **[INV-ENC-D13..D17]** e os cinco de segurança **[INV-ENC-S1..S5]**, escritos
  na lei §5 com o caminho do guarda de cada um. Nascem como teste no degrau
  que os implementa (J no motor e nos relógios; D na Fase 3; S nas Fases 3 e
  5), entram no `INVARIANTES.md` **no mesmo PR** e nunca se flexibilizam.
  **O motor é função de (estado atual, agora)**: rodar duas vezes não cria
  duas ofertas; relógios são reavaliação periódica, nunca timer agendado
  (sobrevive a reinício, deploy e queda do Redis).

- **Reconhecer não é autorizar.** O `papel` que a `identidade` devolve é de
  exibição. Quem decide se alguém está na fila, se pode aceitar, se é do
  plantão, é esta célula, fail-CLOSED, conferindo as listas dela (a do
  professor é a mesma do fórum até a `identidade` ter o papel).

- **Os parâmetros são DADO, com histórico.** Nenhum número da seção 6.12 do
  plano vive em código; o motor lê o valor vigente em `agora`. Mudar é linha
  nova com motivo, pela tela do Admin. Um teste-guarda reprova constante
  mágica no motor (lei §3.8).

- **A escola é 18+.** Não há responsável, não há trava de idade, e nenhum
  desenho novo assume criança no sistema (lei §3.1). O que continua, porque
  não era sobre idade: comunicação estruturada, sem contato direto, sem dado
  de contato do aluno para o cliente.

- **Esta célula não sabe o que é dinheiro.** Ela só sabe "pago",
  "repassado", "reembolsado", por porta interna e por evento. Cobrança,
  retenção, taxa, repasse e reembolso são da `pagamentos` (lei §9, critério
  de morte 3).

- **Esta célula não constrói portfólio.** O Estúdio (`/estudio/<apelido>`,
  opt-in, célula `pages`) é a casa; daqui sai só a porta de peças aprovadas
  e autorizadas (lei §3.5).

## Critérios de morte (lei §9)
Se a construção começar a desenhar **lista de freelancers, propostas, lances,
ranking, chat livre, matchmaking por IA**, uma **segunda regra de ordem** na
fila, **dinheiro dentro desta célula**, um **segundo portfólio**, ou um
**parâmetro em código**, **pare e reabra a decisão** com o mantenedor.

## O que esta célula ainda NÃO resolveu
Registrado para ninguém achar que foi esquecimento (lei §8):

1. **Preço, taxa, moeda e o mecanismo de custódia** (decisões 1, 2 e 3 do
   plano), com o parecer jurídico (4) como portão da Fase 3.
2. **Onde moram os arquivos da entrega** (`.fbx`, `.blend`, texturas). A
   plataforma não guarda arquivo hoje (`PLANO-PORTFOLIO-DO-ALUNO.md` §3), e o
   worker de auditoria com Blender é imagem própria. Decisão da Fase 5, com
   o mantenedor.
3. **Quem revisa até existir Nível 3, e quanto vale a revisão** (8).
4. **Portfólio automático ou opt-in** (12): a casa diz opt-in; a Fase 6 espera
   a resposta.

## Estado da construção
O estado de cada degrau se lê **no balcão** (`python ci/fila.py listar
--ao-vivo`), nunca aqui. A escada inteira, com as tarefas TAR-107 a TAR-118,
está na lei §7. **Até o degrau 2.10 (compose + Traefik), o `deploy-celula`
desta célula fica vermelho — isso é esperado** (`armadilhas/088`).
