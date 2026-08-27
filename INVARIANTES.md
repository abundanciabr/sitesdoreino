# INVARIANTES — Jurisprudência Pré-Paga da Plataforma

Formato: **o quê / por quê / teste-guarda / célula dona**. Os invariantes de dinheiro
nascem ANTES da primeira feature, com guarda no mesmo PR — a lei existe antes da
primeira oportunidade de violá-la.

**Regras de trabalho:**
1. Código que toca um invariante referencia o código dele em comentário (ex.: `[INV-P3]`).
2. Teste-guarda é intocável: nunca deletar, desativar ou afrouxar para passar.
3. Evidência falsificável: correção em invariante apresenta a saída crua vermelho→verde.
4. Invariante sem guarda no mesmo PR só entra na seção final (dívida), com dono e prazo.

---

### [INV-P1] Snapshot do Pedido é Create-Only
- **O quê:** `Order.items`, `Order.total_cents` e `Order.customer` são congelados na
  criação. Nenhum caminho de código os atualiza depois — nem UPSERT, nem reprocesso,
  nem admin. Correção de pedido = novo pedido + cancelamento do antigo.
- **Por quê:** snapshot mutável é recibo que mente — um UPSERT descuidado zera campos,
  um reajuste de preço reescreve o passado do cliente, e o suporte nunca mais sabe o
  que a pessoa realmente comprou e por quanto.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p1_snapshot.py` — cria pedido,
  tenta alterar itens/total por todos os caminhos públicos, assert de imutabilidade.
- **Célula dona:** checkout

### [INV-P2] Dinheiro é Calculado no Servidor
- **O quê:** o cliente envia intenção (`bump_ids`, `method`, dados); o servidor
  recalcula itens e total a partir do catálogo. Qualquer valor monetário vindo do
  navegador é ignorado. Padrão client-sends-intent / server-validates.
- **Por quê:** total computado no cliente é superfície de manipulação de preço —
  basta editar o payload no DevTools para comprar por um centavo.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p2_server_money.py` — payload
  adulterado com `total_cents` falso e `price_cents` falsos ⇒ snapshot sai com os
  valores do catálogo.
- **Célula dona:** checkout

### [INV-P3] Webhook Idempotente por mp_payment_id
- **O quê:** o mesmo webhook entregue N vezes produz UMA transição de estado e UM
  evento na outbox. Chave de deduplicação: `mp_payment_id` + status alvo.
- **Por quê:** o Mercado Pago reentrega webhooks por design (retry, timeout,
  reprocessamento). Sem deduplicação, cada reentrega duplicaria matrícula, e-mail
  e linha de ledger.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p3_webhook_idempotente.py` —
  POST do mesmo webhook assinado 3×; assert: 1 transição, 1 linha de outbox.
- **Célula dona:** pagamentos

### [INV-P4] Criação de Intent Idempotente por X-Idempotency-Key
- **O quê:** `POST /intents` com a mesma chave devolve a MESMA intent (200), sem nova
  tentativa de cobrança. Toda escrita ao MP também leva `X-Idempotency-Key` própria.
- **Por quê:** refresh na página de pagamento, retry de rede e double-click são
  comportamento normal de usuário — e nenhum deles pode virar dupla cobrança.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p4_intent_idempotente.py` —
  2× POST mesma chave ⇒ mesma intent, 1 chamada ao provider (mock).
- **Célula dona:** pagamentos

### [INV-P5] Matrícula sob Lock, Idempotente por order_id
- **O quê:** o consumer de `pagamento.aprovado` matricula dentro de
  `transaction.atomic()` + `select_for_update()`, com unicidade por `order_id`.
  Evento duplicado ou concorrente ⇒ UMA matrícula.
- **Por quê:** eventos chegam duplicados e concorrentes por natureza (é a garantia
  at-least-once do transporte). Duplicar matrícula duplica acessos, e-mails de
  boas-vindas e tickets de suporte.
- **Teste-Guarda:** `services/alunos/tests/test_inv_p5_matricula_lock.py` — dois
  consumers processando o mesmo evento em threads ⇒ 1 matrícula no banco.
- **Célula dona:** alunos

### [INV-P6] Outbox Transacional
- **O quê:** todo evento emitido é gravado na tabela outbox NA MESMA transação da
  mudança de estado que o justifica. O relay (Huey) publica no Redis Streams depois.
  Estado sem evento e evento sem estado são ambos impossíveis.
- **Por quê:** "pagou mas não matriculou" e "matriculou sem pagar" são as duas
  falhas que destroem confiança num funil. O outbox elimina a janela entre commit e
  publicação.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p6_outbox.py` — aprovação ⇒
  na mesma transação existe linha de outbox; falha simulada do relay ⇒ evento
  permanece pendente e é republicado, nunca perdido.
- **Célula dona:** pagamentos (padrão replicado em quiz e checkout para seus eventos)

### [INV-P7] Status na UI Deriva do Servidor
- **O quê:** as páginas de pagamento fazem polling de `GET /pedidos/{id}` (ou intent).
  Nenhuma máquina de estado no navegador decide "pago"; nenhum status é inferido do
  passo do wizard ou de índice de array.
- **Por quê:** status inferido de estado local quebra com refresh, aba duplicada e
  o retorno do app do banco após o Pix. Dados do servidor sobrevivem a tudo isso.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p7_status_servidor.py` +
  revisão de `pix.js`/`cartao.js`: os arquivos não contêm transição local para "pago".
- **Célula dona:** checkout

### [INV-P8] Segredo de Produção Só Existe em Produção
- **O quê:** `MP_ACCESS_TOKEN` de produção (`APP_USR-…`) existe em UM lugar no
  universo: `/opt/plataforma/env/pagamentos.env` na VPS, escrito manualmente pelo
  mantenedor. Dev, CI, worktrees e agentes conhecem apenas `TEST-…`.
- **Por quê:** credencial cara alcançável de ambiente de teste queima dinheiro real
  mais cedo ou mais tarde — um loop de testes com a chave errada cobra de verdade.
  Aqui isso não é proibido: é inexistente.
- **Teste-Guarda:** `ci/guarda-de-segredos.sh` (roda em todo PR — reprova `APP_USR-`
  e chaves privadas no repo) + red-team golpe nº 10.
- **Célula dona:** plataforma (CI)

### [INV-P9] Pix e Cartão Mutuamente Invisíveis
- **O quê:** `methods/pix` e `methods/card` não se importam (independência), e nenhum
  importa `providers/*` diretamente (só via `core.gateway`). No front, `pix.js` e
  `cartao.js` não compartilham estado nem funções além de `api.js`.
- **Por quê:** mudança num método de pagamento não pode alcançar o outro — nem por
  import, nem por estado compartilhado. Enquanto um método estiver em manutenção,
  o outro continua vendendo. A arquitetura diz "não" em check time.
- **Teste-Guarda:** `services/pagamentos/.importlinter` (`lint-imports` no `make ci`)
  + cross-smoke (`ci/cross-smoke.sh`): tocou um método, o smoke do outro roda.
- **Célula dona:** pagamentos

### [INV-P10] Webhook Sem Assinatura Válida ⇒ 403 e Zero Efeito
- **O quê:** todo webhook valida `x-signature` (HMAC com `MP_WEBHOOK_SECRET`) ANTES de
  qualquer leitura de payload com efeito. Inválido ⇒ 403, nada gravado, nada emitido.
- **Por quê:** um webhook forjado que aprovasse pedidos seria matrícula grátis em
  escala. Autenticação de origem vem antes de qualquer efeito colateral.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p10_assinatura.py` — payload
  válido sem assinatura e com assinatura errada ⇒ 403 + banco intacto + outbox vazia.
- **Célula dona:** pagamentos

### [INV-P11] Fronteira de Site (multissítio)
- **O quê:** o site é resolvido do Host UMA vez por requisição (middleware
  CONV-SITE) e toda consulta pública é filtrada por `site_id`. Host não cadastrado
  ⇒ 404 — nunca "cai" num site padrão. Oferta, sessão, pedido, lead e matrícula de
  um site jamais aparecem em outro.
- **Por quê:** com dezenas de marcas em teste no mesmo deploy, o vazamento clássico
  de multi-tenant (preço/oferta de um site aparecendo em outro, ou host
  desconhecido servindo o site nº 1) contamina experimentos e quebra confiança —
  e é silencioso até acontecer em público.
- **Teste-Guarda:** `services/catalogo/tests/test_inv_p11_fronteira_site.py`
  (dois sites com o mesmo slug e preços distintos ⇒ cada host vê só o seu; host
  aleatório ⇒ 404) + `services/checkout/tests/test_inv_p11_fronteira_site.py`
  (sessão criada no site A não fecha pedido com oferta do site B).
- **Célula dona:** catalogo + checkout (padrão replicado em quiz, leads e alunos)

### [INV-P12] Um Único Assinante do Cookie de Sessão do Site
- **O quê:** o cookie `meshcraft_sessao` (`Path=/`, alcance de site inteiro) é
  emitido e assinado por **uma só célula: `identidade`**. Nenhuma outra célula
  escreve `request.session`, instala `SessionMiddleware`, declara
  `SESSION_ENGINE` ou assina cookie com esse nome — as demais **perguntam**
  quem é a pessoa por HTTP (`getSession`/`getSessionFull`).
- **Por quê:** duas células assinando o MESMO cookie com chaves diferentes
  produzem um cabo-de-guerra invisível — entrar por uma desloga da outra, e
  vice-versa — **sem erro em lugar nenhum, sem log, sem alarme**. Ninguém
  reporta "fui deslogado": as pessoas reentram e seguem, e a plataforma perde
  sessão o dia inteiro sem nada acusar. A `DECISAO-celula-de-identidade.md` §5
  registra o episódio em que isso quase entrou em produção, e a §6.4 o proíbe
  por escrito; este invariante é o mecanismo que faltava à proibição.
- **Teste-Guarda:**
  `services/admin/tests/test_inv_admin_nao_assina_sessao.py` — mede a
  CONFIGURAÇÃO da célula (sem SessionMiddleware, sem django.contrib.sessions
  e sem SESSION_ENGINE no settings dela), porque sem essas três
  `request.session` nem existe. Provado por mutação na gênese da célula:
  instalar o SessionMiddleware deixa o guarda vermelho.
- **Célula dona:** identidade (única emissora) — guarda plantado em `admin`,
  a primeira célula a nascer **depois** da regra; toda célula futura que
  consuma sessão herda a mesma obrigação.

### [INV-SUG10] Corredor do ChangeSpec (nada entra em desenvolvimento sem ele)
- **O quê:** `Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` se
  existir um ChangeSpec **aprovado** registrado referenciando aquela sugestão
  (`docs/caixa-de-sugestoes/FORMATO-CHANGESPEC.md` §5 e a última linha da §8 da
  `ESPECIFICACAO-CELULA.md`). Quem registra é só quem está em
  `SUGESTOES_APROVADORES` — lista **fail-closed**: ausente ou vazia ⇒ ninguém
  aprova ⇒ nada entra em desenvolvimento. Estar em `SUGESTOES_STAFF_EMAILS` não
  basta: moderar e autorizar desenvolvimento são dois papéis. O registro é
  append-only, como o histórico de status.
- **Por quê:** o corredor existe para que uma ideia aprovada **nunca** vire um
  prompt aberto do tipo "implemente isso" para um agente. Sem ele, o passo em que
  se decide escopo, células proibidas e critérios de aceitação é justamente o que
  desaparece sob pressa — e o agente escreve o próprio mandato. Fail-closed no
  aprovador pelo mesmo motivo: "não sei quem pode aprovar" não pode virar "então
  pode qualquer um".
- **Teste-Guarda:**
  `services/sugestoes/tests/test_inv_changespec_trava_o_desenvolvimento.py` —
  a trava reprovando nos três degraus (ponto de estrangulamento, `Sugestao.save()`
  e o trigger `sugestoes_exige_changespec` do Postgres, que pega `QuerySet.update()`
  e SQL cru), passando com ChangeSpec registrado, sem quebrar as outras transições,
  e o registro recusando edição e remoção. O portão do aprovador (lista ausente,
  lista vazia, staff sem mandato) está em `services/sugestoes/tests/test_changespecs.py`.
- **Célula dona:** sugestoes

### [INV-P13] A Porta da Área Administrativa é Fail-CLOSED
- **O quê:** a célula `admin` tem UM ponto de autorização (o middleware da
  porta) e ele nega por padrão. Não conseguir perguntar quem é a pessoa ⇒
  **503, nunca abre e nunca redireciona**; sessão válida cujo e-mail não está
  em `ADMIN_EMAILS` ⇒ **404**; sem sessão ⇒ 302 para o login. A resposta da
  `identidade` — inclusive o campo `papel` — nunca autoriza nada: quem decide
  é a lista desta célula, na hora.
- **Por quê:** é a segunda metade de *reconhecer não é autorizar*
  (`DECISAO-onde-mora-a-sessao.md` §4), e a que faltava ter mecanismo.
  Reconhecimento falha ABERTO porque não saber o nome de alguém não pode
  derrubar a vitrine; autorização falha FECHADO porque não saber QUEM é
  alguém não pode virar permissão. Os três casos se parecem de dentro (nenhum
  renderiza a página) e são completamente diferentes de fora: trocar o 503 por
  302 manda o mantenedor a um login que também caiu; trocar o 404 por 200 abre
  a operação da plataforma para qualquer conta Google.
- **Teste-Guarda:**
  `services/admin/tests/test_inv_porta_fail_closed.py` — uma linha da tabela,
  um teste, com a rede dublada por `respx`. Provado por mutação na entrega da
  porta: redirecionar em vez de 503 ⇒ 5 vermelhos; deixar passar quem não está
  na lista ⇒ 3; `frame-ancestors 'none'` ⇒ 1; isentar um caminho a mais ⇒ 15.
- **Célula dona:** admin

### [INV-SUG11] Identidade Cunhada Guarda o Id da Plataforma
- **O quê:** toda `Identidade` cunhada pela célula `sugestoes` depois da migration
  `0006` guarda, ao lado do id opaco que ela mesma cunha, o **id da identidade da
  plataforma** que a resposta do contrato entregou (`SessionFull.id` de
  `getSessionFull`, `contracts/identidade.openapi.yaml`). A linha que já existia
  sem ele o ganha **na reentrada** da pessoa; uma linha que já tem um id **não é
  sobrescrita** por outro. Nada disto autoriza nem recusa ninguém: id ausente,
  nulo ou colidindo com outra linha local não fecha a porta — quem autoriza
  continua sendo e-mail + (staff | matrícula). E o casamento por **e-mail**
  continua sendo a chave de recuperação: o id novo é dado a mais, não substituto.
- **Por quê:** hoje não existe um identificador de pessoa que atravesse a
  plataforma — `identidade` e `sugestoes` cunham dois ids opacos diferentes para a
  mesma pessoa, e o único elo entre eles é o e-mail, que por decisão do mantenedor
  (`DECISAO-EVO-01-identidade.md` §3) vive numa linha só e não circula. Sem este
  invariante, todo evento que a Caixa publica carrega um id que **não significa
  nada fora dela**, e uma caixa central de notificações receberia o fato sem
  conseguir endereçar ninguém (`docs/notificacoes/PLANO-MESTRE.md` §2). O elo que
  faltava já passava na mão a cada entrada e era descartado na porta; é a Fase 1
  do plano, e sem ela nenhuma das outras funciona.
- **Teste-Guarda:**
  `services/sugestoes/tests/test_inv_id_da_plataforma.py` — cunhagem, reentrada,
  não-sobrescrita, a porta abrindo com id ausente/nulo/em branco, a colisão de
  unicidade não derrubando nem a cunhagem nem a reentrada, e a varredura de AST
  que mantém **um único** caminho de cunhagem no código de produção (um segundo
  nasceria sem o campo). A forma da coluna (`null=True, unique=True` +
  `CheckConstraint` contra `''`) tem guarda próprio no mesmo arquivo: é ela que
  decide se a migration sobe sobre uma tabela cheia. O antídoto operacional que a
  §9 do plano exige é `manage.py relatorio_id_da_plataforma`, com guarda em
  `services/sugestoes/tests/test_relatorio_id_da_plataforma.py`.
- **Célula dona:** sugestoes (obrigação herdada por qualquer célula que cunhe
  identidade local a partir da resposta da `identidade`)

### [INV-SUG12] A Carta Endereça pelo Id da Plataforma, ou Não Sai
- **O quê:** todo evento `notificacao.devida` que a `sugestoes` publica endereça
  pelo **id da plataforma** (`destinatario_id`), nunca pelo id local. Interessado
  que ainda não tem esse id **não recebe carta** — e continua recebendo o `Aviso`
  local, sem que a moderação seja interrompida. Já **quem modera** sem id de
  plataforma interrompe tudo: nada é escrito, a transação inteira volta atrás e a
  pessoa recebe uma tela em português dizendo para entrar de novo.
- **Por quê:** os dois ids são strings opacas parecidas e o contrato aceita as
  duas formas, então trocar um pelo outro **não faz barulho nenhum** — a falha só
  apareceria na Fase 3, com a caixa central cheia de cartas para ninguém. A
  assimetria entre as duas ausências é decisão de desenho, não descuido: um
  votante pode ter entrado pela última vez meses atrás, e travar a moderação de
  uma ideia popular por causa dele seria absurdo — a carta é aditiva. Quem modera,
  ao contrário, está autenticado NESTA requisição; chegar sem id significa que
  algo quebrou agora, e o contrato `sugestao.status-alterado.v2` exige `ator_id`.
  Como o INV-P6 não admite estado sem evento, recusar os dois juntos é a única
  saída correta. Lei: `docs/decisoes/DECISAO-fase-2-do-sininho.md` (Rito de
  Contrato de 26/08/2026, com o mantenedor presente).
- **Teste-Guarda:**
  `services/sugestoes/tests/test_inv_carta_endereca_pelo_id_da_plataforma.py` — o
  id da carta é o da plataforma e é DIFERENTE do local; quem não tem id é pulado
  e ainda assim avisado; o ator sem id reverte tudo (status intacto, zero eventos,
  zero avisos, 409 com instrução em português); a carta aponta para o fato que a
  gerou; e nada de e-mail, título ou texto do aluno viaja nela. O custo do leque
  não crescer com a plateia tem guarda próprio, provado por sabotagem:
  `services/sugestoes/tests/test_volume_das_cartas.py` (com `create()` por pessoa,
  10 consultas para 5 destinatários viram 46 para 41).
- **Célula dona:** sugestoes

---

## Invariantes da própria CI

Os invariantes acima protegem a plataforma. Este protege o INSTRUMENTO que
verifica os outros — porque um portão que erra para o lado do verde não protege
coisa alguma, e ainda gasta a confiança de todo mundo.

### [INV-CI01] Portão Crítico é Fail-Closed
- **O quê:** todo portão crítico prova positivamente que executou a medição
  antes de devolver sucesso. A semântica é de quatro estados, e não de dois:

  | Situação | Estado | Exit |
  |---|---|---|
  | mediu e o estado está correto | `PASS` | 0 |
  | mediu e encontrou violação | `FAIL` | 1 |
  | **não conseguiu medir** | `ERROR` | 2 |
  | medição DECLARADA não aplicável | `SKIP` | 0 |

  É proibido o caminho `não conseguiu validar → PASS`. Em particular:
  ferramenta ausente, arquivo obrigatório ausente, raiz não resolvida, stdout
  vazio, exceção engolida, subprocesso sem propagação de exit code e `SKIP`
  inferido da ausência de evidência são todos `ERROR`. `SKIP` só existe quando
  alguém o declarou por escrito (ex.: `ci/manifesto-de-contratos.json`).
- **Por quê:** em 2026-08 o freeze de contrato imprimiu
  `✅ Freeze de contrato: OK` **com o contrato divergente**. O script chamava
  `python3`, que não existia naquela máquina; as duas pontas de
  `diff <(norm A) <(norm B)` viraram vazio; `diff(vazio, vazio)` deu igualdade.
  Uma ferramenta ausente virou aprovação. Um portão que só sabe dizer "não
  observei diferença" é indistinguível de um portão desligado — e o dia em que
  ele desliga sozinho é justamente o dia em que ninguém percebe.
- **Teste-Guarda:** `ci/tests/test_contract_freeze.py` — suíte adversarial que
  prova o portão reprovando quando deve: contrato divergente ⇒ `FAIL`;
  exportador quebrado, silencioso, ausente ou cuspindo lixo ⇒ `ERROR`;
  congelado ausente ou malformado ⇒ `ERROR`; raiz não resolvida ⇒ `ERROR`;
  dois lados vazios ⇒ `ERROR` (nunca `PASS`); `not-applicable` sem motivo
  declarado ⇒ `ERROR`. Roda no workflow `muralhas` a cada PR.
- **Célula dona:** o repositório (`ci/`) — não pertence a nenhuma célula.

#### Escopo de conformidade (atualize junto com a realidade)

INV-CI01 vale para os portões migrados. Declarar "CI fail-closed global" sem
esta tabela seria a mesma classe de erro que o invariante combate: afirmar mais
do que foi medido.

| Portão | Onde roda | Conforme? |
|---|---|---|
| freeze de contrato (`ci/contract_freeze.py`) | local + `make ci` da célula | **sim** |
| sonda de autenticação efetiva | junto do freeze | **sim** |
| cerca de célula · orçamento · guarda de segredos | workflow `muralhas` | **sim** |
| detecção de escopo + gate terminal (`ci-celula.yml`) | workflow `ci-celula` | **sim** |
| runner canônico (`ci/ci.py`) | local, `make`, workflow | **sim** |
| `contrato-check` dos 8 `services/*/Makefile` | `make ci` da célula | **não** — decide pelo disco em vez do manifesto (mitigado: a auditoria do manifesto roda em `muralhas` a cada PR) |
| merge guardado (`ci/mergear.py`) | terminal, antes do merge | **sim** — recusa check vermelho, ausente ou pulado sem declaração |
| **portão de deploy** (`ci/portao_de_deploy.py`) | workflows `deploy-celula` e `deploy-infra`, ANTES de build/SSH | **sim** — 25 testes adversariais (tabela de estados completa) em `muralhas` e `alarme-main`; **provado ao vivo em 22/08/2026**: commit vermelho mergeado de propósito ⇒ `portao: failure`, `deploy: skipped` (run 32567765127); revert verde ⇒ deploy executado (run 32567900961) |
| alarme da `main` (`alarme-main.yml`) | GitHub, após push na main | **não é portão** — avisa depois; modo de falha é "não avisou" |
| **branch protection** | GitHub | **sim, desde 26/08/2026** — ruleset `main protegida` (id 21570247): PR obrigatório, sem deleção, sem force-push, required checks `muralhas` + `ci-celula-gate`, `bypass_actors` vazio (`current_user_can_bypass: "never"`). Ver abaixo |

#### A cadeia de merge FECHOU em 26/08/2026

Um portão fail-closed só protege se algo exigir que ele passe. De 19/08 a
26/08/2026 nada exigia: o GitHub respondia à API de branch protection deste
repositório `Upgrade to GitHub Pro or make this repository public to enable this
feature. (HTTP 403)`, e o estado honesto era "o merge não é barrável; o deploy
é — e está barrado desde 22/08/2026".

**Deixou de ser.** Com o repositório público (23/08/2026), a proteção nativa
ficou disponível de graça e foi ligada em 26/08/2026 pelo agente, via API:
ruleset `main protegida` (id 21570247) — PR obrigatório na `main`, sem deleção,
sem force-push, e **required status checks `muralhas` + `ci-celula-gate`**,
ambos pinados ao app do GitHub Actions (`integration_id: 15368`).

Três escolhas de desenho que são parte do invariante, não detalhe:

- `required_approving_review_count: 0` e `require_code_owner_review: false` —
  obrigatórios num repositório de UM colaborador, que não pode aprovar o
  próprio PR (§1 H9): qualquer valor acima trancaria todo PR para sempre.
  A força aqui vem dos required checks, não de aprovação humana (Lei 4).
- **`ci-celula` NÃO é required check; `ci-celula-gate` é.** O primeiro fica
  `skipped` em PR que não toca célula, e required check `skipped` conta como
  satisfeito — seria [INV-CI01] violado pela porta da frente. O gate é o job
  terminal `if: always()` que consolida a tabela-verdade.
- `bypass_actors` vazio: `current_user_can_bypass: "never"`, inclusive para o
  dono da conta e para o agente que usa o token dele. Rulesets, ao contrário
  da branch protection clássica, não isentam administrador por padrão — foi
  por isso que se escolheu o ruleset. A saída de emergência é **desligar** o
  ruleset (`-f enforcement=disabled`), ato visível e auditável, nunca um
  bypass silencioso.

Prova de fora, medida no dia: escrita direta na `main` pela API — que ignora o
`.githooks/pre-push` local — recusada com **HTTP 409** `Repository rule
violations found / Changes must be made through a pull request. / 2 of 2
required status checks are expected.` Nada foi gravado. As regras que o GitHub
considera ativas se consultam em `repos/<owner>/<repo>/rules/branches/main`,
nunca na tela de settings.

O que isto **não** fecha: o run de deploy continua rodando depois do merge e
não é required check de nada — quem o barra é o portão de deploy (terceiro
degrau abaixo), e quem confere o veredito é o agente (CLAUDE.md). Armadilhas de
quem for mexer no ruleset: `armadilhas/126-ruleset-de-main-que-trava-todo-merge.md`.

(Correção de registro, 21/08/2026: o parágrafo anterior desta seção dizia
"decisão de custo consciente enquanto o projeto não fatura". Está incorreto —
é **impossibilidade de pagamento**: o cartão do mantenedor não é aceito pelo
GitHub e não há outra forma disponível. Não recomende "assine o Pro" — essa
porta está fechada. Ver ARMADILHAS-OPERACAO.md §1 H3.)

Os degraus grátis da Escada da Imposição (RITOS.md §2), em ordem de força:

1. `ci/mergear.py` — recusa mergear PR com check vermelho quando o merge sai
   do terminal. Não vê o botão do site. Desde 22/08/2026 é o caminho único
   legítimo de merge, executado pelo agente (Lei 4 — mergear é trabalho do
   agente; `--confirmo <N>` no lugar do prompt, e conferência `state=MERGED`
   embutida no próprio script).
2. `alarme-main` — abre issue se a `main` quebrar. Avisa depois; não impede.
3. **Portão de deploy** (`ci/portao_de_deploy.py`, 22/08/2026) — o degrau que
   faltava: ANTES de qualquer build ou SSH, prova que `ci-celula`,
   `alarme-main` e as muralhas do PR de origem estão verdes no commit;
   `skipped` não é verde; push direto na main não vira deploy; workflow novo
   e vermelho no mesmo SHA também barra. **Provado ao vivo**: merge vermelho
   deliberado ⇒ `deploy: skipped` (run 32567765127); revert verde ⇒ deploy
   executado (run 32567900961). O clique no botão continua livre — mas deixou
   de alcançar a produção, que é onde mora o cliente.

---

## Dívida de invariantes (nasce vazia — que permaneça assim)

| Código | O quê | Dono | Prazo | Motivo de estar sem guarda |
|---|---|---|---|---|
| — | — | — | — | — |

> Se esta tabela crescer, cada linha é uma esperança no lugar de uma lei.
